// SPDX-License-Identifier: MIT
// Synthetic HC prefill matrices with an independent sampled FP64 oracle.
// No original model weights or CPU model forward are used.
#include <hip/hip_fp16.h>
#include <hip/hip_runtime.h>
#include <hipblaslt/hipblaslt-ext.hpp>

#include <algorithm>
#include <array>
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

static void Blas(hipblasStatus_t status) {
  Require(status == HIPBLAS_STATUS_SUCCESS, "hipBLASLt operation failed");
}
struct LibraryPlan {
  hipblasLtHandle_t handle{};
  hipblasLtMatmulDesc_t operation{};
  hipblasLtMatrixLayout_t weights{}, input{}, output{};
  hipblasLtMatmulPreference_t preference{};
  LibraryPlan() = default;
  LibraryPlan(const LibraryPlan &) = delete;
  LibraryPlan &operator=(const LibraryPlan &) = delete;
  ~LibraryPlan() {
    if (preference)
      (void)hipblasLtMatmulPreferenceDestroy(preference);
    if (output)
      (void)hipblasLtMatrixLayoutDestroy(output);
    if (input)
      (void)hipblasLtMatrixLayoutDestroy(input);
    if (weights)
      (void)hipblasLtMatrixLayoutDestroy(weights);
    if (operation)
      (void)hipblasLtMatmulDescDestroy(operation);
    if (handle)
      (void)hipblasLtDestroy(handle);
  }
  void Init(unsigned m, unsigned k, unsigned n) {
    Blas(hipblasLtCreate(&handle));
    Blas(hipblasLtMatmulDescCreate(&operation, HIPBLAS_COMPUTE_32F, HIP_R_32F));
    const hipblasOperation_t transpose = HIPBLAS_OP_T, normal = HIPBLAS_OP_N;
    Blas(hipblasLtMatmulDescSetAttribute(operation,
                                         HIPBLASLT_MATMUL_DESC_TRANSA,
                                         &transpose, sizeof(transpose)));
    Blas(hipblasLtMatmulDescSetAttribute(
        operation, HIPBLASLT_MATMUL_DESC_TRANSB, &normal, sizeof(normal)));
    Blas(hipblasLtMatrixLayoutCreate(&weights, HIP_R_16F, k, m, k));
    Blas(hipblasLtMatrixLayoutCreate(&input, HIP_R_16F, k, n, k));
    Blas(hipblasLtMatrixLayoutCreate(&output, HIP_R_32F, m, n, m));
    Blas(hipblasLtMatmulPreferenceCreate(&preference));
  }
};

