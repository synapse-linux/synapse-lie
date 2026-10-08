// SPDX-License-Identifier: MIT
// Component-only shared-down mirror. Synthetic operators; no model executor.
#include <algorithm>
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
namespace q = gufo::models::qwen38_flash_next::rocm;

static void Require(bool condition, const char* message) {
  if (!condition)
    throw std::runtime_error(message);
}
static void Hip(hipError_t value) {
  if (value != hipSuccess)
    throw std::runtime_error(hipGetErrorString(value));
}
struct Device {
  void* storage{};
  void* data{};
  std::size_t bytes{};
  static constexpr std::size_t guard = 64;
  explicit Device(std::size_t size) : bytes(size) {
    Hip(hipMalloc(&storage, bytes + 2 * guard));
    data = static_cast<std::uint8_t*>(storage) + guard;
  }
  void Guard(hipStream_t stream) {
    Hip(hipMemsetAsync(storage, 0xA7, guard, stream));
    Hip(hipMemsetAsync(static_cast<std::uint8_t*>(data) + bytes, 0xA7, guard,
                       stream));
  }
  void CheckGuards(hipStream_t stream) const {
    std::array<std::uint8_t, 2 * guard> got{};
    Hip(hipMemcpyAsync(got.data(), storage, guard, hipMemcpyDeviceToHost,
                       stream));
    Hip(hipMemcpyAsync(got.data() + guard,
                       static_cast<const std::uint8_t*>(data) + bytes, guard,
                       hipMemcpyDeviceToHost, stream));
    Hip(hipStreamSynchronize(stream));
    for (auto byte : got)
      Require(byte == 0xA7, "Corrupted device guard");
  }
  Device(const Device&) = delete;
  Device& operator=(const Device&) = delete;
  ~Device() {
    if (storage)
      (void)hipFree(storage);
  }
};
static std::string Hash(const std::vector<std::uint8_t>& bytes) {
  return gufo::crypto::Sha256Hex(bytes);
}
static std::vector<std::uint8_t> Read(const Device& buffer,
                                      hipStream_t stream) {
  buffer.CheckGuards(stream);
  std::vector<std::uint8_t> result(buffer.bytes);
  Hip(hipMemcpyAsync(result.data(), buffer.data, buffer.bytes,
                     hipMemcpyDeviceToHost, stream));
  Hip(hipStreamSynchronize(stream));
  return result;
}
template<class T>
static void Upload(Device& destination, const std::vector<T>& source,
                   hipStream_t stream) {
  Require(destination.bytes == source.size() * sizeof(T),
          "Invalid input byte count");
  destination.Guard(stream);
  Hip(hipMemcpyAsync(destination.data, source.data(), destination.bytes,
                     hipMemcpyHostToDevice, stream));
  Hip(hipStreamSynchronize(stream));
}
struct Random {
  std::uint32_t state{713};
  std::uint32_t Next() {
    state = state * 1664525u + 1013904223u;
    return state;
  }
  float Value() { return (float(int(Next() >> 16) - 32768)) / 32768.0f; }
};

// Independent integer binary16 product, retained from the qualified format
// fixture.
static std::uint16_t ExactProduct(std::uint16_t scale, int code) {
  const unsigned absolute = scale & 0x7FFFU;
  if (code == 0 || absolute == 0)
    return 0;
  const unsigned exp = absolute >> 10, frac = absolute & 1023U;
  unsigned magnitude =
      (exp ? 1024U + frac : frac) * unsigned(code < 0 ? -code : code);
  const unsigned sign = ((scale >> 15) ^ unsigned(code < 0)) << 15;
  const int exponent = exp ? int(exp) - 25 : -24;
  const unsigned top = 31U - unsigned(__builtin_clz(magnitude));
  int unbiased = int(top) + exponent;
  if (unbiased < -14)
    return std::uint16_t(sign | magnitude);
  unsigned mantissa;
  if (top <= 10)
    mantissa = magnitude << (10 - top);
  else {
    const unsigned shift = top - 10, mask = (1U << shift) - 1U;
    mantissa = magnitude >> shift;
    const unsigned remainder = magnitude & mask, halfway = 1U << (shift - 1);
    mantissa +=
        remainder > halfway || (remainder == halfway && (mantissa & 1U));
  }
  if (mantissa == 2048) {
    mantissa = 1024;
    ++unbiased;
  }
  Require(unbiased <= 15, "Format oracle overflow");
  return std::uint16_t(sign | unsigned(unbiased + 15) << 10 |
                       (mantissa & 1023U));
}

