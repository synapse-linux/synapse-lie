// SPDX-License-Identifier: MIT
// Synthetic component qualification. Never a model/token-rate benchmark.
#define main retained_packed_benchmark_main
#include "q2_packed_bench.cpp"
#undef main
#include "q2_iq2_routes.hpp"
#include <limits>

namespace {
constexpr unsigned kColumns = 640, kRows = 2560, kExperts = 512, kUsed = 10;
constexpr unsigned kRowBytes = 3 * 84, kGuard = 32;

template <class T> void Upload(Device &dst, const std::vector<T> &src) {
  Hip(hipMemcpy(dst.data, src.data(), src.size() * sizeof(T), hipMemcpyHostToDevice));
}
template <class T> std::vector<T> Download(const Device &src, std::size_t count) {
  std::vector<T> out(count);
  Hip(hipMemcpy(out.data(), src.data, count * sizeof(T), hipMemcpyDeviceToHost));
  return out;
}
template <class T> void Guard(const std::vector<T> &data, std::size_t count) {
  const auto *bytes = reinterpret_cast<const unsigned char *>(data.data());
  for (std::size_t i = 0; i < kGuard * sizeof(T); ++i)
    Check(bytes[i] == 0xa5 && bytes[(kGuard + count) * sizeof(T) + i] == 0xa5,
          "Scaled row output guard changed");
}

// Independent scalar conversion checks all finite elements. Nonfinite inputs
// are retained for exact cross-process differential checks, not reinterpreted.
unsigned ObservePack(const Device &packed, const Device &inverse,
                     const std::vector<float> &input, const std::string &name) {
  const auto rows = input.size() / kColumns;
  const auto halves = Download<std::uint16_t>(packed, input.size() + 2 * kGuard);
  const auto scales = Download<float>(inverse, rows + 2 * kGuard);
  Guard(halves, input.size());
  Guard(scales, rows);
  unsigned mismatches = 0, nonfinite_rows = 0;
  for (std::size_t row = 0; row < rows; ++row) {
    double peak = 0;
    bool finite = true;
    for (unsigned c = 0; c < kColumns; ++c) {
      const float value = input[row * kColumns + c];
      finite &= std::isfinite(value);
      peak = std::max(peak, std::abs(double(value)));
    }
    if (!finite) { ++nonfinite_rows; continue; }
    int exponent = 0;
    std::frexp(peak, &exponent);
    // The existing implementation clamps all nonzero subnormal rows to +120.
    const int shift = peak == 0 ? 0 : std::clamp(14 - exponent, -120, 120);
    const float inv = std::ldexp(1.0f, -shift);
    mismatches += std::bit_cast<std::uint32_t>(inv) !=
                  std::bit_cast<std::uint32_t>(scales[kGuard + row]);
    for (unsigned c = 0; c < kColumns; ++c) {
      const auto i = row * kColumns + c;
      const auto expected = __float2half_rn(float(std::ldexp(double(input[i]), shift)));
      mismatches += std::bit_cast<std::uint16_t>(expected) != halves[kGuard + i];
    }
  }
  const auto hs = std::span(halves).subspan(kGuard, input.size());
  const auto ss = std::span(scales).subspan(kGuard, rows);
  // Complete small operator buffers are retained. Large cycles retain hashes
  // over every element plus the independently checked sampled down values.
  if (rows <= 257) {
    for (auto [suffix, bytes] : {
             std::pair{"f16", std::as_bytes(hs)},
             std::pair{"inverse", std::as_bytes(ss)}}) {
      std::ofstream out("results/row-" + name + "." + suffix, std::ios::binary);
      out.write(reinterpret_cast<const char *>(bytes.data()), bytes.size());
      Check(bool(out), "Cannot retain scaled row buffer");
    }
  }
  std::cout << "{\"event\":\"row_pack\",\"case\":\"" << name
            << "\",\"rows\":" << rows << ",\"values\":" << input.size()
            << ",\"input_sha256\":\"" << Digest<float>(input)
            << "\",\"half_sha256\":\"" << Digest<std::uint16_t>(hs)
            << "\",\"inverse_sha256\":\"" << Digest<float>(ss)
            << "\",\"finite_mismatches\":" << mismatches
            << ",\"nonfinite_rows\":" << nonfinite_rows << "}\n";
  return mismatches;
}

unsigned SmallChecks() {
  unsigned failures = 0;
  for (unsigned rows : {1u, 3u, 33u, 257u}) {
    for (unsigned pattern = 0; pattern < 8; ++pattern) {
      std::vector<float> input(std::size_t(rows) * kColumns);
      for (std::size_t i = 0; i < input.size(); ++i) {
        const std::uint32_t sign = (i & 1) ? 0x80000000U : 0;
        const auto value = float(int((i * 17 + 31) % 251) - 125) + 0.137f;
        switch (pattern) {
        case 0: input[i] = std::bit_cast<float>(sign); break;
        case 1: input[i] = value / 256; break;
        case 2: input[i] = std::bit_cast<float>(sign | (1U + unsigned(i % 0x7fffff))); break;
        case 3: input[i] = std::bit_cast<float>(sign | (0x7fffffU + unsigned(i % 3))); break;
        case 4: input[i] = std::bit_cast<float>(sign | (0x7f7fffffU - unsigned(i % 8192))); break;
        case 5: input[i] = std::ldexp(value / 128, int(i % 250) - 125); break;
        case 6: input[i] = std::bit_cast<float>(sign | (i % 3 ? 0x7fc01234U : 0x7f800000U)); break;
        case 7: {
          // Exhaust the finite half bit patterns at the large row count.
          const auto bits = static_cast<std::uint16_t>((i % 0x7c00) | (((i / 0x7c00) & 1) << 15));
          input[i] = __half2float(std::bit_cast<__half>(bits));
          break;
        }
        }
      }
      Device x(input.size() * 4), h((input.size() + 2 * kGuard) * 2);
      Device inverse((rows + 2 * kGuard) * 4);
      Upload(x, input);
      Hip(hipMemset(h.data, 0xa5, (input.size() + 2 * kGuard) * 2));
      Hip(hipMemset(inverse.data, 0xa5, (rows + 2 * kGuard) * 4));
      auto *hp = static_cast<__half *>(h.data) + kGuard;
      auto *ip = static_cast<float *>(inverse.data) + kGuard;
      const auto *xp = static_cast<const float *>(x.data);
      for (unsigned columns : {0u, 639u, 641u, 768u})
        Check(!q::PackQ2ScaledRows(xp, hp, ip, rows, columns, nullptr),
              "Scaled packing accepted unsupported columns");
      Check(!q::PackQ2ScaledRows(xp, hp, ip, 0, kColumns, nullptr) &&
                !q::PackQ2ScaledRows(nullptr, hp, ip, rows, kColumns, nullptr) &&
                !q::PackQ2ScaledRows(xp, nullptr, ip, rows, kColumns, nullptr) &&
                !q::PackQ2ScaledRows(xp, hp, nullptr, rows, kColumns, nullptr),
            "Scaled packing accepted invalid pointers or rows");
      Check(q::PackQ2ScaledRows(xp, hp, ip, rows, kColumns, nullptr), "Packing failed");
      Hip(hipDeviceSynchronize());
      const auto copy = Download<float>(x, input.size());
      Check(std::memcmp(input.data(), copy.data(), input.size() * 4) == 0,
            "Packing changed input");
      failures += ObservePack(h, inverse, input,
          std::to_string(rows) + "-pattern" + std::to_string(pattern)) != 0;
    }
  }
  return failures;
}

unsigned Cycle(const iq2_routes::Case &test, const std::vector<unsigned char> &weights,
               const Device &wd) {
  const unsigned slots = test.tokens * kUsed, tile = 48;
  const auto count = std::size_t(slots) * kColumns;
  const auto output_count = std::size_t(slots) * kRows;
  std::array<std::vector<float>, 2> inputs;
  std::array<Device, 2> x{Device(count * 4), Device(count * 4)};
  for (unsigned bank = 0; bank < 2; ++bank) {
    inputs[bank].resize(count);
    for (std::size_t i = 0; i < count; ++i)
      inputs[bank][i] = (float(int((i * 17 + 31 + bank * 19) % 251) - 125) + 0.137f) / 256;
    Upload(x[bank], inputs[bank]);
  }
  std::vector<std::int32_t> tiles;
  for (unsigned e = 0; e < kExperts; ++e)
    for (unsigned row = 0; row < (test.counts[e] + 15) / 16 * 16; row += tile)
      tiles.push_back(e | ((row / tile) << 16));
  const auto compact = q::RoutedCompactRows(slots, kExperts);
  Device id(slots * 4), cd(kExperts * 4), td(tiles.size() * 4);
  Device bounds((kExperts + 1) * 4), cursors(kExperts * 4);
  Device tokens(compact * 4), mapped_slots(compact * 4);
  Device h((count + 2 * kGuard) * 2), inverse((slots + 2 * kGuard) * 4);
  Device out((output_count + 2 * kGuard) * 4);
  Upload(id, test.ids); Upload(cd, test.counts); Upload(td, tiles);
  q::RoutedCompact(static_cast<const std::int32_t *>(id.data),
      static_cast<const std::uint32_t *>(cd.data), static_cast<std::int32_t *>(bounds.data),
      static_cast<std::int32_t *>(cursors.data), static_cast<std::int32_t *>(tokens.data),
      static_cast<std::int32_t *>(mapped_slots.data), test.tokens, kUsed, kExperts, nullptr);
  const auto launch = [&](unsigned bank, bool down) {
    Check(q::PackQ2ScaledRows(static_cast<const float *>(x[bank].data),
        static_cast<__half *>(h.data) + kGuard,
        static_cast<float *>(inverse.data) + kGuard, slots, kColumns, nullptr), "Cycle packing failed");
    if (down)
      Check(q::RoutedQ2ScaledGemm(wd.data, static_cast<const __half *>(h.data) + kGuard,
          static_cast<const float *>(inverse.data) + kGuard,
          static_cast<const std::int32_t *>(td.data), tiles.size(), tile,
          static_cast<const std::int32_t *>(bounds.data),
          static_cast<const std::int32_t *>(mapped_slots.data),
          static_cast<float *>(out.data) + kGuard, kRows, kColumns, nullptr), "Cycle down failed");
  };
  std::cout << "{\"event\":\"row_geometry\",\"case\":\"" << test.name
            << "\",\"tokens\":" << test.tokens << ",\"slots\":" << slots
            << ",\"tile\":48,\"active_experts\":" << test.active
            << ",\"active_weight_bytes\":" << std::size_t(test.active) * kRows * kRowBytes
            << ",\"input_banks\":2,\"input_bytes_per_bank\":" << count * 4
            << ",\"weight_sha256\":\"" << Digest<unsigned char>(weights) << "\"}\n";
  hipEvent_t begin, end;
  Hip(hipEventCreate(&begin)); Hip(hipEventCreate(&end));
  for (unsigned sample = 0; sample < 7; ++sample) {
    for (unsigned position = 0; position < 2; ++position) {
      const bool down = (position ^ (sample & 1)) != 0;
      Hip(hipEventRecord(begin));
      for (unsigned repeat = 0; repeat < 8; ++repeat) launch(repeat & 1, down);
      Hip(hipEventRecord(end)); Hip(hipEventSynchronize(end));
      float ms = 0; Hip(hipEventElapsedTime(&ms, begin, end));
      std::cout << "{\"event\":\"row_timing\",\"case\":\"" << test.name
                << "\",\"scope\":\"" << (down ? "pack-down" : "pack")
                << "\",\"sample\":" << sample << ",\"warmup\":" << (sample < 2 ? "true" : "false")
                << ",\"calls\":8,\"us_per_call\":" << ms * 1000 / 8 << "}\n";
    }
  }
  Hip(hipEventDestroy(begin)); Hip(hipEventDestroy(end));
  unsigned failures = 0;
  for (unsigned bank = 0; bank < 2; ++bank) {
    Hip(hipMemset(h.data, 0xa5, (count + 2 * kGuard) * 2));
    Hip(hipMemset(inverse.data, 0xa5, (slots + 2 * kGuard) * 4));
    Hip(hipMemset(out.data, 0xa5, (output_count + 2 * kGuard) * 4));
    launch(bank, true); Hip(hipDeviceSynchronize());
    const auto name = test.name + "-bank" + std::to_string(bank);
    failures += ObservePack(h, inverse, inputs[bank], name) != 0;
    const auto got = Download<float>(out, output_count + 2 * kGuard);
    Guard(got, output_count);
    for (std::size_t i = kGuard; i < kGuard + output_count; ++i)
      Check(std::isfinite(got[i]) && std::bit_cast<std::uint32_t>(got[i]) != 0xa5a5a5a5U,
            "Down cycle nonfinite or unwritten output");
    const auto values = std::span(got).subspan(kGuard, output_count);
    double error2 = 0, norm2 = 0, maximum = 0, peak = 0;
    std::ofstream samples("results/row-" + name + "-samples.jsonl");
    samples.precision(17);
    for (unsigned i = 0; i < 1024; ++i) {
      const unsigned slot = (i * 7919 + 17) % slots, row = (i * 101 + 127) % kRows;
      const auto *wr = weights.data() + (std::size_t(test.ids[slot]) * kRows + row) * kRowBytes;
      double expected = 0;
      for (unsigned c = 0; c < kColumns; ++c)
        expected += double(Weight(wr, c)) * inputs[bank][std::size_t(slot) * kColumns + c];
      const float value = values[std::size_t(slot) * kRows + row];
      const double delta = double(value) - expected;
      error2 += delta * delta; norm2 += expected * expected;
      maximum = std::max(maximum, std::abs(delta)); peak = std::max(peak, std::abs(expected));
      samples << "{\"slot\":" << slot << ",\"row\":" << row << ",\"value\":" << value
              << ",\"reference\":" << expected << "}\n";
    }
    Check(bool(samples), "Cannot save independent down samples");
    const auto rms = std::sqrt(error2 / std::max(norm2, 1e-30));
    const auto relative_max = maximum / std::max(peak, 1e-20);
    failures += rms > 0.002 || relative_max > 0.002;
    std::cout << "{\"event\":\"row_down\",\"case\":\"" << name
              << "\",\"values\":" << output_count << ",\"sha256\":\"" << Digest<float>(values)
              << "\",\"independent_samples\":1024,\"relative_rms\":" << rms
              << ",\"error_over_peak\":" << relative_max << "}\n";
  }
  return failures;
}
} // namespace

