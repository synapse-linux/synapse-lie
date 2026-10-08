// SPDX-License-Identifier: MIT
// Retain independent MoE/norm cases and compare complete F32/F16 frontiers.
#define Q2_HC_NORM_CHECKS 1
#include "q2_hc_moe_fused.cpp"

struct HalfOutput {
  static constexpr std::size_t guard = 32;
  const std::size_t size;
  Device device;
  explicit HalfOutput(std::size_t count)
      : size(count), device((count + 2 * guard) * sizeof(__half)) {
    Hip(hipMemset(device.data, 0xFF, (count + 2 * guard) * sizeof(__half)));
  }
  __half* Data() { return static_cast<__half*>(device.data) + guard; }
  std::vector<__half> Read() {
    std::vector<__half> host(size + 2 * guard);
    Hip(hipMemcpy(host.data(), device.data, host.size() * sizeof(__half),
                  hipMemcpyDeviceToHost));
    const auto* bytes = reinterpret_cast<const unsigned char*>(host.data());
    for (std::size_t i = 0; i < guard * sizeof(__half); ++i)
      Require(bytes[i] == 0xFF &&
                  bytes[(guard + size) * sizeof(__half) + i] == 0xFF,
              "Half output guard changed");
    std::vector<__half> result(host.begin() + guard,
                               host.begin() + guard + size);
    for (__half value : result)
      Require(std::isfinite(__half2float(value)),
              "Non-finite or unwritten half output");
    return result;
  }
};
static bool HalfExact(const std::vector<__half>& a,
                      const std::vector<__half>& b) {
  return a.size() == b.size() &&
         std::memcmp(a.data(), b.data(), a.size() * sizeof(__half)) == 0;
}
static void SaveHalf(const std::string& name,
                     const std::vector<__half>& values) {
  std::ofstream out("results/" + name, std::ios::binary);
  out.write(reinterpret_cast<const char*>(values.data()),
            values.size() * sizeof(__half));
  Require(bool(out), "Cannot save half norm output");
}

#ifndef Q2_HC_SEQUENCE_CHECKS
static bool LaunchNorm(Inputs& in, Output& res, Output& norm, HalfOutput& half,
                       Device& block, bool moe, bool candidate) {
  if (moe) {
    if (!q::HcCombineMoeF32(
            res.Data(), in.ed.Data(), in.wd.Data(), in.sd.Data(), in.gd.Data(),
            Inputs::stride, in.used, in.id.Data(), in.parts, in.nd.Data(),
            norm.Data(), in.tokens, Inputs::hidden, Inputs::streams,
            Inputs::eps, nullptr, candidate ? half.Data() : nullptr))
      return false;
  } else if (candidate) {
    if (!q::HcCombineF32Half(res.Data(), block.Data(), in.id.Data(), in.parts,
                             in.nd.Data(), norm.Data(), half.Data(), in.tokens,
                             Inputs::hidden, Inputs::streams, Inputs::eps,
                             nullptr))
      return false;
  } else {
    q::HcCombine(res.Data(), block.Data(), in.id.Data(), in.parts, in.nd.Data(),
                 norm.Data(), in.tokens, Inputs::hidden, Inputs::streams,
                 Inputs::eps, nullptr);
  }
  if (!candidate)
    q::NarrowActivations(norm.Data(), half.Data(), false, in.residual.size(),
                         nullptr);
  return true;
}

static bool NormCase(unsigned tokens, unsigned pattern, bool moe) {
  Inputs in(tokens, 8, 3, pattern);
  const auto count = in.residual.size();
  Output ref(count), fused(count), rn(count), fn(count);
  HalfOutput rh(count), fh(count);
  Device block(in.shared.size() * sizeof(float));
  Upload(block.Data(), in.shared);
  Upload(ref.Data(), in.residual);
  Upload(fused.Data(), in.residual);
  Require(LaunchNorm(in, ref, rn, rh, block, moe, false),
          "Reference dispatch refused");
  Require(LaunchNorm(in, fused, fn, fh, block, moe, true),
          "Fused norm dispatch refused");
  Hip(hipGetLastError());
  Hip(hipDeviceSynchronize());
  const auto a = ref.Read(), b = fused.Read(), an = rn.Read(), bn = fn.Read();
  const auto ah = rh.Read(), bh = fh.Read();
  in.CheckInputs();
  CheckInput(block, in.shared);
  // Independent scalar IEEE narrowing over every reference F32 norm value.
  std::vector<__half> expected(count);
  for (std::size_t i = 0; i < count; ++i)
    expected[i] = __float2half_rn(an[i]);
  const bool exact = Exact(a, b) && Exact(an, bn) && HalfExact(ah, bh) &&
                     HalfExact(expected, bh);
  const auto label = "hc-norm-n" + std::to_string(tokens) + "-p" +
                     std::to_string(pattern) + "-moe" + std::to_string(moe);
  Save(label + "-reference-res.f32", a);
  Save(label + "-fused-res.f32", b);
  Save(label + "-reference-norm.f32", an);
  Save(label + "-fused-norm.f32", bn);
  SaveHalf(label + "-reference.f16", ah);
  SaveHalf(label + "-fused.f16", bh);
  std::cout << "{\"event\":\"hc_norm_half\",\"label\":\"" << label
            << "\",\"values\":" << count
            << ",\"exact_residual\":" << std::boolalpha << Exact(a, b)
            << ",\"exact_norm\":" << Exact(an, bn)
            << ",\"exact_half\":" << HalfExact(ah, bh)
            << ",\"scalar_narrowing_exact\":" << HalfExact(expected, bh)
            << "}\n";
  for (unsigned n : {0u, 15u})
    Require(!q::HcCombineF32Half(fused.Data(), block.Data(), in.id.Data(),
                                 in.parts, in.nd.Data(), fn.Data(), fh.Data(),
                                 n, Inputs::hidden, 4, Inputs::eps, nullptr),
            "Accepted unsupported short batch");
  Require(!q::HcCombineF32Half(fused.Data(), block.Data(), in.id.Data(),
                               in.parts, nullptr, fn.Data(), fh.Data(), tokens,
                               Inputs::hidden, 4, Inputs::eps, nullptr),
          "Accepted missing gamma");
  Require(!q::HcCombineF32Half(fused.Data(), block.Data(), in.id.Data(),
                               in.parts, in.nd.Data(), fn.Data(), nullptr,
                               tokens, Inputs::hidden, 4, Inputs::eps, nullptr),
          "Accepted missing half output");
  Hip(hipDeviceSynchronize());
  Require(Exact(fused.Read(), b) && Exact(fn.Read(), bn) &&
              HalfExact(fh.Read(), bh),
          "Rejected norm dispatch changed outputs");
  return exact;
}

