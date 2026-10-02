// SPDX-License-Identifier: MIT
// Original-shape synthetic Q2 operator benchmark, never a CPU model forward.
#include "q2_packed_fixture.hpp"
#include "src/core/crypto/sha256.hpp"

#include <array>
#include <span>

namespace q = gufo::models::qwen38_flash_next::rocm;
template <typename T> static std::string Digest(std::span<const T> data) {
  return gufo::crypto::Sha256Hex(std::span(
      reinterpret_cast<const std::uint8_t *>(data.data()), data.size_bytes()));
}
static std::uint32_t Next(std::uint32_t &state) {
  state ^= state << 13;
  state ^= state >> 17;
  state ^= state << 5;
  return state;
}
static float Weight(const unsigned char *row, unsigned col) {
  const auto *block = row + (col / 256) * 84;
  const unsigned i = col % 256;
  __half d, m;
  std::memcpy(&d, block + 80, 2);
  std::memcpy(&m, block + 82, 2);
  const auto sm = block[i / 16];
  const unsigned code =
      (block[16 + (i / 128) * 32 + i % 32] >> (2 * ((i % 128) / 32))) & 3;
  // Independent scalar interpretation, evaluated in F32 like the retained
  // format oracle before sampled FP64 products. Padding is never consumed.
  return __half2float(d) * (sm & 15) * code - __half2float(m) * (sm >> 4);
}
static bool Bench() {
  constexpr unsigned experts = 512, used = 10, tokens = 2048;
  constexpr unsigned rows = 2560, logical = 640, stored = 768, tile = 48;
  constexpr unsigned slots = tokens * used, row_bytes = stored / 256 * 84;
  constexpr std::size_t guard = 32, output_count = std::size_t(slots) * rows;
  std::vector<unsigned char> weights(std::size_t(experts) * rows * row_bytes);
  std::uint32_t random = 0x25112048;
  for (unsigned row = 0; row < experts * rows; ++row) {
    const __half d = __float2half_rn(0.00319f * (1 + row % 3));
    const __half m = __float2half_rn(0.00271f * (1 + row % 2));
    for (unsigned block = 0; block < stored / 256; ++block) {
      auto *out = weights.data() + std::size_t(row) * row_bytes + block * 84;
      for (unsigned i = 0; i < 80; ++i)
        out[i] = static_cast<unsigned char>(Next(random));
      std::memcpy(out + 80, &d, 2);
      std::memcpy(out + 82, &m, 2);
    }
  }
  std::vector<float> x(std::size_t(slots) * logical);
  std::vector<std::uint32_t> packed(x.size());
  for (std::size_t i = 0; i < x.size(); ++i) {
    x[i] = (float(int(Next(random) % 2001) - 1000) + 0.137f) / 2048.0f;
    packed[i] = PackCompensated(x[i]);
  }
  std::vector<std::int32_t> ids(slots), tiles;
  std::vector<std::uint32_t> counts(experts);
  for (unsigned slot = 0; slot < slots; ++slot) {
    ids[slot] = static_cast<int>((slot * 73 + 17) % experts);
    ++counts[ids[slot]];
  }
  for (unsigned e = 0; e < experts; ++e)
    for (unsigned t = 0; t < (counts[e] + 15) / 16 * 16; t += tile)
      tiles.push_back(static_cast<int>(e | ((t / tile) << 16)));
  const auto compact_rows = q::RoutedCompactRows(slots, experts);
  Device wd(weights.size()), xd(x.size() * 4), pd(packed.size() * 4);
  Device id(ids.size() * 4), cd(counts.size() * 4), td(tiles.size() * 4);
  Device bounds((experts + 1) * 4), cursors(experts * 4);
  Device row_token(compact_rows * 4), row_slot(compact_rows * 4);
  Device raw((output_count + 2 * guard) * 4);
  Device candidate((output_count + 2 * guard) * 4);
  Hip(hipMemcpy(wd.data, weights.data(), weights.size(),
                hipMemcpyHostToDevice));
  Hip(hipMemcpy(xd.data, x.data(), x.size() * 4, hipMemcpyHostToDevice));
  Hip(hipMemcpy(pd.data, packed.data(), packed.size() * 4,
                hipMemcpyHostToDevice));
  Hip(hipMemcpy(id.data, ids.data(), ids.size() * 4, hipMemcpyHostToDevice));
  Hip(hipMemcpy(cd.data, counts.data(), counts.size() * 4,
                hipMemcpyHostToDevice));
  Hip(hipMemcpy(td.data, tiles.data(), tiles.size() * 4,
                hipMemcpyHostToDevice));
  Hip(hipMemset(raw.data, 0xA5, (output_count + 2 * guard) * 4));
  Hip(hipMemset(candidate.data, 0xA5, (output_count + 2 * guard) * 4));
  q::RoutedCompact(static_cast<const std::int32_t *>(id.data),
                   static_cast<const std::uint32_t *>(cd.data),
                   static_cast<std::int32_t *>(bounds.data),
                   static_cast<std::int32_t *>(cursors.data),
                   static_cast<std::int32_t *>(row_token.data),
                   static_cast<std::int32_t *>(row_slot.data), tokens, used,
                   experts, nullptr);
  auto launch = [&](bool use_packed) {
    const auto *t = static_cast<const std::int32_t *>(td.data);
    const auto *b = static_cast<const std::int32_t *>(bounds.data);
    const auto *r = static_cast<const std::int32_t *>(row_slot.data);
    if (use_packed)
      Check(q::RoutedQ2GemmPacked(wd.data,
                                  static_cast<const std::uint32_t *>(pd.data),
                                  t, tiles.size(), tile, b, r,
                                  static_cast<float *>(candidate.data) + guard,
                                  rows, logical, nullptr),
            "Packed dispatch failed");
    else
      Check(q::RoutedQ2Gemm(wd.data, static_cast<const float *>(xd.data), t,
                            tiles.size(), tile, b, r,
                            static_cast<float *>(raw.data) + guard, rows,
                            logical, nullptr),
            "Raw-input dispatch failed");
  };
  std::cout << "{\"event\":\"geometry\",\"tokens\":" << tokens
            << ",\"experts\":" << experts << ",\"used\":" << used
            << ",\"rows\":" << rows << ",\"logical_k\":" << logical
            << ",\"stored_k\":" << stored << ",\"tile\":" << tile
            << ",\"tiles\":" << tiles.size()
            << ",\"weight_bytes\":" << weights.size() << ",\"weight_sha256\":\""
            << Digest<unsigned char>(weights) << "\",\"input_sha256\":\""
            << Digest<float>(x) << "\"}\n";
  for (int i = 0; i < 3; ++i) {
    launch(false);
    launch(true);
  }
  Hip(hipDeviceSynchronize());
  hipEvent_t begin, end;
  Hip(hipEventCreate(&begin));
  Hip(hipEventCreate(&end));
  constexpr unsigned launches = 8;
  for (unsigned rep = 0; rep < 5; ++rep) {
    for (unsigned position = 0; position < 2; ++position) {
      const bool use_packed = (position ^ (rep & 1)) != 0;
      Hip(hipEventRecord(begin, nullptr));
      for (unsigned i = 0; i < launches; ++i)
        launch(use_packed);
      Hip(hipEventRecord(end, nullptr));
      Hip(hipEventSynchronize(end));
      Hip(hipGetLastError());
      float ms = 0;
      Hip(hipEventElapsedTime(&ms, begin, end));
      std::cout << "{\"event\":\"microbench\",\"packed\":"
                << (use_packed ? "true" : "false") << ",\"rep\":" << rep
                << ",\"position\":" << position << ",\"launches\":" << launches
                << ",\"us_per_launch\":" << ms * 1000.0 / launches << "}\n";
    }
  }
  Hip(hipEventDestroy(begin));
  Hip(hipEventDestroy(end));
  std::vector<float> reference(output_count + 2 * guard), got(reference.size());
  Hip(hipMemcpy(reference.data(), raw.data, reference.size() * 4,
                hipMemcpyDeviceToHost));
  Hip(hipMemcpy(got.data(), candidate.data, got.size() * 4,
                hipMemcpyDeviceToHost));
  for (const auto *values : {&reference, &got}) {
    for (std::size_t i = 0; i < guard; ++i)
      Check(std::bit_cast<std::uint32_t>((*values)[i]) == 0xA5A5A5A5U &&
                std::bit_cast<std::uint32_t>(
                    (*values)[guard + output_count + i]) == 0xA5A5A5A5U,
            "Benchmark output guard changed");
    for (std::size_t i = 0; i < output_count; ++i)
      Check(std::isfinite((*values)[guard + i]) &&
                std::bit_cast<std::uint32_t>((*values)[guard + i]) !=
                    0xA5A5A5A5U,
            "Nonfinite or unwritten benchmark output");
  }
  const auto rs = std::span(reference).subspan(guard, output_count);
  const auto cs = std::span(got).subspan(guard, output_count);
  const bool exact = std::memcmp(rs.data(), cs.data(), rs.size_bytes()) == 0;
  double error2 = 0, norm2 = 0, maximum = 0, peak = 0;
  std::ofstream samples("results/packed-bench-samples.jsonl");
  for (unsigned i = 0; i < 1024; ++i) {
    const unsigned slot = (i * 7919 + 17) % slots, row = (i * 101 + 127) % rows;
    const auto *wr =
        weights.data() + (std::size_t(ids[slot]) * rows + row) * row_bytes;
    double expected = 0;
    for (unsigned c = 0; c < logical; ++c)
      expected += double(Weight(wr, c)) * x[std::size_t(slot) * logical + c];
    const float value = cs[std::size_t(slot) * rows + row];
    const double delta = double(value) - expected;
    error2 += delta * delta;
    norm2 += expected * expected;
    maximum = std::max(maximum, std::abs(delta));
    peak = std::max(peak, std::abs(expected));
    samples.precision(17);
    samples << "{\"slot\":" << slot << ",\"row\":" << row
            << ",\"value\":" << value << ",\"reference\":" << expected << "}\n";
  }
  Check(bool(samples), "Cannot save independent samples");
  const double rms = std::sqrt(error2 / std::max(norm2, 1e-30));
  const double scaled_max = maximum / std::max(peak, 1e-20);
  std::cout << "{\"event\":\"replay\",\"values\":" << output_count
            << ",\"exact\":" << (exact ? "true" : "false")
            << ",\"raw_sha256\":\"" << Digest<float>(rs)
            << "\",\"packed_sha256\":\"" << Digest<float>(cs)
            << "\",\"independent_samples\":1024,\"relative_rms\":" << rms
            << ",\"error_over_peak\":" << scaled_max << "}\n";
  return exact && rms <= 0.002 && scaled_max <= 0.002;
}

int main() {
  try {
    Hip(hipSetDevice(0));
    std::cout << std::unitbuf;
    std::cout.precision(12);
    // Preserve the requested performance samples even if numerical replay
    // subsequently fails. A numerical failure still returns exit 1.
    Check(Bench(), "Synthetic Q2 benchmark replay or oracle failed");
    std::cout << "PASS synthetic packed Q2 benchmark; no model inference\n";
  } catch (const std::exception &ex) {
    std::cerr << ex.what() << '\n';
    return 1;
  }
}