int main() {
  try {
    Hip(hipSetDevice(0)); std::cout << std::unitbuf; std::cout.precision(12);
    const auto cases = iq2_routes::Load("config/q2-iq2-live-epilogue-plan.json");
    std::vector<unsigned char> weights(std::size_t(kExperts) * kRows * kRowBytes);
    std::uint32_t random = 0x25112048;
    for (unsigned row = 0; row < kExperts * kRows; ++row) {
      const __half d = __float2half_rn(0.00319f * (1 + row % 3));
      const __half m = __float2half_rn(0.00271f * (1 + row % 2));
      for (unsigned block = 0; block < 3; ++block) {
        auto *p = weights.data() + std::size_t(row) * kRowBytes + block * 84;
        for (unsigned i = 0; i < 80; ++i) p[i] = static_cast<unsigned char>(Next(random));
        std::memcpy(p + 80, &d, 2); std::memcpy(p + 82, &m, 2);
      }
    }
    Device wd(weights.size()); Upload(wd, weights);
    unsigned failures = 0;
    // Preserve performance even when an independent numerical check rejects.
    for (const auto &test : cases) failures += Cycle(test, weights, wd);
    failures += SmallChecks();
    std::cout << "{\"event\":\"row_summary\",\"cycles\":5,\"small_cases\":32,"
                 "\"model_inference\":false,\"failures\":" << failures << "}\n";
    return failures ? 1 : 0;
  } catch (const std::exception &e) {
    std::cerr << e.what() << '\n'; return 1;
  }
}