static bool NormBench(bool moe) {
  constexpr unsigned tokens = 2048, launches = 32;
  Inputs in(tokens, 8, 3, 0);
  Output ref(in.residual.size()), fused(in.residual.size());
  Output rn(in.residual.size()), fn(in.residual.size());
  HalfOutput rh(in.residual.size()), fh(in.residual.size());
  Device block(in.shared.size() * sizeof(float));
  Upload(block.Data(), in.shared);
  auto launch = [&](bool candidate) {
    Require(LaunchNorm(in, candidate ? fused : ref, candidate ? fn : rn,
                       candidate ? fh : rh, block, moe, candidate),
            "Norm benchmark dispatch refused");
  };
  for (bool candidate : {false, true}) {
    Upload(candidate ? fused.Data() : ref.Data(), in.residual);
    for (unsigned i = 0; i < 4; ++i)
      launch(candidate);
  }
  Hip(hipGetLastError());
  Hip(hipDeviceSynchronize());
  hipEvent_t begin, end;
  Hip(hipEventCreate(&begin));
  Hip(hipEventCreate(&end));
  bool exact = true;
  for (unsigned rep = 0; rep < 5; ++rep) {
    for (unsigned arm = 0; arm < 2; ++arm) {
      const bool candidate = ((rep + arm) % 2) != 0;
      Upload(candidate ? fused.Data() : ref.Data(), in.residual);
      Hip(hipEventRecord(begin, nullptr));
      for (unsigned i = 0; i < launches; ++i)
        launch(candidate);
      Hip(hipEventRecord(end, nullptr));
      Hip(hipEventSynchronize(end));
      Hip(hipGetLastError());
      float elapsed = 0;
      Hip(hipEventElapsedTime(&elapsed, begin, end));
      std::cout << "{\"event\":\"hc_norm_microbench\",\"moe\":"
                << std::boolalpha << moe << ",\"candidate\":" << candidate
                << ",\"rep\":" << rep << ",\"tokens\":" << tokens
                << ",\"iterations\":" << launches
                << ",\"microseconds_per_iteration\":"
                << double(elapsed) * 1000 / launches << "}\n";
    }
    const bool same = Exact(ref.Read(), fused.Read()) &&
                      Exact(rn.Read(), fn.Read()) &&
                      HalfExact(rh.Read(), fh.Read());
    exact = same && exact;
    std::cout << "{\"event\":\"hc_norm_microbench_replay\",\"moe\":" << moe
              << ",\"rep\":" << rep << ",\"exact\":" << same << "}\n";
  }
  in.CheckInputs();
  CheckInput(block, in.shared);
  Hip(hipEventDestroy(begin));
  Hip(hipEventDestroy(end));
  return exact;
}

int main(int argc, char** argv) {
  try {
    Require(argc == 2 && (std::string(argv[1]) == "operators" ||
                          std::string(argv[1]) == "bench"),
            "Expected operators or bench");
    Hip(hipSetDevice(0));
    std::cout << std::setprecision(12) << std::boolalpha;
    bool pass = true;
    pass = Case(16, 0, true, 8, 3) && pass;
    pass = Case(17, 1, true, 8, 3) && pass;
    pass = Case(33, 2, true, 8, 3) && pass;
    pass = Case(97, 0, true, 8, 1) && pass;
    pass = Case(129, 0, true, 8, 3) && pass;
    pass = Case(16, 0, false, 8, 3) && pass;
    pass = Case(17, 0, true, 1, 3) && pass;
    pass = Case(17, 0, true, 32, 7) && pass;
    for (bool moe : {false, true}) {
      pass = NormCase(16, 0, moe) && pass;
      pass = NormCase(17, 1, moe) && pass;
      pass = NormCase(97, 2, moe) && pass;
    }
    if (std::string(argv[1]) == "bench")
      for (bool moe : {false, true})
        pass = NormBench(moe) && pass;
    std::cout << (pass ? "PASS" : "FAIL")
              << " synthetic HC norm half output; no model inference\n";
    return pass ? 0 : 1;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
#endif
