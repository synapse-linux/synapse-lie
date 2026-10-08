// SPDX-License-Identifier: MIT
// Lossless Q8 layout screen. Synthetic data only; no model or prefill change.
#include "qfn_mmq_prelude.h"
namespace qfn_mmq {
#include "mmvq.hpp"
#include "unary.hpp"
#include "vecdotq.hpp"
#include "experiments/q2-decode-q8-control.inc"
#include "experiments/q2-decode-q8-planar.inc"
}
#include <array>
#include <chrono>
#include <cmath>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <vector>

namespace q = qfn_mmq;
static void Require(bool ok, const char* message) {
  if (!ok) throw std::runtime_error(message);
}
static void Hip(hipError_t rc) {
  if (rc != hipSuccess) throw std::runtime_error(hipGetErrorString(rc));
}
struct Device {
  void* storage{};
  void* data{};
  size_t bytes;
  bool allocation_end;
  explicit Device(size_t size, bool end=false) : bytes(size), allocation_end(end) {
    Hip(hipMalloc(&storage, size+(end?64:128)));
    data = static_cast<unsigned char*>(storage)+64;
    Hip(hipMemset(storage, 0xa7, size+(end?64:128)));
  }
  ~Device() {
    if (storage) { const auto rc=hipFree(storage); (void)rc; }
  }
  Device(const Device&)=delete;
  Device& operator=(const Device&)=delete;
  void Put(const void* src) { Hip(hipMemcpy(data,src,bytes,hipMemcpyHostToDevice)); }
  void Clear() { Hip(hipMemset(data,0xff,bytes)); }
  std::vector<unsigned char> Read() const {
    std::array<unsigned char,128> guard{};
    guard.fill(0xa7);
    Hip(hipMemcpy(guard.data(),storage,64,hipMemcpyDeviceToHost));
    if (!allocation_end)
      Hip(hipMemcpy(guard.data()+64,static_cast<const unsigned char*>(data)+bytes,64,hipMemcpyDeviceToHost));
    Require(std::all_of(guard.begin(),guard.end(),[](auto x){return x==0xa7;}),"Device guard changed");
    std::vector<unsigned char> out(bytes);
    Hip(hipMemcpy(out.data(),data,bytes,hipMemcpyDeviceToHost));
    return out;
  }
};

struct Matrix {
  std::vector<q::block_q8_0> original;
  Device encoded, codes, scales;
  Matrix(size_t blocks, uint32_t& rng, unsigned family)
      : original(blocks), encoded(blocks*sizeof(q::block_q8_0),true),
        codes(blocks*32,true), scales(blocks*2,true) {
    static_assert(sizeof(q::block_q8_0)==34);
    for (size_t i=0;i<blocks;++i) {
      rng=rng*1664525u+1013904223u;
      float d=0.000513f*float(1+rng%3);
      if (family==2) d=i%3 ? -0.f : 0.f;
      if (family==3 && i%7==0) d=-d;
      original[i].d=__float2half_rn(d);
      if (family==4) {
        const uint16_t bits=i;
        std::memcpy(&original[i].d,&bits,2);
      }
      for (auto& v:original[i].qs) {
        rng=rng*1664525u+1013904223u;
        v=static_cast<int8_t>(int(rng>>24)-128);
      }
    }
    encoded.Put(original.data());
  }
  void Pack(hipStream_t stream) {
    q::PackQ8PlanarKernel<<<(original.size()+255)/256,256,0,stream>>>(
        static_cast<const q::block_q8_0*>(encoded.data),static_cast<int*>(codes.data),
        static_cast<unsigned short*>(scales.data),original.size());
    Hip(hipGetLastError());
  }
  void Check() const {
    const auto raw=encoded.Read(), c=codes.Read(), s=scales.Read();
    Require(std::memcmp(raw.data(),original.data(),raw.size())==0,"Original weights changed");
    for (size_t i=0;i<original.size();++i) {
      Require(std::memcmp(c.data()+32*i,original[i].qs,32)==0,"Packed codes changed");
      Require(std::memcmp(s.data()+2*i,&original[i].d,2)==0,"Packed scale bits changed");
    }
  }
};
struct Inputs {
  unsigned m,k,banks,steps;
  bool gated;
  std::vector<q::block_q8_1> x;
  Device xd;
  std::vector<std::unique_ptr<Matrix>> weights,gates;
  Inputs(unsigned rows,unsigned cols,bool gate,unsigned family,bool timed)
      : m(rows),k(cols),steps(timed?64:3),gated(gate),x(k/32),xd(x.size()*sizeof(x[0]),true) {
    const size_t one=size_t(m)*(k/32)*sizeof(q::block_q8_0)*(1+gated);
    banks=timed?std::max<size_t>(1,(64*1024*1024+one-1)/one):2;
    Require(banks<=steps,"Insufficient calls to rotate the weight bank");
    uint32_t rng=713;
    for (auto& block:x) {
      block.ds=__floats2half2_rn(family==1?0.0000158f:0.00373f,0.f);
      for (auto& v:block.qs) {
        rng=rng*1664525u+1013904223u;
        v=static_cast<int8_t>(int(rng>>24)-128);
      }
    }
    xd.Put(x.data());
    for (unsigned i=0;i<banks;++i) {
      weights.emplace_back(std::make_unique<Matrix>(size_t(m)*(k/32),rng,family));
      if (gated) gates.emplace_back(std::make_unique<Matrix>(size_t(m)*(k/32),rng,family));
    }
  }
  void Unchanged() const {
    const auto raw=xd.Read();
    Require(std::memcmp(raw.data(),x.data(),raw.size())==0,"Activation changed");
    for (const auto& m:weights) m->Check();
    for (const auto& m:gates) m->Check();
  }
};

