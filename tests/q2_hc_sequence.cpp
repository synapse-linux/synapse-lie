// SPDX-License-Identifier: MIT
// Synthetic producer/consumer checks; no CPU model forward or serving claim.
#define Q2_HC_SEQUENCE_CHECKS 1
#include "q2_hc_norm_half.cpp"

#include <openssl/sha.h>
#include <set>
#include <sstream>

static constexpr unsigned kColumns = Inputs::hidden * Inputs::streams;
static constexpr unsigned kRows = 320;

template<typename T>
static std::string Digest(const std::vector<T>& values) {
  unsigned char hash[SHA256_DIGEST_LENGTH];
  Require(SHA256(reinterpret_cast<const unsigned char*>(values.data()),
                  values.size() * sizeof(T), hash) != nullptr,
          "Cannot hash full output");
  std::ostringstream out;
  for (unsigned char byte : hash)
    out << std::hex << std::setfill('0') << std::setw(2) << unsigned(byte);
  return out.str();
}

struct Weights {
  const unsigned count;
  std::vector<__half> values;
  Device device;
  explicit Weights(unsigned copies)
      : count(copies), values(std::size_t(copies) * kRows * kColumns),
        device(values.size() * sizeof(__half)) {
    Random rng{1967};
    for (__half& value : values)
      value = __float2half_rn(rng.Next() / 64.0f);
    Hip(hipMemcpy(device.data, values.data(), values.size() * sizeof(__half),
                  hipMemcpyHostToDevice));
  }
  const __half* Data(unsigned index) {
    Require(index < count, "Weight index out of range");
    return static_cast<const __half*>(device.data) +
           std::size_t(index) * kRows * kColumns;
  }
  void Check() {
    std::vector<__half> copy(values.size());
    Hip(hipMemcpy(copy.data(), device.data, copy.size() * sizeof(__half),
                  hipMemcpyDeviceToHost));
    Require(HalfExact(copy, values), "Projection weights changed");
  }
};

struct State {
  Output residual, norm, down;
  HalfOutput half;
  explicit State(unsigned tokens)
      : residual(std::size_t(tokens) * kColumns),
        norm(std::size_t(tokens) * kColumns),
        down(std::size_t(tokens) * kRows), half(std::size_t(tokens) * kColumns) {}
};

static bool Launch(Inputs& in, State& state, Weights& weights, unsigned index,
                    bool moe, bool paired) {
  if (moe) {
    const bool ok = paired ? q::HcCombineMoeF32Half(
        state.residual.Data(), in.ed.Data(), in.wd.Data(), in.sd.Data(),
        in.gd.Data(), Inputs::stride, in.used, in.id.Data(), in.parts,
        in.nd.Data(), state.norm.Data(), in.tokens, Inputs::hidden,
        Inputs::streams, Inputs::eps, nullptr, state.half.Data()) :
        in.Fused(state.residual, state.norm, true);
    if (!ok) return false;
  } else if (paired) {
    if (!q::HcCombineF32Half(state.residual.Data(), in.sd.Data(), in.id.Data(),
          in.parts, in.nd.Data(), state.norm.Data(), state.half.Data(),
          in.tokens, Inputs::hidden, Inputs::streams, Inputs::eps, nullptr))
      return false;
  } else {
    q::HcCombine(state.residual.Data(), in.sd.Data(), in.id.Data(), in.parts,
        in.nd.Data(), state.norm.Data(), in.tokens, Inputs::hidden,
        Inputs::streams, Inputs::eps, nullptr);
  }
  if (!paired)
    q::NarrowActivations(state.norm.Data(), state.half.Data(), false,
                        state.norm.size, nullptr);
  return q::UnquantizedF16Gemm(weights.Data(index), state.half.Data(),
      state.down.Data(), in.tokens, kRows, kColumns, nullptr);
}

static std::set<unsigned> Edges(unsigned count, unsigned tile) {
  std::set<unsigned> result{0, count - 1};
  for (unsigned base = 0; base < count; base += tile)
    for (unsigned delta : {0u, 1u, 15u, 16u, 31u, 32u, 63u, 64u, 127u})
      if (delta < tile && base + delta < count) result.insert(base + delta);
  return result;
}

