// SPDX-License-Identifier: MIT
// Synthetic GPU HC projection/mixing checks; no CPU model forward.
#include <hip/hip_fp16.h>
#include <hip/hip_runtime.h>

#include <algorithm>
#include <bit>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hpp"

namespace q = gufo::models::qwen38_flash_next::rocm;
static void Require(bool value, const char *reason) {
  if (!value)
    throw std::runtime_error(reason);
}
static void Hip(hipError_t status) {
  Require(status == hipSuccess, hipGetErrorString(status));
}
struct Device {
  void *data{};
  explicit Device(std::size_t bytes) { Hip(hipMalloc(&data, bytes)); }
  ~Device() { (void)hipFree(data); }
  Device(const Device &) = delete;
  Device &operator=(const Device &) = delete;
};
template <typename T> struct Output {
  static constexpr std::size_t guard = 32;
  const std::size_t size;
  Device device;
  explicit Output(std::size_t count)
      : size(count), device((count + 2 * guard) * sizeof(T)) {
    Hip(hipMemset(device.data, 0xFF, (count + 2 * guard) * sizeof(T)));
  }
  T *Data() { return static_cast<T *>(device.data) + guard; }
  std::vector<T> Read(bool written = true) {
    std::vector<T> host(size + 2 * guard);
    Hip(hipMemcpy(host.data(), device.data, host.size() * sizeof(T),
                  hipMemcpyDeviceToHost));
    const auto *bytes = reinterpret_cast<const unsigned char *>(host.data());
    for (std::size_t i = 0; i < guard * sizeof(T); ++i)
      Require(bytes[i] == 0xFF && bytes[(guard + size) * sizeof(T) + i] == 0xFF,
              "Output guard changed");
    std::vector<T> result(host.begin() + guard, host.begin() + guard + size);
    if (written) {
      for (T value : result)
        Require(std::isfinite(float(value)), "Non-finite or unwritten output");
    } else {
      for (std::size_t i = 0; i < size * sizeof(T); ++i)
        Require(bytes[guard * sizeof(T) + i] == 0xFF,
                "Disabled output changed");
    }
    return result;
  }
};
struct Random {
  std::uint32_t state;
  float Next() {
    state ^= state << 13;
    state ^= state >> 17;
    state ^= state << 5;
    return (static_cast<int>(state % 2001) - 1000) / 997.0f;
  }
};
template <typename T>
static bool Exact(const std::vector<T> &a, const std::vector<T> &b) {
  return a.size() == b.size() &&
         std::memcmp(a.data(), b.data(), a.size() * sizeof(T)) == 0;
}
template <typename T>
static void Save(const std::string &name, const std::vector<T> &data) {
  std::ofstream file("results/" + name, std::ios::binary);
  file.write(reinterpret_cast<const char *>(data.data()),
             data.size() * sizeof(T));
  Require(bool(file), "Cannot save HC fusion evidence");
}
template <typename T>
static void Upload(Device &device, const std::vector<T> &data) {
  Hip(hipMemcpy(device.data, data.data(), data.size() * sizeof(T),
                hipMemcpyHostToDevice));
}
template <typename T>
static void CheckInput(const Device &device, const std::vector<T> &expected) {
  std::vector<T> actual(expected.size());
  Hip(hipMemcpy(actual.data(), device.data, actual.size() * sizeof(T),
                hipMemcpyDeviceToHost));
  Require(Exact(actual, expected), "Read-only input changed");
}
struct Error {
  double error2{}, expected2{}, peak{}, maximum{};
  std::size_t values{};
  void Add(double expected, float value) {
    Require(std::isfinite(value) && std::isfinite(expected), "Invalid oracle");
    const double delta = double(value) - expected;
    error2 += delta * delta;
    expected2 += expected * expected;
    peak = std::max(peak, std::abs(expected));
    maximum = std::max(maximum, std::abs(delta));
    ++values;
  }
  double Rms() const { return std::sqrt(error2 / std::max(expected2, 1e-60)); }
  double Scaled() const { return maximum / std::max(peak, 1e-30); }
  bool Pass() const { return Rms() <= 0.00002 && Scaled() <= 0.00002; }
};