static void Launch(unsigned arm,const Inputs& in,Device& output,unsigned step,hipStream_t stream) {
  const auto bank=step%in.banks;
  const auto& w=*in.weights[bank];
  const auto* x=static_cast<const q::block_q8_1*>(in.xd.data);
  auto* out=static_cast<float*>(output.data);
  if (arm) {
    const auto* codes=static_cast<const int*>(w.codes.data);
    const auto* scales=static_cast<const unsigned short*>(w.scales.data);
    if (in.gated) {
      const auto& g=*in.gates[bank];
      q::Q8PlanarDecodeKernel<true><<<in.m,32,0,stream>>>(codes,scales,
          static_cast<const int*>(g.codes.data),static_cast<const unsigned short*>(g.scales.data),x,out,in.k);
    } else q::Q8PlanarDecodeKernel<false><<<in.m,32,0,stream>>>(codes,scales,nullptr,nullptr,x,out,in.k);
  } else {
    if (in.gated) q::mul_mat_vec_q8<1,true><<<in.m,32,0,stream>>>(w.encoded.data,in.gates[bank]->encoded.data,x,out,in.k,in.m,in.k/32);
    else q::mul_mat_vec_q8<1,false><<<in.m,32,0,stream>>>(w.encoded.data,nullptr,x,out,in.k,in.m,in.k/32);
  }
  Hip(hipGetLastError());
}

