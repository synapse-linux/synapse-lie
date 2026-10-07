// SPDX-License-Identifier: MIT
// Synthetic Q8 consumer comparison; original encoded bytes and row reductions.
#include "qfn_mmq_prelude.h"
namespace qfn_mmq {
#include "mmvq.hpp"
#include "unary.hpp"
#include "vecdotq.hpp"
#include "experiments/q2-decode-q8-control.inc"
#include "experiments/q2-decode-q8-compact.inc"
}
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include "src/core/crypto/sha256.hpp"

namespace q = qfn_mmq;
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
    std::vector<uint8_t> out(bytes);
    Hip(hipMemcpy(out.data(), data, bytes, hipMemcpyDeviceToHost));
    return out;
  }
};
static std::string Hash(const Device& d) { return gufo::crypto::Sha256Hex(d.Read()); }

struct Inputs {
  unsigned m, k, banks, iterations;
  bool gated;
  std::vector<q::block_q8_1> x;
  std::vector<std::vector<q::block_q8_0>> weights, gates;
  Device xd;
  std::vector<std::unique_ptr<Device>> wd, gd;
  std::vector<std::string> hashes;
  std::string xhash;
  Inputs(unsigned rows, unsigned cols, bool gate, bool tiny, bool timed)
      : m(rows), k(cols), gated(gate), x(k/32), xd(x.size()*sizeof(x[0])) {
    const size_t one = size_t(m)*(k/32)*sizeof(q::block_q8_0);
    banks = timed ? std::max<size_t>(2, (48*1024*1024 + one*(1+gated)-1)/(one*(1+gated))) : 2;
    Require(banks <= 64, "Unexpected bank budget");
    // Several rotations use distinct destinations, checked before any reuse.
    iterations = timed ? banks * std::max(1u, (64u + banks - 1) / banks) : banks;
    uint32_t rng=713;
    const auto next = [&]() { rng=rng*1664525u+1013904223u; return rng; };
    for (auto& b : x) {
      b.ds=__floats2half2_rn(tiny ? 0.0000158f : 0.00373f, 0.f);
      for (auto& v : b.qs) v=static_cast<int8_t>(int(next()>>24)-128);
    }
    Hip(hipMemcpy(xd.data,x.data(),xd.bytes,hipMemcpyHostToDevice));
    xhash=Hash(xd);
    for (unsigned r=0;r<banks;++r) {
      weights.emplace_back(size_t(m)*(k/32));
      gates.emplace_back(gated ? weights.back().size() : 0);
      for (auto* values : {&weights.back(), &gates.back()})
        for (auto& b : *values) {
          b.d=__float2half_rn(0.000513f*float(1+next()%3));
          for (auto& v : b.qs) v=static_cast<int8_t>(int(next()>>24)-128);
        }
      wd.emplace_back(std::make_unique<Device>(one));
      Hip(hipMemcpy(wd.back()->data,weights.back().data(),one,hipMemcpyHostToDevice));
      hashes.push_back(Hash(*wd.back()));
      if (gated) {
        gd.emplace_back(std::make_unique<Device>(one));
        Hip(hipMemcpy(gd.back()->data,gates.back().data(),one,hipMemcpyHostToDevice));
        hashes.push_back(Hash(*gd.back()));
      }
    }
  }
  void Unchanged() const {
    Require(Hash(xd)==xhash,"Input changed");
    for (unsigned r=0;r<banks;++r) {
      Require(Hash(*wd[r])==hashes[r*(1+gated)],"Weight changed");
      if (gated) Require(Hash(*gd[r])==hashes[r*2+1],"Gate changed");
    }
  }
};
static void Launch(bool candidate, const Inputs& in, Device& out, unsigned r, hipStream_t stream) {
  const auto* x=static_cast<const q::block_q8_1*>(in.xd.data);
  auto* y=static_cast<float*>(out.data);
  const void* w=in.wd[r]->data;
  const void* g=in.gated ? in.gd[r]->data : nullptr;
  if (candidate) {
    if (in.gated) q::mul_mat_vec_q8_compact<true><<<in.m,32,0,stream>>>(w,g,x,y,in.k,in.m,in.k/32);
    else q::mul_mat_vec_q8_compact<false><<<in.m,32,0,stream>>>(w,nullptr,x,y,in.k,in.m,in.k/32);
  } else {
    if (in.gated) q::mul_mat_vec_q8<1,true><<<in.m,32,0,stream>>>(w,g,x,y,in.k,in.m,in.k/32);
    else q::mul_mat_vec_q8<1,false><<<in.m,32,0,stream>>>(w,nullptr,x,y,in.k,in.m,in.k/32);
  }
  Hip(hipGetLastError());
}
static bool Oracle(const Inputs& in, const std::vector<uint8_t>& bytes, unsigned r,
                   const std::string& label, bool candidate) {
  for (size_t i=0;i<bytes.size()/4;++i) {
    float value; std::memcpy(&value,bytes.data()+4*i,4);
    Require(std::isfinite(value),"Nonfinite or unwritten output");
  }
  double error=0,norm=0,max_error=0,peak=0;
  for (unsigned s=0;s<64;++s) {
    const unsigned row=s<8 ? std::array<unsigned,8>{0,1,2,3,4,31,in.m-2,in.m-1}[s] : (s*997+r*73)%in.m;
    double dot=0,gate=0;
    for (unsigned b=0;b<in.k/32;++b) {
      const auto& x=in.x[b]; const auto& w=in.weights[r][size_t(row)*(in.k/32)+b];
      int sum=0,gsum=0;
      for (unsigned j=0;j<32;++j) {
        sum+=int(w.qs[j])*int(x.qs[j]);
        if (in.gated) gsum+=int(in.gates[r][size_t(row)*(in.k/32)+b].qs[j])*int(x.qs[j]);
      }
      dot+=double(sum)*double(__half2float(w.d))*double(__low2float(x.ds));
      if (in.gated) gate+=double(gsum)*double(__half2float(in.gates[r][size_t(row)*(in.k/32)+b].d))*double(__low2float(x.ds));
    }
    const double expected=in.gated ? dot*gate/(1+std::exp(-gate)) : dot;
    float actual; std::memcpy(&actual,bytes.data()+4*row,4);
    const double delta=actual-expected;
    error+=delta*delta; norm+=expected*expected;
    max_error=std::max(max_error,std::abs(delta)); peak=std::max(peak,std::abs(expected));
  }
  const double rrms=std::sqrt(error/std::max(norm,1e-300)),scaled=max_error/std::max(peak,1e-300);
  const bool pass=rrms<=2e-5 && scaled<=2e-5;
  std::cout << "{\"event\":\"q8_compact_oracle\",\"case\":\"" << label << "\",\"bank\":" << r << ",\"candidate\":" << candidate
    << ",\"samples\":64,\"relative_rms\":" << rrms << ",\"scaled_error\":" << scaled << ",\"limit\":0.00002,\"pass\":" << pass << "}\n";
  return pass;
}
static bool Case(const std::string& name,unsigned m,unsigned k,bool gated,bool tiny,bool timed,hipStream_t stream) {
  Inputs in(m,k,gated,tiny,timed);
  std::array<std::vector<std::unique_ptr<Device>>,2> outputs;
  for (auto& arm:outputs) for (unsigned r=0;r<in.iterations;++r) arm.emplace_back(std::make_unique<Device>(size_t(m)*4));
  hipEvent_t begin{},end{}; Hip(hipEventCreate(&begin)); Hip(hipEventCreate(&end));
  bool pass=true;
  for (unsigned rep=0;rep<(timed?7u:1u);++rep) {
    const std::string label=name+"-r"+std::to_string(rep);
    std::array<std::vector<std::vector<uint8_t>>,2> bytes;
    for (unsigned order=0;order<2;++order) {
      const unsigned arm=(rep+order)%2;
      for (auto& out:outputs[arm]) out->Clear();
      Hip(hipStreamSynchronize(stream));
      const auto start=std::chrono::steady_clock::now(); Hip(hipEventRecord(begin,stream));
      for (unsigned r=0;r<in.iterations;++r) Launch(arm,in,*outputs[arm][r],r%in.banks,stream);
      Hip(hipEventRecord(end,stream)); Hip(hipEventSynchronize(end));
      const auto stop=std::chrono::steady_clock::now(); Hip(hipGetLastError());
      float ms=0; Hip(hipEventElapsedTime(&ms,begin,end));
      if (timed) {
        std::cout << "{\"event\":\"q8_compact_timing\",\"case\":\"" << name << "\",\"rep\":" << rep << ",\"order\":" << order
          << ",\"candidate\":" << bool(arm) << ",\"warmup\":" << (rep<2) << ",\"iterations\":" << in.iterations
          << ",\"weight_bytes\":" << in.banks*in.wd[0]->bytes*(1+gated) << ",\"gpu_event_valid\":" << (std::isfinite(ms)&&ms>0) << ",\"gpu_event_us\":";
        if (std::isfinite(ms)) std::cout << double(ms)*1000/in.iterations; else std::cout << "null";
        std::cout << ",\"completed_wall_us\":" << std::chrono::duration<double,std::micro>(stop-start).count()/in.iterations << "}\n";
      }
      for (unsigned r=0;r<in.iterations;++r) {
        bytes[arm].push_back(outputs[arm][r]->Read());
        pass=Oracle(in,bytes[arm].back(),r%in.banks,label+"-i"+std::to_string(r),arm)&&pass;
      }
    }
    for (unsigned r=0;r<in.iterations;++r) {
      const bool exact=bytes[0][r]==bytes[1][r]; pass=exact&&pass;
      std::cout << "{\"event\":\"q8_compact_pair\",\"case\":\"" << label << "\",\"bank\":" << r << ",\"bytes\":" << bytes[0][r].size()
        << ",\"reference_sha256\":\"" << gufo::crypto::Sha256Hex(bytes[0][r]) << "\",\"candidate_sha256\":\"" << gufo::crypto::Sha256Hex(bytes[1][r]) << "\",\"exact\":" << exact << "}\n";
      if (!exact) for (unsigned arm=0;arm<2;++arm) {
        std::ofstream out(label+"-"+std::to_string(r)+"-"+std::to_string(arm)+".bin",std::ios::binary);
        out.write(reinterpret_cast<const char*>(bytes[arm][r].data()),bytes[arm][r].size());
        Require(bool(out),"Failed to preserve numeric disagreement");
      }
    }
  }
  in.Unchanged(); Hip(hipEventDestroy(end)); Hip(hipEventDestroy(begin));
  std::cout << "{\"event\":\"q8_compact_case\",\"case\":\"" << name << "\",\"rows\":" << m << ",\"cols\":" << k << ",\"banks\":" << in.banks
    << ",\"inputs_unchanged\":true,\"guards_finite_written\":true}\n";
  return pass;
}
int main() {
  try {
    std::cout << std::boolalpha << std::defaultfloat << std::setprecision(12);
    hipStream_t stream{}; Hip(hipStreamCreateWithFlags(&stream,hipStreamNonBlocking));
    bool pass=Case("k2592-tiny",1028,2592,false,true,false,stream);
    pass=Case("ssm-in",16384,2560,false,false,true,stream)&&pass;
    pass=Case("attn-out",2560,6144,false,false,true,stream)&&pass;
    pass=Case("shared-down",2560,640,false,false,true,stream)&&pass;
    pass=Case("gated",640,2560,true,false,true,stream)&&pass;
    pass=Case("k224-gated-tiny",33,224,true,true,false,stream)&&pass;
    pass=Case("k256-plain",31,256,false,false,false,stream)&&pass;
    pass=Case("k288-gated",35,288,true,false,false,stream)&&pass;
    Hip(hipStreamSynchronize(stream)); Hip(hipStreamDestroy(stream));
    std::cout << "{\"event\":\"q8_compact_complete\",\"numerical_pass\":" << pass << ",\"timing_retained\":true,\"safe_completion\":true,\"model_inference\":false}\n";
    return pass?0:1;
  } catch (const std::exception& e) { std::cerr << "FAIL: " << e.what() << '\n'; return 2; }
}
