// SPDX-License-Identifier: MIT
// Eight-value half consumer versus literal measured1570 four-value consumer.
// Synthetic operator timing; original-weight model timing is separate.
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <bit>
#include <algorithm>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "src/core/crypto/sha256.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
namespace gufo::models::qwen38_flash_next::rocm {
#include "experiments/q2-half-consumer-eight-control.inc"
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
struct Output {
  std::size_t count;
  bool half;
  std::size_t offset;
  Device device;
  Output(std::size_t n, bool h, std::size_t prefix = 64)
      : count(n), half(h), offset(prefix), device(n * (h ? 2 : 4) + prefix + 64) {}
  void* Data() { return static_cast<std::uint8_t*>(device.data) + offset; }
  void Poison(hipStream_t stream) {
    std::vector<std::uint8_t> bytes(device.bytes, 0xa5);
    for (std::size_t i = 0; i < count; ++i) {
      const std::uint32_t pattern = half ? 0x7e55u : 0x7fc0beefu;
      std::memcpy(bytes.data() + offset + i * (half ? 2 : 4), &pattern, half ? 2 : 4);
    }
    Upload(device, bytes, stream);
  }
  std::vector<std::uint8_t> Checked(hipStream_t stream) {
    auto bytes = Read(device, stream);
    for (std::size_t i = 0; i < offset; ++i)
      Require(bytes[i] == 0xa5,
              "Output leading guard changed; refusing further device work");
    for (std::size_t i = 0; i < 64; ++i)
      Require(bytes[bytes.size() - 1 - i] == 0xa5,
              "Output guard changed; refusing further device work");
    for (std::size_t i = 0; i < count; ++i) {
      std::uint32_t bits = 0;
      std::memcpy(&bits, bytes.data() + offset + i * (half ? 2 : 4), half ? 2 : 4);
      Require(bits != (half ? 0x7e55u : 0x7fc0beefu),
              "Required output unwritten; refusing further device work");
    }
    return bytes;
  }
};

static void Save(const std::string& name, const std::vector<std::uint8_t>& bytes) {
  std::ofstream f("results/" + name + ".bin", std::ios::binary);
  f.write(reinterpret_cast<const char*>(bytes.data()), bytes.size());
  Require(bool(f), "Failed to preserve changed output");
}

struct CaseInputs {
  unsigned n, used, stride, parts;
  std::size_t count, prefix;
  std::array<std::unique_ptr<Device>, 3> experts;
  std::array<std::string, 3> expert_hash;
  Device residual_input, weights, shared, gate, inject, gamma, expanded;
  std::array<std::string, 6> input_hash;
  Output residual, scales, norm;
  CaseInputs(unsigned tokens, unsigned top, unsigned gate_stride,
             unsigned injection_parts, std::size_t offset, hipStream_t stream)
      : n(tokens), used(top), stride(gate_stride), parts(injection_parts),
        count(std::size_t(n) * used * 2560), prefix(offset),
        residual_input(std::size_t(n) * 10240 * 4), weights(std::size_t(n) * used * 4),
        shared(std::size_t(n) * 2560 * 4), gate(std::size_t(n) * stride * 4),
        inject(std::size_t(n) * 4 * parts * 4), gamma(10240 * 4), expanded(count * 4),
        residual(std::size_t(n) * 10240, false), scales(std::size_t(n) * 4, false),
        norm(std::size_t(n) * 10240, true) {
    Random rng;
    unsigned index = 0;
    for (Device* d : {&residual_input, &weights, &shared, &gate, &inject, &gamma}) {
      std::vector<float> values(d->bytes / 4);
      for (std::size_t i = 0; i < values.size(); ++i) {
        const float unit = float(rng.Next() >> 8) / 16777216.0f;
        values[i] = d == &gamma ? 0.5f + unit : d == &weights ? unit / used : (unit - 0.5f) * 0.5f;
        if (i % 113 == 0 && d != &gamma) values[i] = -0.0f;
      }
      Upload(*d, values, stream);
      input_hash[index++] = Hash(Read(*d, stream));
    }
    for (unsigned rotation = 0; rotation < 3; ++rotation) {
      // The allocation ends at the final valid half: no readable trailing pad.
      std::vector<std::uint8_t> bytes(prefix + count * 2, 0xa5);
      for (std::size_t i = 0; i < count; ++i) {
        const float unit = float(int(rng.Next() >> 16) - 32768) / 32768.0f;
        float value = unit * 4.0f;
        if (i % 257 == 0) value = -0.0f;
        else if (i % 263 == 0) value = std::ldexp(1.0f, -24);
        else if (i % 269 == 0) value = -std::ldexp(1.0f, -14);
        else if (i % 271 == 0) value = (i % 2 ? -1.0f : 1.0f) * 65504.0f;
        const __half half = __float2half_rn(value);
        std::memcpy(bytes.data() + prefix + i * 2, &half, 2);
      }
      experts[rotation] = std::make_unique<Device>(bytes.size());
      Upload(*experts[rotation], bytes, stream);
      expert_hash[rotation] = Hash(bytes);
    }
  }
  const __half* Expert(unsigned rotation) {
    return reinterpret_cast<const __half*>(static_cast<const std::uint8_t*>(experts[rotation]->data) + prefix);
  }
  void Expand(unsigned rotation, hipStream_t stream) {
    const auto bytes = Read(*experts[rotation], stream);
    std::vector<float> values(count);
    for (std::size_t i = 0; i < count; ++i) {
      __half half;
      std::memcpy(&half, bytes.data() + prefix + i * 2, 2);
      values[i] = __half2float(half);
    }
    Upload(expanded, values, stream);
  }
  void Reset(hipStream_t stream) {
    residual.Poison(stream); scales.Poison(stream); norm.Poison(stream);
    Hip(hipMemcpyAsync(residual.Data(), residual_input.data, residual_input.bytes,
                      hipMemcpyDeviceToDevice, stream));
  }
  void Run(unsigned arm, unsigned rotation, hipStream_t stream) {
    auto* res = static_cast<float*>(residual.Data());
    const auto* w = static_cast<const float*>(weights.data);
    const auto* sh = static_cast<const float*>(shared.data);
    const auto* g = static_cast<const float*>(gate.data);
    const auto* inj = static_cast<const float*>(inject.data);
    const auto* gm = static_cast<const float*>(gamma.data);
    auto* sc = static_cast<float*>(scales.Data());
    auto* nh = static_cast<__half*>(norm.Data());
    if (arm == 0) {
      hipLaunchKernelGGL(q::HcCombineMoeHalfEightControlKernel, dim3(n), dim3(256),
          0, stream, res, Expert(rotation), w, sh, g, stride, used, inj, parts,
          gm, sc, 2560, 1.0e-6f, nh);
      Hip(hipGetLastError());
    } else if (arm == 1) {
      Require(q::HcCombineMoeHalfDeferredNorm(res, Expert(rotation), w, sh, g,
          stride, used, inj, parts, gm, sc, n, 2560, 4, 1.0e-6f, stream, nh),
          "Candidate dispatch refused");
    } else {
      Require(q::HcCombineMoeDeferredNorm(res, static_cast<const float*>(expanded.data),
          w, sh, g, stride, used, inj, parts, gm, sc, n, 2560, 4, 1.0e-6f, stream, nh),
          "Expanded F32 dispatch refused");
    }
  }
  std::array<std::vector<std::uint8_t>, 3> ReadAll(hipStream_t stream) {
    return {residual.Checked(stream), scales.Checked(stream), norm.Checked(stream)};
  }
  void Unchanged(hipStream_t stream) {
    for (unsigned r = 0; r < 3; ++r)
      Require(Hash(Read(*experts[r], stream)) == expert_hash[r], "Expert input changed");
    unsigned index = 0;
    for (Device* d : {&residual_input, &weights, &shared, &gate, &inject, &gamma})
      Require(Hash(Read(*d, stream)) == input_hash[index++], "Consumer input changed");
  }
};

static std::size_t Nonfinite(const std::array<std::vector<std::uint8_t>, 3>& all) {
  std::size_t count = 0;
  for (unsigned k = 0; k < 3; ++k) {
    const unsigned step = k == 2 ? 2 : 4;
    for (std::size_t i = 64; i < all[k].size() - 64; i += step) {
      float value;
      if (k == 2) {
        __half half; std::memcpy(&half, all[k].data() + i, 2); value = __half2float(half);
      } else std::memcpy(&value, all[k].data() + i, 4);
      count += !std::isfinite(value);
    }
  }
  return count;
}

static bool Case(unsigned n, unsigned used, std::size_t prefix, bool timing,
                 hipStream_t stream) {
  const std::string name = "n" + std::to_string(n) + "-u" + std::to_string(used) +
                           "-p" + std::to_string(prefix);
  const unsigned stride = prefix == 64 ? 1 : 5;
  const unsigned parts = n == 16 ? 1 : n == 17 ? 3 : 10;
  CaseInputs in(n, used, stride, parts, prefix, stream);
  bool pass = true;
  for (unsigned rotation = 0; rotation < 3; ++rotation) {
    in.Expand(rotation, stream);
    in.Reset(stream); in.Run(0, rotation, stream); const auto parent = in.ReadAll(stream);
    in.Reset(stream); in.Run(2, rotation, stream); const auto expanded = in.ReadAll(stream);
    in.Reset(stream); in.Run(1, rotation, stream); const auto candidate = in.ReadAll(stream);
    const bool exact = parent == candidate, expanded_exact = expanded == candidate;
    const auto nonfinite = Nonfinite(parent) + Nonfinite(expanded) + Nonfinite(candidate);
    pass = pass && exact && expanded_exact && nonfinite == 0;
    std::cout << "{\"event\":\"half_consumer_eight_replay\",\"case\":\"" << name
              << "\",\"rotation\":" << rotation << ",\"n\":" << n << ",\"used\":" << used
              << ",\"prefix\":" << prefix << ",\"gate_stride\":" << stride
              << ",\"inject_parts\":" << parts << ",\"parent_exact\":" << exact
              << ",\"expanded_half_exact\":" << expanded_exact << ",\"nonfinite_values\":" << nonfinite
              << ",\"guards_exact\":true,\"all_written\":true,\"output_sha256\":[";
    for (unsigned k = 0; k < 3; ++k) {
      if (k) std::cout << ',';
      std::cout << "{\"parent\":\"" << Hash(parent[k]) << "\",\"candidate\":\"" << Hash(candidate[k])
                << "\",\"expanded\":\"" << Hash(expanded[k]) << "\"}";
      if (!exact || !expanded_exact || nonfinite) {
        const auto file = name + "-r" + std::to_string(rotation) + "-o" + std::to_string(k);
        Save(file + "-parent", parent[k]); Save(file + "-expanded", expanded[k]);
        Save(file + "-candidate", candidate[k]);
      }
    }
    std::cout << "]}\n";
  }
  if (timing) {
    Require(in.count * 2 * 3 > 32u * 1024 * 1024, "Rotation fits hardware cache");
    hipEvent_t begin{}, end{};
    Hip(hipEventCreate(&begin)); Hip(hipEventCreate(&end));
    for (unsigned rep = 0; rep < 7; ++rep)
      for (unsigned order = 0; order < 2; ++order) {
        const unsigned arm = (rep + order) % 2;
        in.Reset(stream); Hip(hipStreamSynchronize(stream));
        Hip(hipEventRecord(begin, stream));
        for (unsigned rotation = 0; rotation < 3; ++rotation) in.Run(arm, rotation, stream);
        Hip(hipEventRecord(end, stream)); Hip(hipEventSynchronize(end));
        float ms = 0; Hip(hipEventElapsedTime(&ms, begin, end));
        std::cout << "{\"event\":\"half_consumer_eight_timing\",\"case\":\"" << name
                  << "\",\"rep\":" << rep << ",\"order\":" << order
                  << ",\"candidate\":" << bool(arm) << ",\"warmup\":" << (rep < 2)
                  << ",\"input_rotation_bytes\":" << in.count * 2 * 3
                  << ",\"iterations\":3,\"us_per_iteration\":" << double(ms) * 1000 / 3 << "}\n";
        Require(Nonfinite(in.ReadAll(stream)) == 0, "Nonfinite timed consumer output");
      }
    Hip(hipEventDestroy(end)); Hip(hipEventDestroy(begin));
  }
  in.Unchanged(stream);
  std::cout << "{\"event\":\"half_consumer_eight_immutable\",\"case\":\"" << name << "\",\"inputs_exact\":true}\n";
  return pass;
}

int main() {
  try {
    std::cout << std::boolalpha << std::defaultfloat << std::setprecision(12);
    hipStream_t stream{}; Hip(hipStreamCreateWithFlags(&stream, hipStreamNonBlocking));
    bool pass = true;
    for (unsigned n : {16u, 17u, 33u, 129u})
      for (unsigned used : {1u, 2u, 10u, 32u})
        for (std::size_t prefix : {64u, 68u})
          pass = Case(n, used, prefix, false, stream) && pass;
    for (unsigned used : {2u, 10u, 32u})
      pass = Case(2048, used, 64, true, stream) && pass;
    Hip(hipStreamSynchronize(stream)); Hip(hipStreamDestroy(stream));
    std::cout << "{\"event\":\"half_consumer_eight_complete\",\"numerical_pass\":" << pass
              << ",\"timing_retained\":true,\"model_inference\":false}\n";
    return pass ? 0 : 1;
  } catch (const std::exception& error) {
    std::cerr << "FAIL: " << error.what() << '\n';
    return 1;
  }
}
