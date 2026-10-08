// SPDX-License-Identifier: MIT
// New four-wave IQ2 gate/up versus the literal retained1585 parent.
// Synthetic operator timing; original-weight model timing is separate.
#include <array>
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

#include "src/core/crypto/sha256.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
namespace gufo::models::qwen38_flash_next::rocm {
#include "experiments/q2-iq2-four-wave-control.inc"
}
namespace q = gufo::models::qwen38_flash_next::rocm;

static void Require(bool condition, const char* message) {
  if (!condition)
    throw std::runtime_error(message);
}
static void Hip(hipError_t status) {
  if (status != hipSuccess)
    throw std::runtime_error(hipGetErrorString(status));
}
struct Device {
  void* data{};
  std::size_t bytes;
  explicit Device(std::size_t size) : bytes(size) {
    Hip(hipMalloc(&data, size ? size : 4));
  }
  Device(const Device&) = delete;
  Device& operator=(const Device&) = delete;
  ~Device() { hipFree(data); }
};
template<class T>
static void Upload(Device& device, const std::vector<T>& host,
                   hipStream_t stream) {
  Require(device.bytes == host.size() * sizeof(T), "Upload size differs");
  if (device.bytes)
    Hip(hipMemcpyAsync(device.data, host.data(), device.bytes,
                       hipMemcpyHostToDevice, stream));
  Hip(hipStreamSynchronize(stream));
}
static std::vector<std::uint8_t> Read(const Device& device,
                                      hipStream_t stream) {
  std::vector<std::uint8_t> result(device.bytes);
  if (device.bytes)
    Hip(hipMemcpyAsync(result.data(), device.data, device.bytes,
                       hipMemcpyDeviceToHost, stream));
  Hip(hipStreamSynchronize(stream));
  return result;
}
static std::string Hash(const std::vector<std::uint8_t>& bytes) {
  return gufo::crypto::Sha256Hex(bytes);
}
struct Random {
  std::uint32_t state{901};
  std::uint32_t Next() {
    state = state * 1664525u + 1013904223u;
    return state;
  }
};
struct Inputs {
  unsigned n, m, k, experts, used, width;
  std::vector<__half> activation;
  std::vector<std::int32_t> bounds, tokens, slots, narrow, wide;
  std::vector<std::uint8_t> encoded;
  std::array<std::unique_ptr<Device>, 3> gate, up;
  std::array<std::string, 3> gate_hash, up_hash;
  Device x;
  std::unique_ptr<Device> bd, td, sd, nd, wd;

