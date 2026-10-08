// SPDX-License-Identifier: MIT
// New Q2 down unread-store suppression versus the literal saved parent kernel.
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
#include <utility>
#include <vector>

#include "src/core/crypto/sha256.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
namespace gufo::models::qwen38_flash_next::rocm {
#include "experiments/q2-down-live-stage-control.inc"
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
  ~Device() { (void)hipFree(data); }
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
  std::vector<float> inverse;
  std::vector<std::int32_t> bounds, slots, tiles;
  std::vector<std::uint8_t> encoded;
  std::array<std::unique_ptr<Device>, 3> weights;
  std::array<std::string, 3> weight_hash;
  Device x, scale;
  std::unique_ptr<Device> bd, sd, td;

  Inputs(unsigned tokens, unsigned output, unsigned inner, unsigned active,
         unsigned top, unsigned tile, hipStream_t stream)
      : n(tokens),
        m(output),
        k(inner),
        experts(active),
        used(top),
        width(tile),
        activation(std::size_t(n) * used * k),
        inverse(std::size_t(n) * used),
        bounds(experts + 1),
        encoded(std::size_t(experts) * m * ((k + 255) / 256) * 84),
        x(activation.size() * 2),
        scale(inverse.size() * 4) {
    Require(k % 64 == 0 && used <= experts, "Invalid Q2 shape");
    Random rng;
    for (std::size_t i = 0; i < activation.size(); ++i) {
      const float magnitude = i % 97 == 0 ? 8192.0f : 16.0f;
      const float value = i % 37 == 0   ? -0.0f
                          : i % 41 == 0 ? 0.0000001f
                                        : float(int(rng.Next() >> 16) - 32768) /
                                              32768 * magnitude;
      activation[i] = __float2half_rn(value);
    }
    for (std::size_t i = 0; i < inverse.size(); ++i)
      inverse[i] = std::ldexp(1.0f, int(i % 17) - 8);
    Upload(x, activation, stream);
    Upload(scale, inverse, stream);
    std::vector<unsigned> counts(experts), cursor(experts);
    for (unsigned slot = 0; slot < n * used; ++slot)
      ++counts[slot % experts];
    for (unsigned e = 0; e < experts; ++e)
      bounds[e + 1] = bounds[e] + ((counts[e] + 15) / 16) * 16;
    slots.assign(bounds.back(), -1);
    for (unsigned slot = 0; slot < n * used; ++slot) {
      const unsigned e = slot % experts;
      slots[unsigned(bounds[e]) + cursor[e]++] = std::int32_t(slot);
    }
    for (unsigned e = 0; e < experts; ++e)
      for (unsigned j = 0; j < (counts[e] + 15) / 16 * 16; j += width)
        tiles.push_back(std::int32_t(e | (j / width) << 16));
    bd = std::make_unique<Device>(bounds.size() * 4);
    sd = std::make_unique<Device>(slots.size() * 4);
    td = std::make_unique<Device>(tiles.size() * 4);
    Upload(*bd, bounds, stream);
    Upload(*sd, slots, stream);
    Upload(*td, tiles, stream);
    for (unsigned rotation = 0; rotation < 3; ++rotation) {
      for (std::size_t block = 0; block < encoded.size(); block += 84) {
        for (unsigned i = 0; i < 80; ++i)
          encoded[block + i] = std::uint8_t(rng.Next() >> 24);
        const auto index = block / 84 + rotation;
        const float value = index % 29 == 0   ? 0.0f
                            : index % 31 == 0 ? -0.0000001f
                            : index % 43 == 0 ? -0.00125f
                                              : 0.00125f;
        const __half d = __float2half_rn(value),
                     minimum = __float2half_rn(value * 0.75f);
        std::memcpy(encoded.data() + block + 80, &d, 2);
        std::memcpy(encoded.data() + block + 82, &minimum, 2);
      }
      weights[rotation] = std::make_unique<Device>(encoded.size());
      Upload(*weights[rotation], encoded, stream);
      weight_hash[rotation] = Hash(encoded);
    }
  }
  void Unchanged(hipStream_t stream) {
    for (unsigned r = 0; r < 3; ++r)
      Require(Hash(Read(*weights[r], stream)) == weight_hash[r],
              "Weights changed");
    for (const auto& pair :
         {std::pair<const Device*, const void*>{&x, activation.data()},
          std::pair<const Device*, const void*>{&scale, inverse.data()}}) {
      const auto bytes = Read(*pair.first, stream);
      Require(std::memcmp(bytes.data(), pair.second, bytes.size()) == 0,
              "Input changed");
    }
  }
};