static void Save(const std::string& path,
                 const std::vector<std::uint8_t>& data) {
  std::ofstream file(path, std::ios::binary);
  Require(bool(file), "Cannot retain rejected output");
  file.write(reinterpret_cast<const char*>(data.data()), data.size());
  Require(bool(file), "Cannot finish rejected output");
}
struct Inputs {
  static constexpr unsigned m = 2560, k = 640;
  unsigned n, rotations;
  std::vector<__half> activation;
  Device x;
  std::vector<std::unique_ptr<Device>> weights, mirrors;
  std::vector<std::string> weights_sha, mirrors_sha;
  bool format_pass{true};
  Inputs(unsigned rows, unsigned count, hipStream_t stream)
      : n(rows),
        rotations(count),
        activation(std::size_t(n) * k),
        x(activation.size() * 2) {
    Random rng;
    for (auto& a : activation)
      a = __float2half_rn(rng.Value() * .125f);
    Upload(x, activation, stream);
    for (unsigned r = 0; r < rotations; ++r) {
      std::vector<std::uint8_t> encoded(std::size_t(m) * k / 32 * 34);
      std::vector<std::uint16_t> expected(std::size_t(m) * k);
      for (std::size_t block = 0; block < expected.size() / 32; ++block) {
        const __half value = __float2half_rn(.002f + .0001f * r);
        std::uint16_t d = __builtin_bit_cast(std::uint16_t, value);
        if (block % 23 == 0)
          d = 0;
        if (block % 29 == 0)
          d = 1;
        if (block % 3 == 0)
          d |= 0x8000u;
        std::memcpy(encoded.data() + block * 34, &d, 2);
        for (unsigned c = 0; c < 32; ++c) {
          const auto bits = std::uint8_t(rng.Next() >> 24);
          encoded[block * 34 + 2 + c] = bits;
          const int code = bits < 128 ? int(bits) : int(bits) - 256;
          expected[block * 32 + c] = ExactProduct(d, code);
        }
      }
      weights.push_back(std::make_unique<Device>(encoded.size()));
      Upload(*weights.back(), encoded, stream);
      weights_sha.push_back(Hash(encoded));
      mirrors.push_back(std::make_unique<Device>(expected.size() * 2));
      auto& mirror = *mirrors.back();
      mirror.Guard(stream);
      Hip(hipMemsetAsync(mirror.data, 0xFF, mirror.bytes, stream));
      Require(q::ConvertQ8Mirror(weights.back()->data, mirror.data,
                                 expected.size(), stream),
              "Mirror conversion failed");
      const auto got = Read(mirror, stream);
      mirrors_sha.push_back(Hash(got));
      std::size_t changed = 0, unwritten = 0;
      for (std::size_t i = 0; i < expected.size(); ++i) {
        std::uint16_t value;
        std::memcpy(&value, got.data() + i * 2, 2);
        changed += value != expected[i];
        unwritten += value == 0xFFFFu;
      }
      std::cout << "{\"event\":\"shared_down_mirror_format\",\"tokens\":" << n
                << ",\"rotation\":" << r << ",\"values\":" << expected.size()
                << ",\"changed\":" << changed << ",\"unwritten\":" << unwritten
                << ",\"guards_exact\":true,\"pass\":" << (changed == 0)
                << "}\n";
      if (changed) {
        const std::string stem = "results/shared-down-mirror-" +
                                 std::to_string(n) + "-" + std::to_string(r);
        Save(stem + "-weights.bin", encoded);
        Save(stem + "-mirror.bin", got);
      }
      Require(unwritten == 0, "Mirror contains missing stores");
      format_pass = changed == 0 && format_pass;
    }
  }
  void Unchanged(hipStream_t stream) const {
    const auto got = Read(x, stream);
    Require(std::memcmp(got.data(), activation.data(), got.size()) == 0,
            "Activations changed");
    for (unsigned r = 0; r < rotations; ++r) {
      Require(Hash(Read(*weights[r], stream)) == weights_sha[r],
              "Weights changed");
      Require(Hash(Read(*mirrors[r], stream)) == mirrors_sha[r],
              "Mirror changed");
    }
  }
};
static constexpr std::array<const char*, 4> kArms{"original-q8", "generic-f16",
                                                  "fixed-q8", "fixed-f16"};
