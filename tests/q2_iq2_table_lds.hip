// SPDX-License-Identifier: MIT
// IQ2 compact table LDS reuse versus the literal fixed-bound measured parent.
// Synthetic guarded operator checks, separate from original-weight inference.
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
#include "experiments/iq2_mixed_tiles.h"
#include "experiments/q2_iq2_tail16_routes.inc"
#include "src/core/crypto/sha256.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
namespace gufo::models::qwen38_flash_next::rocm {
#include "experiments/q2-iq2-register-stage-control.inc"
}
namespace q = gufo::models::qwen38_flash_next::rocm;

static void Require(bool value, const char* message) {
  if (!value) throw std::runtime_error(message);
}
static void Hip(hipError_t value) {
  if (value != hipSuccess) throw std::runtime_error(hipGetErrorString(value));
}
struct Device {
  void* data{};
  std::size_t bytes;
  explicit Device(std::size_t size) : bytes(size) {
    Hip(hipMalloc(&data, size ? size : 4));
  }
  Device(const Device&) = delete;
  Device& operator=(const Device&) = delete;
  ~Device() { (void)hipFree(data); }
};
template<class T>
static void Upload(Device& out, const std::vector<T>& in, hipStream_t stream) {
  Require(out.bytes == in.size() * sizeof(T), "Upload size differs");
  if (out.bytes) Hip(hipMemcpyAsync(out.data, in.data(), out.bytes,
                                  hipMemcpyHostToDevice, stream));
  Hip(hipStreamSynchronize(stream));
}
static std::vector<std::uint8_t> Read(const Device& in, hipStream_t stream) {
  std::vector<std::uint8_t> out(in.bytes);
  if (in.bytes) Hip(hipMemcpyAsync(out.data(), in.data, in.bytes,
                                 hipMemcpyDeviceToHost, stream));
  Hip(hipStreamSynchronize(stream));
  return out;
}
static std::string Hash(const std::vector<std::uint8_t>& in) {
  return gufo::crypto::Sha256Hex(in);
}
struct Random {
  std::uint32_t state{901};
  std::uint32_t Next() { return state = state * 1664525u + 1013904223u; }
};
struct Inputs {
  unsigned n, m, k, experts, used, nonempty{};
  bool skew;
  std::vector<__half> activation;
  std::vector<std::int32_t> bounds, tokens, slots;
  std::array<std::vector<std::int32_t>, 2> maps;
  std::array<lie_iq2_tile_spans, 2> spans{};
  std::vector<std::uint8_t> encoded;
  std::array<std::unique_ptr<Device>, 3> gate, up;
  std::array<std::string, 3> gate_hash, up_hash;
  Device x;
  std::unique_ptr<Device> bd, td, sd;
  std::array<std::unique_ptr<Device>, 2> md;

