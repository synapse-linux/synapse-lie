// SPDX-License-Identifier: MIT
// Complete synthetic HC cycles, including the last consumers of the F32 norm.
#define Q2_HC_DEFERRED_CHECKS 1
#include "q2_hc_sequence.cpp"

struct PipelineState {
  State prefix;
  Output scales, mixed, inject;
  HalfOutput low;
  explicit PipelineState(unsigned n)
      : prefix(n), scales(std::size_t(n) * 4),
        mixed(std::size_t(n) * Inputs::hidden),
        inject(std::size_t(n) * 4 * q::HcInjectPartsVec4(Inputs::hidden)),
        low(std::size_t(n) * kRows) {}
};

static void Reset(Inputs& in, PipelineState& state) {
  Require(in.parts == q::HcInjectPartsVec4(Inputs::hidden), "Partial layout differs");
  Upload(state.prefix.residual.Data(), in.residual);
  Upload(state.inject.Data(), in.inject);
}

static bool Prefix(Inputs& in, PipelineState& state, Weights& weights,
                   unsigned index, bool moe, bool deferred) {
  State& p = state.prefix;
  if (moe) {
    const bool ok = deferred ? q::HcCombineMoeDeferredNorm(
        p.residual.Data(), in.ed.Data(), in.wd.Data(), in.sd.Data(), in.gd.Data(),
        Inputs::stride, in.used, state.inject.Data(), in.parts, in.nd.Data(),
        state.scales.Data(), in.tokens, Inputs::hidden, Inputs::streams,
        Inputs::eps, nullptr, p.half.Data()) : q::HcCombineMoeF32(
        p.residual.Data(), in.ed.Data(), in.wd.Data(), in.sd.Data(), in.gd.Data(),
        Inputs::stride, in.used, state.inject.Data(), in.parts, in.nd.Data(),
        p.norm.Data(), in.tokens, Inputs::hidden, Inputs::streams, Inputs::eps, nullptr);
    if (!ok) return false;
  } else if (deferred) {
    if (!q::HcCombineDeferredNorm(p.residual.Data(), in.sd.Data(),
          state.inject.Data(), in.parts, in.nd.Data(), state.scales.Data(),
          p.half.Data(), in.tokens, Inputs::hidden, Inputs::streams,
          Inputs::eps, nullptr)) return false;
  } else {
    q::HcCombine(p.residual.Data(), in.sd.Data(), state.inject.Data(), in.parts,
        in.nd.Data(), p.norm.Data(), in.tokens, Inputs::hidden, Inputs::streams,
        Inputs::eps, nullptr);
  }
  if (!deferred)
    q::NarrowActivations(p.norm.Data(), p.half.Data(), false, p.norm.size, nullptr);
  return q::UnquantizedF16Gemm(weights.Data(index), p.half.Data(), p.down.Data(),
                              in.tokens, kRows, kColumns, nullptr);
}

// Inputs::gamma contains one norm row. Injection requires four separate rows,
// so use a dedicated immutable allocation, never read beyond that norm row.
struct InjectWeights {
  std::vector<float> values;
  Device device;
  InjectWeights() : values(4 * kColumns), device(values.size() * sizeof(float)) {
    Random rng{2389};
    for (float& value : values) value = __half2float(__float2half_rn(rng.Next() / 64));
    Upload(device.Data(), values);
  }
};

static bool Mix(Inputs& in, PipelineState& state, Weights& up,
                InjectWeights& inject, unsigned index, bool deferred,
                bool injection = true) {
  State& p = state.prefix;
  q::SiluScale(p.down.Data(), .25f, std::size_t(in.tokens) * kRows, nullptr);
  q::NarrowActivations(p.down.Data(), state.low.Data(), false,
                       std::size_t(in.tokens) * kRows, nullptr);
  const float* iw = injection ? inject.device.Data() : nullptr;
  float* io = injection ? state.inject.Data() : nullptr;
  if (deferred)
    return q::HcMixDeferredNorm(up.Data(index), state.low.Data(), p.residual.Data(),
        iw, state.mixed.Data(), p.half.Data(), io, in.tokens, Inputs::hidden,
        kRows, nullptr, state.scales.Data(), in.nd.Data());
  return q::HcMixRawF16Gemm(up.Data(index), state.low.Data(), p.norm.Data(),
      iw, state.mixed.Data(), p.half.Data(), io, in.tokens, Inputs::hidden, kRows, nullptr);
}

