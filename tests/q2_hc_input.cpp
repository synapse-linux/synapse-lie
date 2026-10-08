// SPDX-License-Identifier: MIT
// Original sampled FP64 HC checks plus exact fused-narrowing consumer replay.
#define Q2_HC_INPUT_CHECKS 1
#include "q2_hc_pp.cpp"
#include <cstring>

#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hpp"

static constexpr unsigned input_m = 320, input_k = 10240;
static std::vector<float> FloatInput(unsigned n, unsigned pattern) {
  std::vector<float> values(std::size_t(n) * input_k);
  Random random{179 + pattern};
  for (std::size_t i = 0; i < values.size(); ++i) {
    float v = random.Next();
    if (pattern == 1)
      v *= std::ldexp(1.0f, -12);
    if (pattern == 2)
      v = (i % 2 ? -1.0f : 1.0f) + v * 0.001f;
    // Include F16 ties, subnormals and signed zero among ordinary inputs.
    if (i % 64 == 0) {
      const float edges[] = {0.0f,           -0.0f,          0x1p-25f,
                             -0x1p-25f,      0x1p-24f,       -0x1p-24f,
                             1.00048828125f, -1.00048828125f};
      v = edges[(i / 64) % 8];
    }
    values[i] = v;
  }
  if (pattern == 3)
    for (unsigned t = 1; t < n; ++t)
      std::copy_n(values.data(), input_k,
                  values.data() + std::size_t(t) * input_k);
  return values;
}

struct InputOutput {
  static constexpr unsigned guard = 32;
  static constexpr float sentinel = 123456.0f;
  std::size_t count;
  Device storage;
  explicit InputOutput(std::size_t n)
      : count(n), storage((n + 2 * guard) * sizeof(float)) {
    std::vector<float> values(n + 2 * guard, sentinel);
    Hip(hipMemcpy(storage.data, values.data(), values.size() * sizeof(float),
                  hipMemcpyHostToDevice));
  }
  float *Data() { return static_cast<float *>(storage.data) + guard; }
  std::vector<float> Read() {
    std::vector<float> values(count + 2 * guard);
    Hip(hipMemcpy(values.data(), storage.data, values.size() * sizeof(float),
                  hipMemcpyDeviceToHost));
    for (unsigned i = 0; i < guard; ++i)
      Require(values[i] == sentinel && values[guard + count + i] == sentinel,
              "Fused input output guard changed");
    for (std::size_t i = guard; i < guard + count; ++i)
      Require(std::isfinite(values[i]) && values[i] != sentinel,
              "Non-finite or unwritten fused input output");
    return {values.begin() + guard, values.end() - guard};
  }
};

static void SaveInputOutput(const std::string &label,
                            const std::vector<float> &values) {
  std::ofstream saved("results/" + label + ".f32", std::ios::binary);
  saved.write(reinterpret_cast<const char *>(values.data()), values.size() * 4);
  Require(bool(saved), "Cannot save fused input output");
}

