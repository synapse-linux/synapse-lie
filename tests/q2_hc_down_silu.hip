// SPDX-License-Identifier: MIT
// Original HC down plus SiLU versus a fused operation. Synthetic data only.
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
namespace gufo::models::qwen38_flash_next::rocm {
void HcDownSilu(const __half*, const float*, float*, hipStream_t, float*);
}
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
  std::vector<__half> wd, wu;
  std::vector<float> x, iw;
  Device dd{W * Banks * sizeof(__half)}, du{W * Banks * sizeof(__half)},
      dx{G * Banks * sizeof(float)}, di{S * G * Banks * sizeof(float)};
  Data() : wd(W * Banks), wu(W * Banks), x(G * Banks), iw(S * G * Banks) {
    Random random;
    for (auto& v : wd)
      v = __float2half(random.Next() * .05F);
    for (auto& v : wu)
      v = __float2half(random.Next() * .05F);
    for (auto& v : x)
      v = random.Next();
    for (auto& v : iw)
      v = random.Next() * .05F;
  }
  void Send() {
    Upload(dd, wd);
    Upload(du, wu);
    Upload(dx, x);
    Upload(di, iw);
  }
  void Unchanged() {
    const auto a = dd.Read<__half>(), b = du.Read<__half>();
    const auto c = dx.Read<float>(), d = di.Read<float>();
    Require(std::memcmp(a.data(), wd.data(), dd.bytes) == 0 &&
                std::memcmp(b.data(), wu.data(), du.bytes) == 0 &&
                std::memcmp(c.data(), x.data(), dx.bytes) == 0 &&
                std::memcmp(d.data(), iw.data(), di.bytes) == 0,
            "Input mutation");
  }
};
struct Outputs {
  Device raw{K * Calls * sizeof(float)}, lo{K * Calls * sizeof(float)},
      mixed{H * Calls * sizeof(float)}, inject{S * P * Calls * sizeof(float)};
  void Poison(hipStream_t stream) {
    raw.Poison(stream);
    lo.Poison(stream);
    mixed.Poison(stream);
    inject.Poison(stream);
  }
};
static void Launch(bool candidate, bool witness, bool chain, Data& in,
                   Outputs& out, unsigned slot, hipStream_t stream) {
  const unsigned bank = slot % Banks;
  auto* wd = in.dd.ptr<__half>() + bank * W;
  auto* x = in.dx.ptr<float>() + bank * G;
  auto* lo = out.lo.ptr<float>() + slot * K;
  if (candidate) {
    q::HcDownSilu(wd, x, lo, stream,
                  witness ? out.raw.ptr<float>() + slot * K : nullptr);
  } else {
    q::SmallGemm(wd, q::WeightType::kF16, x, lo, 1, K, G, stream);
    if (witness)
      Hip(hipMemcpyAsync(out.raw.ptr<float>() + slot * K, lo, K * sizeof(float),
                         hipMemcpyDeviceToDevice, stream));
    q::SiluScale(lo, .25F, K, stream);
  }
  if (chain) {
    q::HcScalarUpMix(in.du.ptr<__half>() + bank * W, lo, x,
                     in.di.ptr<float>() + bank * S * G,
                     out.mixed.ptr<float>() + slot * H,
                     out.inject.ptr<float>() + slot * S * P, stream, nullptr);
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
  std::cout << "{\"event\":\"hc_down_silu_pair\",\"label\":\"" << label
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
  std::cout << "{\"event\":\"hc_down_silu_oracle\",\"label\":\"" << label
            << "\",\"samples\":" << want.size() << ",\"relative_rms\":" << rms
            << ",\"scaled_error\":" << scaled
            << ",\"limit\":0.00002,\"pass\":" << pass << "}\n";
  return pass;
}

static bool Oracle(const Data& in, const Outputs& a, const Outputs& b,
                   unsigned pattern) {
  std::vector<double> raw(K), scaled(K);
  for (unsigned row = 0; row < K; ++row) {
    double dot = 0;
    for (unsigned j = 0; j < G; ++j)
      dot += double(__half2float(in.wd[std::size_t(row) * G + j])) *
             double(in.x[j]);
    raw[row] = dot;
    const double x = dot * .25;
    scaled[row] = x / (1.0 + std::exp(-x));
  }
  bool pass = true;
  for (unsigned arm = 0; arm < 2; ++arm) {
    const auto& out = arm ? b : a;
    const auto rr = out.raw.Read<float>(), ll = out.lo.Read<float>();
    const std::string label =
        "p" + std::to_string(pattern) + (arm ? "-candidate" : "-reference");
    pass = Metric(raw, std::vector<double>(rr.begin(), rr.begin() + K),
                  label + "-raw") &&
           pass;
    pass = Metric(scaled, std::vector<double>(ll.begin(), ll.begin() + K),
                  label + "-silu") &&
           pass;
  }
  return pass;
}
static bool Case(Data& in, Outputs& a, Outputs& b, unsigned pattern,
                 hipStream_t stream) {
  a.Poison(stream);
  b.Poison(stream);
  Launch(false, true, true, in, a, 0, stream);
  Launch(true, true, true, in, b, 0, stream);
  Hip(hipStreamSynchronize(stream));
  const std::string label = "p" + std::to_string(pattern);
  bool pass =
      Compare(a.raw.Read<float>(), b.raw.Read<float>(), K, label + "-raw");
  pass = Compare(a.lo.Read<float>(), b.lo.Read<float>(), K, label + "-silu") &&
         pass;
  pass = Compare(a.mixed.Read<float>(), b.mixed.Read<float>(), H,
                 label + "-mix") &&
         pass;
  pass = Compare(a.inject.Read<float>(), b.inject.Read<float>(), S * P,
                 label + "-inject") &&
         pass;
  // The inherited GPU flush mode defines F32 subnormal replay; the
  // independent real-arithmetic formula covers all other input families.
  if (pattern != 5)
    pass = Oracle(in, a, b, pattern) && pass;
  return pass;
}
static bool Bench(Data& in, Outputs& a, Outputs& b, bool chain,
                  hipStream_t stream) {
  Outputs* out[] = {&a, &b};
  hipGraphExec_t exec[2]{};
  for (unsigned arm = 0; arm < 2; ++arm) {
    out[arm]->Poison(stream);
    Launch(arm, false, chain, in, *out[arm], 0, stream);
    Hip(hipStreamSynchronize(stream));
    Hip(hipStreamBeginCapture(stream, hipStreamCaptureModeThreadLocal));
    for (unsigned slot = 0; slot < Calls; ++slot)
      Launch(arm, false, chain, in, *out[arm], slot, stream);
    hipGraph_t graph{};
    Hip(hipStreamEndCapture(stream, &graph));
    Hip(hipGraphInstantiate(&exec[arm], graph, nullptr, nullptr, 0));
    Hip(hipGraphDestroy(graph));
  }
  bool pass = true;
  for (unsigned rep = 0; rep < 7; ++rep) {
    for (unsigned order = 0; order < 2; ++order) {
      unsigned arm = order ^ (rep & 1U);
      out[arm]->Poison(stream);
      Hip(hipStreamSynchronize(stream));
      const auto start = std::chrono::steady_clock::now();
      Hip(hipGraphLaunch(exec[arm], stream));
      Hip(hipStreamSynchronize(stream));
      const double us = std::chrono::duration<double, std::micro>(
                            std::chrono::steady_clock::now() - start)
                            .count() /
                        Calls;
      std::cout << "{\"event\":\"hc_down_silu_timing\",\"chain\":" << chain
                << ",\"rep\":" << rep << ",\"order\":" << order
                << ",\"candidate\":" << bool(arm) << ",\"warmup\":" << (rep < 2)
                << ",\"completed_wall_us\":" << us << ",\"calls\":" << Calls
                << ",\"distinct_weights_bytes\":"
                << W * Banks * sizeof(__half) * (chain ? 2 : 1)
                << ",\"captured_graph\":true}\n";
    }
    const std::string label = (chain ? "chain" : "down") + std::to_string(rep);
    pass = Compare(a.lo.Read<float>(), b.lo.Read<float>(), K * Calls,
                   label + "-silu") &&
           pass;
    pass = Compare(a.mixed.Read<float>(), b.mixed.Read<float>(), H * Calls,
                   label + "-mix", !chain) &&
           pass;
    pass = Compare(a.inject.Read<float>(), b.inject.Read<float>(),
                   S * P * Calls, label + "-inject", !chain) &&
           pass;
    for (auto* p : out) {
      const auto raw = p->raw.Read<std::uint32_t>();
      Require(std::all_of(raw.begin(), raw.end(),
                          [](auto v) { return v == 0xFFFFFFFFU; }),
              "Timed graph wrote raw witness");
    }
  }
  for (auto graph : exec)
    Hip(hipGraphExecDestroy(graph));
  return pass;
}
int main() {
  try {
    std::cout << std::boolalpha << std::setprecision(12) << std::unitbuf;
    std::filesystem::create_directory("results");
    Data data;
    Outputs a, b;
    const auto w = data.wd;
    const auto x = data.x;
    hipStream_t stream{};
    Hip(hipStreamCreateWithFlags(&stream, hipStreamNonBlocking));
    bool pass = true;
    for (unsigned pattern = 0; pattern < 7; ++pattern) {
      std::copy(w.begin(), w.end(), data.wd.begin());
      std::copy(x.begin(), x.end(), data.x.begin());
      for (unsigned i = 0; i < G; ++i) {
        if (pattern == 1)
          data.x[i] *= 1e-7F;
        if (pattern == 2)
          data.x[i] = (i % 2 ? -1.0F : 1.0F) + data.x[i] * .001F;
        if (pattern == 3)
          data.x[i] = i % 2 ? -0.0F : 0.0F;
        if (pattern == 5)
          data.x[i] = std::bit_cast<float>(std::uint32_t((i % 31) + 1) |
                                           (i % 2 ? 0x80000000U : 0U));
        if (pattern == 6)
          data.x[i] *= 1000.F;
      }
      if (pattern == 4)
        for (std::size_t i = 0; i < W; ++i)
          data.wd[i] = std::bit_cast<__half>(
              std::uint16_t(((i % 1023) + 1) | (i % 2 ? 0x8000U : 0U)));
      data.Send();
      pass = Case(data, a, b, pattern, stream) && pass;
      data.Unchanged();
    }
    std::copy(w.begin(), w.end(), data.wd.begin());
    std::copy(x.begin(), x.end(), data.x.begin());
    data.Send();
    // Preserve performance even if numerical qualification fails.
    pass = Bench(data, a, b, false, stream) && pass;
    pass = Bench(data, a, b, true, stream) && pass;
    data.Unchanged();
    Hip(hipStreamDestroy(stream));
    std::cout << "{\"event\":\"hc_down_silu_complete\",\"numerical_pass\":"
              << pass << ",\"safe_completion\":true,\"model_access\":false}\n";
    return pass ? 0 : 1;
  } catch (const std::exception& error) {
    std::cerr << "FAIL: " << error.what() << '\n';
    return 2;
  }
}