  Inputs(unsigned rows, unsigned output, unsigned inner, unsigned active,
         unsigned top, unsigned tile, hipStream_t stream)
      : n(rows),
        m(output),
        k(inner),
        experts(active),
        used(top),
        width(tile),
        activation(std::size_t(n) * k),
        bounds(experts + 1),
        encoded(std::size_t(experts) * m * (k / 256) * 66),
        x(activation.size() * 2) {
    Require(k % 256 == 0 && used <= experts, "Invalid IQ2 shape");
    Random rng;
    for (std::size_t i = 0; i < activation.size(); ++i) {
      const float value = i % 37 == 0 ? -0.0f
                          : i % 41 == 0
                              ? 0.0000001f
                              : float(int(rng.Next() >> 16) - 32768) / 262144;
      activation[i] = __float2half_rn(value);
    }
    Upload(x, activation, stream);
    std::vector<unsigned> counts(experts), cursor(experts);
    for (unsigned slot = 0; slot < n * used; ++slot)
      ++counts[slot % experts];
    for (unsigned e = 0; e < experts; ++e)
      bounds[e + 1] = bounds[e] + ((counts[e] + 15) / 16) * 16;
    tokens.assign(bounds.back(), -1);
    slots.assign(bounds.back(), -1);
    for (unsigned slot = 0; slot < n * used; ++slot) {
      const unsigned expert = slot % experts;
      const auto offset = unsigned(bounds[expert]) + cursor[expert]++;
      tokens[offset] = std::int32_t(slot / used);
      slots[offset] = std::int32_t(slot);
    }
    for (unsigned e = 0; e < experts; ++e) {
      if (width) {
        for (unsigned j = 0; j < (counts[e] + 15) / 16 * 16; j += width)
          narrow.push_back(std::int32_t(e | (j / width) << 16));
      } else {
        const unsigned groups = (counts[e] + 63) / 64;
        for (unsigned j = 0; j < groups / 2; ++j)
          wide.push_back(std::int32_t(e | j << 16));
        if (groups & 1)
          narrow.push_back(std::int32_t(e | (groups - 1) << 16));
      }
    }
    bd = std::make_unique<Device>(bounds.size() * 4);
    td = std::make_unique<Device>(tokens.size() * 4);
    sd = std::make_unique<Device>(slots.size() * 4);
    nd = std::make_unique<Device>(narrow.size() * 4);
    wd = std::make_unique<Device>(wide.size() * 4);
    Upload(*bd, bounds, stream);
    Upload(*td, tokens, stream);
    Upload(*sd, slots, stream);
    Upload(*nd, narrow, stream);
    Upload(*wd, wide, stream);
    for (unsigned rotation = 0; rotation < 3; ++rotation) {
      for (unsigned projection = 0; projection < 2; ++projection) {
        for (std::size_t block = 0; block < encoded.size(); block += 66) {
          const float scale = (block / 66) % 29 == 0   ? 0.0f
                              : (block / 66) % 31 == 0 ? -0.0000001f
                              : (block / 66) % 43 == 0 ? -0.00125f
                                                       : 0.00125f;
          const __half d = __float2half_rn(scale);
          std::memcpy(encoded.data() + block, &d, 2);
          for (unsigned group = 0; group < 8; ++group) {
            const std::uint32_t indices = rng.Next(), signs = rng.Next();
            std::memcpy(encoded.data() + block + 2 + group * 8, &indices, 4);
            std::memcpy(encoded.data() + block + 6 + group * 8, &signs, 4);
          }
        }
        auto& device = projection ? up[rotation] : gate[rotation];
        auto& digest = projection ? up_hash[rotation] : gate_hash[rotation];
        device = std::make_unique<Device>(encoded.size());
        Upload(*device, encoded, stream);
        digest = Hash(encoded);
      }
    }
  }
  void Unchanged(hipStream_t stream) {
    for (unsigned r = 0; r < 3; ++r) {
      Require(Hash(Read(*gate[r], stream)) == gate_hash[r],
              "Gate weights changed");
      Require(Hash(Read(*up[r], stream)) == up_hash[r], "Up weights changed");
    }
    const auto bytes = Read(x, stream);
    Require(std::memcmp(bytes.data(), activation.data(), bytes.size()) == 0,
            "Activations changed");
  }
};
template<unsigned BN, bool Packed>
static void LaunchWidth(bool candidate, Inputs& in, Device& output,
                        unsigned rotation, const Device& map, unsigned tiles,
                        hipStream_t stream) {
  if (!tiles)
    return;
  const dim3 grid((in.m + 63) / 64, tiles);
  auto* out = static_cast<float*>(output.data) + 16;
  if (candidate) {
    constexpr bool four_wave = BN == 64 && !Packed;
    hipLaunchKernelGGL((q::RoutedF16GEMMKernel<q::WeightType::kIQ2_XXS, 128, BN,
                                               2, true, Packed, false, four_wave>),
                       grid, dim3(four_wave ? 128 : 256), 0, stream, in.gate[rotation]->data,
                       static_cast<const __half*>(in.x.data),
                       static_cast<const std::int32_t*>(map.data),
                       static_cast<const std::int32_t*>(in.bd->data),
                       static_cast<const std::int32_t*>(in.td->data),
                       static_cast<const std::int32_t*>(in.sd->data), nullptr,
                       out, nullptr, in.m, in.k, in.up[rotation]->data);
  } else {
    hipLaunchKernelGGL((q::RoutedIq2FourWaveControlKernel<q::WeightType::kIQ2_XXS,
                                                     128, BN, 2, true, Packed>),
                       grid, dim3(256), 0, stream, in.gate[rotation]->data,
                       static_cast<const __half*>(in.x.data),
                       static_cast<const std::int32_t*>(map.data),
                       static_cast<const std::int32_t*>(in.bd->data),
                       static_cast<const std::int32_t*>(in.td->data),
                       static_cast<const std::int32_t*>(in.sd->data), nullptr,
                       out, nullptr, in.m, in.k, in.up[rotation]->data);
  }
  Hip(hipGetLastError());
}
template<bool Packed>
static void Launch(bool candidate, Inputs& in, Device& output,
                   unsigned rotation, hipStream_t stream) {
  switch (in.width) {
    case 16:
      LaunchWidth<16, Packed>(candidate, in, output, rotation, *in.nd,
                              in.narrow.size(), stream);
      break;
    case 48:
      LaunchWidth<48, Packed>(candidate, in, output, rotation, *in.nd,
                              in.narrow.size(), stream);
      break;
    case 64:
      LaunchWidth<64, Packed>(candidate, in, output, rotation, *in.nd,
                              in.narrow.size(), stream);
      break;
    case 128:
      LaunchWidth<128, Packed>(candidate, in, output, rotation, *in.nd,
                               in.narrow.size(), stream);
      break;
    case 0:
      LaunchWidth<128, Packed>(candidate, in, output, rotation, *in.wd,
                               in.wide.size(), stream);
      LaunchWidth<64, Packed>(candidate, in, output, rotation, *in.nd,
                              in.narrow.size(), stream);
      break;
    default:
      throw std::runtime_error("Invalid tile width");
  }
}
template<bool Packed>
static bool Case(const std::string& label, unsigned n, unsigned m, unsigned k,
                 unsigned experts, unsigned used, unsigned width, bool bench,
                 hipStream_t stream) {
  Inputs in(n, m, k, experts, used, width, stream);
  const std::size_t bytes = (std::size_t(n) * used * m + 32) * 4;
  Device reference(bytes), candidate(bytes);
  bool pass = true;
  for (unsigned r = 0; r < 3; ++r) {
    Hip(hipMemsetAsync(reference.data, 0xa5, bytes, stream));
    Hip(hipMemsetAsync(candidate.data, 0xa5, bytes, stream));
    Launch<Packed>(false, in, reference, r, stream);
    Launch<Packed>(true, in, candidate, r, stream);
    const auto a = Read(reference, stream), b = Read(candidate, stream);
    std::size_t changed = 0, nonfinite = 0, unwritten = 0;
    bool guards = true;
    for (std::size_t i = 0; i < bytes; i += 4) {
      std::uint32_t av, bv;
      std::memcpy(&av, a.data() + i, 4);
      std::memcpy(&bv, b.data() + i, 4);
      if (i < 64 || i >= bytes - 64) {
        guards = guards && av == 0xa5a5a5a5U && bv == 0xa5a5a5a5U;
      } else {
        changed += av != bv;
        unwritten += av == 0xa5a5a5a5U || bv == 0xa5a5a5a5U;
        if constexpr (!Packed) {
          float af, bf;
          std::memcpy(&af, &av, 4);
          std::memcpy(&bf, &bv, 4);
          nonfinite += !std::isfinite(af) || !std::isfinite(bf);
        }
      }
    }
    const bool exact = !changed && !nonfinite && !unwritten && guards;
    pass = pass && exact;
    std::cout << "{\"event\":\"iq2_four_wave_replay\",\"case\":\"" << label
              << "\",\"rotation\":" << r << ",\"packed\":" << Packed
              << ",\"bytes\":" << bytes << ",\"changed_values\":" << changed
              << ",\"nonfinite_values\":" << nonfinite
              << ",\"unwritten_values\":" << unwritten
              << ",\"guards_exact\":" << guards << ",\"exact\":" << exact
              << ",\"reference_sha256\":\"" << Hash(a)
              << "\",\"candidate_sha256\":\"" << Hash(b)
              << "\",\"gate_sha256\":\"" << in.gate_hash[r]
              << "\",\"up_sha256\":\"" << in.up_hash[r] << "\"}\n";
    if (!exact) {
      for (unsigned arm = 0; arm < 2; ++arm) {
        const auto& values = arm ? b : a;
        const auto file = "results/" + label + "-" + std::to_string(r) +
                          (arm ? "-candidate.bin" : "-reference.bin");
        std::ofstream saved(file, std::ios::binary);
        saved.write(reinterpret_cast<const char*>(values.data()),
                    values.size());
        Require(bool(saved), "Failed to preserve changed output");
      }
    }
    Require(guards, "IQ2 output guard changed; refusing further device work");
    Require(unwritten == 0, "Required output remains unwritten");
  }
  if (bench) {
    Require(in.encoded.size() * 6 > 32u * 1024 * 1024,
            "Weight rotation does not exceed MALL");
    hipEvent_t begin{}, end{};
    Hip(hipEventCreate(&begin));
    Hip(hipEventCreate(&end));
    for (unsigned rep = 0; rep < 7; ++rep) {
      for (unsigned order = 0; order < 2; ++order) {
        const bool is_candidate = (rep + order) % 2;
        auto& output = is_candidate ? candidate : reference;
        Hip(hipEventRecord(begin, stream));
        for (unsigned r = 0; r < 3; ++r)
          Launch<Packed>(is_candidate, in, output, r, stream);
        Hip(hipEventRecord(end, stream));
        Hip(hipEventSynchronize(end));
        float ms{};
        Hip(hipEventElapsedTime(&ms, begin, end));
        std::cout << "{\"event\":\"iq2_four_wave_timing\",\"case\":\""
                  << label << "\",\"rep\":" << rep << ",\"order\":" << order
                  << ",\"candidate\":" << is_candidate
                  << ",\"warmup\":" << (rep < 2) << ",\"tokens\":" << n
                  << ",\"output_rows\":" << m << ",\"inner\":" << k
                  << ",\"active_experts\":" << experts << ",\"width\":" << width
                  << ",\"wide_tiles\":" << in.wide.size()
                  << ",\"narrow_tiles\":" << in.narrow.size()
                  << ",\"iterations\":3,\"weight_bytes\":"
                  << in.encoded.size() * 6
                  << ",\"us_per_iteration\":" << double(ms) * 1000 / 3 << "}\n";
      }
    }
    Hip(hipEventDestroy(end));
    Hip(hipEventDestroy(begin));
  }
  in.Unchanged(stream);
  return pass;
}