static bool InputCase(rocm::BlasLt &blas, unsigned n, unsigned pattern) {
  const auto weights = Values(std::size_t(input_m) * input_k, 431, 0.03125f);
  const auto input = FloatInput(n, pattern);
  std::vector<__half> rounded(input.size());
  for (std::size_t i = 0; i < input.size(); ++i)
    rounded[i] = __float2half_rn(input[i]);
  Device wd(weights.size() * 2), xd(input.size() * 4), hd(input.size() * 2);
  Hip(hipMemcpy(wd.data, weights.data(), weights.size() * 2,
                hipMemcpyHostToDevice));
  Hip(hipMemcpy(xd.data, input.data(), input.size() * 4,
                hipMemcpyHostToDevice));
  // Both input allocations end at the last live element, including ragged n.
  rocm::NarrowActivations(static_cast<float *>(xd.data), hd.data, false,
                          input.size(), nullptr);
  InputOutput reference(std::size_t(n) * input_m), candidate(reference.count);
  Gemm(blas, wd.data, hd.data, reference.Data(), input_m, input_k, n);
  Require(rocm::HcDownF32InputGemm(wd.data, static_cast<float *>(xd.data),
                                   candidate.Data(), n, nullptr),
          "Fused input dispatch refused");
  Hip(hipGetLastError());
  Hip(hipDeviceSynchronize());
  const auto a = reference.Read(), b = candidate.Read();
  std::vector<__half> gpu_rounded(rounded.size());
  Hip(hipMemcpy(gpu_rounded.data(), hd.data, rounded.size() * 2,
                hipMemcpyDeviceToHost));
  Require(std::memcmp(rounded.data(), gpu_rounded.data(), rounded.size() * 2) ==
              0,
          "Independent scalar narrowing differs from reference GPU");
  std::vector<float> input_after(input.size());
  Hip(hipMemcpy(input_after.data(), xd.data, input.size() * 4,
                hipMemcpyDeviceToHost));
  Require(std::memcmp(input.data(), input_after.data(), input.size() * 4) == 0,
          "Fused input mutated its source");
  double error2 = 0, reference2 = 0, maximum = 0, peak = 0;
  unsigned positions = 0;
  for (unsigned t : Boundaries(n, 128))
    for (unsigned row : Boundaries(input_m, 64)) {
      double sum = 0;
      for (unsigned k = 0; k < input_k; ++k)
        sum += double(__half2float(weights[std::size_t(row) * input_k + k])) *
               double(__half2float(rounded[std::size_t(t) * input_k + k]));
      const double delta = b[std::size_t(t) * input_m + row] - sum;
      error2 += delta * delta;
      reference2 += sum * sum;
      maximum = std::max(maximum, std::abs(delta));
      peak = std::max(peak, std::abs(sum));
      ++positions;
    }
  const double rrms = std::sqrt(error2 / std::max(reference2, 1e-60));
  const double scaled_max = maximum / std::max(peak, 1e-30);
  const bool exact = std::memcmp(a.data(), b.data(), a.size() * 4) == 0;
  std::size_t row_differences = 0;
  if (pattern == 3)
    for (unsigned t = 1; t < n; ++t)
      for (unsigned row = 0; row < input_m; ++row)
        row_differences += b[std::size_t(t) * input_m + row] != b[row];
  for (unsigned short_n : {0u, 1u, 95u})
    Require(!rocm::HcDownF32InputGemm(wd.data, static_cast<float *>(xd.data),
                                      candidate.Data(), short_n, nullptr),
            "Fused input accepted unsupported batch");
  Require(!rocm::HcDownF32InputGemm(nullptr, static_cast<float *>(xd.data),
                                    candidate.Data(), n, nullptr) &&
              !rocm::HcDownF32InputGemm(wd.data, nullptr, candidate.Data(), n,
                                        nullptr) &&
              !rocm::HcDownF32InputGemm(wd.data, static_cast<float *>(xd.data),
                                        nullptr, n, nullptr),
          "Fused input accepted null storage");
  Hip(hipDeviceSynchronize());
  Require(candidate.Read() == b, "Rejected input dispatch changed output");
  const auto label =
      "hc-input-n" + std::to_string(n) + "-p" + std::to_string(pattern);
  SaveInputOutput(label + "-reference", a);
  SaveInputOutput(label + "-candidate", b);
  const bool numeric = rrms <= 2e-5 && scaled_max <= 2e-5;
  std::cout << std::scientific << std::setprecision(12)
            << "{\"event\":\"hc_input_operator\",\"label\":\"" << label
            << "\",\"n\":" << n << ",\"pattern\":" << pattern
            << ",\"values\":" << b.size() << ",\"oracle_values\":" << positions
            << ",\"exact\":" << (exact ? "true" : "false")
            << ",\"relative_rms\":" << rrms
            << ",\"error_over_peak\":" << scaled_max
            << ",\"row_differences\":" << row_differences
            << ",\"numeric_ok\":" << (numeric ? "true" : "false") << "}\n";
  return exact && numeric && row_differences == 0;
}