static void Launch(unsigned arm, const Inputs& in, Device& out, unsigned r,
                   hipStream_t stream) {
  const std::array calls{q::DenseF16Gemm, q::SharedDownMirrorGemm,
                         q::SharedDownFixedQ8Gemm, q::SharedDownFixedF16Gemm};
  const auto call = calls.at(arm);
  const bool mirror = (arm & 1u) != 0;
  const void* weights = mirror ? in.mirrors[r]->data : in.weights[r]->data;
  Require(call(weights, static_cast<const __half*>(in.x.data),
               static_cast<float*>(out.data), in.n, in.m, in.k, stream),
          "Shared-down launch refused");
  Hip(hipGetLastError());
}
static bool Oracle(const Inputs& in, unsigned r,
                   const std::vector<std::uint8_t>& out, const char* arm,
                   hipStream_t stream) {
  const auto weights = Read(*in.weights[r], stream);
  double squared = 0, reference_squared = 0, peak = 0, reference_peak = 0;
  bool finite = true;
  for (unsigned sample = 0; sample < 24; ++sample) {
    const unsigned token = sample % 3 == 0 ? in.n - 1 : (sample * 127u) % in.n;
    const unsigned row = (sample * 431u) % in.m;
    double expected = 0;
    for (unsigned col = 0; col < in.k; ++col) {
      const auto offset = (std::size_t(row) * (in.k / 32) + col / 32) * 34;
      std::uint16_t scale;
      std::memcpy(&scale, weights.data() + offset, 2);
      const unsigned bits = weights[offset + 2 + col % 32];
      const int code = bits < 128 ? int(bits) : int(bits) - 256;
      const auto weight = __builtin_bit_cast(__half, ExactProduct(scale, code));
      expected +=
          double(__half2float(weight)) *
          double(__half2float(in.activation[std::size_t(token) * in.k + col]));
    }
    float value;
    std::memcpy(&value, out.data() + (std::size_t(token) * in.m + row) * 4, 4);
    finite = finite && std::isfinite(value) && std::isfinite(expected);
    const double delta = double(value) - expected;
    squared += delta * delta;
    reference_squared += expected * expected;
    peak = std::max(peak, std::abs(delta));
    reference_peak = std::max(reference_peak, std::abs(expected));
  }
  const double relative =
      std::sqrt(squared / std::max(reference_squared, 1e-24));
  const double scaled = peak / std::max(reference_peak, 1e-12);
  const bool pass = finite && relative <= .002 && scaled <= .002;
  std::cout << "{\"event\":\"shared_down_mirror_oracle\",\"tokens\":" << in.n
            << ",\"rotation\":" << r << ",\"arm\":\"" << arm
            << "\",\"samples\":24,\"finite\":" << finite
            << ",\"relative_rms\":";
  if (std::isfinite(relative))
    std::cout << relative;
  else
    std::cout << "null";
  std::cout << ",\"scaled_error\":";
  if (std::isfinite(scaled))
    std::cout << scaled;
  else
    std::cout << "null";
  std::cout << ",\"limit\":0.002,\"pass\":" << pass << "}\n";
  return pass;
}
static bool Case(unsigned n, hipStream_t stream) {
  const bool timed = n == 2048;
  Inputs in(n, timed ? 24 : 3, stream);
  Device reference(std::size_t(n) * in.m * 4), generic_half(reference.bytes),
      fixed_q8(reference.bytes), fixed_half(reference.bytes);
  const std::array<Device*, 4> outputs{&reference, &generic_half, &fixed_q8,
                                       &fixed_half};
  bool pass = in.format_pass;
  std::array<std::string, 4> last;
  for (unsigned r = 0; r < in.rotations; ++r) {
    for (Device* out : outputs) {
      out->Guard(stream);
      Hip(hipMemsetAsync(out->data, 0xFF, out->bytes, stream));
    }
    for (unsigned arm = 0; arm < outputs.size(); ++arm)
      Launch(arm, in, *outputs[arm], r, stream);
    const auto a = Read(reference, stream);
    last[0] = Hash(a);
    const bool reference_oracle = Oracle(in, r, a, kArms[0], stream);
    for (unsigned arm = 1; arm < outputs.size(); ++arm) {
      const auto b = Read(*outputs[arm], stream);
      last[arm] = Hash(b);
      std::size_t changed = 0, unwritten = 0, nonfinite = 0;
      for (std::size_t offset = 0; offset < a.size(); offset += 4) {
        std::uint32_t ia, ib;
        std::memcpy(&ia, a.data() + offset, 4);
        std::memcpy(&ib, b.data() + offset, 4);
        changed += ia != ib;
        unwritten += ia == 0xFFFFFFFFu || ib == 0xFFFFFFFFu;
        nonfinite += !std::isfinite(__builtin_bit_cast(float, ia)) ||
                     !std::isfinite(__builtin_bit_cast(float, ib));
      }
      const bool exact = changed == 0 && unwritten == 0 && nonfinite == 0;
      const bool candidate_oracle = Oracle(in, r, b, kArms[arm], stream);
      std::cout << "{\"event\":\"shared_down_mirror_pair\",\"tokens\":" << n
                << ",\"rotation\":" << r << ",\"arm\":\"" << kArms[arm]
                << "\",\"changed\":" << changed
                << ",\"unwritten\":" << unwritten
                << ",\"nonfinite\":" << nonfinite
                << ",\"guards_exact\":true,\"reference_sha256\":\"" << Hash(a)
                << "\",\"candidate_sha256\":\"" << Hash(b)
                << "\",\"exact\":" << exact << "}\n";
      if (!exact || !reference_oracle || !candidate_oracle) {
        const auto stem = "results/shared-down-mirror-" + std::to_string(n) +
                          "-" + std::to_string(r);
        Save(stem + "-reference.bin", a);
        Save(stem + "-" + kArms[arm] + ".bin", b);
      }
      Require(unwritten == 0, "Missing shared-down output store");
      pass = exact && reference_oracle && candidate_oracle && pass;
    }
  }
  if (timed) {
    const auto bytes = in.weights[0]->bytes * in.rotations;
    Require(bytes > 32u * 1024 * 1024, "Q8 rotation must exceed MALL");
    hipEvent_t start{}, end{};
    Hip(hipEventCreate(&start));
    Hip(hipEventCreate(&end));
    for (unsigned rep = 0; rep < 7; ++rep) {
      for (unsigned order = 0; order < outputs.size(); ++order) {
        const unsigned arm = (rep + order) % outputs.size();
        Hip(hipEventRecord(start, stream));
        for (unsigned r = 0; r < in.rotations; ++r)
          Launch(arm, in, *outputs[arm], r, stream);
        Hip(hipEventRecord(end, stream));
        Hip(hipEventSynchronize(end));
        float ms;
        Hip(hipEventElapsedTime(&ms, start, end));
        std::cout << "{\"event\":\"shared_down_mirror_timing\",\"tokens\":" << n
                  << ",\"rep\":" << rep << ",\"order\":" << order
                  << ",\"arm\":\"" << kArms[arm]
                  << "\",\"warmup\":" << (rep < 2)
                  << ",\"iterations\":" << in.rotations
                  << ",\"q8_weight_bytes\":" << bytes
                  << ",\"mirror_weight_bytes\":"
                  << in.mirrors[0]->bytes * in.rotations
                  << ",\"us_per_iteration\":"
                  << double(ms) * 1000 / in.rotations << "}\n";
      }
    }
    Hip(hipEventDestroy(end));
    Hip(hipEventDestroy(start));
    for (unsigned arm = 0; arm < outputs.size(); ++arm)
      Require(Hash(Read(*outputs[arm], stream)) == last[arm],
              "Timing output changed from numerical replay");
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
    for (unsigned n : {96u, 97u, 127u, 129u, 1025u, 2048u, 2049u})
      pass = Case(n, stream) && pass;
    Hip(hipStreamSynchronize(stream));
    Hip(hipStreamDestroy(stream));
    std::cout
        << "{\"event\":\"shared_down_mirror_complete\",\"numerical_pass\":"
        << pass << ",\"timing_retained\":true,\"model_inference\":false}\n";
    return pass ? 0 : 1;
  } catch (const std::exception& ex) {
    std::cerr << "FAIL: " << ex.what() << '\n';
    return 2;
  }
}