static bool ConsumerOracle(Inputs& in, PipelineState& reference,
    PipelineState& candidate, Weights& up, InjectWeights& inject,
    unsigned index, bool injection, const std::string& label) {
  const auto xn = reference.prefix.norm.Read();
  const auto low = reference.low.Read();
  const auto mixed = candidate.mixed.Read(), partial = candidate.inject.Read();
  Error me, ie;
  for (unsigned t : Edges(in.tokens, 128)) {
    for (unsigned h : Edges(Inputs::hidden, 64)) {
      double value = 0;
      for (unsigned s = 0; s < 4; ++s) {
        const unsigned row = s * Inputs::hidden + h;
        const auto offset = std::size_t(index) * kRows * kColumns + std::size_t(row) * kRows;
        double gate = 0;
        for (unsigned k = 0; k < kRows; ++k)
          gate += double(__half2float(up.values[offset + k])) *
                  double(__half2float(low[std::size_t(t) * kRows + k]));
        value += double(xn[std::size_t(t) * kColumns + row]) / (1.0 + std::exp(-gate));
      }
      me.Add(value * .25, mixed[std::size_t(t) * Inputs::hidden + h]);
    }
    if (injection)
      for (unsigned out = 0; out < 4; ++out)
        for (unsigned part = 0; part < in.parts; ++part) {
          double value = 0;
          for (unsigned s = 0; s < 4; ++s)
            for (unsigned h = part * 1024; h < std::min(Inputs::hidden, (part + 1) * 1024); ++h)
              value += double(inject.values[out * kColumns + s * Inputs::hidden + h]) *
                       double(xn[std::size_t(t) * kColumns + s * Inputs::hidden + h]);
          ie.Add(value, partial[(std::size_t(t) * 4 + out) * in.parts + part]);
        }
  }
  const bool pass = me.Pass() && (!injection || ie.Pass());
  std::cout << "{\"event\":\"hc_deferred_consumer_oracle\",\"label\":\"" << label
            << "\",\"mix_values\":" << me.values << ",\"mix_rrms\":" << me.Rms()
            << ",\"mix_peak_scaled\":" << me.Scaled() << ",\"inject_values\":" << ie.values
            << ",\"inject_rrms\":" << ie.Rms() << ",\"inject_peak_scaled\":" << ie.Scaled()
            << ",\"pass\":" << pass << "}\n";
  return pass;
}

