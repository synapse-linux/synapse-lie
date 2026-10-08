// SPDX-License-Identifier: MIT
// Capacity regression and operator timing, separate from original-model speed.
// Reuse the unmodified official Gufo FP64 attention formula and HIP utilities
// at f783fedb9bea2ec7de941f6da4e02f4a4596b29e. The upstream main is not
// executed.
#include <array>
#include <chrono>
#include <iomanip>

#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
#define main lie_retained_attention_test_main
#include "tests/models/qwen38_flash_next/attention_ops_test.cpp"
#undef main

namespace {
constexpr std::size_t kGuard = 32;
constexpr float kPoison = -12345.0F;

void RequireCapacity(bool condition, const char* message) {
  if (!condition)
    throw std::runtime_error(message);
}

std::vector<float> ReadGuarded(HipBuffer<float>* buffer, std::size_t count) {
  const auto values = Download(buffer, count + 2 * kGuard);
  for (std::size_t i = 0; i < kGuard; ++i) {
    RequireCapacity(
        values[i] == kPoison && values[kGuard + count + i] == kPoison,
        "attention output guard changed");
  }
  return {values.begin() + kGuard, values.end() - kGuard};
}

template<typename T>
void CheckUnchanged(HipBuffer<T>* device, const std::vector<T>& original) {
  std::vector<T> actual(original.size());
  CheckHip(hipMemcpy(actual.data(), device->get(), device->bytes(),
                     hipMemcpyDeviceToHost),
           "input verification");
  RequireCapacity(
      std::memcmp(actual.data(), original.data(), device->bytes()) == 0,
      "attention changed an immutable input");
}

struct CapacityCase {
  const char* name;
  std::uint32_t n, start, pitch, selected;
  bool time;
};

bool CheckCapacity(const CapacityCase& c, std::uint32_t seed) {
  const std::uint32_t end = c.start + c.n;
  const std::uint32_t visible_words = (end + 127U) / 128U;
  RequireCapacity(c.pitch >= visible_words && end <= 266240 && c.selected > 1,
                  "invalid fixture geometry");
  const std::size_t count = std::size_t(c.n) * kQWidth;
  const std::size_t kv_count = std::size_t(end) * kKvWidth;
  const auto qv = MakeValues(count, seed, 4.0F);
  const auto gate = MakeValues(count, seed ^ 0x5555U, 3.0F);
  std::vector<__half> keys(kv_count), values(kv_count);
  {
    const auto kf = MakeValues(kv_count, seed ^ 0xAAAAU, 1.0F);
    const auto vf = MakeValues(kv_count, seed ^ 0x3333U, 1.0F);
    for (std::size_t i = 0; i < kv_count; ++i) {
      keys[i] = __float2half(kf[i]);
      values[i] = __float2half(vf[i]);
    }
  }
  // Poison allocated but invisible words. Select the first and last complete
  // blocks and spread the rest, exercising the ninth local scan slot as well
  // as both compact-list and bitset union representations.
  std::vector<std::uint32_t> mask(std::size_t(c.n) * c.pitch, 0xFFFFFFFFU);
  for (std::uint32_t t = 0; t < c.n; ++t) {
    auto* row = mask.data() + std::size_t(t) * c.pitch;
    std::fill(row, row + visible_words, 0);
    const std::uint32_t complete = (c.start + t + 1) / kRatio;
    RequireCapacity(complete >= c.selected, "selection exceeds visible blocks");
    for (std::uint32_t j = 0; j < c.selected; ++j) {
      const auto block =
          std::uint32_t(std::uint64_t(j) * (complete - 1) / (c.selected - 1));
      row[block / 32] |= 1U << (block % 32);
    }
  }
  HipBuffer<float> dq(count), dg(count), reference(count + 2 * kGuard),
      candidate(count + 2 * kGuard);
  HipBuffer<__half> dk(kv_count), dv(kv_count);
  HipBuffer<std::uint32_t> dm(mask.size()), dp(1);
  Upload(&dq, qv);
  Upload(&dg, gate);
  Upload(&dk, keys);
  Upload(&dv, values);
  Upload(&dm, mask);
  Upload(&dp, std::vector<std::uint32_t>{c.start});
  const std::vector<float> poison(count + 2 * kGuard, kPoison);
  Upload(&reference, poison);
  Upload(&candidate, poison);
  const auto fallback = [&] {
    q::Attention(dq.get(), dk.get(), dv.get(), dm.get(), c.pitch,
                 reference.get() + kGuard, nullptr, 1, c.n, dp.get(), kHeads,
                 kKvHeads, kDim, kRatio, nullptr);
    q::SigmoidMul(reference.get() + kGuard, dg.get(), count, nullptr);
  };
  const auto wmma = [&](bool last_only = false) {
    RequireCapacity(q::WmmaCausalAttention(
                        dq.get(), dg.get(), dk.get(), dv.get(), dm.get(),
                        c.pitch, candidate.get() + kGuard, c.n, c.start, kHeads,
                        kKvHeads, kDim, kRatio, nullptr, last_only),
                    "WMMA rejected an admitted visible extent/pitch");
  };
  fallback();
  wmma();
  CheckHip(hipDeviceSynchronize(), "capacity check");
  const auto ref = ReadGuarded(&reference, count);
  const auto out = ReadGuarded(&candidate, count);
  double worst = 0;
  for (std::size_t i = 0; i < count; ++i) {
    RequireCapacity(std::isfinite(ref[i]) && std::isfinite(out[i]) &&
                        ref[i] != kPoison && out[i] != kPoison,
                    "nonfinite or unwritten attention value");
    worst = std::max(worst, std::abs(double(ref[i]) - out[i]));
  }
  // Full FP64 formula for every correctness row; production-sized timed rows
  // additionally compare every element against the unchanged GPU fallback.
  double fp64_reference = 0, fp64_candidate = 0;
  if (!c.time) {
    const auto exact = Fp64Attention(qv, gate, keys, values, mask.data(),
                                     c.pitch, c.n, c.start);
    for (std::size_t i = 0; i < count; ++i) {
      RequireCapacity(std::isfinite(exact[i]), "nonfinite independent formula");
      fp64_reference = std::max(fp64_reference, std::abs(exact[i] - ref[i]));
      fp64_candidate = std::max(fp64_candidate, std::abs(exact[i] - out[i]));
    }
  }
  wmma();
  CheckHip(hipDeviceSynchronize(), "capacity replay");
  const auto replay = ReadGuarded(&candidate, count);
  RequireCapacity(
      std::memcmp(out.data(), replay.data(), count * sizeof(float)) == 0,
      "attention replay changed bytes");
  Upload(&candidate, poison);
  wmma(true);
  CheckHip(hipDeviceSynchronize(), "last group");
  const auto tail = ReadGuarded(&candidate, count);
  const std::size_t first = std::size_t((c.n - 1) / 4 * 4) * kQWidth;
  for (std::size_t i = 0; i < count; ++i) {
    RequireCapacity(i < first ? tail[i] == kPoison : tail[i] == out[i],
                    "last group changed an excluded row or result");
  }
  // Rejection must occur before a launch, without touching any result.
  for (const auto [n, start, pitch] :
       {std::array<std::uint32_t, 3>{0, c.start, c.pitch},
        {1, UINT32_MAX, c.pitch},
        {1, 266240, c.pitch},
        {c.n, c.start, visible_words - 1}}) {
    RequireCapacity(
        !q::WmmaCausalAttention(dq.get(), dg.get(), dk.get(), dv.get(),
                                dm.get(), pitch, candidate.get() + kGuard, n,
                                start, kHeads, kKvHeads, kDim, kRatio, nullptr),
        "invalid extent was accepted");
  }
  CheckHip(hipDeviceSynchronize(), "rejection check");
  const auto rejected = ReadGuarded(&candidate, count);
  RequireCapacity(
      std::memcmp(tail.data(), rejected.data(), count * sizeof(float)) == 0,
      "rejected launch changed bytes");
  if (c.time) {
    hipEvent_t begin{}, finish{};
    CheckHip(hipEventCreate(&begin), "event create");
    CheckHip(hipEventCreate(&finish), "event create");
    for (unsigned repeat = 0; repeat < 7; ++repeat) {
      for (unsigned arm = 0; arm < 2; ++arm) {
        const bool use_wmma = ((repeat + arm) & 1U) != 0;
        CheckHip(hipDeviceSynchronize(), "timing boundary");
        const auto start = std::chrono::steady_clock::now();
        CheckHip(hipEventRecord(begin), "event record");
        if (use_wmma)
          wmma();
        else
          fallback();
        CheckHip(hipEventRecord(finish), "event record");
        CheckHip(hipEventSynchronize(finish), "timing completion");
        const double wall = std::chrono::duration<double, std::milli>(
                                std::chrono::steady_clock::now() - start)
                                .count();
        float device = 0;
        CheckHip(hipEventElapsedTime(&device, begin, finish), "elapsed time");
        std::cout << "{\"event\":\"attention_capacity_time\",\"case\":\""
                  << c.name << "\",\"arm\":\""
                  << (use_wmma ? "wmma" : "fallback")
                  << "\",\"repeat\":" << repeat
                  << ",\"warmup\":" << (repeat < 2 ? "true" : "false")
                  << ",\"wall_ms\":" << wall << ",\"hip_ms\":" << device
                  << "}\n";
      }
    }
    CheckHip(hipEventDestroy(begin), "event destroy");
    CheckHip(hipEventDestroy(finish), "event destroy");
    const auto after = ReadGuarded(&candidate, count);
    const auto ref_after = ReadGuarded(&reference, count);
    RequireCapacity(
        std::memcmp(out.data(), after.data(), count * sizeof(float)) == 0 &&
            std::memcmp(ref.data(), ref_after.data(), count * sizeof(float)) ==
                0,
        "timed attention changed its result");
  }
  CheckUnchanged(&dq, qv);
  CheckUnchanged(&dg, gate);
  CheckUnchanged(&dm, mask);
  CheckUnchanged(&dk, keys);
  CheckUnchanged(&dv, values);
  const bool ok =
      worst < 2e-2 &&
      (c.time || (fp64_reference <= kFp64Limit && fp64_candidate < 2e-2));
  std::cout
      << "{\"event\":\"attention_capacity_check\",\"case\":\"" << c.name
      << "\",\"rows\":" << c.n << ",\"start\":" << c.start
      << ",\"pitch\":" << c.pitch << ",\"selected\":" << c.selected
      << ",\"fp64_checked\":" << (c.time ? "false" : "true")
      << ",\"fallback_error\":" << fp64_reference
      << ",\"wmma_fp64_error\":" << fp64_candidate
      << ",\"wmma_fallback_error\":" << worst
      << ",\"guards_replay_last_only_inputs_exact\":true,\"numerical_pass\":"
      << (ok ? "true" : "false") << "}\n";
  return ok;
}
}  // namespace

