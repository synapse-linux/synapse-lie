// SPDX-License-Identifier: MIT
// Retained independent HC up checks and rotating-weight fused-path timings.
#define Q2_HC_UP_CHAINS_CHECKS 1
#include "q2_hc_up_fused.cpp"

static bool Benchmark() {
  constexpr unsigned tokens = 2048, hidden = 2560, rank = 320,
                     rows = 4 * hidden;
  constexpr unsigned matrices = 16, launches = 16;
  constexpr std::size_t weight_bytes = std::size_t(rows) * rank * 2;
  const std::size_t count = std::size_t(tokens) * hidden;
  Random rng{717};
  Device weights(weight_bytes * matrices);
  for (unsigned i = 0; i < matrices; ++i) {
    std::vector<__half> values(weight_bytes / 2);
    for (auto &v : values)
      v = __float2half_rn(rng.Next() * .03125f);
    Hip(hipMemcpy(static_cast<char *>(weights.data) + i * weight_bytes,
                  values.data(), weight_bytes, hipMemcpyHostToDevice));
  }
  std::vector<__half> low(std::size_t(tokens) * rank);
  std::vector<float> norm(std::size_t(tokens) * rows);
  for (auto &v : low)
    v = __float2half_rn(rng.Next());
  for (auto &v : norm)
    v = rng.Next();
  Device ld(low.size() * 2), xd(norm.size() * 4), gates(norm.size() * 4);
  Upload(ld, low);
  Upload(xd, norm);
  Output<float> separate(count), fused(count);
  Output<__half> separate_half(count), fused_half(count);
  auto launch = [&](bool mix, unsigned matrix) {
    const void *w =
        static_cast<const char *>(weights.data) + matrix * weight_bytes;
    const auto *input = static_cast<const __half *>(ld.data);
    const auto *xn = static_cast<const float *>(xd.data);
    if (mix) {
      Require(q::HcMixRawF16Gemm(w, input, xn, nullptr, fused.Data(),
                                 fused_half.Data(), nullptr, tokens, hidden,
                                 rank, nullptr),
              "Fused HC up benchmark refused");
    } else {
      Require(q::UnquantizedF16Gemm(w, input, static_cast<float *>(gates.data),
                                    tokens, rows, rank, nullptr),
              "Separate HC up benchmark refused");
      q::HcMixEpilogueVec4(xn, static_cast<const float *>(gates.data), nullptr,
                           separate.Data(), nullptr, tokens, hidden, 4,
                           nullptr);
      q::NarrowActivations(separate.Data(), separate_half.Data(), false, count,
                           nullptr);
    }
    Hip(hipGetLastError());
  };
  for (bool mix : {false, true})
    for (unsigned i = 0; i < matrices; ++i)
      launch(mix, i);
  Hip(hipDeviceSynchronize());
  hipEvent_t begin{}, end{};
  Hip(hipEventCreate(&begin));
  Hip(hipEventCreate(&end));
  bool pass = true;
  for (unsigned rep = 0; rep < 5; ++rep) {
    for (unsigned order = 0; order < 2; ++order) {
      const bool mix = (rep + order) % 2 != 0;
      Hip(hipEventRecord(begin, nullptr));
      for (unsigned i = 0; i < launches; ++i)
        launch(mix, i % matrices);
      Hip(hipEventRecord(end, nullptr));
      Hip(hipEventSynchronize(end));
      float ms = 0;
      Hip(hipEventElapsedTime(&ms, begin, end));
      std::cout << std::scientific << std::setprecision(12)
                << "{\"event\":\"hc_up_chain_timing\",\"fused\":"
                << (mix ? "true" : "false") << ",\"rep\":" << rep
                << ",\"order\":" << order << ",\"n\":" << tokens
                << ",\"launches\":" << launches
                << ",\"weight_bytes\":" << weight_bytes * matrices
                << ",\"us_per_launch\":" << ms * 1000.0 / launches << "}\n";
    }
    const bool exact = Exact(separate.Read(), fused.Read()) &&
                       Exact(separate_half.Read(), fused_half.Read());
    pass &= exact;
    std::cout << "{\"event\":\"hc_up_chain_replay\",\"rep\":" << rep
              << ",\"exact\":" << (exact ? "true" : "false") << "}\n";
  }
  CheckInput(ld, low);
  CheckInput(xd, norm);
  Hip(hipEventDestroy(begin));
  Hip(hipEventDestroy(end));
  return pass;
}

int main() {
  try {
    std::cout << std::unitbuf << std::setprecision(12);
    Hip(hipSetDevice(0));
    unsigned failures = 0;
    failures += !Case(96, 0, true, true);
    failures += !Case(97, 1, true, true);
    failures += !Case(129, 0, true, true);
    failures += !Case(129, 2, true, true);
    failures += !Case(129, 0, false, true);
    failures += !Case(129, 0, true, false);
    failures += !Case(2048, 0, true, true);
    for (unsigned n : {127, 128, 257})
      failures += !Case(n, 0, true, true);
    failures += !Case(129, 3, true, true);
    const bool replay = Benchmark();
    std::cout << "{\"event\":\"hc_up_chain_summary\",\"cases\":11,\"failures\":"
              << failures << ",\"bench_exact\":" << (replay ? "true" : "false")
              << "}\n";
    return failures || !replay ? 1 : 0;
  } catch (const std::exception &error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