static bool Replay(Inputs& in, PipelineState& ref, PipelineState& cand,
                   const std::string& label, bool save) {
  Require(q::ReconstructHcNorm(cand.prefix.residual.Data(), cand.scales.Data(),
      in.nd.Data(), cand.prefix.norm.Data(), in.tokens, nullptr), "Reconstruction refused");
  Hip(hipGetLastError());
  Hip(hipDeviceSynchronize());
  bool exact = true;
  for (const auto& item : std::vector<std::pair<std::string, std::pair<Output*, Output*>>>{
      {"residual", {&ref.prefix.residual, &cand.prefix.residual}},
      {"norm", {&ref.prefix.norm, &cand.prefix.norm}},
      {"silu_down", {&ref.prefix.down, &cand.prefix.down}},
      {"mixed", {&ref.mixed, &cand.mixed}}, {"inject", {&ref.inject, &cand.inject}}}) {
    const auto a = item.second.first->Read(), b = item.second.second->Read();
    exact = Exact(a, b) && exact;
    std::cout << "{\"event\":\"hc_deferred_buffer\",\"label\":\"" << label
              << "\",\"buffer\":\"" << item.first << "\",\"exact\":" << Exact(a, b)
              << ",\"reference_sha256\":\"" << Digest(a)
              << "\",\"candidate_sha256\":\"" << Digest(b) << "\"}\n";
    if (save && (item.first == "mixed" || item.first == "inject")) {
      Save(label + "-reference-" + item.first + ".f32", a);
      Save(label + "-candidate-" + item.first + ".f32", b);
    }
  }
  const auto ah = ref.prefix.half.Read(), bh = cand.prefix.half.Read();
  const auto al = ref.low.Read(), bl = cand.low.Read();
  bool scalar = true;
  const auto mixed = ref.mixed.Read(), norm = ref.prefix.norm.Read();
  for (std::size_t i = 0; i < bh.size(); ++i) {
    const __half expected = __float2half_rn(i < mixed.size() ? mixed[i] : norm[i]);
    scalar &= std::memcmp(&expected, &bh[i], sizeof(__half)) == 0;
  }
  exact = exact && HalfExact(ah, bh) && HalfExact(al, bl) && scalar;
  std::cout << "{\"event\":\"hc_deferred_replay\",\"label\":\"" << label
            << "\",\"half_exact\":" << HalfExact(ah, bh) << ",\"low_exact\":" << HalfExact(al, bl)
            << ",\"scalar_half_exact\":" << scalar << ",\"reference_half_sha256\":\"" << Digest(ah)
            << "\",\"candidate_half_sha256\":\"" << Digest(bh)
            << "\",\"reference_low_sha256\":\"" << Digest(al)
            << "\",\"candidate_low_sha256\":\"" << Digest(bl)
            << "\",\"exact\":" << exact << "}\n";
  cand.scales.Read();
  return exact;
}

static bool DeferredCase(unsigned tokens, unsigned pattern, bool moe, bool injection = true) {
  Inputs in(tokens, 8, 3, pattern);
  Weights down(1), up(1);
  InjectWeights iw;
  PipelineState ref(tokens), cand(tokens);
  Reset(in, ref); Reset(in, cand);
  Require(Prefix(in, ref, down, 0, moe, false), "Reference prefix refused");
  Require(Prefix(in, cand, down, 0, moe, true), "Deferred prefix refused");
  Hip(hipDeviceSynchronize());
  cand.prefix.norm.Read(false);  // The producer must not materialize F32 rows.
  const auto scales = cand.scales.Read();
  Require(q::ReconstructHcNorm(cand.prefix.residual.Data(), cand.scales.Data(),
      in.nd.Data(), cand.prefix.norm.Data(), tokens, nullptr), "Reconstruction refused");
  Hip(hipDeviceSynchronize());
  const std::string label = "hc-deferred-n" + std::to_string(tokens) + "-p" +
      std::to_string(pattern) + "-moe" + std::to_string(moe) + "-i" + std::to_string(injection);
  bool pass = Compare(in, ref.prefix, cand.prefix, down, 0, label,
                      tokens == 97, true, moe);
  Require(Mix(in, ref, up, iw, 0, false, injection), "Reference mix refused");
  Require(Mix(in, cand, up, iw, 0, true, injection), "Deferred mix refused");
  Hip(hipGetLastError()); Hip(hipDeviceSynchronize());
  Require(Exact(scales, cand.scales.Read()), "Consumer overwrote normalization scales");
  pass = Replay(in, ref, cand, label, true) && pass;
  pass = ConsumerOracle(in, ref, cand, up, iw, 0, injection, label) && pass;
  for (unsigned missing = 0; missing < 2; ++missing)
    Require(!q::HcMixDeferredNorm(up.Data(0), cand.low.Data(), cand.prefix.residual.Data(),
        iw.device.Data(), cand.mixed.Data(), cand.prefix.half.Data(), cand.inject.Data(),
        tokens, Inputs::hidden, kRows, nullptr,
        missing == 0 ? nullptr : cand.scales.Data(), missing == 1 ? nullptr : in.nd.Data()),
        "Missing reconstruction input accepted");
  Hip(hipDeviceSynchronize());
  pass = Replay(in, ref, cand, label + "-after-refusal", false) && pass;
  in.CheckInputs(); down.Check(); up.Check(); CheckInput(iw.device, iw.values);
  return pass;
}

