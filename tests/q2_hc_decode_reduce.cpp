// SPDX-License-Identifier: MIT
// Same-process GPU comparison; synthetic weights only, never model inference.
#define main OriginalHcFixtureMain
#include "q2_hc.cpp"
#undef main
#include <bit>
#include <cstring>

static constexpr unsigned kRows = 320, kColumns = 10240;
static constexpr std::size_t kGuard = 32;
static constexpr float kSentinel = 123456.0f;

static void Dispatch(bool candidate, const void *w, const void *x, void *y) {
  if (candidate)
    rocm::SmallGemm(w, rocm::WeightType::kF16, static_cast<const float *>(x),
                    static_cast<float *>(y), 1, kRows, kColumns, nullptr);
  else
    rocm::HcDownF16Reference(static_cast<const __half *>(w),
                             static_cast<const float *>(x),
                             static_cast<float *>(y), nullptr);
}

static void SavePair(const std::string &prefix, const std::vector<float> &ref,
                     const std::vector<float> &candidate) {
  for (const auto &arm :
       {std::pair{"reference", &ref}, std::pair{"candidate", &candidate}}) {
    std::ofstream output("results/" + prefix + "-" + arm.first + ".f32",
                         std::ios::binary);
    output.write(reinterpret_cast<const char *>(arm.second->data()),
                 std::streamsize(arm.second->size() * sizeof(float)));
    Require(bool(output), "Cannot save reduction frontier");
  }
}

static bool ExactCase(unsigned pattern) {
  auto w = Weights(kRows, kColumns, 431 + pattern);
  std::vector<float> x(kColumns);
  Random rng{179 + pattern};
  for (unsigned i = 0; i < kColumns; ++i) {
    const float value = rng.Next();
    x[i] = pattern == 1   ? std::ldexp(value, -18)
           : pattern == 2 ? (i % 2 ? -1.0f : 1.0f) + value * .001f
           : pattern == 3 ? (i % 2 ? -0.0f : 0.0f)
           : pattern == 5 ? std::bit_cast<float>(std::uint32_t((i % 31) + 1) |
                                                 (i % 2 ? 0x80000000u : 0u))
                          : value;
  }
  if (pattern == 4) {
    for (std::size_t i = 0; i < w.size(); ++i) {
      const auto bits =
          std::uint16_t((i % 1023) + 1) | std::uint16_t(i % 2 ? 0x8000u : 0u);
      static_assert(sizeof(__half) == sizeof(std::uint16_t));
      const std::uint16_t packed = std::uint16_t(bits);
      std::memcpy(&w[i], &packed, sizeof(packed));
    }
  }
  Device wd(w.size() * sizeof(__half)), xd(x.size() * sizeof(float));
  Device yd((kRows + 2 * kGuard) * sizeof(float));
  Hip(hipMemcpy(wd.data, w.data(), w.size() * sizeof(__half),
                hipMemcpyHostToDevice));
  Hip(hipMemcpy(xd.data, x.data(), x.size() * sizeof(float),
                hipMemcpyHostToDevice));
  std::vector<float> outputs[2];
  for (unsigned arm = 0; arm < 2; ++arm) {
    std::vector<float> got(kRows + 2 * kGuard, kSentinel);
    Hip(hipMemcpy(yd.data, got.data(), got.size() * sizeof(float),
                  hipMemcpyHostToDevice));
    Dispatch(arm == 1, wd.data, xd.data,
             static_cast<float *>(yd.data) + kGuard);
    Hip(hipGetLastError());
    Hip(hipDeviceSynchronize());
    Hip(hipMemcpy(got.data(), yd.data, got.size() * sizeof(float),
                  hipMemcpyDeviceToHost));
    for (std::size_t i = 0; i < kGuard; ++i)
      Require(got[i] == kSentinel && got[kRows + kGuard + i] == kSentinel,
              "Reduction output guard changed");
    outputs[arm].assign(got.begin() + kGuard, got.end() - kGuard);
    for (float value : outputs[arm])
      Require(std::isfinite(value) && value != kSentinel,
              "Reduction output missing or nonfinite");
  }
  const auto label = "reduce-p" + std::to_string(pattern);
  SavePair(label, outputs[0], outputs[1]);
  const bool exact = std::memcmp(outputs[0].data(), outputs[1].data(),
                                 kRows * sizeof(float)) == 0;
  std::cout << "{\"event\":\"reduce_exact\",\"pattern\":" << pattern
            << ",\"values\":" << kRows
            << ",\"exact\":" << (exact ? "true" : "false") << "}\n";
  return exact;
}