// Independent library diagnostic. No model activations, global tuning cache,
// original weight mutation or automatic selection in the production path.
static unsigned LibrarySweep(rocm::BlasLt &native, unsigned m, unsigned k) {
  constexpr unsigned n = 2048, rotations = 16, launches = 16, guard = 32;
  constexpr std::size_t max_workspace = 64ULL << 20;
  constexpr float sentinel = 123456.0f;
  LibraryPlan plan;
  plan.Init(m, k, n);
  struct Choice {
    hipblasLtMatmulAlgo_t algorithm;
    int index;
    std::size_t workspace;
  };
  std::vector<Choice> choices;
  std::set<int> seen;
  const float one = 1, zero = 0;
  for (std::size_t cap : {std::size_t(0), max_workspace}) {
    Blas(hipblasLtMatmulPreferenceSetAttribute(
        plan.preference, HIPBLASLT_MATMUL_PREF_MAX_WORKSPACE_BYTES, &cap,
        sizeof(cap)));
    std::array<hipblasLtMatmulHeuristicResult_t, 32> results{};
    int found = 0;
    Blas(hipblasLtMatmulAlgoGetHeuristic(
        plan.handle, plan.operation, plan.weights, plan.input, plan.output,
        plan.output, plan.preference, results.size(), results.data(), &found));
    Require(found >= 0 && found <= int(results.size()),
            "Invalid heuristic count");
    std::cout << std::scientific << std::setprecision(12)
              << "{\"event\":\"library_heuristics\",\"m\":" << m
              << ",\"k\":" << k << ",\"n\":" << n << ",\"cap_bytes\":" << cap
              << ",\"found\":" << found << "}\n";
    for (int i = 0; i < found; ++i) {
      auto &candidate = results[i];
      std::size_t required = 0;
      const int index = hipblaslt_ext::getIndexFromAlgo(candidate.algo);
      const auto status = hipblaslt_ext::matmulIsAlgoSupported(
          plan.handle, plan.operation, &one, plan.weights, plan.input, &zero,
          plan.output, plan.output, candidate.algo, required);
      const bool usable = candidate.state == HIPBLAS_STATUS_SUCCESS &&
                          status == HIPBLAS_STATUS_SUCCESS && required <= cap &&
                          candidate.workspaceSize <= cap && index >= 0;
      std::cout << std::scientific << std::setprecision(12)
                << "{\"event\":\"library_choice\",\"m\":" << m
                << ",\"cap_bytes\":" << cap << ",\"rank\":" << i
                << ",\"algorithm\":" << index
                << ",\"state\":" << int(candidate.state)
                << ",\"support_status\":" << int(status)
                << ",\"workspace_bytes\":" << required
                << ",\"heuristic_workspace_bytes\":" << candidate.workspaceSize
                << ",\"usable\":" << (usable ? "true" : "false") << "}\n";
      if (usable && seen.insert(index).second)
        choices.push_back({candidate.algo, index, required});
    }
  }
  Require(!choices.empty(), "No usable library candidate");
  const std::size_t matrix_bytes = std::size_t(m) * k * 2;
  const std::size_t count = std::size_t(m) * n;
  Device wd(matrix_bytes * rotations), xd(std::size_t(n) * k * 2);
  Device yd((count + 2 * guard) * 4), workspace(max_workspace);
  const auto w = Values(std::size_t(m) * k, 431, 0.03125f);
  const auto x = Values(std::size_t(n) * k, 179, 1.0f);
  for (unsigned i = 0; i < rotations; ++i) {
    const auto weights = Values(std::size_t(m) * k, 431 + i, 0.03125f);
    Hip(hipMemcpy(static_cast<char *>(wd.data) + i * matrix_bytes,
                  weights.data(), matrix_bytes, hipMemcpyHostToDevice));
  }
  Hip(hipMemcpy(xd.data, x.data(), x.size() * 2, hipMemcpyHostToDevice));
  std::vector<std::size_t> positions;
  std::vector<double> expected;
  const auto rows = Boundaries(m, m == 320 ? 64 : 128);
  const auto tokens = Boundaries(n, m == 320 ? 64 : 128);
  double reference2 = 0, peak = 0;
  for (unsigned t : tokens)
    for (unsigned r : rows) {
      double sum = 0;
      for (unsigned j = 0; j < k; ++j)
        sum += double(__half2float(w[std::size_t(r) * k + j])) *
               double(__half2float(x[std::size_t(t) * k + j]));
      positions.push_back(std::size_t(t) * m + r);
      expected.push_back(sum);
      reference2 += sum * sum;
      peak = std::max(peak, std::abs(sum));
    }
  std::vector<float> output(count + 2 * guard), reference;
  std::vector<__half> repeated(x.size());
  for (unsigned t = 0; t < n; ++t)
    std::copy_n(x.data(), k, repeated.data() + std::size_t(t) * k);
  hipEvent_t begin{}, end{};
  Hip(hipEventCreate(&begin));
  Hip(hipEventCreate(&end));
  unsigned failures = 0;
  // Native before and after bound drift across the sequential algorithm sweep.
  for (std::size_t arm = 0; arm < choices.size() + 2; ++arm) {
    Choice *choice =
        arm > 0 && arm <= choices.size() ? &choices[arm - 1] : nullptr;
    const int index = choice ? choice->index : -1;
    auto launch = [&](unsigned rotation) {
      const auto *weights =
          static_cast<char *>(wd.data) + (rotation % rotations) * matrix_bytes;
      auto *out = static_cast<float *>(yd.data) + guard;
      if (choice)
        Blas(hipblasLtMatmul(plan.handle, plan.operation, &one, weights,
                             plan.weights, xd.data, plan.input, &zero, out,
                             plan.output, out, plan.output, &choice->algorithm,
                             choice->workspace ? workspace.data : nullptr,
                             choice->workspace, nullptr));
      else
        Gemm(native, weights, xd.data, out, m, k, n);
      Hip(hipGetLastError());
    };
    std::fill(output.begin(), output.end(), sentinel);
    Hip(hipMemcpy(yd.data, output.data(), output.size() * 4,
                  hipMemcpyHostToDevice));
    launch(0);
    Hip(hipDeviceSynchronize());
    Hip(hipMemcpy(output.data(), yd.data, output.size() * 4,
                  hipMemcpyDeviceToHost));
    for (unsigned i = 0; i < guard; ++i)
      Require(output[i] == sentinel && output[guard + count + i] == sentinel,
              "Library output guard changed");
    for (std::size_t i = 0; i < count; ++i)
      Require(std::isfinite(output[guard + i]) && output[guard + i] != sentinel,
              "Library output is non-finite or unwritten");
    if (reference.empty())
      reference.assign(output.begin() + guard, output.end() - guard);
    double error2 = 0, maximum = 0;
    std::vector<float> samples;
    for (std::size_t i = 0; i < positions.size(); ++i) {
      const float value = output[guard + positions[i]];
      const double delta = value - expected[i];
      error2 += delta * delta;
      maximum = std::max(maximum, std::abs(delta));
      samples.push_back(value);
    }
    const double rrms = std::sqrt(error2 / std::max(reference2, 1e-60));
    const double scaled_max = maximum / std::max(peak, 1e-30);
    const bool numeric_ok = rrms <= 0.00002 && scaled_max <= 0.00002;
    failures += !numeric_ok;
    std::size_t changed = 0;
    for (std::size_t i = 0; i < count; ++i)
      changed += output[guard + i] != reference[i];
    const auto digest = gufo::crypto::Sha256Hex(
        std::span(reinterpret_cast<const std::uint8_t *>(output.data() + guard),
                  count * 4));
    std::cout << std::scientific << std::setprecision(12)
              << "{\"event\":\"library_operator\",\"m\":" << m << ",\"k\":" << k
              << ",\"n\":" << n << ",\"arm\":" << arm
              << ",\"algorithm\":" << index
              << ",\"workspace_bytes\":" << (choice ? choice->workspace : 0)
              << ",\"relative_rms\":" << rrms
              << ",\"error_over_peak\":" << scaled_max
              << ",\"oracle_values\":" << positions.size()
              << ",\"changed_native_values\":" << changed
              << ",\"full_output_sha256\":\"" << digest
              << "\",\"numeric_ok\":" << (numeric_ok ? "true" : "false")
              << "}\n";
    const auto label = std::to_string(m) + "-arm" + std::to_string(arm);
    std::ofstream saved("results/hc-library-" + label + ".f32",
                        std::ios::binary);
    saved.write(reinterpret_cast<const char *>(samples.data()),
                samples.size() * 4);
    Require(bool(saved), "Cannot save library oracle samples");
    for (unsigned i = 0; i < rotations; ++i)
      launch(i);
    Hip(hipDeviceSynchronize());
    for (unsigned rep = 0; rep < 5; ++rep) {
      Hip(hipEventRecord(begin, nullptr));
      for (unsigned i = 0; i < launches; ++i)
        launch(i);
      Hip(hipEventRecord(end, nullptr));
      Hip(hipEventSynchronize(end));
      float ms = 0;
      Hip(hipEventElapsedTime(&ms, begin, end));
      std::cout << std::scientific << std::setprecision(12)
                << "{\"event\":\"library_timing\",\"m\":" << m << ",\"k\":" << k
                << ",\"n\":" << n << ",\"arm\":" << arm
                << ",\"algorithm\":" << index << ",\"rep\":" << rep
                << ",\"launches\":" << launches
                << ",\"weight_bytes\":" << matrix_bytes * rotations
                << ",\"us_per_launch\":" << ms * 1000.0 / launches << "}\n";
    }
    // Identical input rows must not acquire a tile-position-dependent result.
    Hip(hipMemcpy(xd.data, repeated.data(), repeated.size() * 2,
                  hipMemcpyHostToDevice));
    launch(0);
    Hip(hipDeviceSynchronize());
    Hip(hipMemcpy(output.data(), yd.data, output.size() * 4,
                  hipMemcpyDeviceToHost));
    std::size_t inconsistent = 0;
    double max_row_delta = 0;
    for (unsigned t = 1; t < n; ++t)
      for (unsigned r = 0; r < m; ++r) {
        const float value = output[guard + std::size_t(t) * m + r];
        Require(std::isfinite(value), "Non-finite repeated-row output");
        inconsistent += value != output[guard + r];
        max_row_delta = std::max(max_row_delta,
                                 std::abs(double(value) - output[guard + r]));
      }
    failures += inconsistent != 0;
    std::cout << std::scientific << std::setprecision(12)
              << "{\"event\":\"library_row_invariance\",\"m\":" << m
              << ",\"arm\":" << arm << ",\"algorithm\":" << index
              << ",\"inconsistent_values\":" << inconsistent
              << ",\"max_absolute_delta\":" << max_row_delta << "}\n";
    Hip(hipMemcpy(xd.data, x.data(), x.size() * 2, hipMemcpyHostToDevice));
  }
  Hip(hipEventDestroy(begin));
  Hip(hipEventDestroy(end));
  std::cout << std::scientific << std::setprecision(12)
            << "{\"event\":\"library_summary\",\"m\":" << m
            << ",\"algorithms\":" << choices.size()
            << ",\"failures\":" << failures << "}\n";
  return failures;
}
int main(int argc, char **argv) {
  try {
    Require(argc == 2, "Usage: q2_hc_pp operators|bench|library");
    const std::string mode = argv[1];
    Require(mode == "operators" || mode == "bench" || mode == "library",
            "Unsupported mode");
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
    if (mode == "library") {
      failures += LibrarySweep(*blas, 320, 10240);
      failures += LibrarySweep(*blas, 10240, 320);
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
