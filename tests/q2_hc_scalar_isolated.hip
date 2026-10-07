// SPDX-License-Identifier: MIT
// Isolated scalar HC codegen and original common kernels. Synthetic data only.
#include <algorithm>
#include <array>
#include <bit>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
// The candidate is linked from its separate production HIP compilation unit.
namespace q = gufo::models::qwen38_flash_next::rocm;
constexpr unsigned H = 2560, K = 320, S = 4, G = H * S, P = 10;
constexpr unsigned Banks = 16, Calls = 64;
constexpr std::size_t W = std::size_t(G) * K;
static void Require(bool value, const char* message) {
  if (!value)
    throw std::runtime_error(message);
}
static void Hip(hipError_t error) {
  if (error != hipSuccess)
    throw std::runtime_error(hipGetErrorString(error));
}
struct Device {
  void* base{};
  void* data{};
  std::size_t bytes;
  static constexpr std::size_t Guard = 64;
  explicit Device(std::size_t n) : bytes(n) {
    Hip(hipMalloc(&base, n + 2 * Guard));
    data = static_cast<char*>(base) + Guard;
    Hip(hipMemset(base, 0xA7, Guard));
    Hip(hipMemset(static_cast<char*>(data) + n, 0xA7, Guard));
  }
  ~Device() { (void)hipFree(base); }
  void Check() const {
    std::array<unsigned char, 2 * Guard> got{};
    Hip(hipMemcpy(got.data(), base, Guard, hipMemcpyDeviceToHost));
    Hip(hipMemcpy(got.data() + Guard, static_cast<const char*>(data) + bytes,
                  Guard, hipMemcpyDeviceToHost));
    Require(
        std::all_of(got.begin(), got.end(), [](auto v) { return v == 0xA7; }),
        "Device guard changed");
  }
  void Poison(hipStream_t stream) {
    Hip(hipMemsetAsync(data, 0xFF, bytes, stream));
  }
  template<class T>
  T* ptr() {
    return static_cast<T*>(data);
  }
  template<class T>
  std::vector<T> Read() const {
    Check();
    std::vector<T> result(bytes / sizeof(T));
    Hip(hipMemcpy(result.data(), data, bytes, hipMemcpyDeviceToHost));
    return result;
  }
};
template<class T>
static void Upload(Device& out, const std::vector<T>& in) {
  Require(out.bytes == in.size() * sizeof(T), "Input size differs");
  Hip(hipMemcpy(out.data, in.data(), out.bytes, hipMemcpyHostToDevice));
}
struct Random {
  std::uint32_t state{113};
  float Next() {
    state = state * 1664525U + 1013904223U;
    return float(int(state >> 16) - 32768) / 32768.0F;
  }
};
struct Data {
  std::vector<__half> w;
  std::vector<float> lo, xn, iw;
  Device dw{W * Banks * sizeof(__half)}, dl{K * Banks * sizeof(float)},
      dx{G * Banks * sizeof(float)}, di{S * G * Banks * sizeof(float)};
  Data() : w(W * Banks), lo(K * Banks), xn(G * Banks), iw(S * G * Banks) {
    Random random;
    for (auto& v : w)
      v = __float2half(random.Next() * 0.05F);
    for (auto& v : lo)
      v = random.Next() * 0.25F;
    for (auto& v : xn)
      v = random.Next();
    for (auto& v : iw)
      v = random.Next() * 0.05F;
  }
  void Send() {
    Upload(dw, w);
    Upload(dl, lo);
    Upload(dx, xn);
    Upload(di, iw);
  }
  void Unchanged() {
    const auto a = dw.Read<__half>();
    const auto b = dl.Read<float>(), c = dx.Read<float>(), d = di.Read<float>();
    Require(std::memcmp(a.data(), w.data(), dw.bytes) == 0 &&
                std::memcmp(b.data(), lo.data(), dl.bytes) == 0 &&
                std::memcmp(c.data(), xn.data(), dx.bytes) == 0 &&
                std::memcmp(d.data(), iw.data(), di.bytes) == 0,
            "Input mutation");
  }
};
struct Outputs {
  Device gates{G * Calls * sizeof(float)}, mixed{H * Calls * sizeof(float)},
      inject{S * P * Calls * sizeof(float)};
  void Poison(hipStream_t stream) {
    gates.Poison(stream);
    mixed.Poison(stream);
    inject.Poison(stream);
  }
};
static void Launch(bool candidate, bool witness, bool injection, Data& in,
                   Outputs& out, unsigned slot, hipStream_t stream) {
  const unsigned bank = slot % Banks;
  auto* w = in.dw.ptr<__half>() + bank * W;
  auto* lo = in.dl.ptr<float>() + bank * K;
  auto* xn = in.dx.ptr<float>() + bank * G;
  auto* iw = injection ? in.di.ptr<float>() + bank * S * G : nullptr;
  auto* gates = out.gates.ptr<float>() + slot * G;
  auto* mixed = out.mixed.ptr<float>() + slot * H;
  auto* inject = out.inject.ptr<float>() + slot * S * P;
  if (candidate) {
    q::HcScalarUpMix(w, lo, xn, iw, mixed, inject, stream,
                     witness ? gates : nullptr);
  } else {
    q::SmallGemm(w, q::WeightType::kF16, lo, gates, 1, G, K, stream);
    q::HcMixEpilogue(xn, gates, iw, mixed, inject, 1, H, S, stream);
  }
  Hip(hipGetLastError());
}
static bool Compare(const std::vector<float>& a, const std::vector<float>& b,
                    unsigned count, const std::string& label,
                    bool poisoned = false) {
  unsigned changed = 0;
  for (unsigned i = 0; i < count; ++i) {
    const auto aa = std::bit_cast<std::uint32_t>(a[i]),
               bb = std::bit_cast<std::uint32_t>(b[i]);
    if (poisoned) {
      Require(aa == 0xFFFFFFFFU && bb == 0xFFFFFFFFU, "Unused output changed");
    } else {
      Require(std::isfinite(a[i]) && std::isfinite(b[i]),
              "Nonfinite or unwritten output");
    }
    changed += aa != bb;
  }
  std::cout << "{\"event\":\"hc_scalar_pair\",\"label\":\"" << label
            << "\",\"values\":" << count << ",\"changed\":" << changed
            << ",\"exact\":" << (changed == 0) << "}\n";
  if (changed) {
    for (unsigned arm = 0; arm < 2; ++arm) {
      const auto& v = arm ? b : a;
      std::ofstream file(
          "results/" + label + (arm ? "-candidate.f32" : "-reference.f32"),
          std::ios::binary);
      file.write(reinterpret_cast<const char*>(v.data()),
                 count * sizeof(float));
      Require(bool(file), "Cannot retain changed output");
    }
  }
  return changed == 0;
}
static bool Metric(const std::vector<double>& want,
                   const std::vector<double>& got, const std::string& label) {
  double error2 = 0, norm2 = 0, peak = 0, worst = 0;
  for (unsigned i = 0; i < want.size(); ++i) {
    const double error = std::abs(got[i] - want[i]);
    error2 += error * error;
    norm2 += want[i] * want[i];
    peak = std::max(peak, std::abs(want[i]));
    worst = std::max(worst, error);
  }
  const double rms = std::sqrt(error2 / std::max(norm2, 1e-60));
  const double scaled = worst / std::max(peak, 1e-30);
  const bool pass = rms <= 2e-5 && scaled <= 2e-5;
  std::cout << "{\"event\":\"hc_scalar_oracle\",\"label\":\"" << label
            << "\",\"samples\":" << want.size() << ",\"relative_rms\":" << rms
            << ",\"scaled_error\":" << scaled
            << ",\"limit\":0.00002,\"pass\":" << pass << "}\n";
  return pass;
}
static bool Oracle(const Data& in, const std::vector<float>& gates,
                   const std::vector<float>& mixed,
                   const std::vector<float>& inject, bool injection,
                   const std::string& label) {
  constexpr unsigned samples[] = {0,   1,   31,  32,   63,   127,  128,  255,
                                  256, 511, 512, 1023, 1024, 2047, 2048, 2559};
  std::vector<double> gw, gg, mw, mg, iw, ig;
  for (unsigned h : samples) {
    double mix = 0;
    for (unsigned s = 0; s < S; ++s) {
      double dot = 0;
      const unsigned row = s * H + h;
      for (unsigned k = 0; k < K; ++k)
        dot += double(__half2float(in.w[std::size_t(row) * K + k])) *
               double(in.lo[k]);
      gw.push_back(dot);
      gg.push_back(gates[row]);
      mix += double(in.xn[row]) / (1.0 + std::exp(-dot));
    }
    mw.push_back(mix / S);
    mg.push_back(mixed[h]);
  }
  bool pass = Metric(gw, gg, label + "-gate");
  pass = Metric(mw, mg, label + "-mix") && pass;
  if (injection) {
    for (unsigned o = 0; o < S; ++o) {
      for (unsigned p = 0; p < P; ++p) {
        double dot = 0;
        for (unsigned i = p * 256; i < (p + 1) * 256; ++i)
          for (unsigned s = 0; s < S; ++s)
            dot +=
                double(in.iw[(o * S + s) * H + i]) * double(in.xn[s * H + i]);
        iw.push_back(dot);
        ig.push_back(inject[o * P + p]);
      }
    }
    pass = Metric(iw, ig, label + "-injection") && pass;
  }
  return pass;
}
static bool Case(Data& in, Outputs& a, Outputs& b, unsigned pattern,
                 bool injection, hipStream_t stream) {
  const auto label =
      "p" + std::to_string(pattern) + (injection ? "-inject" : "-head");
  a.Poison(stream);
  b.Poison(stream);
  Launch(false, true, injection, in, a, 0, stream);
  Launch(true, true, injection, in, b, 0, stream);
  Hip(hipStreamSynchronize(stream));
  const auto ag = a.gates.Read<float>(), bg = b.gates.Read<float>();
  const auto am = a.mixed.Read<float>(), bm = b.mixed.Read<float>();
  const auto ai = a.inject.Read<float>(), bi = b.inject.Read<float>();
  bool pass = Compare(ag, bg, G, label + "-gate");
  pass = Compare(am, bm, H, label + "-mix") && pass;
  pass = Compare(ai, bi, S * P, label + "-inject", !injection) && pass;
  // F32 subnormals use the inherited GPU arithmetic mode; exact replay is
  // their gate. The independent real-arithmetic oracle covers other cases.
  if (pattern != 5) {
    pass = Oracle(in, ag, am, ai, injection, label + "-reference") && pass;
    pass = Oracle(in, bg, bm, bi, injection, label + "-candidate") && pass;
  }
  return pass;
}
static bool Bench(Data& in, Outputs& a, Outputs& b, bool injection,
                  hipStream_t stream) {
  Outputs* outputs[] = {&a, &b};
  hipGraphExec_t exec[2]{};
  for (unsigned arm = 0; arm < 2; ++arm) {
    outputs[arm]->Poison(stream);
    Launch(arm, true, injection, in, *outputs[arm], 0, stream);
    Hip(hipStreamSynchronize(stream));
    Hip(hipStreamBeginCapture(stream, hipStreamCaptureModeThreadLocal));
    for (unsigned i = 0; i < Calls; ++i)
      Launch(arm, false, injection, in, *outputs[arm], i, stream);
    hipGraph_t graph{};
    Hip(hipStreamEndCapture(stream, &graph));
    Hip(hipGraphInstantiate(&exec[arm], graph, nullptr, nullptr, 0));
    (void)hipGraphDestroy(graph);
  }
  bool pass = true;
  for (unsigned rep = 0; rep < 7; ++rep) {
    for (unsigned order = 0; order < 2; ++order) {
      const unsigned arm = order ^ (rep & 1U);
      outputs[arm]->Poison(stream);
      Hip(hipStreamSynchronize(stream));
      hipEvent_t begin{}, end{};
      Hip(hipEventCreate(&begin));
      Hip(hipEventCreate(&end));
      const auto start = std::chrono::steady_clock::now();
      Hip(hipEventRecord(begin, stream));
      Hip(hipGraphLaunch(exec[arm], stream));
      Hip(hipEventRecord(end, stream));
      Hip(hipStreamSynchronize(stream));
      const double us = std::chrono::duration<double, std::micro>(
                            std::chrono::steady_clock::now() - start)
                            .count() /
                        Calls;
      float ms = 0;
      Hip(hipEventElapsedTime(&ms, begin, end));
      (void)hipEventDestroy(begin);
      (void)hipEventDestroy(end);
      std::cout << "{\"event\":\"hc_scalar_timing\",\"injection\":" << injection
                << ",\"rep\":" << rep << ",\"order\":" << order
                << ",\"candidate\":" << bool(arm) << ",\"warmup\":" << (rep < 2)
                << ",\"completed_wall_us\":" << us
                << ",\"gpu_event_us\":" << ms * 1000 / Calls
                << ",\"gpu_event_valid\":" << (std::isfinite(ms) && ms > 0)
                << ",\"calls\":" << Calls
                << ",\"distinct_weights_bytes\":" << W * Banks * sizeof(__half)
                << ",\"captured_graph\":true}\n";
    }
    const auto label = std::string(injection ? "inject" : "head") + "-rep" +
                       std::to_string(rep);
    pass = Compare(a.mixed.Read<float>(), b.mixed.Read<float>(), H * Calls,
                   label + "-mix") &&
           pass;
    pass = Compare(a.inject.Read<float>(), b.inject.Read<float>(),
                   S * P * Calls, label + "-inject", !injection) &&
           pass;
    // Candidate graph must not materialize its deleted gate plane.
    const auto gate = b.gates.Read<std::uint32_t>();
    Require(std::all_of(gate.begin(), gate.end(),
                        [](auto v) { return v == 0xFFFFFFFFU; }),
            "Candidate graph wrote deleted gate plane");
  }
  for (auto e : exec)
    (void)hipGraphExecDestroy(e);
  return pass;
}
int main() {
  try {
    std::cout << std::boolalpha << std::setprecision(12) << std::unitbuf;
    std::filesystem::create_directory("results");
    Data data;
    Outputs reference, candidate;
    const auto w = data.w;
    const auto lo = data.lo;
    const auto xn = data.xn;
    hipStream_t stream{};
    Hip(hipStreamCreateWithFlags(&stream, hipStreamNonBlocking));
    bool pass = true;
    for (unsigned pattern = 0; pattern < 6; ++pattern) {
      std::copy(w.begin(), w.end(), data.w.begin());
      std::copy(lo.begin(), lo.end(), data.lo.begin());
      std::copy(xn.begin(), xn.end(), data.xn.begin());
      for (unsigned i = 0; i < K; ++i) {
        if (pattern == 1)
          data.lo[i] *= 1e-7F;
        if (pattern == 2)
          data.lo[i] = (i % 2 ? -1.0F : 1.0F) + data.lo[i] * .001F;
        if (pattern == 3)
          data.lo[i] = i % 2 ? -0.0F : 0.0F;
        if (pattern == 5)
          data.lo[i] = std::bit_cast<float>(std::uint32_t((i % 31) + 1) |
                                            (i % 2 ? 0x80000000U : 0U));
      }
      if (pattern == 4)
        for (std::size_t i = 0; i < W; ++i)
          data.w[i] = std::bit_cast<__half>(
              std::uint16_t(((i % 1023) + 1) | (i % 2 ? 0x8000U : 0U)));
      data.Send();
      pass = Case(data, reference, candidate, pattern, false, stream) && pass;
      pass = Case(data, reference, candidate, pattern, true, stream) && pass;
      data.Unchanged();
    }
    std::copy(w.begin(), w.end(), data.w.begin());
    std::copy(lo.begin(), lo.end(), data.lo.begin());
    std::copy(xn.begin(), xn.end(), data.xn.begin());
    data.Send();
    pass = Bench(data, reference, candidate, true, stream) && pass;
    pass = Bench(data, reference, candidate, false, stream) && pass;
    data.Unchanged();
    Hip(hipStreamDestroy(stream));
    std::cout << "{\"event\":\"hc_scalar_complete\",\"numerical_pass\":" << pass
              << ",\"safe_completion\":true,\"model_access\":false}\n";
    return pass ? 0 : 1;
  } catch (const std::exception& e) {
    std::cerr << "FAIL: " << e.what() << '\n';
    return 2;
  }
}