// Independent FP64 operator formula, including tiny inputs and full norm rows.
static bool NormOracle(const Inputs& in, bool moe,
                       const std::vector<float>& actual_res,
                       const std::vector<float>& actual_norm) {
  Error re, ne;
  std::vector<double> block(Inputs::hidden), residual(Inputs::hidden);
  for (unsigned t = 0; t < in.tokens; ++t) {
    const double gate = 1.0 / (1.0 + std::exp(-double(in.gate[t * Inputs::stride])));
    for (unsigned i = 0; i < Inputs::hidden; ++i) {
      double value = 0;
      if (moe) {
        for (unsigned e = 0; e < in.used; ++e)
          value += double(in.weights[t * in.used + e]) *
              double(in.experts[(std::size_t(t) * in.used + e) * Inputs::hidden + i]);
        value += gate * double(in.shared[std::size_t(t) * Inputs::hidden + i]);
      } else {
        value = in.shared[std::size_t(t) * Inputs::hidden + i];
      }
      block[i] = value;
    }
    for (unsigned s = 0; s < Inputs::streams; ++s) {
      double logit = 0, squares = 0;
      for (unsigned p = 0; p < in.parts; ++p)
        logit += in.inject[(std::size_t(t) * Inputs::streams + s) * in.parts + p];
      const double weight = 2.0 / (1.0 + std::exp(-logit / Inputs::streams));
      const std::size_t base = std::size_t(t) * kColumns + s * Inputs::hidden;
      for (unsigned i = 0; i < Inputs::hidden; ++i) {
        residual[i] = double(in.residual[base + i]) + weight * block[i];
        squares += residual[i] * residual[i];
        re.Add(residual[i], actual_res[base + i]);
      }
      const double scale = 1.0 / std::sqrt(squares / Inputs::hidden + double(Inputs::eps));
      for (unsigned i = 0; i < Inputs::hidden; ++i)
        ne.Add(residual[i] * scale * double(in.gamma[s * Inputs::hidden + i]),
               actual_norm[base + i]);
    }
  }
  const bool pass = re.Pass() && ne.Pass();
  std::cout << "{\"event\":\"hc_sequence_norm_oracle\",\"tokens\":" << in.tokens
            << ",\"moe\":" << moe << ",\"res_rrms\":" << re.Rms()
            << ",\"norm_rrms\":" << ne.Rms() << ",\"res_peak_scaled\":" << re.Scaled()
            << ",\"norm_peak_scaled\":" << ne.Scaled() << ",\"pass\":" << pass << "}\n";
  return pass;
}

static bool Compare(Inputs& in, State& reference, State& paired,
                    Weights& weights, unsigned index, const std::string& label,
                    bool save, bool first, bool moe) {
  const auto ar = reference.residual.Read(), br = paired.residual.Read();
  const auto an = reference.norm.Read(), bn = paired.norm.Read();
  const auto ah = reference.half.Read(), bh = paired.half.Read();
  const auto ad = reference.down.Read(), bd = paired.down.Read();
  std::vector<__half> scalar(an.size());
  for (std::size_t i = 0; i < an.size(); ++i) scalar[i] = __float2half_rn(an[i]);
  Error down;
  for (unsigned t : Edges(in.tokens, 128))
    for (unsigned m : Edges(kRows, 64)) {
      double expected = 0;
      const auto base = (std::size_t(index) * kRows + m) * kColumns;
      for (unsigned k = 0; k < kColumns; ++k)
        expected += double(__half2float(weights.values[base + k])) *
                    double(__half2float(scalar[std::size_t(t) * kColumns + k]));
      down.Add(expected, bd[std::size_t(t) * kRows + m]);
    }
  const bool exact = Exact(ar, br) && Exact(an, bn) && HalfExact(ah, bh) &&
                     HalfExact(scalar, bh) && Exact(ad, bd);
  const bool norm_pass = !first || NormOracle(in, moe, br, bn);
  if (save) {
    Save(label + "-reference-norm.f32", an);
    Save(label + "-paired-norm.f32", bn);
    SaveHalf(label + "-reference-half.f16", ah);
    SaveHalf(label + "-paired-half.f16", bh);
    Save(label + "-reference-down.f32", ad);
    Save(label + "-paired-down.f32", bd);
  }
  std::cout << "{\"event\":\"hc_sequence_replay\",\"label\":\"" << label
            << "\",\"res_exact\":" << Exact(ar, br) << ",\"norm_exact\":" << Exact(an, bn)
            << ",\"half_exact\":" << HalfExact(ah, bh)
            << ",\"scalar_half_exact\":" << HalfExact(scalar, bh)
            << ",\"down_exact\":" << Exact(ad, bd)
            << ",\"down_rrms\":" << down.Rms() << ",\"down_peak_scaled\":" << down.Scaled()
            << ",\"down_oracle_values\":" << down.values
            << ",\"reference_res_sha256\":\"" << Digest(ar)
            << "\",\"paired_res_sha256\":\"" << Digest(br)
            << "\",\"reference_norm_sha256\":\"" << Digest(an)
            << "\",\"paired_norm_sha256\":\"" << Digest(bn)
            << "\",\"reference_half_sha256\":\"" << Digest(ah)
            << "\",\"paired_half_sha256\":\"" << Digest(bh)
            << "\",\"reference_down_sha256\":\"" << Digest(ad)
            << "\",\"paired_down_sha256\":\"" << Digest(bd)
            << "\",\"pass\":" << (exact && down.Pass() && norm_pass) << "}\n";
  return exact && down.Pass() && norm_pass;
}