static bool Oracle(const Inputs& in,const std::vector<unsigned char>& raw,unsigned bank,
                   const std::string& label,unsigned arm) {
  double error=0,norm=0,max_error=0,peak=0;
  for (unsigned sample=0;sample<64;++sample) {
    const unsigned row=sample<4 ? std::array<unsigned,4>{0,1,in.m-2,in.m-1}[sample] : (sample*997+bank*73)%in.m;
    double dot=0,gate=0;
    for (unsigned b=0;b<in.k/32;++b) {
      const auto& x=in.x[b];const auto& w=in.weights[bank]->original[size_t(row)*(in.k/32)+b];
      int sum=0,gsum=0;
      for (unsigned j=0;j<32;++j) {
        sum+=int(w.qs[j])*int(x.qs[j]);
        if (in.gated) gsum+=int(in.gates[bank]->original[size_t(row)*(in.k/32)+b].qs[j])*int(x.qs[j]);
      }
      dot+=double(sum)*double(__half2float(w.d))*double(__low2float(x.ds));
      if (in.gated) gate+=double(gsum)*double(__half2float(in.gates[bank]->original[size_t(row)*(in.k/32)+b].d))*double(__low2float(x.ds));
    }
    const double expected=in.gated ? dot*gate/(1+std::exp(-gate)) : dot;
    float actual;std::memcpy(&actual,raw.data()+4*row,4);
    const double delta=actual-expected;
    error+=delta*delta;norm+=expected*expected;max_error=std::max(max_error,std::abs(delta));peak=std::max(peak,std::abs(expected));
  }
  const double rrms=std::sqrt(error/std::max(norm,1e-300)),scaled=max_error/std::max(peak,1e-300);
  const bool pass=rrms<=2e-5 && scaled<=2e-5;
  std::cout<<"{\"event\":\"q8_planar_oracle\",\"case\":\""<<label<<"\",\"bank\":"<<bank<<",\"candidate\":"<<bool(arm)
      <<",\"samples\":64,\"relative_rms\":"<<rrms<<",\"scaled_error\":"<<scaled<<",\"limit\":0.00002,\"pass\":"<<pass<<"}\n";
  return pass;
}