int main() {
  std::cout << std::setprecision(12) << std::unitbuf;
  try {
    const CapacityCase cases[] = {
        {"short-pitch2080", 3, 16384, 2080, 512, false},
        {"early-tail17", 17, 65529, 2080, 512, false},
        {"late-pitch8192", 3, 65536, 8192, 512, false},
        {"native-end", 1, 262143, 2080, 512, false},
        {"cross-native-end", 3, 262143, 2080, 512, false},
        {"headroom-end-compact", 1, 266239, 2080, 512, false},
        {"headroom-end-bitset", 1, 266239, 8192, 2053, false},
        {"headroom-tail3-bitset", 3, 266237, 2080, 2053, false},
        {"pp128-at16k", 128, 16384, 2080, 512, true},
        {"pp128-at256k", 128, 262112, 2080, 512, true}};
    bool ok = true;
    std::uint32_t seed = 0xCACA1234;
    for (const auto& c : cases) {
      const bool passed = CheckCapacity(c, seed++);
      ok = passed && ok;  // Preserve finite numerical failures and still time.
    }
    std::cout
        << "{\"event\":\"attention_capacity_complete\",\"cases\":10,"
           "\"timing_samples\":28,\"device_work_safe\":true,\"numerical_pass\":"
        << (ok ? "true" : "false") << "}\n";
    return ok ? 0 : 1;
  } catch (const std::exception& e) {
    std::cerr << e.what() << '\n';
    return 2;
  }
}