template<unsigned BN>
static void LaunchWidth(bool candidate, Inputs& in, Device& output,
                        unsigned rotation, hipStream_t stream) {
  const dim3 grid((in.m + 127) / 128, in.tiles.size());
  auto* out = static_cast<float*>(output.data) + 16;
  const auto* x = static_cast<const __half*>(in.x.data);
  const auto* tiles = static_cast<const std::int32_t*>(in.td->data);
  const auto* bounds = static_cast<const std::int32_t*>(in.bd->data);
  const auto* slots = static_cast<const std::int32_t*>(in.sd->data);
  if (candidate) {
    Require(q::RoutedQ2ScaledGemm(in.weights[rotation]->data, x,
                static_cast<const float*>(in.scale.data), tiles,
                static_cast<std::uint32_t>(in.tiles.size()), BN, bounds, slots,
                out, in.m, in.k, stream), "Candidate dispatch refused");
  } else {
    hipLaunchKernelGGL(
        (q::RoutedDownLiveControlKernel<q::WeightType::kQ2_K, 128, BN, 2, false,
                                       false, true>),
        grid, dim3(256), 0, stream, in.weights[rotation]->data, x, tiles,
        bounds, slots, slots, nullptr, out, nullptr, in.m, in.k, in.scale.data);
  }
  Hip(hipGetLastError());
}
static void Launch(bool candidate, Inputs& in, Device& output,
                   unsigned rotation, hipStream_t stream) {
  switch (in.width) {
    case 16:
      LaunchWidth<16>(candidate, in, output, rotation, stream);
      break;
    case 48:
      LaunchWidth<48>(candidate, in, output, rotation, stream);
      break;
    case 64:
      LaunchWidth<64>(candidate, in, output, rotation, stream);
      break;
    default:
      throw std::runtime_error("Invalid tile width");
  }
}

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
    Launch(false, in, reference, r, stream);
    Launch(true, in, candidate, r, stream);
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
        float af, bf;
        std::memcpy(&af, &av, 4);
        std::memcpy(&bf, &bv, 4);
        nonfinite += !std::isfinite(af) || !std::isfinite(bf);
      }
    }
    const bool exact = !changed && !nonfinite && !unwritten && guards;
    pass = pass && exact;
    std::cout << "{\"event\":\"down_live_stage_replay\",\"case\":\"" << label
              << "\",\"rotation\":" << r << ",\"bytes\":" << bytes
              << ",\"changed_values\":" << changed
              << ",\"nonfinite_values\":" << nonfinite
              << ",\"unwritten_values\":" << unwritten
              << ",\"guards_exact\":" << guards << ",\"exact\":" << exact
              << ",\"reference_sha256\":\"" << Hash(a)
              << "\",\"candidate_sha256\":\"" << Hash(b)
              << "\",\"weight_sha256\":\"" << in.weight_hash[r] << "\"}\n";
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
    Require(guards && !unwritten, "Output guard changed or required output unwritten; refusing further device work");
  }
  if (bench) {
    Require(in.encoded.size() * 3 > 32u * 1024 * 1024,
            "Weight rotation below MALL");
    hipEvent_t begin{}, end{};
    Hip(hipEventCreate(&begin));
    Hip(hipEventCreate(&end));
    for (unsigned rep = 0; rep < 7; ++rep) {
      for (unsigned order = 0; order < 2; ++order) {
        const bool is_candidate = (rep + order) % 2;
        auto& output = is_candidate ? candidate : reference;
        Hip(hipEventRecord(begin, stream));
        for (unsigned r = 0; r < 3; ++r)
          Launch(is_candidate, in, output, r, stream);
        Hip(hipEventRecord(end, stream));
        Hip(hipEventSynchronize(end));
        float ms{};
        Hip(hipEventElapsedTime(&ms, begin, end));
        std::cout << "{\"event\":\"down_live_stage_timing\",\"case\":\""
                  << label << "\",\"rep\":" << rep << ",\"order\":" << order
                  << ",\"candidate\":" << is_candidate
                  << ",\"warmup\":" << (rep < 2) << ",\"tokens\":" << n
                  << ",\"output_rows\":" << m << ",\"inner\":" << k
                  << ",\"active_experts\":" << experts << ",\"width\":" << width
                  << ",\"tiles\":" << in.tiles.size()
                  << ",\"iterations\":3,\"weight_bytes\":"
                  << in.encoded.size() * 3
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
    for (unsigned width : {16u, 48u, 64u})
      for (unsigned n : {1u, 15u, 16u, 17u, 31u, 32u, 33u, 47u, 48u,
                         49u, 63u, 64u, 65u, 95u, 96u, 97u, 129u})
        for (unsigned m : {1u, 129u, 2560u})
          pass = Case("edge-w" + std::to_string(width) + "-n" +
                      std::to_string(n) + "-m" + std::to_string(m),
                      n, m, 640, 1, 1, width, false, stream) && pass;
    for (unsigned width : {48u, 64u})
      for (unsigned active : {64u, 128u, 512u})
        pass = Case("mixed-w" + std::to_string(width) + "-e" +
                    std::to_string(active), 2048, 2560, 640, active,
                    10, width, true, stream) && pass;
    Hip(hipStreamSynchronize(stream));
    Hip(hipStreamDestroy(stream));
    std::cout << "{\"event\":\"down_live_stage_complete\",\"numerical_pass\":"
              << pass
              << ",\"timing_retained\":true,\"model_inference\":false}\n";
    return pass ? 0 : 1;
  } catch (const std::exception& error) {
    std::cerr << "FAIL: " << error.what() << '\n';
    return 1;
  }
}
