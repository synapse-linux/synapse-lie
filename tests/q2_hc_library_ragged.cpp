// SPDX-License-Identifier: MIT
// Synthetic complete cycles: unchanged norm/narrowing, native or library down.
#define Q2_HC_DEFERRED_CHECKS 1
#include "q2_hc_sequence.cpp"
#include "src/models/qwen38_flash_next/kernels/rocm/blaslt.hpp"

static bool RaggedDown(q::BlasLt &blas, State &state, Weights &weights,
                       unsigned index, unsigned tokens, bool library) {
  if (!library)
    return q::UnquantizedF16Gemm(weights.Data(index), state.half.Data(),
                                 state.down.Data(), tokens, kRows, kColumns,
                                 nullptr);
  std::string error;
  if (blas.Gemm(weights.Data(index), state.half.Data(), state.down.Data(),
                HIP_R_16F, kRows, tokens, kColumns, &error))
    return true;
  if (error != "no workspace-free hipBLASLt kernel for the GEMM shape")
    throw std::runtime_error(error);
  std::cout << "{\"event\":\"ragged_unsupported\",\"tokens\":" << tokens
            << ",\"algorithm\":7526}\n";
  return false;
}

static bool RaggedLaunch(q::BlasLt &blas, Inputs &in, State &state,
                         Weights &weights, unsigned index, bool moe,
                         bool library) {
  if (moe) {
    Require(in.Fused(state.residual, state.norm, true), "MoE control refused");
  } else {
    q::HcCombine(state.residual.Data(), in.sd.Data(), in.id.Data(), in.parts,
                 in.nd.Data(), state.norm.Data(), in.tokens, Inputs::hidden,
                 Inputs::streams, Inputs::eps, nullptr);
  }
  q::NarrowActivations(state.norm.Data(), state.half.Data(), false,
                       state.norm.size, nullptr);
  return RaggedDown(blas, state, weights, index, in.tokens, library);
}

static bool RaggedCase(q::BlasLt &blas, unsigned tokens, unsigned pattern,
                       bool moe) {
  Inputs in(tokens, 10, 3, pattern);
  Weights weights(1);
  State reference(tokens), candidate(tokens);
  Upload(reference.residual.Data(), in.residual);
  Upload(candidate.residual.Data(), in.residual);
  Require(RaggedLaunch(blas, in, reference, weights, 0, moe, false),
          "Native dispatch refused");
  const bool supported =
      RaggedLaunch(blas, in, candidate, weights, 0, moe, true);
  Hip(hipGetLastError());
  Hip(hipDeviceSynchronize());
  if (!supported)
    return false;
  std::cout << std::defaultfloat << std::setprecision(12);
  const std::string label = "ragged-n" + std::to_string(tokens) + "-p" +
                            std::to_string(pattern) + "-moe" +
                            std::to_string(moe);
  // Both consumers retain the same independent FP64 limits. Compare also
  // checks all norm/half/residual bytes and every output guard/finite value.
  const bool native_pass = Compare(in, reference, reference, weights, 0,
                                   label + "-native", false, true, moe);
  const bool candidate_pass = Compare(in, reference, candidate, weights, 0,
                                      label + "-library", false, true, moe);
  Require(Exact(reference.residual.Read(), candidate.residual.Read()) &&
              Exact(reference.norm.Read(), candidate.norm.Read()) &&
              HalfExact(reference.half.Read(), candidate.half.Read()),
          "Unchanged producer output differs");
  Save(label + "-native.f32", reference.down.Read());
  Save(label + "-library.f32", candidate.down.Read());
  in.CheckInputs();
  weights.Check();
  return native_pass && candidate_pass;
}

static bool RepeatedRow(q::BlasLt &blas, unsigned tokens) {
  State reference(tokens), candidate(tokens);
  Weights weights(1);
  std::vector<__half> input(std::size_t(tokens) * kColumns);
  Random rng{879};
  for (unsigned k = 0; k < kColumns; ++k)
    input[k] = __float2half_rn(rng.Next());
  for (unsigned t = 1; t < tokens; ++t)
    std::copy_n(input.data(), kColumns,
                input.data() + std::size_t(t) * kColumns);
  for (State *state : {&reference, &candidate})
    Hip(hipMemcpy(state->half.Data(), input.data(),
                  input.size() * sizeof(__half), hipMemcpyHostToDevice));
  Require(RaggedDown(blas, reference, weights, 0, tokens, false),
          "Native repeated-row dispatch refused");
  if (!RaggedDown(blas, candidate, weights, 0, tokens, true))
    return false;
  Hip(hipGetLastError());
  Hip(hipDeviceSynchronize());
  bool pass = true;
  for (auto [state, library] :
       {std::pair{&reference, false}, std::pair{&candidate, true}}) {
    const auto output = state->down.Read();
    unsigned changed = 0;
    double maximum = 0;
    for (unsigned t = 1; t < tokens; ++t) {
      const float *row = output.data() + std::size_t(t) * kRows;
      changed += std::memcmp(row, output.data(), kRows * sizeof(float)) != 0;
      for (unsigned m = 0; m < kRows; ++m)
        maximum = std::max(maximum, std::abs(double(row[m]) - output[m]));
    }
    const std::string label = "ragged-repeat-n" + std::to_string(tokens) +
                              (library ? "-library" : "-native");
    Save(label + ".f32", output);
    Require(HalfExact(state->half.Read(), input), "Repeated-row input changed");
    std::cout << std::setprecision(12)
              << "{\"event\":\"ragged_position\",\"tokens\":" << tokens
              << ",\"library\":" << library << ",\"changed_rows\":" << changed
              << ",\"max_absolute_delta\":" << maximum << ",\"sha256\":\""
              << Digest(output) << "\"}\n";
    pass = changed == 0 && pass;
  }
  weights.Check();
  return pass;
}

