// SPDX-License-Identifier: MIT
// Shuffled compressed expert slots versus retained contiguous encoded routes.
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


struct Mirror {
  struct View { const void* base; const std::int32_t* map; };
  Device buffer, map, view;
  std::string digest, map_digest, view_digest;
  bool format_pass=true;
  Mirror(const Device& encoded, bool iq2, unsigned experts, unsigned m,
         unsigned k, hipStream_t stream)
      : buffer(encoded.bytes / experts * (2 * experts + 1)),
        map(experts * sizeof(std::int32_t)), view(sizeof(View)) {
    (void)m; (void)k;
    const auto original=Read(encoded,stream);
    const std::size_t stride=original.size()/experts;
    std::vector<std::uint8_t> packed(buffer.bytes,0x53);
    std::vector<std::int32_t> mapping(experts);
    for(unsigned e=0;e<experts;++e) {
      mapping[e]=(17*e+1)%(2*experts+1);
      std::memcpy(packed.data()+std::size_t(mapping[e])*stride,original.data()+e*stride,stride);
    }
    Upload(buffer,packed,stream);
    std::vector<std::uint8_t> mb(map.bytes);std::memcpy(mb.data(),mapping.data(),mb.size());Upload(map,mb,stream);
    View host{buffer.data,static_cast<const std::int32_t*>(map.data)};
    std::vector<std::uint8_t> vb(sizeof(host));std::memcpy(vb.data(),&host,sizeof(host));Upload(view,vb,stream);
    const auto got=Read(buffer,stream);
    std::size_t changed=0;
    for(unsigned e=0;e<experts;++e)for(std::size_t j=0;j<stride;++j)
      changed+=got[std::size_t(mapping[e])*stride+j]!=original[e*stride+j];
    format_pass=changed==0;digest=Hash(got);map_digest=Hash(Read(map,stream));view_digest=Hash(Read(view,stream));
    std::cout<<"{\"event\":\"compressed_cache_format\",\"iq2\":"<<iq2
      <<",\"samples\":"<<original.size()<<",\"elements\":"<<original.size()
      <<",\"changed\":"<<changed<<",\"pass\":"<<format_pass<<"}\n";
  }
  void Unchanged(hipStream_t stream) {
    Require(Hash(Read(buffer,stream))==digest,"Compressed cache changed");
    Require(Hash(Read(map,stream))==map_digest,"Slot map changed");
    Require(Hash(Read(view,stream))==view_digest,"Slot view changed");
  }
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
  std::cout<<"{\"event\":\"compressed_cache_replay\",\"case\":\""<<label
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
    std::cout<<"{\"event\":\"compressed_cache_timing\",\"case\":\""<<label
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
      Require((cached?q::RoutedSlottedIQ2Gemm:q::RoutedGatedIQ2Gemm)(
        cached?gate[r]->view.data:in.gate[r]->data,cached?up[r]->view.data:in.up[r]->data,
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
      const void* w=cached?mirrors[r]->view.data:in.weights[r]->data;
      const auto* x=static_cast<const __half*>(in.x.data);
      const auto* scale=static_cast<const float*>(in.scale.data);
      const auto* tiles=static_cast<const std::int32_t*>(in.td->data);
      const auto* bounds=static_cast<const std::int32_t*>(in.bd->data);
      const auto* slots=static_cast<const std::int32_t*>(in.sd->data);
      bool ok;
      if(half)ok=(cached?q::RoutedSlottedQ2ScaledHalfGemm:q::RoutedQ2ScaledHalfGemm)(w,x,scale,tiles,in.tiles.size(),width,bounds,slots,static_cast<__half*>(cached?b.data:a.data),m,k,stream);
      else ok=(cached?q::RoutedSlottedQ2ScaledGemm:q::RoutedQ2ScaledGemm)(w,x,scale,tiles,in.tiles.size(),width,bounds,slots,static_cast<float*>(cached?b.data:a.data),m,k,stream);
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
    std::cout<<"{\"event\":\"compressed_cache_complete\",\"numerical_pass\":"<<pass
      <<",\"guards_exact\":true,\"all_written\":true,\"immutable\":true,\"timing_retained\":true}\n";
    return pass?0:1;
  } catch(const std::exception& error) {std::cerr<<"FAIL unsafe/runtime: "<<error.what()<<'\n';return 2;}
}