int main() {
  try {
    std::cout << std::boolalpha << std::defaultfloat << std::setprecision(12);
    hipStream_t stream{};
    Hip(hipStreamCreateWithFlags(&stream, hipStreamNonBlocking));
    bool pass = true;
    for (unsigned n : {1u, 17u, 49u, 65u, 129u}) {
      for (unsigned m : {1u, 65u, 127u, 129u, 640u}) {
        const auto name = "edge-n" + std::to_string(n) + "-m" + std::to_string(m);
        pass = Case<false>(name, n, m, 256, 1, 1, 64, false, stream) && pass;
      }
    }
    for (unsigned active : {64u, 128u, 512u})
      pass = Case<false>("mixed-e" + std::to_string(active), 2048, 640, 2560,
                         active, 10, 0, true, stream) &&
             pass;
    // Unchanged production widths and packed output remain direct controls.
    for (unsigned width : {16u, 48u, 128u})
      pass = Case<false>("control-width" + std::to_string(width), 129, 65,
                         256, 1, 1, width, false, stream) && pass;
    pass = Case<true>("control-packed64", 65, 65, 256, 1, 1, 64,
                      false, stream) && pass;
    Hip(hipStreamSynchronize(stream));
    Hip(hipStreamDestroy(stream));
    std::cout << "{\"event\":\"iq2_four_wave_complete\",\"numerical_pass\":"
              << pass
              << ",\"timing_retained\":true,\"model_inference\":false}\n";
    return pass ? 0 : 1;
  } catch (const std::exception& error) {
    std::cerr << "FAIL: " << error.what() << '\n';
    return 2;  // Runtime/guard failure must stop dependent GPU work.
  }
}