static bool RaggedBench(q::BlasLt &blas, unsigned tokens, bool moe) {
  constexpr unsigned iterations = 16;
  Inputs in(tokens, 10, 3, 0);
  Weights weights(iterations); // 100 MiB, original F16 layout and hipMalloc.
  State a(tokens), b(tokens);
  for (State *state : {&a, &b}) {
    for (bool library : {false, true}) {
      Upload(state->residual.Data(), in.residual);
      for (unsigned i = 0; i < iterations; ++i)
        if (!RaggedLaunch(blas, in, *state, weights, i, moe, library))
          return false;
    }
  }
  Hip(hipDeviceSynchronize());
  hipEvent_t begin, end;
  Hip(hipEventCreate(&begin));
  Hip(hipEventCreate(&end));
  bool pass = true;
  for (unsigned rep = 0; rep < 5; ++rep) {
    State *states[2] = {&a, &b};
    if (rep % 2)
      std::swap(states[0], states[1]);
    for (unsigned arm = 0; arm < 2; ++arm) {
      const bool library = (rep + arm) % 2 != 0;
      State &state = *states[library];
      Upload(state.residual.Data(), in.residual);
      Hip(hipEventRecord(begin, nullptr));
      for (unsigned i = 0; i < iterations; ++i)
        Require(RaggedLaunch(blas, in, state, weights, i, moe, library),
                "Warmed dispatch refused");
      Hip(hipEventRecord(end, nullptr));
      Hip(hipEventSynchronize(end));
      Hip(hipGetLastError());
      float elapsed = 0;
      Hip(hipEventElapsedTime(&elapsed, begin, end));
      std::cout << std::defaultfloat << std::setprecision(12)
                << "{\"event\":\"ragged_microbench\",\"tokens\":" << tokens
                << ",\"moe\":" << moe << ",\"library\":" << library
                << ",\"rep\":" << rep
                << ",\"allocation\":" << (&state == &a ? 0 : 1)
                << ",\"iterations\":" << iterations << ",\"weight_bytes\":"
                << weights.values.size() * sizeof(__half)
                << ",\"microseconds_per_iteration\":"
                << double(elapsed) * 1000 / iterations << "}\n";
    }
    pass = Compare(in, *states[0], *states[1], weights, iterations - 1,
                   "ragged-bench-n" + std::to_string(tokens) + "-moe" +
                       std::to_string(moe) + "-rep" + std::to_string(rep),
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
    // Reused fixture also defines standalone helpers; do not run their benches.
    static_cast<void>(&Case);
    static_cast<void>(&Bench);
    Require(argc == 2 && std::string(argv[1]) == "bench", "Expected bench");
    Hip(hipSetDevice(0));
    std::cout << std::setprecision(12) << std::boolalpha;
    std::string error;
    auto blas = q::BlasLt::Create(nullptr, &error);
    Require(bool(blas), error.c_str());
    bool pass = true;
    for (bool moe : {false, true}) {
      for (unsigned tokens : {96u, 97u, 129u, 502u, 2042u, 2047u, 2048u})
        pass = RaggedCase(*blas, tokens, 0, moe) && pass;
      pass = RaggedCase(*blas, 2042, 1, moe) && pass;
    }
    for (unsigned tokens : {97u, 2042u, 2047u, 2048u})
      pass = RepeatedRow(*blas, tokens) && pass;
    // Numerical failures remain failures, but do not suppress performance data.
    for (unsigned tokens : {502u, 2042u, 2047u, 2048u})
      for (bool moe : {false, true})
        pass = RaggedBench(*blas, tokens, moe) && pass;
    std::cout << "{\"event\":\"ragged_complete\",\"numerical_pass\":" << pass
              << ",\"model_inference\":false}\n";
    return pass ? 0 : 1;
  } catch (const std::exception &error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