static bool InputBench(rocm::BlasLt &blas) {
  constexpr unsigned n = 2048, matrices = 16, launches = 16;
  constexpr std::size_t weight_bytes = std::size_t(input_m) * input_k * 2;
  const auto input = FloatInput(n, 0);
  Device weights(weight_bytes * matrices), xd(input.size() * 4),
      hd(input.size() * 2);
  InputOutput reference(std::size_t(n) * input_m), candidate(reference.count);
  for (unsigned i = 0; i < matrices; ++i) {
    const auto w = Values(weight_bytes / 2, 431 + i, 0.03125f);
    Hip(hipMemcpy(static_cast<char *>(weights.data) + i * weight_bytes,
                  w.data(), weight_bytes, hipMemcpyHostToDevice));
  }
  Hip(hipMemcpy(xd.data, input.data(), input.size() * 4,
                hipMemcpyHostToDevice));
  auto launch = [&](bool fused, unsigned matrix) {
    const auto *w =
        static_cast<char *>(weights.data) + (matrix % matrices) * weight_bytes;
    if (fused)
      Require(rocm::HcDownF32InputGemm(w, static_cast<float *>(xd.data),
                                       candidate.Data(), n, nullptr),
              "Fused input benchmark dispatch refused");
    else {
      rocm::NarrowActivations(static_cast<float *>(xd.data), hd.data, false,
                              input.size(), nullptr);
      Gemm(blas, w, hd.data, reference.Data(), input_m, input_k, n);
    }
    Hip(hipGetLastError());
  };
  for (bool fused : {false, true})
    for (unsigned i = 0; i < matrices; ++i)
      launch(fused, i);
  Hip(hipDeviceSynchronize());
  hipEvent_t begin{}, end{};
  Hip(hipEventCreate(&begin));
  Hip(hipEventCreate(&end));
  bool all_exact = true;
  for (unsigned rep = 0; rep < 5; ++rep) {
    for (unsigned order = 0; order < 2; ++order) {
      const bool fused = (rep + order) % 2 != 0;
      Hip(hipEventRecord(begin, nullptr));
      for (unsigned i = 0; i < launches; ++i)
        launch(fused, i);
      Hip(hipEventRecord(end, nullptr));
      Hip(hipEventSynchronize(end));
      float ms = 0;
      Hip(hipEventElapsedTime(&ms, begin, end));
      std::cout << std::scientific << std::setprecision(12)
                << "{\"event\":\"hc_input_timing\",\"fused\":"
                << (fused ? "true" : "false") << ",\"rep\":" << rep
                << ",\"order\":" << order << ",\"launches\":" << launches
                << ",\"weight_bytes\":" << weight_bytes * matrices
                << ",\"n\":" << n
                << ",\"us_per_launch\":" << ms * 1000.0 / launches << "}\n";
    }
    const auto a = reference.Read(), b = candidate.Read();
    const bool exact = std::memcmp(a.data(), b.data(), a.size() * 4) == 0;
    all_exact &= exact;
    std::cout << "{\"event\":\"hc_input_bench_replay\",\"rep\":" << rep
              << ",\"exact\":" << (exact ? "true" : "false") << "}\n";
  }
  Hip(hipEventDestroy(begin));
  Hip(hipEventDestroy(end));
  return all_exact;
}

int main() {
  try {
    std::cout << std::unitbuf << std::setprecision(12);
    Hip(hipSetDevice(0));
    std::string error;
    auto blas = rocm::BlasLt::Create(nullptr, &error);
    if (!blas)
      throw std::runtime_error(error);
    unsigned original_failures = 0;
    // Retain the original 22 cases, including known library-control failures.
    for (unsigned n : {32, 95, 96, 97, 127, 128, 129, 2048}) {
      original_failures += !Case(*blas, 320, 10240, n, 0);
      original_failures += !Case(*blas, 10240, 320, n, 0);
    }
    for (unsigned pattern : {1, 2}) {
      original_failures += !Case(*blas, 320, 10240, 129, pattern);
      original_failures += !Case(*blas, 10240, 320, 129, pattern);
    }
    original_failures += !Case(*blas, 319, 10240, 129, 0);
    original_failures += !Case(*blas, 320, 10208, 129, 0);
    std::cout << "{\"event\":\"pp_operator_summary\",\"cases\":22,\"numerical_"
                 "failures\":"
              << original_failures << "}\n";
    unsigned failures = 0;
    for (unsigned n : {96, 97, 127, 128, 129, 257, 2048})
      failures += !InputCase(*blas, n, 0);
    for (unsigned pattern : {1, 2, 3})
      failures += !InputCase(*blas, 129, pattern);
    const bool bench_exact = InputBench(*blas);
    Bench(*blas, 10240, 320);
    std::cout << "{\"event\":\"hc_input_summary\",\"cases\":10,\"failures\":"
              << failures
              << ",\"bench_exact\":" << (bench_exact ? "true" : "false")
              << ",\"original_failures\":" << original_failures << "}\n";
    return original_failures || failures || !bench_exact ? 1 : 0;
  } catch (const std::exception &ex) {
    std::cerr << ex.what() << '\n';
    return 1;
  }
}
