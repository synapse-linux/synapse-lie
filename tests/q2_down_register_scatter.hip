// SPDX-License-Identifier: MIT
// Q2 register scatter versus literal retained1574 LDS vector scatter.
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
#include "experiments/q2-down-register-scatter-pair-control.inc"
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
      inverse[i] = std::ldexp(1.0f, int(i % 23) - 30);
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

// Independent integer IEEE-754 binary32 -> binary16, round to nearest/even.
static std::uint16_t RoundHalf(float value) {
  const auto bits = std::bit_cast<std::uint32_t>(value);
  const auto sign = std::uint16_t((bits >> 16) & 0x8000u);
  const unsigned exponent = (bits >> 23) & 255u;
  const unsigned fraction = bits & 0x7fffffu;
  if (exponent == 255)
    return sign | (fraction ? 0x7e00u : 0x7c00u);
  if (exponent > 142)
    return sign | 0x7c00u;
  if (exponent < 102)
    return sign;
  const unsigned mantissa = fraction | (exponent ? 0x800000u : 0u);
  const unsigned shift = exponent < 113 ? 126u - exponent : 13u;
  const unsigned lost = mantissa & ((1u << shift) - 1u);
  unsigned rounded = mantissa >> shift;
  const unsigned midpoint = 1u << (shift - 1);
  rounded += lost > midpoint || (lost == midpoint && (rounded & 1u));
  const unsigned encoded = exponent < 113 ? rounded : ((exponent - 113) << 10) + rounded;
  return sign | std::uint16_t(encoded);
}

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

static void LaunchDown(bool candidate, Inputs& in, Output& out, unsigned rotation,
                       hipStream_t stream) {
  const auto* x = static_cast<const __half*>(in.x.data);
  const auto* scale = static_cast<const float*>(in.scale.data);
  const auto* tiles = static_cast<const std::int32_t*>(in.td->data);
  const auto* bounds = static_cast<const std::int32_t*>(in.bd->data);
  const auto* slots = static_cast<const std::int32_t*>(in.sd->data);
  const bool ok = candidate
      ? q::RoutedQ2ScaledHalfGemm(in.weights[rotation]->data, x, scale, tiles,
            in.tiles.size(), in.width, bounds, slots, static_cast<__half*>(out.Data()),
            in.m, in.k, stream)
      : q::RoutedQ2ScaledGemm(in.weights[rotation]->data, x, scale, tiles,
            in.tiles.size(), in.width, bounds, slots, static_cast<float*>(out.Data()),
            in.m, in.k, stream);
  Require(ok, "Down dispatch refused");
}

template<int BN>
static void LaunchParentWidth(Inputs& in, Output& out, unsigned rotation,
                              hipStream_t stream) {
  hipLaunchKernelGGL(
      (q::RoutedQ2RegisterScatterControlKernel<q::WeightType::kQ2_K, 128, BN, 2,
                                      false, false, true>),
      dim3((in.m + 127) / 128, in.tiles.size()), dim3(256), 0, stream,
      in.weights[rotation]->data, static_cast<const __half*>(in.x.data),
      static_cast<const std::int32_t*>(in.td->data),
      static_cast<const std::int32_t*>(in.bd->data),
      static_cast<const std::int32_t*>(in.sd->data),
      static_cast<const std::int32_t*>(in.sd->data), nullptr,
      static_cast<float*>(out.Data()), nullptr, in.m, in.k, in.scale.data);
  Hip(hipGetLastError());
}
static void LaunchParent(Inputs& in, Output& out, unsigned rotation,
                         hipStream_t stream) {
  switch (in.width) {
    case 16: LaunchParentWidth<16>(in, out, rotation, stream); break;
    case 48: LaunchParentWidth<48>(in, out, rotation, stream); break;
    case 64: LaunchParentWidth<64>(in, out, rotation, stream); break;
    default: throw std::runtime_error("Invalid tile width");
  }
}

