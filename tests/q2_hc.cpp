// SPDX-License-Identifier: MIT
// Independent synthetic F16 dot products, not CPU model forward.
#include <hip/hip_fp16.h>
#include <hip/hip_runtime.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hpp"

namespace rocm = gufo::models::qwen38_flash_next::rocm;
static void Require(bool ok, const char *why) {
  if (!ok)
    throw std::runtime_error(why);
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
static std::vector<__half> Weights(unsigned m, unsigned k, unsigned seed) {
  Random rng{seed};
  std::vector<__half> w(std::size_t(m) * k);
  for (auto &v : w)
    v = __float2half(rng.Next() * 0.03125f);
  return w;
}
static void Case(unsigned m, unsigned k, unsigned tokens, unsigned pattern) {
  const auto w = Weights(m, k, 431 + pattern);
  std::vector<float> x(std::size_t(k) * tokens);
  Random rng{179 + pattern};
  for (std::size_t i = 0; i < x.size(); ++i) {
    const float v = rng.Next();
    x[i] = pattern == 1   ? std::ldexp(v, -18)
           : pattern == 2 ? (i % 2 ? -1.0f : 1.0f) + v * 0.001f
                          : v;
  }
  const std::size_t count = std::size_t(m) * tokens;
  constexpr std::size_t guard = 32;
  constexpr float sentinel = 123456.0f;
  std::vector<float> got(count + 2 * guard, sentinel);
  Device wd(w.size() * sizeof(__half)), xd(x.size() * sizeof(float));
  Device yd(got.size() * sizeof(float));
  Hip(hipMemcpy(wd.data, w.data(), w.size() * sizeof(__half),
                hipMemcpyHostToDevice));
  Hip(hipMemcpy(xd.data, x.data(), x.size() * sizeof(float),
                hipMemcpyHostToDevice));
  Hip(hipMemcpy(yd.data, got.data(), got.size() * sizeof(float),
                hipMemcpyHostToDevice));
  rocm::SmallGemm(wd.data, rocm::WeightType::kF16,
                  static_cast<const float *>(xd.data),
                  static_cast<float *>(yd.data) + guard, tokens, m, k, nullptr);
  Hip(hipGetLastError());
  Hip(hipDeviceSynchronize());
  Hip(hipMemcpy(got.data(), yd.data, got.size() * sizeof(float),
                hipMemcpyDeviceToHost));
  for (std::size_t i = 0; i < guard; ++i) {
    Require(got[i] == sentinel && got[count + guard + i] == sentinel,
            "Output guard changed");
  }
  double squared_error = 0, squared_ref = 0, peak = 0, maximum = 0;
  for (unsigned t = 0; t < tokens; ++t) {
    for (unsigned r = 0; r < m; ++r) {
      double expected = 0;
      for (unsigned j = 0; j < k; ++j)
        expected += double(__half2float(w[std::size_t(r) * k + j])) *
                    double(x[std::size_t(t) * k + j]);
      const float value = got[guard + std::size_t(t) * m + r];
      Require(std::isfinite(value), "Non-finite operator output");
      const double delta = double(value) - expected;
      squared_error += delta * delta;
      squared_ref += expected * expected;
      peak = std::max(peak, std::abs(expected));
      maximum = std::max(maximum, std::abs(delta));
    }
  }
  const double rrms = std::sqrt(squared_error / std::max(squared_ref, 1e-60));
  const double scaled_max = maximum / std::max(peak, 1e-30);
  const auto label = std::to_string(m) + "x" + std::to_string(k) + "-t" +
                     std::to_string(tokens) + "-p" + std::to_string(pattern);
  std::cout << "{\"event\":\"operator\",\"label\":\"" << label
            << "\",\"relative_rms\":" << rrms
            << ",\"error_over_peak\":" << scaled_max
            << ",\"max_abs_error\":" << maximum << "}\n";
  std::ofstream output("results/hc-" + label + ".f32", std::ios::binary);
  output.write(reinterpret_cast<const char *>(got.data() + guard),
               static_cast<std::streamsize>(count * sizeof(float)));
  Require(bool(output), "Cannot save operator frontier");
  Require(rrms <= 0.00002 && scaled_max <= 0.00002,
          "Independent F16 operator tolerance exceeded");
}

static void Bench(bool up) {
  const unsigned m = up ? 10240 : 320;
  const unsigned k = up ? 320 : 10240;
  constexpr unsigned matrices = 16, launches = 128;
  const std::size_t matrix_bytes = std::size_t(m) * k * sizeof(__half);
  // Match DeviceModel::Uploader::Copy: hipMalloc and original F16 layout.
  // Rotate 100 MiB of weights, exceeding the 32 MiB cache.
  Device wd(matrix_bytes * matrices), xd(k * sizeof(float)),
      yd(m * sizeof(float));
  for (unsigned i = 0; i < matrices; ++i) {
    const auto w = Weights(m, k, i + 431);
    Hip(hipMemcpy(static_cast<char *>(wd.data) + matrix_bytes * i, w.data(),
                  matrix_bytes, hipMemcpyHostToDevice));
  }
  std::vector<float> x(k);
  Random rng{179};
  for (auto &v : x)
    v = rng.Next();
  Hip(hipMemcpy(xd.data, x.data(), x.size() * sizeof(float),
                hipMemcpyHostToDevice));
  auto launch = [&](unsigned i) {
    rocm::SmallGemm(static_cast<char *>(wd.data) +
                        matrix_bytes * (i % matrices),
                    rocm::WeightType::kF16, static_cast<const float *>(xd.data),
                    static_cast<float *>(yd.data), 1, m, k, nullptr);
  };
  for (unsigned i = 0; i < matrices; ++i)
    launch(i);
  Hip(hipGetLastError());
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
    Hip(hipGetLastError());
    float milliseconds = 0;
    Hip(hipEventElapsedTime(&milliseconds, begin, end));
    std::vector<float> output(m);
    Hip(hipMemcpy(output.data(), yd.data, m * sizeof(float),
                  hipMemcpyDeviceToHost));
    double checksum = 0;
    for (float v : output) {
      Require(std::isfinite(v), "Non-finite microbenchmark output");
      checksum += v;
    }
    std::cout << "{\"event\":\"microbench\",\"rep\":" << rep
              << ",\"matrices\":" << matrices
              << ",\"weight_bytes\":" << matrix_bytes * matrices
              << ",\"launches\":" << launches
              << ",\"us_per_launch\":" << milliseconds * 1000.0 / launches
              << ",\"checksum\":" << checksum << "}\n";
  }
  Hip(hipEventDestroy(begin));
  Hip(hipEventDestroy(end));
}

int main(int argc, char **argv) {
  try {
    Require(argc == 2, "Usage: q2_hc operators|bench|bench-up");
    const std::string mode = argv[1];
    Require(mode == "operators" || mode == "bench" || mode == "bench-up",
            "Unsupported mode");
    std::cout << std::unitbuf << std::setprecision(12);
    Hip(hipSetDevice(0));
    for (unsigned pattern = 0; pattern < 3; ++pattern)
      Case(320, 10240, 1, pattern);
    for (unsigned tokens : {2, 3, 8, 9})
      Case(320, 10240, tokens, 0);
    Case(319, 10240, 1, 0);
    Case(320, 10239, 1, 0);
    Case(10240, 320, 1, 0);
    Case(512, 2560, 1, 0);
    if (mode == "bench" || mode == "bench-up")
      Bench(mode == "bench-up");
    std::cout << "PASS synthetic F16 HC checks; no model inference\n";
    return 0;
  } catch (const std::exception &ex) {
    std::cerr << ex.what() << '\n';
    return 1;
  }
}