static bool Case(unsigned tokens, unsigned pattern, bool injection,
                 bool half_output) {
  constexpr unsigned hidden = 2560, rank = 320, streams = 4;
  constexpr unsigned rows = hidden * streams;
  Random rng{197 + tokens + pattern};
  std::vector<__half> up(std::size_t(rows) * rank);
  std::vector<__half> low(std::size_t(tokens) * rank);
  std::vector<float> xn(std::size_t(tokens) * rows), inject_w(streams * rows);
  for (auto &value : up)
    value = __float2half_rn(rng.Next() * 0.03125f);
  for (auto &value : low)
    value = __float2half_rn(rng.Next() * (pattern == 1 ? 0x1p-18f : 1.0f));
  for (std::size_t i = 0; i < xn.size(); ++i) {
    const float value = rng.Next();
    xn[i] = pattern == 1   ? value * 0x1p-18f
            : pattern == 2 ? ((i / hidden) % 2 ? -1.0f : 1.0f) + value * .001f
                           : value;
  }
  // The original inject weights are F16 widened to F32 without loss.
  for (auto &value : inject_w)
    value = __half2float(__float2half_rn(rng.Next() * .03125f));
  const auto count = std::size_t(tokens) * hidden;
  const auto parts = q::HcInjectPartsVec4(hidden);
  Require(parts == (hidden + 1023) / 1024,
          "Unexpected inject partial geometry");
  const auto inject_count = std::size_t(tokens) * streams * parts;
  Device wd(up.size() * 2), ld(low.size() * 2), xd(xn.size() * 4);
  Device iw(inject_w.size() * 4), gates(std::size_t(tokens) * rows * 4);
  Upload(wd, up);
  Upload(ld, low);
  Upload(xd, xn);
  Upload(iw, inject_w);
  Output<float> ref(count), fused(count), ri(inject_count), fi(inject_count);
  Output<__half> rh(count), fh(count);
  const auto *weight = static_cast<const float *>(iw.data);
  const auto *norm = static_cast<const float *>(xd.data);
  const auto *input = static_cast<const __half *>(ld.data);
  Require(q::UnquantizedF16Gemm(wd.data, input,
                                static_cast<float *>(gates.data), tokens, rows,
                                rank, nullptr),
          "Reference HC up dispatch failed");
  q::HcMixEpilogueVec4(norm, static_cast<const float *>(gates.data),
                       injection ? weight : nullptr, ref.Data(),
                       injection ? ri.Data() : nullptr, tokens, hidden, streams,
                       nullptr);
  if (half_output)
    q::NarrowActivations(ref.Data(), rh.Data(), false, count, nullptr);
  Require(q::HcMixRawF16Gemm(wd.data, input, norm, injection ? weight : nullptr,
                             fused.Data(), half_output ? fh.Data() : nullptr,
                             injection ? fi.Data() : nullptr, tokens, hidden,
                             rank, nullptr),
          "Fused HC up dispatch failed");
  Hip(hipGetLastError());
  Hip(hipDeviceSynchronize());
  const auto a = ref.Read(), b = fused.Read();
  const auto ai = ri.Read(injection), bi = fi.Read(injection);
  const auto ah = rh.Read(half_output), bh = fh.Read(half_output);
  CheckInput(wd, up);
  CheckInput(ld, low);
  CheckInput(xd, xn);
  CheckInput(iw, inject_w);
  Error mix_error, inject_error;
  std::set<unsigned> sample_tokens{0, tokens - 1};
  for (unsigned t = 0; t < tokens; t += 128)
    for (unsigned delta : {0, 1, 15, 16, 31, 32, 63, 64, 95, 96, 127})
      if (t + delta < tokens)
        sample_tokens.insert(t + delta);
  std::set<unsigned> sample_hidden{0, hidden - 1};
  for (unsigned h = 0; h < hidden; h += 64)
    for (unsigned delta : {0, 1, 15, 16, 31, 32, 63})
      sample_hidden.insert(h + delta);
  for (unsigned t : sample_tokens) {
    for (unsigned h : sample_hidden) {
      double expected = 0;
      for (unsigned s = 0; s < streams; ++s) {
        const unsigned row = s * hidden + h;
        double gate = 0;
        for (unsigned k = 0; k < rank; ++k)
          gate += double(__half2float(up[std::size_t(row) * rank + k])) *
                  double(__half2float(low[std::size_t(t) * rank + k]));
        expected +=
            double(xn[std::size_t(t) * rows + row]) / (1.0 + std::exp(-gate));
      }
      mix_error.Add(expected * .25, b[std::size_t(t) * hidden + h]);
    }
    if (injection)
      for (unsigned o = 0; o < streams; ++o)
        for (unsigned part = 0; part < parts; ++part) {
          double expected = 0;
          for (unsigned s = 0; s < streams; ++s)
            for (unsigned h = part * 1024;
                 h < std::min(hidden, (part + 1) * 1024); ++h)
              expected +=
                  double(inject_w[std::size_t(o) * rows + s * hidden + h]) *
                  double(xn[std::size_t(t) * rows + s * hidden + h]);
          inject_error.Add(expected,
                           bi[(std::size_t(t) * streams + o) * parts + part]);
        }
  }
  const auto label =
      "hc-up-n" + std::to_string(tokens) + "-p" + std::to_string(pattern) +
      "-i" + std::to_string(injection) + "-h" + std::to_string(half_output);
  Save(label + "-reference.f32", a);
  Save(label + "-fused.f32", b);
  if (injection) {
    Save(label + "-reference-inject.f32", ai);
    Save(label + "-fused-inject.f32", bi);
  }
  if (half_output) {
    Save(label + "-reference.f16", ah);
    Save(label + "-fused.f16", bh);
  }
  const bool exact = Exact(a, b) && Exact(ai, bi) && Exact(ah, bh);
  const bool independent =
      mix_error.Pass() && (!injection || inject_error.Pass());
  std::cout << std::setprecision(12) << std::boolalpha
            << "{\"event\":\"hc_up_fused\",\"label\":\"" << label
            << "\",\"values\":" << count << ",\"exact_mixed\":" << Exact(a, b)
            << ",\"exact_inject\":" << Exact(ai, bi)
            << ",\"exact_half\":" << Exact(ah, bh)
            << ",\"mix_oracle_values\":" << mix_error.values
            << ",\"mix_rrms\":" << mix_error.Rms()
            << ",\"mix_scaled_max\":" << mix_error.Scaled()
            << ",\"inject_oracle_values\":" << inject_error.values
            << ",\"inject_rrms\":" << inject_error.Rms()
            << ",\"inject_scaled_max\":" << inject_error.Scaled()
            << ",\"independent_pass\":" << independent << "}\n";
  // Unsupported geometry/null pointers must refuse before any launch.
  Require(!q::HcMixRawF16Gemm(wd.data, input, norm, nullptr, fused.Data(),
                              nullptr, nullptr, 95, hidden, rank, nullptr),
          "Accepted short batch");
  Require(!q::HcMixRawF16Gemm(wd.data, input, norm, nullptr, fused.Data(),
                              nullptr, nullptr, tokens, 2564, rank, nullptr),
          "Accepted wrong width");
  Require(!q::HcMixRawF16Gemm(wd.data, input, norm, nullptr, fused.Data(),
                              nullptr, nullptr, tokens, hidden, 321, nullptr),
          "Accepted wrong rank");
  Require(!q::HcMixRawF16Gemm(nullptr, input, norm, nullptr, fused.Data(),
                              nullptr, nullptr, tokens, hidden, rank, nullptr),
          "Accepted null weights");
  Require(!q::HcMixRawF16Gemm(wd.data, input, norm, weight, fused.Data(),
                              nullptr, nullptr, tokens, hidden, rank, nullptr),
          "Accepted missing inject output");
  return exact && independent;
}

int main() {
  try {
    bool pass = true;
    pass = Case(96, 0, true, true) && pass;
    pass = Case(97, 1, true, true) && pass;
    pass = Case(129, 0, true, true) && pass;
    pass = Case(129, 2, true, true) && pass;
    pass = Case(129, 0, false, true) && pass;
    pass = Case(129, 0, true, false) && pass;
    pass = Case(2048, 0, true, true) && pass;
    std::cout << (pass ? "PASS" : "FAIL")
              << " synthetic HC up fusion; no model inference\n";
    return pass ? 0 : 1;
  } catch (const std::exception &error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