static bool DeferredBench(bool moe) {
  constexpr unsigned tokens = 2048, iterations = 16;
  Inputs in(tokens, 8, 3, 0);
  Weights down(iterations), up(iterations);
  InjectWeights iw;
  PipelineState a(tokens), b(tokens);
  auto launch = [&](PipelineState& state, unsigned index, bool deferred) {
    Require(Prefix(in, state, down, index, moe, deferred), "Benchmark prefix refused");
    Require(Mix(in, state, up, iw, index, deferred), "Benchmark mix refused");
  };
  for (PipelineState* state : {&a, &b})
    for (bool deferred : {false, true}) {
      Reset(in, *state);
      for (unsigned i = 0; i < iterations; ++i) launch(*state, i, deferred);
    }
  Hip(hipDeviceSynchronize());
  hipEvent_t begin, end;
  Hip(hipEventCreate(&begin)); Hip(hipEventCreate(&end));
  bool pass = true;
  for (unsigned rep = 0; rep < 5; ++rep) {
    PipelineState* state[2] = {&a, &b};
    if (rep % 2) std::swap(state[0], state[1]);
    for (unsigned arm = 0; arm < 2; ++arm) {
      const bool deferred = (rep + arm) % 2 != 0;
      Reset(in, *state[deferred]);
      Hip(hipEventRecord(begin, nullptr));
      for (unsigned i = 0; i < iterations; ++i) launch(*state[deferred], i, deferred);
      Hip(hipEventRecord(end, nullptr)); Hip(hipEventSynchronize(end));
      Hip(hipGetLastError());
      float elapsed = 0; Hip(hipEventElapsedTime(&elapsed, begin, end));
      std::cout << "{\"event\":\"hc_deferred_microbench\",\"moe\":" << moe
                << ",\"deferred\":" << deferred << ",\"rep\":" << rep
                << ",\"allocation\":" << (state[deferred] == &a ? 0 : 1)
                << ",\"tokens\":" << tokens << ",\"iterations\":" << iterations
                << ",\"weight_bytes\":" << (down.values.size() + up.values.size()) * sizeof(__half)
                << ",\"microseconds_per_iteration\":" << double(elapsed) * 1000 / iterations << "}\n";
    }
    const std::string label = "hc-deferred-bench-moe" + std::to_string(moe) + "-rep" + std::to_string(rep);
    pass = Replay(in, *state[0], *state[1], label, false) && pass;
    pass = ConsumerOracle(in, *state[0], *state[1], up, iw, iterations - 1, true, label) && pass;
  }
  in.CheckInputs(); down.Check(); up.Check(); CheckInput(iw.device, iw.values);
  Hip(hipEventDestroy(begin)); Hip(hipEventDestroy(end));
  return pass;
}

int main(int argc, char** argv) {
  try {
    Require(argc == 2 && std::string(argv[1]) == "bench", "Expected bench");
    Hip(hipSetDevice(0));
    std::cout << std::setprecision(12) << std::boolalpha;
    bool pass = true;
    for (bool moe : {false, true}) {
      pass = DeferredCase(96, 0, moe) && pass;
      pass = DeferredCase(97, 1, moe) && pass;
      pass = DeferredCase(129, 2, moe) && pass;
      pass = DeferredCase(257, 0, moe, false) && pass;
    }
    for (bool moe : {false, true}) pass = DeferredBench(moe) && pass;
    std::cout << (pass ? "PASS" : "FAIL") << " synthetic deferred HC norm; no model inference\n";
    return pass ? 0 : 1;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n'; return 1;
  }
}
