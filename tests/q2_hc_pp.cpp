// SPDX-License-Identifier: MIT
// Synthetic HC prefill matrices with an independent sampled FP64 oracle.
// No original model weights or CPU model forward are used.
#include <hip/hip_fp16.h>
#include <hip/hip_runtime.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <set>
#include <span>
#include <stdexcept>
#include <string>
#include <vector>

#include "src/core/crypto/sha256.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/blaslt.hpp"

namespace rocm = gufo::models::qwen38_flash_next::rocm;
static void Require(bool ok, const char *reason) {
  if (!ok)
    throw std::runtime_error(reason);
}
static void Hip(hipError_t status) {
  Require(status == hipSuccess, hipGetErrorString(status));
}
struct Device {
  void *data{};
  explicit Device(std::size_t bytes) { Hip(hipMalloc(&data, bytes)); }
  ~Device() {
    if (data)
      (void)hipFree(data);
  }
  Device(const Device &) = delete;
  Device &operator=(const Device &) = delete;
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
static std::vector<__half> Values(std::size_t size, unsigned seed, float scale,
                                  bool alternating = false) {
  std::vector<__half> values(size);
  Random random{seed};
  for (std::size_t i = 0; i < size; ++i) {
    float v = random.Next();
    if (alternating)
      v = (i % 2 ? -1.0f : 1.0f) + v * 0.001f;
    values[i] = __float2half(v * scale);
  }
  return values;
}
static void Gemm(rocm::BlasLt &blas, const void *w, const void *x, void *y,
                 unsigned m, unsigned k, unsigned n) {
  std::string error;
  if (!blas.Gemm(w, x, static_cast<float *>(y), HIP_R_16F, m, n, k, &error))
    throw std::runtime_error(error);
  Hip(hipGetLastError());
}
static std::set<unsigned> Boundaries(unsigned size, unsigned tile) {
  std::set<unsigned> positions{0, size - 1};
  for (unsigned start = 0; start < size; start += tile)
    for (unsigned delta : {0, 1, 15, 16, 31, 32, 63, 64, 127})
      if (delta < tile && start + delta < size)
        positions.insert(start + delta);
  return positions;
}
static bool Case(rocm::BlasLt &blas, unsigned m, unsigned k, unsigned n,
                 unsigned pattern) {
  const auto w = Values(std::size_t(m) * k, 431 + pattern, 0.03125f);
  const auto x =
      Values(std::size_t(n) * k, 179 + pattern,
             pattern == 1 ? std::ldexp(1.0f, -12) : 1.0f, pattern == 2);
  const auto count = std::size_t(m) * n;
  constexpr std::size_t guard = 32;
  constexpr float sentinel = 123456.0f;
  std::vector<float> output(count + 2 * guard, sentinel);
  Device wd(w.size() * 2), xd(x.size() * 2), yd(output.size() * 4);
  Hip(hipMemcpy(wd.data, w.data(), w.size() * 2, hipMemcpyHostToDevice));
  Hip(hipMemcpy(xd.data, x.data(), x.size() * 2, hipMemcpyHostToDevice));
  Hip(hipMemcpy(yd.data, output.data(), output.size() * 4,
                hipMemcpyHostToDevice));
  Gemm(blas, wd.data, xd.data, static_cast<float *>(yd.data) + guard, m, k, n);
  Hip(hipDeviceSynchronize());
  Hip(hipMemcpy(output.data(), yd.data, output.size() * 4,
                hipMemcpyDeviceToHost));
  for (std::size_t i = 0; i < guard; ++i)
    Require(output[i] == sentinel && output[guard + count + i] == sentinel,
            "Output guard changed");
  for (std::size_t i = 0; i < count; ++i)
    Require(std::isfinite(output[guard + i]) && output[guard + i] != sentinel,
            "Non-finite or unwritten output");
  // Visit every macro-tile and WMMA boundaries, including ragged token tails.
  // Large matrices are sampled; the entire output is checked finite and hashed.
  const auto rows = Boundaries(m, m == 320 ? 64 : 128);
  const auto tokens = Boundaries(n, m == 320 ? 64 : 128);
  std::vector<float> samples;
  std::vector<std::uint32_t> coordinates;
  double error2 = 0, reference2 = 0, peak = 0, maximum = 0;
  for (unsigned t : tokens) {
    for (unsigned r : rows) {
      double expected = 0;
      for (unsigned j = 0; j < k; ++j)
        expected += double(__half2float(w[std::size_t(r) * k + j])) *
                    double(__half2float(x[std::size_t(t) * k + j]));
      const float value = output[guard + std::size_t(t) * m + r];
      const double delta = double(value) - expected;
      error2 += delta * delta;
      reference2 += expected * expected;
      peak = std::max(peak, std::abs(expected));
      maximum = std::max(maximum, std::abs(delta));
      samples.push_back(value);
      coordinates.push_back(t);
      coordinates.push_back(r);
    }
  }
  const double rrms = std::sqrt(error2 / std::max(reference2, 1e-60));
  const double scaled_max = maximum / std::max(peak, 1e-30);
  const auto label = std::to_string(m) + "x" + std::to_string(k) + "-n" +
                     std::to_string(n) + "-p" + std::to_string(pattern);
  const auto digest = gufo::crypto::Sha256Hex(
      std::span(reinterpret_cast<const std::uint8_t *>(output.data() + guard),
                count * 4));
  std::cout << std::scientific << std::setprecision(12)
            << "{\"event\":\"pp_operator\",\"label\":\"" << label
            << "\",\"values\":" << count
            << ",\"oracle_values\":" << samples.size()
            << ",\"relative_rms\":" << rrms
            << ",\"error_over_peak\":" << scaled_max
            << ",\"max_abs_error\":" << maximum << ",\"full_output_sha256\":\""
            << digest << "\"}\n";
  std::ofstream values("results/hc-pp-" + label + ".f32", std::ios::binary);
  values.write(reinterpret_cast<const char *>(samples.data()),
               samples.size() * 4);
  std::ofstream coords("results/hc-pp-" + label + ".u32", std::ios::binary);
  coords.write(reinterpret_cast<const char *>(coordinates.data()),
               coordinates.size() * 4);
  Require(bool(values) && bool(coords),
          "Cannot save sampled operator evidence");
  return rrms <= 0.00002 && scaled_max <= 0.00002;
}
static void Bench(rocm::BlasLt &blas, unsigned m, unsigned k) {
  constexpr unsigned n = 2048, matrices = 16, launches = 16;
  const auto matrix_bytes = std::size_t(m) * k * 2;
  Device wd(matrix_bytes * matrices), xd(std::size_t(n) * k * 2);
  Device yd(std::size_t(n) * m * 4);
  for (unsigned i = 0; i < matrices; ++i) {
    const auto w = Values(std::size_t(m) * k, 431 + i, 0.03125f);
    Hip(hipMemcpy(static_cast<char *>(wd.data) + i * matrix_bytes, w.data(),
                  matrix_bytes, hipMemcpyHostToDevice));
  }
  const auto x = Values(std::size_t(n) * k, 179, 1.0f);
  Hip(hipMemcpy(xd.data, x.data(), x.size() * 2, hipMemcpyHostToDevice));
  auto launch = [&](unsigned i) {
    Gemm(blas, static_cast<char *>(wd.data) + (i % matrices) * matrix_bytes,
         xd.data, yd.data, m, k, n);
  };
  for (unsigned i = 0; i < matrices; ++i)
    launch(i);
  Hip(hipDeviceSynchronize());
  hipEvent_t begin, end;
  Hip(hipEventCreate(&begin));
  Hip(hipEventCreate(&end));
  for (unsigned rep = 0; rep < 5; ++rep) {
    Hip(hipEventRecord(begin, nullptr));
    for (unsigned i = 0; i < launches; ++i)
      launch(i);
    Hip(hipEventRecord(end, nullptr));
    Hip(hipEventSynchronize(end));
    float milliseconds = 0;
    Hip(hipEventElapsedTime(&milliseconds, begin, end));
    std::vector<float> output(std::size_t(n) * m);
    Hip(hipMemcpy(output.data(), yd.data, output.size() * 4,
                  hipMemcpyDeviceToHost));
    double checksum = 0;
    for (float v : output) {
      Require(std::isfinite(v), "Non-finite microbenchmark output");
      checksum += v;
    }
    const double us = milliseconds * 1000.0 / launches;
    std::cout << std::scientific << std::setprecision(12)
              << "{\"event\":\"pp_microbench\",\"m\":" << m << ",\"k\":" << k
              << ",\"n\":" << n << ",\"rep\":" << rep
              << ",\"matrices\":" << matrices
              << ",\"weight_bytes\":" << matrix_bytes * matrices
              << ",\"launches\":" << launches << ",\"us_per_launch\":" << us
              << ",\"tflops\":" << 2.0 * m * n * k / (us * 1e6)
              << ",\"checksum\":" << checksum << "}\n";
  }
  Hip(hipEventDestroy(begin));
  Hip(hipEventDestroy(end));
}
int main(int argc, char **argv) {
  try {
    Require(argc == 2, "Usage: q2_hc_pp operators|bench");
    const std::string mode = argv[1];
    Require(mode == "operators" || mode == "bench", "Unsupported mode");
    std::cout << std::unitbuf << std::setprecision(12);
    Hip(hipSetDevice(0));
    std::string error;
    auto blas = rocm::BlasLt::Create(nullptr, &error);
    if (!blas)
      throw std::runtime_error(error);
    unsigned failures = 0;
    for (unsigned n : {32, 95, 96, 97, 127, 128, 129, 2048}) {
      failures += !Case(*blas, 320, 10240, n, 0);
      failures += !Case(*blas, 10240, 320, n, 0);
    }
    for (unsigned pattern : {1, 2}) {
      failures += !Case(*blas, 320, 10240, 129, pattern);
      failures += !Case(*blas, 10240, 320, 129, pattern);
    }
    failures += !Case(*blas, 319, 10240, 129, 0);
    failures += !Case(*blas, 320, 10208, 129, 0);
    std::cout << "{\"event\":\"pp_operator_summary\",\"cases\":22,\"numerical_"
                 "failures\":"
              << failures << "}\n";
    // The owner permits exploratory speed measurements before numerical fixes.
    // A numerical failure still produces exit1 after preserving the timings.
    if (mode == "bench") {
      Bench(*blas, 320, 10240);
      Bench(*blas, 10240, 320);
    }
    if (failures) {
      std::cerr << "Independent sampled F16 operator tolerance exceeded\n";
      return 1;
    }
    std::cout << "PASS synthetic HC prefill checks; no model inference\n";
  } catch (const std::exception &ex) {
    std::cerr << ex.what() << '\n';
    return 1;
  }
}
