// SPDX-License-Identifier: MIT
// Original producer controls plus the measured HC-library consumer, timed
// together.
#define Q2_HC_DEFERRED_CHECKS 1
#include "q2_hc_sequence.cpp"
#include "src/models/qwen38_flash_next/kernels/rocm/blaslt.hpp"

static bool LibraryLaunch(q::BlasLt &blas, Inputs &in, State &state,
                          Weights &weights, unsigned index, bool moe,
                          bool paired) {
  if (moe) {
    const bool ok =
        paired
            ? q::HcCombineMoeF32Half(state.residual.Data(), in.ed.Data(),
                                     in.wd.Data(), in.sd.Data(), in.gd.Data(),
                                     Inputs::stride, in.used, in.id.Data(),
                                     in.parts, in.nd.Data(), state.norm.Data(),
                                     in.tokens, Inputs::hidden, Inputs::streams,
                                     Inputs::eps, nullptr, state.half.Data())
            : in.Fused(state.residual, state.norm, true);
    if (!ok)
      return false;
  } else if (paired) {
    if (!q::HcCombineF32Half(state.residual.Data(), in.sd.Data(), in.id.Data(),
                             in.parts, in.nd.Data(), state.norm.Data(),
                             state.half.Data(), in.tokens, Inputs::hidden,
                             Inputs::streams, Inputs::eps, nullptr))
      return false;
  } else {
    q::HcCombine(state.residual.Data(), in.sd.Data(), in.id.Data(), in.parts,
                 in.nd.Data(), state.norm.Data(), in.tokens, Inputs::hidden,
                 Inputs::streams, Inputs::eps, nullptr);
  }
  if (!paired)
    q::NarrowActivations(state.norm.Data(), state.half.Data(), false,
                         state.norm.size, nullptr);
  std::string error;
  if (!blas.Gemm(weights.Data(index), state.half.Data(), state.down.Data(),
                 HIP_R_16F, kRows, in.tokens, kColumns, &error))
    throw std::runtime_error(error);
  return true;
}

static bool LibraryCase(q::BlasLt &blas, unsigned tokens, unsigned pattern,
                        bool moe) {
  Inputs in(tokens, 8, 3, pattern);
  Weights weights(1);
  State a(tokens), b(tokens);
  Upload(a.residual.Data(), in.residual);
  Upload(b.residual.Data(), in.residual);
  Require(LibraryLaunch(blas, in, a, weights, 0, moe, false),
          "Reference dispatch refused");
  Require(LibraryLaunch(blas, in, b, weights, 0, moe, true),
          "Paired dispatch refused");
  Hip(hipGetLastError());
  Hip(hipDeviceSynchronize());
  // Library plan diagnostics modify cout's precision on first use.
  std::cout << std::defaultfloat << std::setprecision(12);
  const auto label = "hc-library-norm-n" + std::to_string(tokens) + "-p" +
                     std::to_string(pattern) + "-moe" + std::to_string(moe);
  // Full arrays are always compared and hashed; bounded small cases are saved.
  const bool pass =
      Compare(in, a, b, weights, 0, label, tokens < 2048, true, moe);
  const auto residual = b.residual.Read(), norm = b.norm.Read();
  const auto half = b.half.Read();
  for (unsigned invalid = 0; invalid < 4; ++invalid) {
    const auto *gamma = invalid == 0 ? nullptr : in.nd.Data();
    auto *half_out = invalid == 1 ? nullptr : b.half.Data();
    const unsigned n = invalid == 2 ? 15 : tokens;
    const unsigned hidden = invalid == 3 ? Inputs::hidden - 1 : Inputs::hidden;
    Require(!q::HcCombineMoeF32Half(
                b.residual.Data(), in.ed.Data(), in.wd.Data(), in.sd.Data(),
                in.gd.Data(), Inputs::stride, in.used, in.id.Data(), in.parts,
                gamma, b.norm.Data(), n, hidden, Inputs::streams, Inputs::eps,
                nullptr, half_out),
            "Invalid MoE pair accepted");
    Require(!q::HcCombineF32Half(b.residual.Data(), in.sd.Data(), in.id.Data(),
                                 in.parts, gamma, b.norm.Data(), half_out, n,
                                 hidden, Inputs::streams, Inputs::eps, nullptr),
            "Invalid ordinary pair accepted");
  }
  Hip(hipDeviceSynchronize());
  Require(Exact(residual, b.residual.Read()) && Exact(norm, b.norm.Read()) &&
              HalfExact(half, b.half.Read()),
          "Refused dispatch modified output");
  in.CheckInputs();
  weights.Check();
  return pass;
}