struct Combine {
  unsigned n, used;
  Device residual_input, weights, shared, gate, inject, gamma;
  Output residual, scales, norm;
  Combine(unsigned tokens, unsigned top, hipStream_t stream)
      : n(tokens), used(top), residual_input(std::size_t(n) * 10240 * 4),
        weights(std::size_t(n) * used * 4), shared(std::size_t(n) * 2560 * 4),
        gate(n * 4), inject(std::size_t(n) * 4 * 3 * 4), gamma(10240 * 4),
        residual(std::size_t(n) * 10240, false), scales(std::size_t(n) * 4, false),
        norm(std::size_t(n) * 10240, true) {
    Random rng;
    for (Device* d : {&residual_input, &weights, &shared, &gate, &inject, &gamma}) {
      std::vector<float> v(d->bytes / 4);
      for (auto& x : v) {
        const float unit = float(rng.Next() >> 8) / 16777216.0f;
        x = d == &gamma ? 0.5f + unit : d == &weights ? unit / used : (unit - 0.5f) * 0.5f;
      }
      Upload(*d, v, stream);
    }
  }
  void Reset(hipStream_t stream) {
    residual.Poison(stream); scales.Poison(stream); norm.Poison(stream);
    Hip(hipMemcpyAsync(residual.Data(), residual_input.data, residual_input.bytes,
                       hipMemcpyDeviceToDevice, stream));
  }
  void Run(Output& down, hipStream_t stream) {
    const bool ok = down.half
      ? q::HcCombineMoeHalfDeferredNorm(static_cast<float*>(residual.Data()),
          static_cast<const __half*>(down.Data()), static_cast<const float*>(weights.data),
          static_cast<const float*>(shared.data), static_cast<const float*>(gate.data),
          1, used, static_cast<const float*>(inject.data), 3,
          static_cast<const float*>(gamma.data), static_cast<float*>(scales.Data()),
          n, 2560, 4, 1.0e-6f, stream, static_cast<__half*>(norm.Data()))
      : q::HcCombineMoeDeferredNorm(static_cast<float*>(residual.Data()),
          static_cast<const float*>(down.Data()), static_cast<const float*>(weights.data),
          static_cast<const float*>(shared.data), static_cast<const float*>(gate.data),
          1, used, static_cast<const float*>(inject.data), 3,
          static_cast<const float*>(gamma.data), static_cast<float*>(scales.Data()),
          n, 2560, 4, 1.0e-6f, stream, static_cast<__half*>(norm.Data()));
    Require(ok, "Combine dispatch refused");
  }
  std::array<std::vector<std::uint8_t>, 3> ReadAll(hipStream_t stream) {
    return {residual.Checked(stream), scales.Checked(stream), norm.Checked(stream)};
  }
};

static void Save(const std::string& name, const std::vector<std::uint8_t>& bytes) {
  std::ofstream f("results/" + name + ".bin", std::ios::binary);
  f.write(reinterpret_cast<const char*>(bytes.data()), bytes.size());
  Require(bool(f), "Failed to preserve changed output");
}

static bool Case(const std::string& label, unsigned n, unsigned m, unsigned experts,
                 unsigned used, unsigned width, bool timing, hipStream_t stream,
                 std::size_t prefix = 64) {
  Inputs in(n, m, 640, experts, used, width, stream);
  const std::size_t count = std::size_t(n) * used * m;
  Output reference(count, false), retained(count, true, prefix), candidate(count, true, prefix), expanded(count, false);
  std::unique_ptr<Combine> combine;
  if (m == 2560 && n >= 16)
    combine = std::make_unique<Combine>(n, used, stream);
  bool pass = true;
  for (unsigned rotation = 0; rotation < 3; ++rotation) {
    reference.Poison(stream); retained.Poison(stream); candidate.Poison(stream); expanded.Poison(stream);
    LaunchDown(false, in, reference, rotation, stream);
    LaunchParent(in, retained, rotation, stream);
    LaunchDown(true, in, candidate, rotation, stream);
    const auto a = reference.Checked(stream), b = candidate.Checked(stream), p = retained.Checked(stream);
    const bool parent_exact = p == b;
    std::vector<float> rounded(count);
    std::size_t mismatch = 0, changed = 0, nonfinite = 0;
    double sum_error = 0, sum_reference = 0, max_abs = 0;
    for (std::size_t i = 0; i < count; ++i) {
      float v; std::uint16_t got;
      std::memcpy(&v, a.data() + 64 + i * 4, 4);
      std::memcpy(&got, b.data() + candidate.offset + i * 2, 2);
      const auto expected = RoundHalf(v);
      rounded[i] = __half2float(std::bit_cast<__half>(expected));
      const float actual = __half2float(std::bit_cast<__half>(got));
      mismatch += expected != got;
      changed += v != actual;
      nonfinite += !std::isfinite(v) || !std::isfinite(actual);
      const double delta = double(v) - actual;
      sum_error += delta * delta; sum_reference += double(v) * v;
      max_abs = std::max(max_abs, std::abs(delta));
    }
    const bool exact_rounding = !mismatch && !nonfinite;
    pass = pass && exact_rounding && parent_exact;
    std::cout << "{\"event\":\"down_register_scatter_replay\",\"case\":\"" << label
              << "\",\"rotation\":" << rotation << ",\"values\":" << count
              << ",\"parent_exact\":" << parent_exact << ",\"retained_parent_sha256\":\"" << Hash(p) << "\""
              << ",\"rounding_mismatches\":" << mismatch << ",\"changed_parent_values\":" << changed
              << ",\"nonfinite_values\":" << nonfinite << ",\"max_abs\":" << max_abs
              << ",\"relative_l2\":" << std::sqrt(sum_error / std::max(sum_reference, 1.0e-300))
              << ",\"guards_exact\":true,\"all_written\":true,\"rounding_exact\":" << exact_rounding
              << ",\"reference_sha256\":\"" << Hash(a) << "\",\"candidate_sha256\":\"" << Hash(b)
              << "\",\"weight_sha256\":\"" << in.weight_hash[rotation] << "\"}\n";
    if (!exact_rounding || !parent_exact) {
      Save(label + "-" + std::to_string(rotation) + "-retained-parent", p);
      Save(label + "-" + std::to_string(rotation) + "-reference", a);
      Save(label + "-" + std::to_string(rotation) + "-candidate", b);
    }
    if (combine) {
      Hip(hipMemcpyAsync(expanded.Data(), rounded.data(), count * 4, hipMemcpyHostToDevice, stream));
      combine->Reset(stream); combine->Run(retained, stream);
      const auto parent = combine->ReadAll(stream);
      combine->Reset(stream); combine->Run(expanded, stream);
      const auto expected = combine->ReadAll(stream);
      combine->Reset(stream); combine->Run(candidate, stream);
      const auto actual = combine->ReadAll(stream);
      const bool same = expected == actual;
      pass = pass && same && parent == actual;
      std::cout << "{\"event\":\"down_register_scatter_consumer\",\"case\":\"" << label
                << "\",\"rotation\":" << rotation << ",\"expanded_half_exact\":" << same
                << ",\"parent_exact\":" << (parent == actual) << ",\"guards_exact\":true,\"all_written\":true}\n";
      if (!same || parent != actual) {
        for (unsigned k = 0; k < 3; ++k) {
          const auto prefix = label + "-" + std::to_string(rotation) + "-consumer-" + std::to_string(k);
          Save(prefix + "-expected", expected[k]); Save(prefix + "-candidate", actual[k]); Save(prefix + "-parent", parent[k]);
        }
      }
    }
  }
  if (timing) {
    Require(combine && in.encoded.size() * 3 > 32u * 1024 * 1024, "Incomplete timing shape");
    hipEvent_t begin{}, end{};
    Hip(hipEventCreate(&begin)); Hip(hipEventCreate(&end));
    for (unsigned cycle = 0; cycle < 2; ++cycle)
      for (unsigned rep = 0; rep < 7; ++rep)
        for (unsigned order = 0; order < 2; ++order) {
          const bool candidate_arm = (rep + order) % 2;
          auto& output = candidate_arm ? candidate : retained;
          combine->Reset(stream); Hip(hipStreamSynchronize(stream));
          Hip(hipEventRecord(begin, stream));
          for (unsigned rotation = 0; rotation < 3; ++rotation) {
            if (candidate_arm) LaunchDown(true, in, output, rotation, stream);
            else LaunchParent(in, output, rotation, stream);
            if (cycle) combine->Run(output, stream);
          }
          Hip(hipEventRecord(end, stream)); Hip(hipEventSynchronize(end));
          float ms = 0; Hip(hipEventElapsedTime(&ms, begin, end));
          std::cout << "{\"event\":\"down_register_scatter_timing\",\"case\":\"" << label
                    << "\",\"scope\":\"" << (cycle ? "down-combine" : "down")
                    << "\",\"rep\":" << rep << ",\"order\":" << order
                    << ",\"candidate\":" << candidate_arm << ",\"warmup\":" << (rep < 2)
                    << ",\"weight_bytes\":" << in.encoded.size() * 3
                    << ",\"iterations\":3,\"us_per_iteration\":" << double(ms) * 1000 / 3 << "}\n";
        }
    Hip(hipEventDestroy(end)); Hip(hipEventDestroy(begin));
  }
  in.Unchanged(stream);
  return pass;
}

