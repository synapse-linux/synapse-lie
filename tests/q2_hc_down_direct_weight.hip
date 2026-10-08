// SPDX-License-Identifier: MIT
// Original HC-down -> SiLU/4 -> F16 consumer input. Synthetic GPU evidence only.
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
#include "src/core/crypto/sha256.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
namespace gufo::models::qwen38_flash_next::rocm {
#include "experiments/q2-hc-down-direct-weight.inc"
}
namespace q = gufo::models::qwen38_flash_next::rocm;
static void Require(bool ok, const char* message) {
  if (!ok) throw std::runtime_error(message);
}
static void Hip(hipError_t error) {
  if (error != hipSuccess) throw std::runtime_error(hipGetErrorString(error));
}
struct Device {
  void* storage{};
  void* data{};
  size_t bytes;
  explicit Device(size_t n) : bytes(n) {
    Hip(hipMalloc(&storage, n + 128));
    data = static_cast<uint8_t*>(storage) + 64;
    Hip(hipMemset(storage, 0xa7, 64));
    Hip(hipMemset(static_cast<uint8_t*>(data) + n, 0xa7, 64));
  }
  ~Device() { if (storage) { const auto ignored = hipFree(storage); (void)ignored; } }
  Device(const Device&) = delete;
  Device& operator=(const Device&) = delete;
  void Clear() { Hip(hipMemset(data, 0xff, bytes)); }
  std::vector<uint8_t> Read() const {
    std::array<uint8_t, 128> guards{};
    Hip(hipMemcpy(guards.data(), storage, 64, hipMemcpyDeviceToHost));
    Hip(hipMemcpy(guards.data() + 64, static_cast<const uint8_t*>(data) + bytes, 64, hipMemcpyDeviceToHost));
    Require(std::all_of(guards.begin(), guards.end(), [](auto x){return x == 0xa7;}), "Device guard changed");
    std::vector<uint8_t> values(bytes);
    Hip(hipMemcpy(values.data(), data, bytes, hipMemcpyDeviceToHost));
    return values;
  }
};
static std::string Hash(const Device& d) { return gufo::crypto::Sha256Hex(d.Read()); }
static constexpr unsigned K = 10240, M = 320, rotations = 8;
struct Inputs {
  unsigned n;
  std::vector<__half> x;
  std::array<std::vector<__half>, rotations> w;
  Device xd;
  std::array<std::unique_ptr<Device>, rotations> wd;
  std::array<std::string, rotations> hashes;
  std::string xhash;
  Inputs(unsigned rows, unsigned pattern) : n(rows), x(size_t(n) * K), xd(x.size()*2) {
    uint32_t rng = 713;
    auto value = [&]() { rng = rng * 1664525u + 1013904223u; return float(int(rng >> 16) - 32768) / 32768.0f; };
    for (size_t i=0; i<x.size(); ++i)
      x[i] = __float2half_rn(pattern == 1 ? value() * 0.00006103515625f :
             pattern == 2 ? ((i & 1) ? -0.125f : 0.125f) : value() * 0.125f);
    Hip(hipMemcpy(xd.data, x.data(), xd.bytes, hipMemcpyHostToDevice));
    xhash = Hash(xd);
    for (unsigned r=0; r<rotations; ++r) {
      w[r].resize(size_t(M)*K);
      for (auto& v : w[r]) v = __float2half_rn(value() * 0.03125f);
      wd[r] = std::make_unique<Device>(w[r].size()*2);
      Hip(hipMemcpy(wd[r]->data, w[r].data(), wd[r]->bytes, hipMemcpyHostToDevice));
      hashes[r] = Hash(*wd[r]);
    }
  }
  void Unchanged() {
    Require(Hash(xd) == xhash, "Input changed");
    for (unsigned r=0; r<rotations; ++r) Require(Hash(*wd[r]) == hashes[r], "Weight changed");
  }
};
struct State {
  Device out, half;
  explicit State(unsigned n) : out(size_t(n)*M*4), half(size_t(n)*M*2) {}
  void Clear() { out.Clear(); half.Clear(); }
};
static void Launch(bool candidate, Inputs& in, State& state, unsigned r, hipStream_t stream) {
  auto fn = candidate ? q::HcDownDirectWeightF16Gemm : q::HcDownBk256F16Gemm;
  Require(fn(in.wd[r]->data, static_cast<const __half*>(in.xd.data), static_cast<float*>(state.out.data), in.n, M, K, stream), "HC down refused");
  q::SiluScale(static_cast<float*>(state.out.data), 0.25f, size_t(in.n)*M, stream);
  q::NarrowActivations(static_cast<const float*>(state.out.data), state.half.data, false, size_t(in.n)*M, stream);
  Hip(hipGetLastError());
}
static bool Oracle(const Inputs& in, const State& state, unsigned r, const std::string& name, bool candidate) {
  const auto bytes = state.out.Read(), half = state.half.Read();
  for (size_t i=0; i<bytes.size()/4; ++i) {
    float a; uint32_t bits; __half b;
    std::memcpy(&a, bytes.data()+4*i, 4); std::memcpy(&bits, bytes.data()+4*i, 4);
    std::memcpy(&b, half.data()+2*i, 2);
    Require(std::isfinite(a) && bits != 0xffffffffu && std::isfinite(__half2float(b)), "Nonfinite or unwritten output");
    const __half narrowed = __float2half_rn(a);
    Require(std::memcmp(&b, &narrowed, 2) == 0, "Consumer F16 boundary changed");
  }
  double err=0, norm=0, max_err=0, peak=0;
  for (unsigned s=0; s<64; ++s) {
    const unsigned t = s < 8 ? std::min(in.n-1, std::array<unsigned,8>{0,15,16,31,32,95,96,in.n-1}[s]) : (s*997u+r*31u)%in.n;
    const unsigned m = s < 8 ? std::array<unsigned,8>{0,15,16,63,64,159,255,319}[s] : (s*73u+r*17u)%M;
    double dot=0;
    for (unsigned k=0; k<K; ++k) dot += double(__half2float(in.x[size_t(t)*K+k])) * double(__half2float(in.w[r][size_t(m)*K+k]));
    const double expected = 0.25 * dot / (1.0 + std::exp(-0.25 * dot));
    float actual; std::memcpy(&actual, bytes.data()+4*(size_t(t)*M+m), 4);
    const double delta = double(actual)-expected;
    err += delta*delta; norm += expected*expected;
    max_err = std::max(max_err, std::abs(delta)); peak = std::max(peak,std::abs(expected));
  }
  const double rrms = std::sqrt(err/std::max(norm,1e-300)), scaled = max_err/std::max(peak,1e-300);
  const bool pass = rrms <= 2e-5 && scaled <= 2e-5;
  std::cout << "{\"event\":\"hc_direct_oracle\",\"case\":\"" << name << "\",\"rotation\":" << r << ",\"candidate\":" << candidate
    << ",\"samples\":64,\"relative_rms\":" << rrms << ",\"scaled_error\":" << scaled << ",\"limit\":0.00002,\"pass\":" << pass << "}\n";
  return pass;
}
static bool Pair(const Device& a, const Device& b, const std::string& name, unsigned r, const char* field) {
  const auto av=a.Read(), bv=b.Read();
  const bool exact = av == bv;
  const std::string as=gufo::crypto::Sha256Hex(av), bs=gufo::crypto::Sha256Hex(bv);
  std::cout << "{\"event\":\"hc_direct_pair\",\"case\":\"" << name << "\",\"rotation\":" << r << ",\"field\":\"" << field
    << "\",\"bytes\":" << av.size() << ",\"reference_sha256\":\"" << as << "\",\"candidate_sha256\":\"" << bs << "\",\"exact\":" << exact << "}\n";
  if (!exact) {
    for (unsigned arm=0; arm<2; ++arm) {
      const auto& data=arm ? bv : av;
      std::ofstream out(name+"-"+std::to_string(r)+"-"+field+"-"+std::to_string(arm)+".bin", std::ios::binary);
      out.write(reinterpret_cast<const char*>(data.data()), data.size());
      Require(bool(out), "Failed to preserve numeric disagreement");
    }
  }
  return exact;
}
static bool Case(const std::string& name, unsigned n, unsigned pattern, bool timed, hipStream_t stream) {
  Inputs in(n,pattern);
  std::array<std::array<std::unique_ptr<State>,rotations>,2> states;
  for (auto& arm : states) for (auto& state : arm) state=std::make_unique<State>(n);
  hipEvent_t begin{},end{}; Hip(hipEventCreate(&begin)); Hip(hipEventCreate(&end));
  bool pass=true;
  for (unsigned rep=0; rep<(timed?7u:1u); ++rep) {
    const std::string label=name+"-r"+std::to_string(rep);
    for (unsigned order=0; order<2; ++order) {
      const unsigned candidate=(rep+order)%2;
      for (auto& state : states[candidate]) state->Clear();
      Hip(hipDeviceSynchronize());
      const auto start=std::chrono::steady_clock::now();
      Hip(hipEventRecord(begin,stream));
      for (unsigned r=0; r<rotations; ++r) Launch(candidate,in,*states[candidate][r],r,stream);
      Hip(hipEventRecord(end,stream)); Hip(hipEventSynchronize(end));
      const auto stop=std::chrono::steady_clock::now(); Hip(hipGetLastError());
      float ms=0; Hip(hipEventElapsedTime(&ms,begin,end));
      if (timed) {
        std::cout << "{\"event\":\"hc_direct_timing\",\"rep\":" << rep << ",\"order\":" << order << ",\"candidate\":" << bool(candidate)
          << ",\"warmup\":" << (rep<2) << ",\"iterations\":8,\"weight_bytes\":" << size_t(rotations)*M*K*2
          << ",\"gpu_event_valid\":" << (std::isfinite(ms)&&ms>0) << ",\"gpu_event_us\":";
        if (std::isfinite(ms)) std::cout << double(ms)*1000/rotations; else std::cout << "null";
        std::cout << ",\"completed_wall_us\":" << std::chrono::duration<double,std::micro>(stop-start).count()/rotations << "}\n";
      }
      for (unsigned r=0; r<rotations; ++r) pass=Oracle(in,*states[candidate][r],r,label,candidate)&&pass;
    }
    for (unsigned r=0; r<rotations; ++r) {
      pass=Pair(states[0][r]->out,states[1][r]->out,label,r,"activated-f32")&&pass;
      pass=Pair(states[0][r]->half,states[1][r]->half,label,r,"consumer-f16")&&pass;
    }
  }
  in.Unchanged(); Hip(hipEventDestroy(end)); Hip(hipEventDestroy(begin));
  std::cout << "{\"event\":\"hc_direct_case\",\"case\":\"" << name << "\",\"inputs_unchanged\":true,\"guards_finite_written\":true}\n";
  return pass;
}
int main() {
  try {
    std::cout << std::boolalpha << std::defaultfloat << std::setprecision(12);
    hipStream_t stream{}; Hip(hipStreamCreateWithFlags(&stream,hipStreamNonBlocking));
    bool pass=Case("n96",96,0,false,stream);
    pass=Case("n97-tiny",97,1,false,stream)&&pass;
    pass=Case("n129-cancellation",129,2,false,stream)&&pass;
    pass=Case("n2048",2048,0,true,stream)&&pass;
    Hip(hipStreamSynchronize(stream)); Hip(hipStreamDestroy(stream));
    std::cout << "{\"event\":\"hc_direct_complete\",\"numerical_pass\":" << pass
      << ",\"timing_retained\":true,\"safe_completion\":true,\"model_inference\":false}\n";
    return pass?0:1;
  } catch (const std::exception& e) {
    std::cerr << "FAIL: " << e.what() << '\n'; return 2;
  }
}
