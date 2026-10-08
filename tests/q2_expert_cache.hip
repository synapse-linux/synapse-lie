// SPDX-License-Identifier: MIT
// Persistent IQ2/Q2_K operands versus the retained encoded routes.
#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
#include "src/core/crypto/sha256.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
namespace q = gufo::models::qwen38_flash_next::rocm;
#include "tests/q2_expert_cache_common.inc"
#include "tests/q2_expert_cache_inputs.inc"
#include "experiments/q2_expert_cache_iq2_grid.inc"

static float HalfValue(std::uint16_t h) {
  const unsigned e = (h >> 10) & 31, f = h & 1023;
  const float v = e ? std::ldexp(float(1024 + f), int(e) - 25)
                    : std::ldexp(float(f), -24);
  return h & 32768 ? -v : v;
}
static std::uint16_t HalfAt(const std::uint8_t* p) {
  std::uint16_t h; std::memcpy(&h,p,2); return h;
}
static std::uint16_t ReferenceWeight(const std::vector<std::uint8_t>& encoded,
    bool iq2, unsigned m, unsigned k, std::size_t flat) {
  const unsigned col = flat % k;
  const std::size_t erow = flat / k;
  const auto* b = encoded.data() + erow * ((k+255)/256) * (iq2 ? 66 : 84)
                  + (col/256) * (iq2 ? 66 : 84);
  if (iq2) {
    const unsigned sub=(col%256)/32, part=(col%32)/8;
    std::uint32_t indices, signs;
    std::memcpy(&indices,b+2+sub*8,4);std::memcpy(&signs,b+6+sub*8,4);
    const unsigned code=(indices>>(8*part))&255, s7=(signs>>(7*part))&127;
    const unsigned signmask=s7 | ((std::popcount(s7)&1U)<<7);
    const int magnitude=(kOracleIq2Grid[code]>>(8*(col%8)))&255;
    const int signed_value=(signmask>>(col%8))&1 ? -magnitude : magnitude;
    const auto scale=RoundHalf(HalfValue(HalfAt(b))*float(2*(signs>>28)+1)*0.125f);
    // Half FMA with a positive-zero addend makes an exact-zero product +0.
    const float product=HalfValue(scale)*float(signed_value);
    return product==0 ? 0 : RoundHalf(product);
  }
  const unsigned idx=col%256, sm=b[idx/16];
  const unsigned code=(b[16+(idx/128)*32+idx%32]>>(2*((idx%128)/32)))&3;
  const float scale=HalfValue(HalfAt(b+80))*float(sm&15);
  const float bias=-HalfValue(HalfAt(b+82))*float(sm>>4);
  return RoundHalf(std::fma(float(code),scale,bias));
}
struct Mirror {
  Device buffer;
  std::string digest;
  bool format_pass=true;
  Mirror(const Device& encoded, bool iq2, unsigned experts, unsigned m,
         unsigned k, hipStream_t stream) : buffer(std::size_t(experts)*m*k*2) {
    Hip(hipMemsetAsync(buffer.data,0x55,buffer.bytes,stream));
    Require(q::ConvertExpertCache(encoded.data,buffer.data,iq2,experts,m,k,stream),
            "Cache conversion refused");
    auto src=Read(encoded,stream), dst=Read(buffer,stream);
    const std::size_t count=std::size_t(experts)*m*k;
    const std::size_t samples=std::min<std::size_t>(count,65536);
    std::size_t changed=0;
    for(std::size_t i=0;i<samples;++i) {
      const std::size_t flat=i*(count-1)/(samples-1);
      const unsigned col=flat%k,row=(flat/k)%m;
      const std::size_t expert=flat/(std::size_t(m)*k);
      const std::size_t index=expert*m*k+((col/16)*m+row)*16+col%16;
      changed+=HalfAt(dst.data()+index*2)!=ReferenceWeight(src,iq2,m,k,flat);
    }
    format_pass=changed==0;digest=Hash(dst);
    std::cout<<"{\"event\":\"expert_cache_format\",\"iq2\":"<<iq2
      <<",\"samples\":"<<samples<<",\"elements\":"<<count
      <<",\"changed\":"<<changed<<",\"pass\":"<<format_pass<<"}\n";
  }
  void Unchanged(hipStream_t stream) { Require(Hash(Read(buffer,stream))==digest,"Cache changed"); }
};
static bool Compare(Device& original, Device& cached, bool half,
    const std::string& label, unsigned rotation, hipStream_t stream) {
  auto a=Read(original,stream),b=Read(cached,stream);
  Require(a.size()==b.size(),"Different output sizes");
  std::size_t changed=0;
  for(std::size_t i=0;i<a.size();i+=half?2:4) {
    std::uint32_t x=0,y=0;
    std::memcpy(&x,a.data()+i,half?2:4);std::memcpy(&y,b.data()+i,half?2:4);
    Require(x!=(half?0x7e55U:0x7fc0beefU) && y!=(half?0x7e55U:0x7fc0beefU),
            "Required output unwritten");
    changed+=x!=y;
  }
  std::cout<<"{\"event\":\"expert_cache_replay\",\"case\":\""<<label
    <<"\",\"rotation\":"<<rotation<<",\"half\":"<<half
    <<",\"bytes\":"<<a.size()<<",\"changed\":"<<changed
    <<",\"exact\":"<<(changed==0)<<",\"guards_exact\":true,\"all_written\":true}\n";
  if(changed) for(unsigned arm=0;arm<2;++arm) {
    const auto& data=arm?b:a;
    std::ofstream out("results/"+label+"-"+std::to_string(rotation)+(arm?"-cache.bin":"-original.bin"),std::ios::binary);
    out.write(reinterpret_cast<const char*>(data.data()),data.size());Require(bool(out),"Output save failed");
  }
  return changed==0;
}
static void Poison(Device& out,bool half,hipStream_t stream) {
  std::vector<std::uint8_t> data(out.bytes);
  const std::uint32_t value=half?0x7e55U:0x7fc0beefU;
  for(std::size_t i=0;i<data.size();i+=half?2:4)std::memcpy(data.data()+i,&value,half?2:4);
  Upload(out,data,stream);
}
template<class Launch>
static void Time(const std::string& label,std::size_t weights,std::size_t mirrors,
                 Launch launch,hipStream_t stream) {
  Require(weights>32*1024*1024 && mirrors>32*1024*1024,"Rotation smaller than MALL");
  hipEvent_t begin,end;Hip(hipEventCreate(&begin));Hip(hipEventCreate(&end));
  for(unsigned rep=0;rep<7;++rep)for(unsigned order=0;order<2;++order) {
    const bool cached=(rep+order)%2;
    Hip(hipEventRecord(begin,stream));
    for(unsigned r=0;r<3;++r)launch(cached,r);
    Hip(hipEventRecord(end,stream));Hip(hipEventSynchronize(end));
    float ms;Hip(hipEventElapsedTime(&ms,begin,end));
    std::cout<<"{\"event\":\"expert_cache_timing\",\"case\":\""<<label
      <<"\",\"rep\":"<<rep<<",\"order\":"<<order<<",\"cached\":"<<cached
      <<",\"warmup\":"<<(rep<2)<<",\"rotations\":3,\"weight_bytes\":"<<weights
      <<",\"cache_bytes\":"<<mirrors<<",\"us\":"<<double(ms)*1000/3<<"}\n";
  }
  Hip(hipEventDestroy(end));Hip(hipEventDestroy(begin));
}
static bool Gate(unsigned n,unsigned m,unsigned k,unsigned experts,unsigned used,
                 unsigned width,bool timing,hipStream_t stream) {
  gate_case::Inputs in(n,m,k,experts,used,width,stream);
  std::array<std::unique_ptr<Mirror>,3> gate,up;
  bool pass=true;
  for(unsigned r=0;r<3;++r) {
    gate[r]=std::make_unique<Mirror>(*in.gate[r],true,experts,m,k,stream);
    up[r]=std::make_unique<Mirror>(*in.up[r],true,experts,m,k,stream);
    pass=gate[r]->format_pass&&up[r]->format_pass&&pass;
  }
  Device a(std::size_t(n)*used*m*4),b(a.bytes);
  const auto launch=[&](bool cached,unsigned r) {
    const auto call=[&](const Device& map,unsigned count,unsigned tile) {
      if(!count)return;
      Require((cached?q::RoutedCachedIQ2Gemm:q::RoutedGatedIQ2Gemm)(
        cached?gate[r]->buffer.data:in.gate[r]->data,cached?up[r]->buffer.data:in.up[r]->data,
        static_cast<const __half*>(in.x.data),static_cast<const std::int32_t*>(map.data),count,tile,
        static_cast<const std::int32_t*>(in.bd->data),static_cast<const std::int32_t*>(in.td->data),
        static_cast<const std::int32_t*>(in.sd->data),static_cast<float*>(cached?b.data:a.data),m,k,stream),
        "Gate/up dispatch refused");
    };
    if(width)call(*in.nd,in.narrow.size(),width);
    else {call(*in.wd,in.wide.size(),128);call(*in.nd,in.narrow.size(),64);}
    Hip(hipGetLastError());
  };
  const std::string label="iq2-n"+std::to_string(n)+"-m"+std::to_string(m)+"-e"+std::to_string(experts)+"-w"+std::to_string(width);
  for(unsigned r=0;r<3;++r) {Poison(a,false,stream);Poison(b,false,stream);launch(false,r);launch(true,r);pass=Compare(a,b,false,label,r,stream)&&pass;}
  if(timing)Time(label,in.encoded.size()*6,gate[0]->buffer.bytes*6,launch,stream);
  for(unsigned r=0;r<3;++r) {launch(false,r);launch(true,r);pass=Compare(a,b,false,label+"-post",r,stream)&&pass;gate[r]->Unchanged(stream);up[r]->Unchanged(stream);}
  in.Unchanged(stream);return pass;
}
static bool Down(unsigned n,unsigned m,unsigned experts,unsigned used,unsigned width,
                 bool timing,hipStream_t stream) {
  constexpr unsigned k=640;
  down_case::Inputs in(n,m,k,experts,used,width,stream);
  std::array<std::unique_ptr<Mirror>,3> mirrors;
  bool pass=true;
  for(unsigned r=0;r<3;++r) {mirrors[r]=std::make_unique<Mirror>(*in.weights[r],false,experts,m,k,stream);pass=mirrors[r]->format_pass&&pass;}
  for(bool half:{false,true}) {
    Device a(std::size_t(n)*used*m*(half?2:4)),b(a.bytes);
    const auto launch=[&](bool cached,unsigned r) {
      const void* w=cached?mirrors[r]->buffer.data:in.weights[r]->data;
      const auto* x=static_cast<const __half*>(in.x.data);
      const auto* scale=static_cast<const float*>(in.scale.data);
      const auto* tiles=static_cast<const std::int32_t*>(in.td->data);
      const auto* bounds=static_cast<const std::int32_t*>(in.bd->data);
      const auto* slots=static_cast<const std::int32_t*>(in.sd->data);
      bool ok;
      if(half)ok=(cached?q::RoutedCachedQ2ScaledHalfGemm:q::RoutedQ2ScaledHalfGemm)(w,x,scale,tiles,in.tiles.size(),width,bounds,slots,static_cast<__half*>(cached?b.data:a.data),m,k,stream);
      else ok=(cached?q::RoutedCachedQ2ScaledGemm:q::RoutedQ2ScaledGemm)(w,x,scale,tiles,in.tiles.size(),width,bounds,slots,static_cast<float*>(cached?b.data:a.data),m,k,stream);
      Require(ok,"Down dispatch refused");Hip(hipGetLastError());
    };
    const std::string label="q2-n"+std::to_string(n)+"-m"+std::to_string(m)+"-e"+std::to_string(experts)+"-w"+std::to_string(width)+(half?"-half":"-float");
    for(unsigned r=0;r<3;++r) {Poison(a,half,stream);Poison(b,half,stream);launch(false,r);launch(true,r);pass=Compare(a,b,half,label,r,stream)&&pass;}
    if(timing&&half)Time(label,in.encoded.size()*3,mirrors[0]->buffer.bytes*3,launch,stream);
    for(unsigned r=0;r<3;++r) {launch(false,r);launch(true,r);pass=Compare(a,b,half,label+"-post",r,stream)&&pass;}
  }
  for(auto& mirror:mirrors)mirror->Unchanged(stream);
  in.Unchanged(stream);return pass;
}
int main() {
  try {
    std::cout<<std::boolalpha<<std::setprecision(12);
    hipStream_t stream;Hip(hipStreamCreateWithFlags(&stream,hipStreamNonBlocking));
    bool pass=true;
    for(unsigned n:{15u,17u,129u}) {
      for(unsigned width:{16u,48u,64u,128u})pass=Gate(n,65,256,1,1,width,false,stream)&&pass;
      for(unsigned width:{16u,48u,64u})pass=Down(n,129,1,1,width,false,stream)&&pass;
    }
    for(unsigned experts:{64u,512u}) {
      pass=Gate(2048,640,2560,experts,10,0,true,stream)&&pass;
      pass=Down(2048,2560,experts,10,48,true,stream)&&pass;
    }
    Hip(hipStreamSynchronize(stream));Hip(hipStreamDestroy(stream));
    std::cout<<"{\"event\":\"expert_cache_complete\",\"numerical_pass\":"<<pass
      <<",\"guards_exact\":true,\"all_written\":true,\"immutable\":true,\"timing_retained\":true}\n";
    return pass?0:1;
  } catch(const std::exception& error) {std::cerr<<"FAIL unsafe/runtime: "<<error.what()<<'\n';return 2;}
}