static bool LibraryBench(q::BlasLt &blas, bool moe, unsigned tokens = 2048) {
  constexpr unsigned iterations = 16;
  Inputs in(tokens, 10, 3, 0);
  Weights weights(iterations); // Rotate 100 MiB; preserve original F16 layout.
  State a(tokens), b(tokens);
  for (State *state : {&a, &b})
    for (bool paired : {false, true}) {
      Upload(state->residual.Data(), in.residual);
      for (unsigned i = 0; i < iterations; ++i)
        Require(LibraryLaunch(blas, in, *state, weights, i, moe, paired),
                "Warmup refused");
    }
  Hip(hipDeviceSynchronize());
  hipEvent_t begin, end;
  std::cout << std::defaultfloat << std::setprecision(12);
  Hip(hipEventCreate(&begin));
  Hip(hipEventCreate(&end));
  bool pass = true;
  for (unsigned rep = 0; rep < 5; ++rep) {
    State *state[2] = {&a, &b};
    if (rep % 2)
      std::swap(state[0], state[1]);
    for (unsigned arm = 0; arm < 2; ++arm) {
      const bool paired = (rep + arm) % 2 != 0;
      Upload(state[paired]->residual.Data(), in.residual);
      Hip(hipEventRecord(begin, nullptr));
      for (unsigned i = 0; i < iterations; ++i)
        Require(
            LibraryLaunch(blas, in, *state[paired], weights, i, moe, paired),
            "Timed dispatch refused");
      Hip(hipEventRecord(end, nullptr));
      Hip(hipEventSynchronize(end));
      Hip(hipGetLastError());
      float elapsed = 0;
      Hip(hipEventElapsedTime(&elapsed, begin, end));
      std::cout
          << "{\"event\":\"hc_library_norm_microbench\",\"moe\":" << moe
          << ",\"paired\":" << paired << ",\"rep\":" << rep
          << ",\"allocation\":" << (state[paired] == &a ? 0 : 1)
          << ",\"tokens\":" << tokens << ",\"iterations\":" << iterations
          << ",\"weight_bytes\":" << weights.values.size() * sizeof(__half)
          << ",\"consumer\":\"hipblaslt-7526\",\"microseconds_per_iteration\":"
          << double(elapsed) * 1000 / iterations << "}\n";
    }
    pass = Compare(in, *state[0], *state[1], weights, iterations - 1,
                   "hc-library-norm-bench-n" + std::to_string(tokens) +
                       "-moe" + std::to_string(moe) + "-rep" +
                       std::to_string(rep),
                   false, false, moe) &&
           pass;
  }
  in.CheckInputs();
  weights.Check();
  Hip(hipEventDestroy(begin));
  Hip(hipEventDestroy(end));
  return pass;
}

int main(int argc, char **argv) {
  try {
    Require(argc == 2 && (std::string(argv[1]) == "bench" ||
                         std::string(argv[1]) == "ragged"),
            "Expected bench or ragged");
    const bool ragged = std::string(argv[1]) == "ragged";
    Hip(hipSetDevice(0));
    std::cout << std::setprecision(12) << std::boolalpha;
    std::string error;
    auto blas = q::BlasLt::Create(nullptr, &error);
    Require(bool(blas), error.c_str());
    bool pass = true;
    for (bool moe : {false, true}) {
      pass = LibraryCase(*blas, 96, 0, moe) && pass;
      pass = LibraryCase(*blas, 97, 1, moe) && pass;
      pass = LibraryCase(*blas, 129, 2, moe) && pass;
      pass = LibraryCase(*blas, 2048, 0, moe) && pass;
      pass = LibraryCase(*blas, 2048, 1, moe) && pass;
      if (ragged) {
        pass = LibraryCase(*blas, 2040, 0, moe) && pass;
        pass = LibraryCase(*blas, 2047, 1, moe) && pass;
      }
    }
    for (bool moe : {false, true}) {
      if (ragged)
        pass = LibraryBench(*blas, moe, 2040) && pass;
      pass = LibraryBench(*blas, moe) && pass;
    }
    std::cout << (pass ? "PASS" : "FAIL")
              << " synthetic HC library cycle; no model inference\n";
    return pass ? 0 : 1;
  } catch (const std::exception &error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