int main() {
  try {
    std::cout << std::boolalpha << std::defaultfloat << std::setprecision(12);
    Require(RoundHalf(1.0f) == 0x3c00u && RoundHalf(-0.0f) == 0x8000u &&
            RoundHalf(65504.0f) == 0x7bffu && RoundHalf(65520.0f) == 0x7c00u &&
            RoundHalf(std::ldexp(1.0f, -24)) == 1u &&
            RoundHalf(std::ldexp(1.0f, -25)) == 0u,
            "Independent RN-even boundary check failed");
    hipStream_t stream{};
    Hip(hipStreamCreateWithFlags(&stream, hipStreamNonBlocking));
    bool pass = true;
    for (unsigned width : {16u, 48u, 64u})
      for (unsigned n : {1u, 15u, 16u, 17u, 47u, 48u, 49u, 63u, 64u, 65u, 129u})
        for (unsigned m : {1u, 2u, 8u, 24u, 128u, 129u, 2560u})
          pass = Case("edge-w" + std::to_string(width) + "-n" + std::to_string(n) +
                      "-m" + std::to_string(m), n, m, 1, 1, width, false, stream) && pass;
    for (unsigned width : {16u, 48u, 64u})
      pass = Case("unaligned4-w" + std::to_string(width), 17, 2560,
                  1, 1, width, false, stream, 68) && pass;
    // One production distribution: the actual fixed-point BN48/512-expert path.
    // Other widths retain numerical edge coverage without redundant timing sweeps.
    pass = Case("mixed-w48-e512", 2048, 2560, 512, 10, 48,
                true, stream) && pass;
    Hip(hipStreamSynchronize(stream)); Hip(hipStreamDestroy(stream));
    std::cout << "{\"event\":\"down_register_scatter_complete\",\"numerical_pass\":" << pass
              << ",\"timing_retained\":true,\"model_inference\":false}\n";
    return pass ? 0 : 1;
  } catch (const std::exception& error) {
    std::cerr << "FAIL: " << error.what() << '\n';
    return 2;
  }
}
