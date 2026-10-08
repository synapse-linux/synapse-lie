// SPDX-License-Identifier: MIT
// Original-F16 HC up/mix: retained paired waves versus a short single chain.
// Synthetic operator evidence only; all allocations and checks are outside
// timing.
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstring>
#include <iomanip>
#include <memory>
#include <set>

#include "src/core/crypto/sha256.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
namespace gufo::models::qwen38_flash_next::rocm {
#include "experiments/q2-hc-up-short-chain-phased-draft.inc"
}
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>

namespace q = gufo::models::qwen38_flash_next::rocm;
using Bytes = std::vector<std::uint8_t>;
constexpr unsigned H = 2560, K = 320, M = 4 * H, Banks = 16;

static void Require(bool value, const char* reason) {
  if (!value)
    throw std::runtime_error(reason);
}
static void Hip(hipError_t value) {
  if (value != hipSuccess)
    throw std::runtime_error(hipGetErrorString(value));
}
struct Device {
  void *storage{}, *data{};
  std::size_t bytes;
  static constexpr std::size_t guard = 64;
  Device(std::size_t size, hipStream_t stream) : bytes(size) {
    Hip(hipMalloc(&storage, bytes + 2 * guard));
    data = static_cast<std::uint8_t*>(storage) + guard;
    Hip(hipMemsetAsync(storage, 0xa7, bytes + 2 * guard, stream));
  }
  Device(const Device&) = delete;
  ~Device() {
    if (storage)
      (void)hipFree(storage);
  }
  void Clear(hipStream_t stream) {
    Hip(hipMemsetAsync(data, 0xff, bytes, stream));
  }
  Bytes Read(hipStream_t stream) const {
    Bytes raw(bytes + 2 * guard);
    Hip(hipMemcpyAsync(raw.data(), storage, raw.size(), hipMemcpyDeviceToHost,
                       stream));
    Hip(hipStreamSynchronize(stream));
    for (std::size_t i = 0; i < guard; ++i)
      Require(raw[i] == 0xa7 && raw[guard + bytes + i] == 0xa7,
              "Device guard changed");
    return Bytes(raw.begin() + guard, raw.end() - guard);
  }
};
template<class T>
static Bytes AsBytes(const std::vector<T>& values) {
  const auto* p = reinterpret_cast<const std::uint8_t*>(values.data());
  return Bytes(p, p + values.size() * sizeof(T));
}
static std::string Hash(const Bytes& bytes) {
  return gufo::crypto::Sha256Hex(bytes);
}
template<class T>
static void Upload(Device& to, const std::vector<T>& values,
                   hipStream_t stream) {
  Require(to.bytes == values.size() * sizeof(T), "Input byte count differs");
  Hip(hipMemcpyAsync(to.data, values.data(), to.bytes, hipMemcpyHostToDevice,
                     stream));
  Hip(hipStreamSynchronize(stream));
}
static float Value(const Bytes& bytes, std::size_t i, bool half = false) {
  if (half) {
    __half v;
    std::memcpy(&v, bytes.data() + i * 2, 2);
    return __half2float(v);
  }
  float v;
  std::memcpy(&v, bytes.data() + i * 4, 4);
  return v;
}
static void Complete(const Bytes& bytes, bool half, bool enabled) {
  if (!enabled) {
    for (auto v : bytes)
      Require(v == 0xff, "Disabled output changed");
  } else {
    for (std::size_t i = 0; i < bytes.size() / (half ? 2 : 4); ++i)
      Require(std::isfinite(Value(bytes, i, half)),
              "Required output unwritten or nonfinite");
  }
}
static void Save(const std::string& path, const Bytes& bytes) {
  std::ofstream file("results/" + path + ".bin", std::ios::binary);
  file.write(reinterpret_cast<const char*>(bytes.data()), bytes.size());
  Require(bool(file), "Cannot preserve operator output");
}
struct Random {
  std::uint32_t state;
  float Next() {
    state = state * 1664525u + 1013904223u;
    return float(int(state >> 16) - 32768) / 32768.f;
  }
};
struct Inputs {
  unsigned n, pattern, banks;
  std::vector<__half> low;
  std::vector<float> residual, scales, gamma, inject;
  std::vector<std::vector<__half>> weights;
  Device x, xn, ns, ng, iw;
  std::vector<std::unique_ptr<Device>> w;
  Inputs(unsigned rows, unsigned p, unsigned count, hipStream_t stream)
      : n(rows),
        pattern(p),
        banks(count),
        low(std::size_t(n) * K),
        residual(std::size_t(n) * M),
        scales(n * 4),
        gamma(M),
        inject(4 * M),
        x(low.size() * 2, stream),
        xn(residual.size() * 4, stream),
        ns(scales.size() * 4, stream),
        ng(gamma.size() * 4, stream),
        iw(inject.size() * 4, stream) {
    Random rng{713 + n + 19 * p};
    for (auto& a : low)
      a = __float2half_rn(rng.Next() * (p == 1 ? 0x1p-18f : .5f));
    for (std::size_t i = 0; i < residual.size(); ++i) {
      float a = rng.Next();
      residual[i] = p == 1   ? a * 0x1p-18f
                    : p == 2 ? ((i / H) % 2 ? -1.f : 1.f) + a * .001f
                             : a;
    }
    for (auto& a : scales)
      a = .5f + .125f * rng.Next();
    for (auto& a : gamma)
      a = 1.f + .125f * rng.Next();
    for (auto& a : inject)
      a = __half2float(__float2half_rn(rng.Next() * .03125f));
    if (p == 3)
      for (unsigned t = 1; t < n; ++t) {
        std::copy_n(low.data(), K, low.data() + std::size_t(t) * K);
        std::copy_n(residual.data(), M, residual.data() + std::size_t(t) * M);
        std::copy_n(scales.data(), 4, scales.data() + t * 4);
      }
    Upload(x, low, stream);
    Upload(xn, residual, stream);
    Upload(ns, scales, stream);
    Upload(ng, gamma, stream);
    Upload(iw, inject, stream);
    for (unsigned b = 0; b < banks; ++b) {
      weights.emplace_back(std::size_t(M) * K);
      for (auto& a : weights.back())
        a = __float2half_rn(rng.Next() * .03125f);
      w.push_back(std::make_unique<Device>(weights.back().size() * 2, stream));
      Upload(*w.back(), weights.back(), stream);
    }
  }
  float Norm(unsigned t, unsigned s, unsigned h, bool deferred) const {
    const float a = residual[std::size_t(t) * M + s * H + h];
    if (!deferred)
      return a;
    // Independently rounded F32 scale*gamma, then residual*factor.
    volatile float factor = scales[t * 4 + s] * gamma[s * H + h];
    volatile float value = a * factor;
    return value;
  }
  void Unchanged(hipStream_t stream) const {
    Require(x.Read(stream) == AsBytes(low) &&
                xn.Read(stream) == AsBytes(residual) &&
                ns.Read(stream) == AsBytes(scales) &&
                ng.Read(stream) == AsBytes(gamma) &&
                iw.Read(stream) == AsBytes(inject),
            "Read-only input changed");
    for (unsigned b = 0; b < banks; ++b)
      Require(w[b]->Read(stream) == AsBytes(weights[b]),
              "Weight input changed");
  }
};
struct State {
  Device mixed, half, inject;
  State(unsigned n, hipStream_t s)
      : mixed(std::size_t(n) * H * 4, s),
        half(std::size_t(n) * H * 2, s),
        inject(std::size_t(n) * 4 * 3 * 4, s) {}
  void Clear(hipStream_t s) {
    mixed.Clear(s);
    half.Clear(s);
    inject.Clear(s);
  }
};
struct Snapshot {
  Bytes mixed, half, inject;
};
static Snapshot Read(const State& out, bool half, bool injection,
                     hipStream_t stream) {
  Snapshot s{out.mixed.Read(stream), out.half.Read(stream),
             out.inject.Read(stream)};
  Complete(s.mixed, false, true);
  Complete(s.half, true, half);
  Complete(s.inject, false, injection);
  return s;
}
static bool Launch(bool candidate, bool deferred, const Inputs& in, State& out,
                   unsigned bank, bool half, bool injection,
                   hipStream_t stream) {
  const auto* x = static_cast<const __half*>(in.x.data);
  const auto* xn = static_cast<const float*>(in.xn.data);
  const auto* iw = injection ? static_cast<const float*>(in.iw.data) : nullptr;
  auto* mixed = static_cast<float*>(out.mixed.data);
  auto* h = half ? static_cast<__half*>(out.half.data) : nullptr;
  auto* inj = injection ? static_cast<float*>(out.inject.data) : nullptr;
  if (deferred) {
    auto fn =
        candidate ? q::HcMixDeferredShortChainPhased : q::HcMixDeferredNorm;
    return fn(in.w[bank]->data, x, xn, iw, mixed, h, inj, in.n, H, K, stream,
              static_cast<const float*>(in.ns.data),
              static_cast<const float*>(in.ng.data));
  }
  auto fn = candidate ? q::HcMixRawF16ShortChainPhased : q::HcMixRawF16Gemm;
  return fn(in.w[bank]->data, x, xn, iw, mixed, h, inj, in.n, H, K, stream);
}
struct Error {
  double error2{}, expected2{}, peak{}, maximum{};
  std::size_t values{};
  void Add(double a, float b) {
    Require(std::isfinite(a) && std::isfinite(b), "Nonfinite oracle value");
    double d = double(b) - a;
    error2 += d * d;
    expected2 += a * a;
    peak = std::max(peak, std::abs(a));
    maximum = std::max(maximum, std::abs(d));
    ++values;
  }
  double Rms() const { return std::sqrt(error2 / std::max(expected2, 1e-60)); }
  double Scaled() const { return maximum / std::max(peak, 1e-30); }
  bool Pass() const { return values && Rms() <= .00002 && Scaled() <= .00002; }
};
static bool Oracle(const Inputs& in, const Snapshot& out, unsigned bank,
                   bool deferred, bool injection, const std::string& label,
                   bool candidate) {
  Error mixed, inject;
  std::set<unsigned> ts{0, 15, 16, 31, 32, 63, 64, in.n - 1};
  for (unsigned t : {95u, 96u, 127u, 128u, 255u, 256u, 2047u, 2048u})
    if (t < in.n)
      ts.insert(t);
  const std::array<unsigned, 12> hs{0,  1,  15,  16,  31,   32,
                                    63, 64, 127, 128, 1023, H - 1};
  for (unsigned t : ts)
    for (unsigned h : hs) {
      double expected = 0;
      for (unsigned s = 0; s < 4; ++s) {
        double gate = 0;
        for (unsigned k = 0; k < K; ++k)
          gate += double(__half2float(
                      in.weights[bank][std::size_t(s * H + h) * K + k])) *
                  double(__half2float(in.low[std::size_t(t) * K + k]));
        expected += double(in.Norm(t, s, h, deferred)) / (1. + std::exp(-gate));
      }
      mixed.Add(expected * .25, Value(out.mixed, std::size_t(t) * H + h));
    }
  if (injection)
    for (unsigned t : ts)
      for (unsigned o = 0; o < 4; ++o)
        for (unsigned part = 0; part < 3; ++part) {
          double expected = 0;
          for (unsigned s = 0; s < 4; ++s)
            for (unsigned h = part * 1024; h < std::min(H, (part + 1) * 1024);
                 ++h)
              expected += double(in.inject[o * M + s * H + h]) *
                          double(in.Norm(t, s, h, deferred));
          inject.Add(expected,
                     Value(out.inject, (std::size_t(t) * 4 + o) * 3 + part));
        }
  bool pass = mixed.Pass() && (!injection || inject.Pass());
  std::cout << "{\"event\":\"hc_short_oracle\",\"label\":\"" << label
            << "\",\"bank\":" << bank << ",\"candidate\":" << candidate
            << ",\"mix_values\":" << mixed.values
            << ",\"mix_rrms\":" << mixed.Rms()
            << ",\"mix_scaled_max\":" << mixed.Scaled()
            << ",\"inject_values\":" << inject.values
            << ",\"inject_rrms\":" << inject.Rms()
            << ",\"inject_scaled_max\":" << inject.Scaled()
            << ",\"limit\":0.00002,\"pass\":" << pass << "}\n";
  return pass;
}
static bool Pair(const Snapshot& a, const Snapshot& b, const std::string& label,
                 unsigned bank, bool half, bool injection, bool save) {
  bool exact = true;
  for (unsigned k = 0; k < 3; ++k) {
    const Bytes& x = k == 0 ? a.mixed : k == 1 ? a.half : a.inject;
    const Bytes& y = k == 0 ? b.mixed : k == 1 ? b.half : b.inject;
    bool enabled = k == 0 || (k == 1 ? half : injection);
    std::size_t changed = 0;
    double max_abs = 0, l2 = 0, ref2 = 0;
    if (enabled)
      for (std::size_t i = 0; i < x.size() / (k == 1 ? 2 : 4); ++i) {
        const auto width = k == 1 ? 2 : 4;
        changed +=
            std::memcmp(x.data() + i * width, y.data() + i * width, width) != 0;
        double ref = Value(x, i, k == 1),
               delta = double(Value(y, i, k == 1)) - ref;
        max_abs = std::max(max_abs, std::abs(delta));
        l2 += delta * delta;
        ref2 += ref * ref;
      }
    const char* name = k == 0 ? "mixed" : k == 1 ? "half" : "inject";
    exact = exact && (x == y);
    std::cout << "{\"event\":\"hc_short_pair\",\"label\":\"" << label
              << "\",\"bank\":" << bank << ",\"buffer\":\"" << name
              << "\",\"bytes\":" << x.size() << ",\"enabled\":" << enabled
              << ",\"changed_values\":" << changed << ",\"max_abs\":" << max_abs
              << ",\"relative_l2\":" << std::sqrt(l2 / std::max(ref2, 1e-60))
              << ",\"parent_sha256\":\"" << Hash(x)
              << "\",\"candidate_sha256\":\"" << Hash(y)
              << "\",\"exact\":" << (x == y) << "}\n";
    if (save && enabled) {
      Save(label + "-" + name + "-parent", x);
      Save(label + "-" + name + "-candidate", y);
    }
  }
  return exact;
}
static bool Case(unsigned n, unsigned pattern, bool deferred, bool half,
                 bool injection, bool timing, hipStream_t stream,
                 bool& oracle_pass) {
  Inputs in(n, pattern, timing ? Banks : 1, stream);
  std::array<std::vector<std::unique_ptr<State>>, 2> states;
  for (auto& arm : states)
    for (unsigned b = 0; b < in.banks; ++b)
      arm.push_back(std::make_unique<State>(n, stream));
  std::string base = "hc-short-n" + std::to_string(n) + "-p" +
                     std::to_string(pattern) + "-d" + std::to_string(deferred) +
                     "-h" + std::to_string(half) + "-i" +
                     std::to_string(injection);
  bool exact = true;
  hipEvent_t begin{}, end{};
  Hip(hipEventCreate(&begin));
  Hip(hipEventCreate(&end));
  for (unsigned rep = 0; rep < (timing ? 7 : 1); ++rep) {
    std::array<std::vector<Snapshot>, 2> got;
    const std::string label = base + "-r" + std::to_string(rep);
    for (unsigned order = 0; order < 2; ++order) {
      unsigned arm = (rep + order) % 2;
      for (auto& out : states[arm])
        out->Clear(stream);
      Hip(hipStreamSynchronize(stream));
      auto started = std::chrono::steady_clock::now();
      Hip(hipEventRecord(begin, stream));
      for (unsigned b = 0; b < in.banks; ++b)
        Require(Launch(arm, deferred, in, *states[arm][b], b, half, injection,
                       stream),
                "HC launch refused");
      Hip(hipGetLastError());
      Hip(hipEventRecord(end, stream));
      Hip(hipEventSynchronize(end));
      double wall = std::chrono::duration<double, std::micro>(
                        std::chrono::steady_clock::now() - started)
                        .count() /
                    in.banks;
      float ms{};
      Hip(hipEventElapsedTime(&ms, begin, end));
      if (timing)
        std::cout << "{\"event\":\"hc_short_timing\",\"label\":\"" << base
                  << "\",\"rep\":" << rep << ",\"order\":" << order
                  << ",\"candidate\":" << bool(arm)
                  << ",\"warmup\":" << (rep < 2)
                  << ",\"iterations\":" << in.banks
                  << ",\"weight_bytes\":" << std::size_t(in.banks) * M * K * 2
                  << ",\"us_per_iteration\":" << double(ms) * 1000 / in.banks
                  << ",\"wall_us_per_iteration\":" << wall << "}\n";
      // Validate every actual timed destination before another launch can
      // overwrite it.
      for (unsigned b = 0; b < in.banks; ++b) {
        got[arm].push_back(Read(*states[arm][b], half, injection, stream));
        oracle_pass =
            Oracle(in, got[arm].back(), b, deferred, injection, label, arm) &&
            oracle_pass;
      }
    }
    for (unsigned b = 0; b < in.banks; ++b)
      exact = Pair(got[0][b], got[1][b], label, b, half, injection,
                   rep == 0 && b == 0) &&
              exact;
  }
  Hip(hipEventDestroy(end));
  Hip(hipEventDestroy(begin));
  in.Unchanged(stream);
  std::cout << "{\"event\":\"hc_short_case\",\"label\":\"" << base
            << "\",\"guards_finite_written\":true,\"inputs_unchanged\":true,"
               "\"actual_timed_buffers_checked\":"
            << timing << "}\n";
  return exact;
}
int main() {
  try {
    std::cout << std::boolalpha << std::setprecision(12);
    hipStream_t stream{};
    Hip(hipStreamCreateWithFlags(&stream, hipStreamNonBlocking));
    bool exact = true, oracle = true;
    for (bool deferred : {false, true}) {
      exact = Case(96, 0, deferred, true, true, false, stream, oracle) && exact;
      exact =
          Case(97, 1, deferred, false, true, false, stream, oracle) && exact;
      exact =
          Case(129, 2, deferred, true, false, false, stream, oracle) && exact;
      exact =
          Case(129, 3, deferred, true, true, false, stream, oracle) && exact;
      exact =
          Case(2049, 0, deferred, true, true, false, stream, oracle) && exact;
      exact =
          Case(2048, 0, deferred, true, true, true, stream, oracle) && exact;
    }
    Hip(hipStreamSynchronize(stream));
    Hip(hipStreamDestroy(stream));
    std::cout << "{\"event\":\"hc_short_complete\",\"safe_completion\":true,"
                 "\"exact\":"
              << exact << ",\"independent_pass\":" << oracle
              << ",\"all_timings_retained\":true,\"model_inference\":false}\n";
    return exact && oracle ? 0 : 1;
  } catch (const std::exception& error) {
    std::cerr << "FAIL: " << error.what() << '\n';
    return 2;
  }
}