static bool SequenceCase(unsigned tokens, unsigned pattern, bool moe) {
  Inputs in(tokens, 8, 3, pattern);
  Weights weights(1);
  State reference(tokens), paired(tokens);
  Upload(reference.residual.Data(), in.residual);
  Upload(paired.residual.Data(), in.residual);
  Require(Launch(in, reference, weights, 0, moe, false), "Reference dispatch refused");
  Require(Launch(in, paired, weights, 0, moe, true), "Paired dispatch refused");
  Hip(hipGetLastError());
  Hip(hipDeviceSynchronize());
  const std::string label = "hc-sequence-n" + std::to_string(tokens) +
      "-p" + std::to_string(pattern) + "-moe" + std::to_string(moe);
  const bool pass = Compare(in, reference, paired, weights, 0, label, true, true, moe);
  const auto residual = paired.residual.Read(), norm = paired.norm.Read();
  const auto half = paired.half.Read();
  for (unsigned invalid = 0; invalid < 4; ++invalid) {
    const auto* gamma = invalid == 0 ? nullptr : in.nd.Data();
    auto* half_out = invalid == 1 ? nullptr : paired.half.Data();
    const unsigned n = invalid == 2 ? 15 : tokens;
    const unsigned hidden = invalid == 3 ? Inputs::hidden - 1 : Inputs::hidden;
    Require(!q::HcCombineMoeF32Half(paired.residual.Data(), in.ed.Data(),
        in.wd.Data(), in.sd.Data(), in.gd.Data(), Inputs::stride, in.used,
        in.id.Data(), in.parts, gamma, paired.norm.Data(), n, hidden,
        Inputs::streams, Inputs::eps, nullptr, half_out), "Invalid MoE pair accepted");
    Require(!q::HcCombineF32Half(paired.residual.Data(), in.sd.Data(), in.id.Data(),
        in.parts, gamma, paired.norm.Data(), half_out, n, hidden,
        Inputs::streams, Inputs::eps, nullptr), "Invalid ordinary pair accepted");
  }
  Hip(hipDeviceSynchronize());
  Require(Exact(residual, paired.residual.Read()) && Exact(norm, paired.norm.Read()) &&
          HalfExact(half, paired.half.Read()), "Refused dispatch modified outputs");
  in.CheckInputs();
  weights.Check();
  return pass;
}

static bool SequenceBench(bool moe) {
  constexpr unsigned tokens = 2048, iterations = 16;
  Inputs in(tokens, 8, 3, 0);
  Weights weights(iterations);  // 100 MiB, hipMalloc as in production.
  State a(tokens), b(tokens);
  for (State* state : {&a, &b})
    for (bool paired : {false, true}) {
      Upload(state->residual.Data(), in.residual);
      for (unsigned i = 0; i < iterations; ++i)
        Require(Launch(in, *state, weights, i, moe, paired), "Warmup refused");
    }
  Hip(hipDeviceSynchronize());
  hipEvent_t begin, end;
  Hip(hipEventCreate(&begin));
  Hip(hipEventCreate(&end));
  bool pass = true;
  for (unsigned rep = 0; rep < 5; ++rep) {
    State* state[2] = {&a, &b};
    if (rep % 2) std::swap(state[0], state[1]);
    for (unsigned arm = 0; arm < 2; ++arm) {
      const bool paired = (rep + arm) % 2 != 0;
      Upload(state[paired]->residual.Data(), in.residual);
      Hip(hipEventRecord(begin, nullptr));
      for (unsigned i = 0; i < iterations; ++i)
        Require(Launch(in, *state[paired], weights, i, moe, paired), "Timed dispatch refused");
      Hip(hipEventRecord(end, nullptr));
      Hip(hipEventSynchronize(end));
      Hip(hipGetLastError());
      float elapsed = 0;
      Hip(hipEventElapsedTime(&elapsed, begin, end));
      std::cout << "{\"event\":\"hc_sequence_microbench\",\"moe\":" << moe
                << ",\"paired\":" << paired << ",\"rep\":" << rep
                << ",\"allocation\":" << (state[paired] == &a ? 0 : 1)
                << ",\"tokens\":" << tokens << ",\"iterations\":" << iterations
                << ",\"weight_bytes\":" << weights.values.size() * sizeof(__half)
                << ",\"microseconds_per_iteration\":" << double(elapsed) * 1000 / iterations
                << "}\n";
    }
    const auto label = "hc-sequence-bench-moe" + std::to_string(moe) + "-rep" + std::to_string(rep);
    pass = Compare(in, *state[0], *state[1], weights, iterations - 1,
                   label, false, false, moe) && pass;
  }
  in.CheckInputs();
  weights.Check();
  Hip(hipEventDestroy(begin));
  Hip(hipEventDestroy(end));
  return pass;
}

int main(int argc, char** argv) {
  try {
    Require(argc == 2 && (std::string(argv[1]) == "bench" || std::string(argv[1]) == "operators"),
            "Expected operators or bench");
    Hip(hipSetDevice(0));
    std::cout << std::setprecision(12) << std::boolalpha;
    bool pass = true;
    for (bool moe : {false, true}) {
      pass = SequenceCase(96, 0, moe) && pass;
      pass = SequenceCase(97, 1, moe) && pass;
      pass = SequenceCase(129, 2, moe) && pass;
    }
    if (std::string(argv[1]) == "bench")
      for (bool moe : {false, true}) pass = SequenceBench(moe) && pass;
    std::cout << (pass ? "PASS" : "FAIL") << " synthetic HC sequence; no model inference\n";
    return pass ? 0 : 1;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
