// SPDX-License-Identifier: MIT
// Synthetic GPU MoE/HC checks, not CPU model forward or serving evidence.
#include <hip/hip_runtime.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hpp"

namespace q = gufo::models::qwen38_flash_next::rocm;
static void Require(bool value, const char* reason) {
  if (!value)
    throw std::runtime_error(reason);
}
static void Hip(hipError_t status) {
  Require(status == hipSuccess, hipGetErrorString(status));
}
struct Device {
  void* data{};
  explicit Device(std::size_t bytes) { Hip(hipMalloc(&data, bytes)); }
  ~Device() { (void)hipFree(data); }
  Device(const Device&) = delete;
  Device& operator=(const Device&) = delete;
  float* Data() { return static_cast<float*>(data); }
};
struct Output {
  static constexpr std::size_t guard = 32;
  const std::size_t size;
  Device device;
  explicit Output(std::size_t count)
      : size(count), device((count + 2 * guard) * sizeof(float)) {
    Hip(hipMemset(device.data, 0xFF, (count + 2 * guard) * sizeof(float)));
  }
  float* Data() { return device.Data() + guard; }
  std::vector<float> Read(bool written = true) {
    std::vector<float> host(size + 2 * guard);
    Hip(hipMemcpy(host.data(), device.data, host.size() * sizeof(float),
                  hipMemcpyDeviceToHost));
    const auto* bytes = reinterpret_cast<const unsigned char*>(host.data());
    for (std::size_t i = 0; i < guard * sizeof(float); ++i)
      Require(
          bytes[i] == 0xFF && bytes[(guard + size) * sizeof(float) + i] == 0xFF,
          "Output guard changed");
    std::vector<float> result(host.begin() + guard,
                              host.begin() + guard + size);
    if (written) {
      for (float value : result)
        Require(std::isfinite(value), "Non-finite or unwritten output");
    } else {
      for (std::size_t i = 0; i < size * sizeof(float); ++i)
        Require(bytes[guard * sizeof(float) + i] == 0xFF,
                "Disabled output changed");
    }
    return result;
  }
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
static bool Exact(const std::vector<float>& a, const std::vector<float>& b) {
  return a.size() == b.size() &&
         std::memcmp(a.data(), b.data(), a.size() * sizeof(float)) == 0;
}
static void Upload(float* output, const std::vector<float>& values) {
  Hip(hipMemcpy(output, values.data(), values.size() * sizeof(float),
                hipMemcpyHostToDevice));
}
static void CheckInput(Device& device, const std::vector<float>& expected) {
  std::vector<float> got(expected.size());
  Hip(hipMemcpy(got.data(), device.data, got.size() * sizeof(float),
                hipMemcpyDeviceToHost));
  Require(Exact(got, expected), "Read-only input changed");
}
static void Save(const std::string& name, const std::vector<float>& values) {
  std::ofstream out("results/" + name, std::ios::binary);
  out.write(reinterpret_cast<const char*>(values.data()),
            static_cast<std::streamsize>(values.size() * sizeof(float)));
  Require(bool(out), "Cannot save MoE/HC operator evidence");
}
struct Error {
  double error2{}, expected2{}, peak{}, maximum{};
  std::size_t values{};
  void Add(double expected, float value) {
    Require(std::isfinite(value) && std::isfinite(expected), "Invalid oracle");
    const double delta = double(value) - expected;
    error2 += delta * delta;
    expected2 += expected * expected;
    peak = std::max(peak, std::abs(expected));
    maximum = std::max(maximum, std::abs(delta));
    ++values;
  }
  double Rms() const { return std::sqrt(error2 / std::max(expected2, 1e-60)); }
  double Scaled() const { return maximum / std::max(peak, 1e-30); }
  bool Pass() const { return Rms() <= .00002 && Scaled() <= .00002; }
};
struct Inputs {
  static constexpr unsigned hidden = 2560, streams = 4, stride = 513;
  static constexpr float eps = 1e-6f;
  const unsigned tokens, used, parts;
  std::vector<float> experts, weights, shared, gate, inject, gamma, residual;
  Device ed, wd, sd, gd, id, nd;
  Inputs(unsigned n, unsigned k, unsigned p, unsigned pattern)
      : tokens(n),
        used(k),
        parts(p),
        experts(std::size_t(n) * k * hidden),
        weights(std::size_t(n) * k),
        shared(std::size_t(n) * hidden),
        gate(std::size_t(n) * stride),
        inject(std::size_t(n) * streams * p),
        gamma(streams * hidden),
        residual(std::size_t(n) * streams * hidden),
        ed(experts.size() * 4),
        wd(weights.size() * 4),
        sd(shared.size() * 4),
        gd(gate.size() * 4),
        id(inject.size() * 4),
        nd(gamma.size() * 4) {
    Random rng{953 + n + pattern};
    const float scale = pattern == 1 ? 0x1p-18f : 1.0f;
    for (auto* vector : {&experts, &shared, &residual})
      for (std::size_t i = 0; i < vector->size(); ++i) {
        const float value = rng.Next();
        (*vector)[i] = pattern == 2 ? (i % 2 ? -1.0f : 1.0f) + value * .001f
                                    : scale * value;
      }
    for (float& value : weights)
      value = .5f + .25f * rng.Next();
    for (unsigned t = 0; t < tokens; ++t) {
      float total = 0;
      for (unsigned k2 = 0; k2 < used; ++k2)
        total += weights[t * used + k2];
      for (unsigned k2 = 0; k2 < used; ++k2)
        weights[t * used + k2] /= total;
    }
    for (float& value : gate)
      value = rng.Next() * .5f;
    for (float& value : inject)
      value = rng.Next() * .5f;
    for (float& value : gamma)
      value = 1.0f + rng.Next() * .125f;
    Upload(ed.Data(), experts);
    Upload(wd.Data(), weights);
    Upload(sd.Data(), shared);
    Upload(gd.Data(), gate);
    Upload(id.Data(), inject);
    Upload(nd.Data(), gamma);
  }
  void Reference(Output& res, Output& norm, Device& block, bool normalization) {
    q::MoeEpilogueVec4(ed.Data(), wd.Data(), sd.Data(), gd.Data(), stride,
                       block.Data(), tokens, used, hidden, nullptr);
    q::HcCombine(res.Data(), block.Data(), id.Data(), parts,
                 normalization ? nd.Data() : nullptr, norm.Data(), tokens,
                 hidden, streams, eps, nullptr);
  }
  bool Fused(Output& res, Output& norm, bool normalization, unsigned n = 0,
             unsigned h = hidden, unsigned s = streams, unsigned k = 0,
             bool missing_experts = false, bool missing_norm = false) {
    return q::HcCombineMoeF32(res.Data(), missing_experts ? nullptr : ed.Data(),
                              wd.Data(), sd.Data(), gd.Data(), stride,
                              k ? k : used, id.Data(), parts,
                              normalization ? nd.Data() : nullptr,
                              missing_norm ? nullptr : norm.Data(),
                              n ? n : tokens, h, s, eps, nullptr);
  }
  void CheckInputs() {
    CheckInput(ed, experts);
    CheckInput(wd, weights);
    CheckInput(sd, shared);
    CheckInput(gd, gate);
    CheckInput(id, inject);
    CheckInput(nd, gamma);
  }
};

static bool Case(unsigned tokens, unsigned pattern, bool normalization,
                 unsigned used, unsigned parts) {
  Inputs in(tokens, used, parts, pattern);
  const auto count = in.residual.size();
  Output ref(count), fused(count), rn(count), fn(count);
  Device block(std::size_t(tokens) * Inputs::hidden * sizeof(float));
  Upload(ref.Data(), in.residual);
  Upload(fused.Data(), in.residual);
  in.Reference(ref, rn, block, normalization);
  Require(in.Fused(fused, fn, normalization), "Fused MoE/HC dispatch refused");
  Hip(hipGetLastError());
  Hip(hipDeviceSynchronize());
  const auto a = ref.Read(), b = fused.Read();
  const auto an = rn.Read(normalization), bn = fn.Read(normalization);
  in.CheckInputs();
  Error re, ne;
  std::vector<double> moe(Inputs::hidden), residual(Inputs::hidden);
  for (unsigned t = 0; t < tokens; ++t) {
    const double gate =
        1.0 / (1.0 + std::exp(-double(in.gate[t * Inputs::stride])));
    for (unsigned i = 0; i < Inputs::hidden; ++i) {
      double value = 0;
      for (unsigned k = 0; k < used; ++k)
        value +=
            double(in.weights[t * used + k]) *
            double(
                in.experts[(std::size_t(t) * used + k) * Inputs::hidden + i]);
      moe[i] =
          value + gate * double(in.shared[std::size_t(t) * Inputs::hidden + i]);
    }
    for (unsigned s = 0; s < Inputs::streams; ++s) {
      double logit = 0;
      for (unsigned p = 0; p < parts; ++p)
        logit += in.inject[(std::size_t(t) * Inputs::streams + s) * parts + p];
      const double weight = 2.0 / (1.0 + std::exp(-logit / Inputs::streams));
      const auto base = (std::size_t(t) * Inputs::streams + s) * Inputs::hidden;
      double squares = 0;
      for (unsigned i = 0; i < Inputs::hidden; ++i) {
        residual[i] = double(in.residual[base + i]) + weight * moe[i];
        re.Add(residual[i], b[base + i]);
        squares += residual[i] * residual[i];
      }
      if (normalization) {
        const double scale =
            1.0 / std::sqrt(squares / Inputs::hidden + double(Inputs::eps));
        for (unsigned i = 0; i < Inputs::hidden; ++i)
          ne.Add(residual[i] * scale * double(in.gamma[s * Inputs::hidden + i]),
                 bn[base + i]);
      }
    }
  }
  const auto label = "hc-moe-n" + std::to_string(tokens) + "-p" +
                     std::to_string(pattern) + "-norm" +
                     std::to_string(normalization) + "-k" +
                     std::to_string(used) + "-parts" + std::to_string(parts);
  Save(label + "-reference-res.f32", a);
  Save(label + "-fused-res.f32", b);
  if (normalization) {
    Save(label + "-reference-norm.f32", an);
    Save(label + "-fused-norm.f32", bn);
  }
  const bool exact = Exact(a, b) && Exact(an, bn);
  const bool oracle = re.Pass() && (!normalization || ne.Pass());
  std::cout << std::setprecision(12) << std::boolalpha
            << "{\"event\":\"hc_moe_fused\",\"label\":\"" << label
            << "\",\"values\":" << count
            << ",\"exact_residual\":" << Exact(a, b)
            << ",\"exact_norm\":" << Exact(an, bn)
            << ",\"residual_oracle_values\":" << re.values
            << ",\"residual_rrms\":" << re.Rms()
            << ",\"residual_scaled_max\":" << re.Scaled()
            << ",\"norm_oracle_values\":" << ne.values
            << ",\"norm_rrms\":" << ne.Rms()
            << ",\"norm_scaled_max\":" << ne.Scaled()
            << ",\"independent_pass\":" << oracle << "}\n";
  Require(!in.Fused(fused, fn, true, 15), "Accepted short batch");
  Require(!in.Fused(fused, fn, true, 0, 2559), "Accepted wrong hidden width");
  Require(!in.Fused(fused, fn, true, 0, Inputs::hidden, 3),
          "Accepted wrong stream count");
  Require(!in.Fused(fused, fn, true, 0, Inputs::hidden, 4, 33),
          "Accepted excess experts");
  Require(!in.Fused(fused, fn, true, 0, Inputs::hidden, 4, 0, true),
          "Accepted missing expert input");
  Require(!in.Fused(fused, fn, true, 0, Inputs::hidden, 4, 0, false, true),
          "Accepted missing norm output");
  Hip(hipDeviceSynchronize());
  Require(Exact(fused.Read(), b) && Exact(fn.Read(normalization), bn),
          "Rejected dispatch changed output");
  return exact && oracle;
}

static bool Bench() {
  constexpr unsigned tokens = 2048, launches = 32;
  Inputs in(tokens, 8, 3, 0);
  Output ref(in.residual.size()), fused(in.residual.size());
  Output rn(in.residual.size()), fn(in.residual.size());
  Device block(std::size_t(tokens) * Inputs::hidden * sizeof(float));
  hipEvent_t begin, end;
  Hip(hipEventCreate(&begin));
  Hip(hipEventCreate(&end));
  bool exact = true;
  auto launch = [&](bool candidate) {
    if (candidate)
      Require(in.Fused(fused, fn, true), "Benchmark dispatch refused");
    else
      in.Reference(ref, rn, block, true);
  };
  // Experts alone exceed 32 MiB, and all allocations match the F32 route.
  for (bool candidate : {false, true}) {
    Upload(candidate ? fused.Data() : ref.Data(), in.residual);
    for (unsigned i = 0; i < 4; ++i)
      launch(candidate);
  }
  Hip(hipGetLastError());
  Hip(hipDeviceSynchronize());
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
      std::cout << "{\"event\":\"hc_moe_microbench\",\"candidate\":"
                << std::boolalpha << candidate << ",\"rep\":" << rep
                << ",\"tokens\":" << tokens << ",\"launches\":" << launches
                << ",\"microseconds_per_iteration\":"
                << double(elapsed) * 1000 / launches << "}\n";
    }
    // Complete buffers checked after timing, including the repeated residual
    // update.
    const bool same =
        Exact(ref.Read(), fused.Read()) && Exact(rn.Read(), fn.Read());
    exact = same && exact;
    std::cout << "{\"event\":\"hc_moe_microbench_replay\",\"rep\":" << rep
              << ",\"exact\":" << same << "}\n";
  }
  in.CheckInputs();
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
    bool pass = true;
    pass = Case(16, 0, true, 8, 3) && pass;
    pass = Case(17, 1, true, 8, 3) && pass;
    pass = Case(33, 2, true, 8, 3) && pass;
    pass = Case(97, 0, true, 8, 1) && pass;
    pass = Case(129, 0, true, 8, 3) && pass;
    pass = Case(16, 0, false, 8, 3) && pass;
    pass = Case(17, 0, true, 1, 3) && pass;
    pass = Case(17, 0, true, 32, 7) && pass;
    // Owner permits exploratory timing even when finite numerical checks fail.
    if (std::string(argv[1]) == "bench")
      pass = Bench() && pass;
    std::cout << (pass ? "PASS" : "FAIL")
              << " synthetic MoE/HC fusion; no model inference\n";
    return pass ? 0 : 1;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
