// SPDX-License-Identifier: MIT
// New native HC candidate and exact retained library recipe; no model forward.
#define main retained_library_norm_main
#include "q2_hc_library_norm.cpp"
#undef main
#include "experiments/q2_hc_blaslt_control.hpp"

static bool Producer(Inputs& in, State& state, bool moe) {
  if (moe)
    return q::HcCombineMoeF32Half(
        state.residual.Data(), in.ed.Data(), in.wd.Data(), in.sd.Data(),
        in.gd.Data(), Inputs::stride, in.used, in.id.Data(), in.parts,
        in.nd.Data(), state.norm.Data(), in.tokens, Inputs::hidden,
        Inputs::streams, Inputs::eps, nullptr, state.half.Data());
  return q::HcCombineF32Half(state.residual.Data(), in.sd.Data(), in.id.Data(),
                             in.parts, in.nd.Data(), state.norm.Data(),
                             state.half.Data(), in.tokens, Inputs::hidden,
                             Inputs::streams, Inputs::eps, nullptr);
}

template<class Blas>
static void Projection(Blas& blas, Inputs& in, State& state, Weights& weights,
                       unsigned index, bool moe, bool complete) {
  if (complete)
    Require(Producer(in, state, moe), "HC producer refused");
  std::string error;
  if (!blas.Gemm(weights.Data(index), state.half.Data(), state.down.Data(),
                 HIP_R_16F, kRows, in.tokens, kColumns, &error))
    throw std::runtime_error(error.empty() ? "HC consumer refused" : error);
}

static bool Check(q::HcBlasLtControl& control, q::BlasLt& native, unsigned n,
                  unsigned pattern, bool moe) {
  Inputs in(n, 8, 3, pattern);
  Weights weights(1);
  State reference(n), candidate(n);
  Upload(reference.residual.Data(), in.residual);
  Upload(candidate.residual.Data(), in.residual);
  Projection(control, in, reference, weights, 0, moe, true);
  Projection(native, in, candidate, weights, 0, moe, true);
  Hip(hipGetLastError());
  Hip(hipDeviceSynchronize());
  const std::string prefix = "hc-bk256-n" + std::to_string(n) + "-p" +
                             std::to_string(pattern) + "-moe" +
                             std::to_string(moe);
  // Retain strict full-byte differential and independent original FP64 limits.
  // A failed verdict never suppresses later component timing or other shapes.
  const bool candidate_pass = Compare(in, reference, candidate, weights, 0,
                                      prefix, n < 2048, true, moe);
  const bool control_pass = Compare(in, candidate, reference, weights, 0,
                                    prefix + "-reverse", false, true, moe);
  const auto before = candidate.down.Read();
  for (unsigned invalid = 0; invalid < 7; ++invalid) {
    const void* w = invalid == 0 ? nullptr : weights.Data(0);
    const __half* x = invalid == 1 ? nullptr : candidate.half.Data();
    float* out = invalid == 2 ? nullptr : candidate.down.Data();
    const std::size_t rows = invalid == 3 ? 95 : invalid == 4 ? 2049 : n;
    const std::size_t m = invalid == 5 ? 319 : kRows;
    const std::size_t k = invalid == 6 ? kColumns - 1 : kColumns;
    Require(!q::HcDownBk256F16Gemm(w, x, out, rows, m, k, nullptr),
            "Invalid native HC request accepted");
  }
  Hip(hipGetLastError());
  Hip(hipDeviceSynchronize());
  Require(Exact(before, candidate.down.Read()), "Refused request wrote output");
  in.CheckInputs();
  weights.Check();
  return candidate_pass && control_pass;
}

static bool Bench(q::HcBlasLtControl& control, q::BlasLt& native, bool moe) {
  constexpr unsigned n = 2048, iterations = 16;
  Inputs in(n, 10, 3, 0);
  Weights weights(iterations);  // 100 MiB original-F16 matrices beyond MALL.
  State reference(n), candidate(n);
  Upload(reference.residual.Data(), in.residual);
  Upload(candidate.residual.Data(), in.residual);
  for (unsigned i = 0; i < iterations; ++i) {
    Projection(control, in, reference, weights, i, moe, true);
    Projection(native, in, candidate, weights, i, moe, true);
  }
  Hip(hipDeviceSynchronize());
  hipEvent_t begin{}, end{};
  Hip(hipEventCreate(&begin));
  Hip(hipEventCreate(&end));
  for (bool complete : {false, true}) {
    for (unsigned rep = 0; rep < 7; ++rep) {
      for (unsigned order = 0; order < 2; ++order) {
        const bool is_native = (rep + order) % 2 != 0;
        State& state = is_native ? candidate : reference;
        Upload(state.residual.Data(), in.residual);
        Require(Producer(in, state, moe), "Warm producer refused");
        Hip(hipDeviceSynchronize());
        Hip(hipEventRecord(begin, nullptr));
        for (unsigned i = 0; i < iterations; ++i) {
          if (is_native)
            Projection(native, in, state, weights, i, moe, complete);
          else
            Projection(control, in, state, weights, i, moe, complete);
        }
        Hip(hipEventRecord(end, nullptr));
        Hip(hipEventSynchronize(end));
        Hip(hipGetLastError());
        float ms = 0;
        Hip(hipEventElapsedTime(&ms, begin, end));
        std::cout << "{\"event\":\"hc_bk256_timing\",\"moe\":" << moe
                  << ",\"complete\":" << complete << ",\"rep\":" << rep
                  << ",\"order\":" << order << ",\"native\":" << is_native
                  << ",\"warmup\":" << (rep < 2) << ",\"tokens\":" << n
                  << ",\"iterations\":" << iterations
                  << ",\"weight_bytes\":" << weights.values.size() * 2
                  << ",\"us_per_iteration\":" << double(ms) * 1000 / iterations
                  << "}\n";
      }
    }
  }
  const auto prefix = "hc-bk256-bench-moe" + std::to_string(moe);
  const bool pass = Compare(in, reference, candidate, weights, iterations - 1,
                            prefix, false, false, moe);
  Save(prefix + "-reference-down.f32", reference.down.Read());
  Save(prefix + "-native-down.f32", candidate.down.Read());
  in.CheckInputs();
  weights.Check();
  Hip(hipEventDestroy(begin));
  Hip(hipEventDestroy(end));
  return pass;
}

int main() {
  try {
    Hip(hipSetDevice(0));
    std::cout << std::setprecision(12) << std::boolalpha;
    std::string error;
    auto control = q::HcBlasLtControl::Create(nullptr, &error);
    Require(bool(control), error.c_str());
    auto native = q::BlasLt::Create(nullptr, &error);
    Require(bool(native), error.c_str());
    bool pass = true;
    for (bool moe : {false, true}) {
      for (const auto [n, pattern] : {std::pair{96u, 0u},
                                      {97u, 1u},
                                      {129u, 2u},
                                      {2048u, 0u},
                                      {2048u, 1u}})
        pass = Check(*control, *native, n, pattern, moe) && pass;
    }
    for (bool moe : {false, true})
      pass = Bench(*control, *native, moe) && pass;
    std::cout << (pass ? "PASS" : "FAIL")
              << " strict HC library replay; component timing retained; no "
                 "model inference\n";
    return pass ? 0 : 1;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