static bool Case(const std::string& name,unsigned m,unsigned k,bool gated,unsigned family,bool timed,hipStream_t stream) {
  Inputs in(m,k,gated,family,timed);
  hipEvent_t begin{},end{};Hip(hipEventCreate(&begin));Hip(hipEventCreate(&end));
  Hip(hipEventRecord(begin,stream));
  for (auto& matrix:in.weights) matrix->Pack(stream);
  for (auto& matrix:in.gates) matrix->Pack(stream);
  Hip(hipEventRecord(end,stream));Hip(hipEventSynchronize(end));
  float packing_ms=0;Hip(hipEventElapsedTime(&packing_ms,begin,end));
  in.Unchanged();
  const size_t bytes=size_t(in.banks)*m*(k/32)*sizeof(q::block_q8_0)*(1+gated);
  std::cout<<"{\"event\":\"q8_planar_pack\",\"case\":\""<<name<<"\",\"original_bytes\":"<<bytes
      <<",\"planar_bytes\":"<<bytes<<",\"additional_resident_bytes\":"<<bytes<<",\"gpu_ms\":"<<packing_ms
      <<",\"all_scale_code_bits_exact\":true}\n";
  std::array<std::vector<std::unique_ptr<Device>>,2> outputs;
  std::array<hipGraph_t,2> graph{};std::array<hipGraphExec_t,2> exec{};
  for (unsigned arm=0;arm<2;++arm) {
    for (unsigned step=0;step<in.steps;++step) outputs[arm].emplace_back(std::make_unique<Device>(size_t(m)*4));
    Hip(hipStreamBeginCapture(stream,hipStreamCaptureModeThreadLocal));
    for (unsigned step=0;step<in.steps;++step) Launch(arm,in,*outputs[arm][step],step,stream);
    Hip(hipStreamEndCapture(stream,&graph[arm]));Hip(hipGraphInstantiate(&exec[arm],graph[arm],nullptr,nullptr,0));
  }
  bool pass=true;
  for (unsigned rep=0;rep<(timed?8u:1u);++rep) {
    std::array<std::vector<std::vector<unsigned char>>,2> bytes_out;
    for (unsigned order=0;order<2;++order) {
      const unsigned arm=(rep+order)%2;
      for (auto& out:outputs[arm]) out->Clear();
      Hip(hipStreamSynchronize(stream));
      const auto start=std::chrono::steady_clock::now();Hip(hipEventRecord(begin,stream));
      Hip(hipGraphLaunch(exec[arm],stream));Hip(hipEventRecord(end,stream));Hip(hipEventSynchronize(end));
      const auto finish=std::chrono::steady_clock::now();Hip(hipGetLastError());
      float ms=0;Hip(hipEventElapsedTime(&ms,begin,end));
      if (timed) std::cout<<"{\"event\":\"q8_planar_timing\",\"case\":\""<<name<<"\",\"rep\":"<<rep<<",\"order\":"<<order
          <<",\"candidate\":"<<bool(arm)<<",\"warmup\":"<<(rep<2)<<",\"iterations\":"<<in.steps<<",\"weight_bytes\":"<<bytes
          <<",\"gpu_event_valid\":"<<(std::isfinite(ms)&&ms>0)<<",\"gpu_event_us\":"<<double(ms)*1000/in.steps
          <<",\"completed_wall_us\":"<<std::chrono::duration<double,std::micro>(finish-start).count()/in.steps<<"}\n";
      for (unsigned step=0;step<in.steps;++step) {
        auto raw=outputs[arm][step]->Read();
        for (size_t i=0;i<raw.size();i+=4) {
          float value;std::memcpy(&value,raw.data()+i,4);
          Require(std::isfinite(value),"Nonfinite or unwritten output");
        }
        if (rep==0 && step<in.banks) pass=Oracle(in,raw,step,name,arm)&&pass;
        bytes_out[arm].push_back(std::move(raw));
      }
    }
    for (unsigned step=0;step<in.steps;++step) {
      const bool exact=bytes_out[0][step]==bytes_out[1][step];pass=exact&&pass;
      std::cout<<"{\"event\":\"q8_planar_pair\",\"case\":\""<<name<<"\",\"rep\":"<<rep<<",\"step\":"<<step
          <<",\"bank\":"<<step%in.banks<<",\"bytes\":"<<bytes_out[0][step].size()<<",\"exact\":"<<exact<<"}\n";
      if (!exact) for (unsigned arm=0;arm<2;++arm) {
        const auto& raw=bytes_out[arm][step];
        std::ofstream out("results/"+name+"-r"+std::to_string(rep)+"-s"+std::to_string(step)+"-a"+std::to_string(arm)+".bin",std::ios::binary);
        out.write(reinterpret_cast<const char*>(raw.data()),raw.size());Require(bool(out),"Failed to save disagreement");
      }
    }
  }
  in.Unchanged();
  for (unsigned arm=0;arm<2;++arm) { Hip(hipGraphExecDestroy(exec[arm]));Hip(hipGraphDestroy(graph[arm])); }
  Hip(hipEventDestroy(end));Hip(hipEventDestroy(begin));
  std::cout<<"{\"event\":\"q8_planar_case\",\"case\":\""<<name<<"\",\"rows\":"<<m<<",\"cols\":"<<k
      <<",\"banks\":"<<in.banks<<",\"inputs_unchanged\":true,\"guards_finite_written\":true}\n";
  return pass;
}
int main() {
  try {
    std::cout<<std::boolalpha<<std::defaultfloat<<std::setprecision(12);
    hipStream_t stream{};Hip(hipStreamCreateWithFlags(&stream,hipStreamNonBlocking));
    {
      uint32_t rng=713;
      Matrix scale_domain(65536,rng,4);
      scale_domain.Pack(stream);Hip(hipStreamSynchronize(stream));scale_domain.Check();
      std::cout<<"{\"event\":\"q8_planar_scale_domain\",\"all_65536_scale_bits_exact\":true,\"codes_exact\":true}\n";
    }
    bool pass=Case("k2592-tiny",257,2592,false,1,false,stream);
    pass=Case("k32-zero",33,32,true,2,false,stream)&&pass;
    pass=Case("k96-signed",9,96,true,3,false,stream)&&pass;
    pass=Case("ssm-in",16384,2560,false,0,true,stream)&&pass;
    pass=Case("attn-out",2560,6144,false,0,true,stream)&&pass;
    pass=Case("vocabulary",248320,2560,false,0,true,stream)&&pass;
    pass=Case("shared-gated",640,2560,true,0,true,stream)&&pass;
    Hip(hipStreamSynchronize(stream));Hip(hipStreamDestroy(stream));
    std::cout<<"{\"event\":\"q8_planar_complete\",\"numerical_pass\":"<<pass
        <<",\"timing_retained\":true,\"safe_completion\":true,\"model_inference\":false}\n";
    return pass?0:1;
  } catch (const std::exception& error) {
    std::cerr<<"FAIL: "<<error.what()<<'\n';return 2;
  }
}