  unsigned Expert(unsigned slot) const {
    if (!skew) return slot % experts;
    const auto within = slot % used;
    return within < 8 ? within
                     : 8 + ((slot / used) * (used - 8) + within - 8) % (experts - 8);
  }
  Inputs(unsigned rows, unsigned output, unsigned inner, unsigned active,
         unsigned top, bool uneven, hipStream_t stream,
         const std::uint32_t* captured = nullptr)
      : n(rows), m(output), k(inner), experts(active), used(top), skew(uneven),
        activation(std::size_t(n) * k), bounds(experts + 1),
        encoded(std::size_t(experts) * m * (k / 256) * 66),
        x(activation.size() * sizeof(__half)) {
    Require(k % 256 == 0 && used <= experts && (!skew || (used == 10 && experts > 10)),
            "Invalid IQ2 shape");
    Random rng;
    for (std::size_t i = 0; i < activation.size(); ++i) {
      const float value = i % 37 == 0 ? -0.0f : i % 41 == 0 ? 0.0000001f
          : float(int(rng.Next() >> 16) - 32768) / 262144;
      activation[i] = __float2half_rn(value);
    }
    Upload(x, activation, stream);
    std::vector<std::uint32_t> counts(experts), cursor(experts);
    if (captured) {
      Require(n == 2048 && experts == 512 && used == 10, "Captured shape changed");
      std::uint32_t total = 0;
      for (unsigned e = 0; e < experts; ++e) {
        counts[e] = captured[e];
        Require(counts[e] <= n, "Captured expert exceeds token count");
        total += counts[e];
      }
      Require(total == n * used, "Captured route total changed");
    } else {
      for (unsigned slot = 0; slot < n * used; ++slot) ++counts[Expert(slot)];
    }
    for (unsigned e = 0; e < experts; ++e)
      {
      nonempty += counts[e] != 0;
      bounds[e + 1] = bounds[e] + ((counts[e] + 15) / 16) * 16;
    }
    tokens.assign(bounds.back(), -1);
    slots.assign(bounds.back(), -1);
    if (captured) {
      // Cyclic token assignment realizes the measured degree counts: each
      // token has exactly used distinct experts, each output slot one owner.
      unsigned next = 0;
      for (unsigned e = 0; e < experts; ++e)
        for (unsigned row = 0; row < counts[e]; ++row, ++next) {
          const auto offset = unsigned(bounds[e]) + row;
          tokens[offset] = std::int32_t(next % n);
          slots[offset] = std::int32_t((next % n) * used + next / n);
        }
    } else {
      for (unsigned slot = 0; slot < n * used; ++slot) {
        const auto e = Expert(slot), offset = unsigned(bounds[e]) + cursor[e]++;
        tokens[offset] = std::int32_t(slot / used);
        slots[offset] = std::int32_t(slot);
      }
    }
    const auto capacity = (std::size_t(n) * used + experts * 15) / 16 + experts + 1;
    for (auto& map : maps) map.resize(capacity);
    lie_iq2_tile_spans original{};
    Require(lie_iq2_mixed_tiles(counts.data(), experts, n, used, maps[0].data(),
                              capacity, &original), "Original map rejected valid input");
    spans[0] = spans[1] = original;
    maps[0].resize(original.wide + original.tail);
    maps[1] = maps[0];
    for (unsigned a = 0; a < 2; ++a) {
      md[a] = std::make_unique<Device>(maps[a].size() * 4);
      Upload(*md[a], maps[a], stream);
    }
    Require(maps[0] == maps[1], "Original128/64 map changed");
    bd = std::make_unique<Device>(bounds.size() * 4);
    td = std::make_unique<Device>(tokens.size() * 4);
    sd = std::make_unique<Device>(slots.size() * 4);
    Upload(*bd, bounds, stream); Upload(*td, tokens, stream); Upload(*sd, slots, stream);
    for (unsigned r = 0; r < 3; ++r) {
      for (unsigned projection = 0; projection < 2; ++projection) {
        for (std::size_t block = 0; block < encoded.size(); block += 66) {
          const float scale = (block / 66) % 29 == 0 ? 0.0f
              : (block / 66) % 31 == 0 ? -0.0000001f
              : (block / 66) % 43 == 0 ? -0.00125f : 0.00125f;
          const __half d = __float2half_rn(scale);
          std::memcpy(encoded.data() + block, &d, 2);
          for (unsigned g = 0; g < 8; ++g) {
            const std::uint32_t indices = rng.Next(), signs = rng.Next();
            std::memcpy(encoded.data() + block + 2 + g * 8, &indices, 4);
            std::memcpy(encoded.data() + block + 6 + g * 8, &signs, 4);
          }
        }
        auto& device = projection ? up[r] : gate[r];
        auto& digest = projection ? up_hash[r] : gate_hash[r];
        device = std::make_unique<Device>(encoded.size());
        Upload(*device, encoded, stream); digest = Hash(encoded);
      }
    }
  }
  template<class T>
  static void Same(const Device& device, const std::vector<T>& values,
                   hipStream_t stream) {
    const auto bytes = Read(device, stream);
    Require(bytes.size() == values.size() * sizeof(T) &&
                (!bytes.size() || std::memcmp(bytes.data(), values.data(), bytes.size()) == 0),
            "Immutable input changed");
  }
  void Unchanged(hipStream_t stream) {
    for (unsigned r = 0; r < 3; ++r) {
      Require(Hash(Read(*gate[r], stream)) == gate_hash[r], "Gate weights changed");
      Require(Hash(Read(*up[r], stream)) == up_hash[r], "Up weights changed");
    }
    Same(x, activation, stream); Same(*bd, bounds, stream);
    Same(*td, tokens, stream); Same(*sd, slots, stream);
    for (unsigned a = 0; a < 2; ++a) Same(*md[a], maps[a], stream);
  }
};
template<unsigned BN>
static void LaunchWidth(Inputs& in, Device& out, unsigned rotation, unsigned arm,
                        unsigned offset, unsigned tiles, hipStream_t stream) {
  if (!tiles) return;
  if (arm && in.m == 640 && in.k == 2560) {
    Require(q::RoutedGatedIQ2Gemm(in.gate[rotation]->data, in.up[rotation]->data,
        static_cast<const __half*>(in.x.data),
        static_cast<const std::int32_t*>(in.md[arm]->data) + offset, tiles, BN,
        static_cast<const std::int32_t*>(in.bd->data),
        static_cast<const std::int32_t*>(in.td->data),
        static_cast<const std::int32_t*>(in.sd->data),
        static_cast<float*>(out.data) + 16, in.m, in.k, stream),
        "Production IQ2 table LDS dispatch rejected");
    Hip(hipGetLastError());
    return;
  }
  const dim3 grid((in.m + 63) / 64, tiles);
  if (!arm && in.m == 640 && in.k == 2560) {
    hipLaunchKernelGGL((q::RoutedIq2FixedBoundsKernel<q::WeightType::kIQ2_XXS,
                       128, BN, 2, true, false>),
        grid, dim3(256), 0, stream, in.gate[rotation]->data,
        static_cast<const __half*>(in.x.data),
        static_cast<const std::int32_t*>(in.md[arm]->data) + offset,
        static_cast<const std::int32_t*>(in.bd->data),
        static_cast<const std::int32_t*>(in.td->data),
        static_cast<const std::int32_t*>(in.sd->data), nullptr,
        static_cast<float*>(out.data) + 16, nullptr, in.m, in.k, in.up[rotation]->data);
    Hip(hipGetLastError());
    return;
  }
  if (arm) {
    // Exercise the private body at ragged edges as well as its production shapes.
    hipLaunchKernelGGL((q::RoutedF16GEMMKernel<q::WeightType::kIQ2_XXS,
                       128, BN, 2, true, false>),
        grid, dim3(256), 0, stream, in.gate[rotation]->data,
        static_cast<const __half*>(in.x.data),
        static_cast<const std::int32_t*>(in.md[arm]->data) + offset,
        static_cast<const std::int32_t*>(in.bd->data),
        static_cast<const std::int32_t*>(in.td->data),
        static_cast<const std::int32_t*>(in.sd->data), nullptr,
        static_cast<float*>(out.data) + 16, nullptr, in.m, in.k, in.up[rotation]->data);
    Hip(hipGetLastError());
    return;
  }
  hipLaunchKernelGGL((q::RoutedIq2RegisterStageControlKernel<q::WeightType::kIQ2_XXS, 128, BN,
                                            2, true, false>),
      grid, dim3(256), 0, stream, in.gate[rotation]->data,
      static_cast<const __half*>(in.x.data),
      static_cast<const std::int32_t*>(in.md[arm]->data) + offset,
      static_cast<const std::int32_t*>(in.bd->data),
      static_cast<const std::int32_t*>(in.td->data),
      static_cast<const std::int32_t*>(in.sd->data), nullptr,
      static_cast<float*>(out.data) + 16, nullptr, in.m, in.k, in.up[rotation]->data);
  Hip(hipGetLastError());
}
static void Launch(bool candidate, Inputs& in, Device& out, unsigned rotation,
                   hipStream_t stream) {
  const unsigned arm = candidate ? 1 : 0;
  const auto& s = in.spans[arm];
  LaunchWidth<128>(in, out, rotation, arm, 0, s.wide, stream);
  LaunchWidth<64>(in, out, rotation, arm, s.wide, s.tail, stream);
}
static bool Case(const std::string& label, unsigned n, unsigned m, unsigned k,
                 unsigned experts, unsigned used, bool skew, bool bench,
                 hipStream_t stream, const std::uint32_t* captured = nullptr) {
  Inputs in(n, m, k, experts, used, skew, stream, captured);
  const auto& s = in.spans[1];
  std::cout << "{\"event\":\"iq2_table_lds_map\",\"case\":\"" << label
      << "\",\"reference_wide128\":" << in.spans[0].wide
      << ",\"reference_tail64\":" << in.spans[0].tail
      << ",\"candidate_wide128\":" << s.wide
      << ",\"candidate_tail64\":" << s.tail
      << ",\"nonempty_experts\":" << in.nonempty
      << ",\"maps_exact\":true,\"skew\":" << skew << "}\n";
  const std::size_t bytes = (std::size_t(n) * used * m + 32) * 4;
  Device reference(bytes), candidate(bytes);
  bool pass = true;
  const auto check_output = [&](unsigned r, bool after_timing) {
    if (!after_timing) {
      Hip(hipMemsetAsync(reference.data, 0xa5, bytes, stream));
      Hip(hipMemsetAsync(candidate.data, 0xa5, bytes, stream));
      Launch(false, in, reference, r, stream); Launch(true, in, candidate, r, stream);
    }
    const auto a = Read(reference, stream), b = Read(candidate, stream);
    std::size_t changed = 0, nonfinite = 0, unwritten = 0;
    bool guards = true;
    for (std::size_t i = 0; i < bytes; i += 4) {
      std::uint32_t av, bv; float af, bf;
      std::memcpy(&av, a.data() + i, 4); std::memcpy(&bv, b.data() + i, 4);
      if (i < 64 || i >= bytes - 64) {
        guards = guards && av == 0xa5a5a5a5U && bv == 0xa5a5a5a5U;
      } else {
        changed += av != bv;
        unwritten += av == 0xa5a5a5a5U || bv == 0xa5a5a5a5U;
        std::memcpy(&af, &av, 4); std::memcpy(&bf, &bv, 4);
        nonfinite += !std::isfinite(af) || !std::isfinite(bf);
      }
    }
    const bool exact = !changed && !nonfinite && !unwritten && guards;
    pass = pass && exact;
    std::cout << "{\"event\":\"iq2_table_lds_replay\",\"case\":\"" << label
        << "\",\"after_timing\":" << after_timing << ",\"rotation\":" << r << ",\"packed\":false,\"bytes\":" << bytes
        << ",\"changed_values\":" << changed << ",\"nonfinite_values\":" << nonfinite
        << ",\"unwritten_values\":" << unwritten << ",\"guards_exact\":" << guards
        << ",\"exact\":" << exact << ",\"reference_sha256\":\"" << Hash(a)
        << "\",\"candidate_sha256\":\"" << Hash(b) << "\",\"gate_sha256\":\""
        << in.gate_hash[r] << "\",\"up_sha256\":\"" << in.up_hash[r] << "\"}\n";
    if (!exact) {
      for (unsigned arm = 0; arm < 2; ++arm) {
        const auto& values = arm ? b : a;
        const auto file = "results/" + label + "-" + std::to_string(r) + (after_timing ? "-post" : "-initial") +
            (arm ? "-candidate.bin" : "-reference.bin");
        std::ofstream saved(file, std::ios::binary);
        saved.write(reinterpret_cast<const char*>(values.data()), values.size());
        Require(bool(saved), "Failed to preserve changed output");
      }
    }
    Require(guards, "IQ2 output guard changed; refusing further device work");
    Require(!unwritten, "IQ2 output unwritten; refusing further device work");
    Require(!nonfinite, "IQ2 output nonfinite; refusing further device work");
  };
  for (unsigned r = 0; r < 3; ++r) check_output(r, false);
  if (bench) {
    Require(in.encoded.size() * 6 > 32u * 1024 * 1024, "Weight rotation below MALL");
    hipEvent_t begin{}, end{};
    Hip(hipEventCreate(&begin)); Hip(hipEventCreate(&end));
    for (unsigned rep = 0; rep < 7; ++rep) {
      for (unsigned order = 0; order < 2; ++order) {
        const bool is_candidate = (rep + order) % 2;
        auto& output = is_candidate ? candidate : reference;
        const auto wall_begin = std::chrono::steady_clock::now();
        Hip(hipEventRecord(begin, stream));
        for (unsigned r = 0; r < 3; ++r) Launch(is_candidate, in, output, r, stream);
        Hip(hipEventRecord(end, stream)); Hip(hipEventSynchronize(end));
        const double wall_us = std::chrono::duration<double, std::micro>(
            std::chrono::steady_clock::now() - wall_begin).count();
        float ms{}; Hip(hipEventElapsedTime(&ms, begin, end));
        std::uint32_t event_bits{}; std::memcpy(&event_bits, &ms, 4);
        const bool event_valid = std::isfinite(ms) && ms > 0;
        Require(std::isfinite(wall_us) && wall_us > 0, "Invalid monotonic operator timer");
        std::cout << "{\"event\":\"iq2_table_lds_timing\",\"case\":\"" << label
            << "\",\"rep\":" << rep << ",\"order\":" << order
            << ",\"candidate\":" << is_candidate << ",\"warmup\":" << (rep < 2)
            << ",\"tokens\":" << n << ",\"output_rows\":" << m << ",\"inner\":" << k
            << ",\"expert_capacity\":" << experts << ",\"skew\":" << skew
            << ",\"iterations\":3,\"weight_bytes\":" << in.encoded.size() * 6
            << ",\"raw_hip_ms\":" << ms << ",\"raw_hip_bits\":" << event_bits
            << ",\"hip_timer_valid\":" << event_valid
            << ",\"wall_us_per_iteration\":" << wall_us / 3 << "}\n";
      }
    }
    check_output(2, true);  // Inspect the final timed outputs without another launch.
    Hip(hipEventDestroy(end)); Hip(hipEventDestroy(begin));
  }
  in.Unchanged(stream);
  return pass;
}
int main() {
  try {
    std::cout << std::boolalpha << std::defaultfloat << std::setprecision(12);
    hipStream_t stream{}; Hip(hipStreamCreateWithFlags(&stream, hipStreamNonBlocking));
    bool pass = true;
    for (unsigned n : {1u, 16u, 17u, 49u, 65u, 129u, 144u, 145u, 257u})
      for (unsigned m : {1u, 65u, 640u})
        pass = Case("edge-n" + std::to_string(n) + "-m" + std::to_string(m),
                    n, m, 256, 1, 1, false, false, stream) && pass;
    for (unsigned n : {1u, 17u, 65u, 145u})
      pass = Case("fixed-edge-n" + std::to_string(n), n, 640, 2560, 1, 1,
                  false, false, stream) && pass;
    pass = Case("uniform-e160", 2048, 640, 2560, 160, 10, false, true, stream) && pass;
    pass = Case("uniform-e512", 2048, 640, 2560, 512, 10, false, true, stream) && pass;
    pass = Case("real-layer0", 2048, 640, 2560, 512, 10, false, true, stream, kLayer0Counts) && pass;
    pass = Case("real-layer3", 2048, 640, 2560, 512, 10, false, true, stream, kLayer3Counts) && pass;
    pass = Case("real-layer22", 2048, 640, 2560, 512, 10, false, true, stream, kLayer22Counts) && pass;
    Hip(hipStreamSynchronize(stream)); Hip(hipStreamDestroy(stream));
    std::cout << "{\"event\":\"iq2_table_lds_complete\",\"numerical_pass\":" << pass
        << ",\"timing_retained\":true,\"model_inference\":false}\n";
    return pass ? 0 : 1;
  } catch (const std::exception& error) {
    std::cerr << "FAIL: " << error.what() << '\n'; return 2;
  }
}