static bool PairedBench() {
  constexpr unsigned matrices = 16, launches = 128;
  const std::size_t bytes = std::size_t(kRows) * kColumns * sizeof(__half);
  Device wd(bytes * matrices), xd(kColumns * sizeof(float)),
      yd(kRows * sizeof(float));
  for (unsigned i = 0; i < matrices; ++i) {
    const auto w = Weights(kRows, kColumns, i + 431);
    Hip(hipMemcpy(static_cast<char *>(wd.data) + bytes * i, w.data(), bytes,
                  hipMemcpyHostToDevice));
  }
  std::vector<float> x(kColumns);
  Random rng{179};
  for (float &value : x)
    value = rng.Next();
  Hip(hipMemcpy(xd.data, x.data(), x.size() * sizeof(float),
                hipMemcpyHostToDevice));
  auto launch = [&](bool candidate, unsigned index) {
    Dispatch(candidate,
             static_cast<char *>(wd.data) + bytes * (index % matrices), xd.data,
             yd.data);
  };
  bool all_exact = true;
  for (unsigned i = 0; i < matrices; ++i) {
    std::vector<float> output[2];
    for (unsigned arm = 0; arm < 2; ++arm) {
      launch(arm == 1, i);
      Hip(hipGetLastError());
      output[arm].resize(kRows);
      Hip(hipMemcpy(output[arm].data(), yd.data, kRows * sizeof(float),
                    hipMemcpyDeviceToHost));
      for (float value : output[arm])
        Require(std::isfinite(value), "Nonfinite rotated frontier");
    }
    const bool exact = std::memcmp(output[0].data(), output[1].data(),
                                   kRows * sizeof(float)) == 0;
    all_exact = all_exact && exact;
    SavePair("reduce-rotation-" + std::to_string(i), output[0], output[1]);
    std::cout << "{\"event\":\"reduce_rotation\",\"matrix\":" << i
              << ",\"values\":" << kRows
              << ",\"exact\":" << (exact ? "true" : "false") << "}\n";
  }
  Hip(hipGetLastError());
  Hip(hipDeviceSynchronize());
  hipEvent_t begin, end;
  Hip(hipEventCreate(&begin));
  Hip(hipEventCreate(&end));
  for (unsigned rep = 0; rep < 5; ++rep) {
    double us[2]{};
    std::vector<float> output[2];
    for (unsigned order = 0; order < 2; ++order) {
      const unsigned arm = order ^ (rep & 1);
      Hip(hipEventRecord(begin, nullptr));
      for (unsigned i = 0; i < launches; ++i)
        launch(arm == 1, i);
      Hip(hipEventRecord(end, nullptr));
      Hip(hipEventSynchronize(end));
      Hip(hipGetLastError());
      float milliseconds = 0;
      Hip(hipEventElapsedTime(&milliseconds, begin, end));
      us[arm] = milliseconds * 1000.0 / launches;
      output[arm].resize(kRows);
      Hip(hipMemcpy(output[arm].data(), yd.data, kRows * sizeof(float),
                    hipMemcpyDeviceToHost));
      for (float value : output[arm])
        Require(std::isfinite(value), "Nonfinite timed frontier");
    }
    const bool exact = std::memcmp(output[0].data(), output[1].data(),
                                   kRows * sizeof(float)) == 0;
    all_exact = all_exact && exact;
    SavePair("reduce-bench-" + std::to_string(rep), output[0], output[1]);
    std::cout << "{\"event\":\"reduce_bench\",\"rep\":" << rep
              << ",\"candidate_first\":" << (rep & 1 ? "true" : "false")
              << ",\"matrices\":" << matrices
              << ",\"weight_bytes\":" << bytes * matrices
              << ",\"launches\":" << launches << ",\"reference_us\":" << us[0]
              << ",\"candidate_us\":" << us[1]
              << ",\"exact\":" << (exact ? "true" : "false") << "}\n";
  }
  Hip(hipEventDestroy(begin));
  Hip(hipEventDestroy(end));
  return all_exact;
}

int main(int argc, char **argv) {
  try {
    Require(argc == 2 && std::string(argv[1]) == "bench",
            "Usage: q2_hc_decode_reduce bench");
    std::cout << std::unitbuf << std::setprecision(12);
    Hip(hipSetDevice(0));
    bool independent_ok = true;
    const auto independent = [&](unsigned m, unsigned k, unsigned tokens,
                                 unsigned pattern) {
      try {
        Case(m, k, tokens, pattern);
      } catch (const std::exception &e) {
        if (std::string(e.what()) !=
            "Independent F16 operator tolerance exceeded")
          throw;
        independent_ok = false;
        std::cout << "{\"event\":\"independent_failure\",\"m\":" << m
                  << ",\"k\":" << k << ",\"tokens\":" << tokens
                  << ",\"pattern\":" << pattern << "}\n";
      }
    };
    // Preserve the original eleven independent FP64 cases and their limits.
    for (unsigned pattern = 0; pattern < 3; ++pattern)
      independent(320, 10240, 1, pattern);
    for (unsigned tokens : {2, 3, 8, 9})
      independent(320, 10240, tokens, 0);
    independent(319, 10240, 1, 0);
    independent(320, 10239, 1, 0);
    independent(10240, 320, 1, 0);
    independent(512, 2560, 1, 0);
    bool exact = true;
    for (unsigned pattern = 0; pattern < 6; ++pattern)
      exact = ExactCase(pattern) && exact;
    // Preserve performance evidence even when exact replay fails.
    exact = PairedBench() && exact;
    const bool pass = exact && independent_ok;
    std::cout << (pass ? "PASS" : "FAIL")
              << " synthetic HC decode reduction; no model inference\n";
    return pass ? 0 : 1;
  } catch (const std::exception &e) {
    std::cerr << "FAIL: " << e.what() << '\n';
    return 1;
  }
}
