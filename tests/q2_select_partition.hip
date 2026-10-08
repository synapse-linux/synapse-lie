// SPDX-License-Identifier: MIT
// Exact two-stage sparse block selection, isolated from original model inference.
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>
#include "src/core/crypto/sha256.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
#include "experiments/q2-select-partition.inc"
namespace q = gufo::models::qwen38_flash_next::rocm;
static void Require(bool ok,const char* msg){if(!ok)throw std::runtime_error(msg);}
static void Hip(hipError_t rc){if(rc!=hipSuccess)throw std::runtime_error(hipGetErrorString(rc));}
struct Device {
  void *storage{},*data{}; size_t bytes;
  explicit Device(size_t n):bytes(n){
    Hip(hipMalloc(&storage,n+128));data=static_cast<uint8_t*>(storage)+64;
    Hip(hipMemset(storage,0xa7,64));Hip(hipMemset(static_cast<uint8_t*>(data)+n,0xa7,64));
  }
  ~Device(){if(storage){const auto rc=hipFree(storage);(void)rc;}}
  Device(const Device&)=delete;Device& operator=(const Device&)=delete;
  std::vector<uint8_t> Read()const{
    std::array<uint8_t,128> guard{};
    Hip(hipMemcpy(guard.data(),storage,64,hipMemcpyDeviceToHost));
    Hip(hipMemcpy(guard.data()+64,static_cast<const uint8_t*>(data)+bytes,64,hipMemcpyDeviceToHost));
    Require(std::all_of(guard.begin(),guard.end(),[](auto b){return b==0xa7;}),"Device guard changed");
    std::vector<uint8_t> out(bytes);Hip(hipMemcpy(out.data(),data,bytes,hipMemcpyDeviceToHost));return out;
  }
};
constexpr unsigned pitch=33440,words=1045,budget=512;
struct Fixture {
  Device scores{pitch*4},pos{4},a{words*4},b{words*4},keys{q::q2SelectSlots*4},ids{q::q2SelectSlots*4};
  hipStream_t stream{};std::array<hipGraph_t,2> graphs{};std::array<hipGraphExec_t,2> execs{};
  Fixture(){
    Hip(hipStreamCreateWithFlags(&stream,hipStreamNonBlocking));
    for(unsigned arm=0;arm<2;++arm){
      Hip(hipStreamBeginCapture(stream,hipStreamCaptureModeGlobal));
      if(arm){
        hipLaunchKernelGGL(q::Q2SelectPartitions,dim3(q::q2SelectParts),dim3(256),0,stream,
          static_cast<const float*>(scores.data),static_cast<const unsigned*>(pos.data),
          static_cast<unsigned*>(keys.data),static_cast<unsigned*>(ids.data));
        hipLaunchKernelGGL(q::Q2SelectMerge,dim3(1),dim3(256),0,stream,
          static_cast<unsigned*>(b.data),static_cast<const unsigned*>(pos.data),
          static_cast<const unsigned*>(keys.data),static_cast<const unsigned*>(ids.data),words);
      }else hipLaunchKernelGGL(q::SelectMarkKernel,dim3(1),dim3(256),0,stream,
        static_cast<unsigned*>(a.data),static_cast<const float*>(scores.data),
        static_cast<const unsigned*>(pos.data),0u,4u,budget,words,pitch);
      Hip(hipGetLastError());Hip(hipStreamEndCapture(stream,&graphs[arm]));
      Hip(hipGraphInstantiate(&execs[arm],graphs[arm],nullptr,nullptr,0));
    }
  }
  ~Fixture(){for(unsigned i=0;i<2;++i){(void)hipGraphExecDestroy(execs[i]);(void)hipGraphDestroy(graphs[i]);}(void)hipStreamDestroy(stream);}
};
static unsigned Bits(float f){unsigned v;std::memcpy(&v,&f,4);return v;}
static bool Case(Fixture& f,const char* name,unsigned complete,unsigned pattern,bool timed){
  Require(complete>0&&complete<=pitch,"Fixture exceeds capacity");
  std::vector<unsigned> input(pitch,0x7fc00001u),order(complete),expected(words);
  unsigned rng=0x573b7941u;
  for(unsigned i=0;i<complete;++i){
    rng=rng*1664525u+1013904223u;
    unsigned v=Bits(1.f+float(rng>>8)/16777216.f*8.f);
    if(pattern==1)v=Bits(3.f);
    if(pattern==2)v=0;
    if(pattern==3)v=Bits(float(i)/16.f);
    if(pattern==4)v=Bits(i<256?0.001f:100000.f+float(i%1024));
    if(pattern==5)v=0x3f800000u+(i%17);
    if(pattern==6)v=1+(i%31);
    input[i]=v;
  }
  if(complete<=budget)std::fill(expected.begin(),expected.end(),~0u);
  else{
    std::iota(order.begin(),order.end(),0u);
    std::sort(order.begin(),order.end(),[&](unsigned a,unsigned b){return input[a]==input[b]?a<b:input[a]>input[b];});
    for(unsigned i=0;i<budget;++i)expected[order[i]/32]|=1u<<(order[i]%32);
  }
  std::vector<uint8_t> oracle(expected.size()*4);std::memcpy(oracle.data(),expected.data(),oracle.size());
  const unsigned start=complete*4-1;
  Hip(hipMemcpy(f.scores.data,input.data(),f.scores.bytes,hipMemcpyHostToDevice));
  Hip(hipMemcpy(f.pos.data,&start,4,hipMemcpyHostToDevice));
  const auto source_hash=gufo::crypto::Sha256Hex(f.scores.Read()),pos_hash=gufo::crypto::Sha256Hex(f.pos.Read());
  const std::array<Device*,2> outputs{&f.a,&f.b};bool pass=true;
  hipEvent_t begin{},end{};Hip(hipEventCreate(&begin));Hip(hipEventCreate(&end));
  for(unsigned rep=0;rep<(timed?11u:1u);++rep){
    std::array<std::vector<uint8_t>,2> values;
    for(unsigned serial=0;serial<2;++serial){
      const unsigned arm=(rep+serial)%2;auto& out=*outputs[arm];
      Hip(hipMemset(out.data,0xd3,out.bytes));Hip(hipDeviceSynchronize());
      const auto t0=std::chrono::steady_clock::now();Hip(hipEventRecord(begin,f.stream));
      Hip(hipGraphLaunch(f.execs[arm],f.stream));Hip(hipEventRecord(end,f.stream));Hip(hipEventSynchronize(end));
      const auto t1=std::chrono::steady_clock::now();float ms=0;Hip(hipEventElapsedTime(&ms,begin,end));
      if(timed)std::cout<<"{\"event\":\"partition_timing\",\"case\":\""<<name<<"\",\"rep\":"<<rep<<",\"arm\":"<<arm<<",\"order\":"<<serial<<",\"warmup\":"<<(rep<2)<<",\"complete\":"<<complete<<",\"gpu_event_valid\":"<<(ms>0&&std::isfinite(ms))<<",\"gpu_event_us\":"<<double(ms)*1000<<",\"completed_wall_us\":"<<std::chrono::duration<double,std::micro>(t1-t0).count()<<"}\n";
      values[arm]=out.Read();
      (void)f.keys.Read();(void)f.ids.Read();
    }
    const bool exact=values[0]==values[1],aok=values[0]==oracle,bok=values[1]==oracle;
    pass=pass&&exact&&aok&&bok;
    std::cout<<"{\"event\":\"partition_pair\",\"case\":\""<<name<<"\",\"rep\":"<<rep<<",\"complete\":"<<complete<<",\"exact\":"<<exact<<",\"retained_oracle\":"<<aok<<",\"partition_oracle\":"<<bok<<",\"retained_sha256\":\""<<gufo::crypto::Sha256Hex(values[0])<<"\",\"partition_sha256\":\""<<gufo::crypto::Sha256Hex(values[1])<<"\"}\n";
    if(!exact||!aok||!bok)for(unsigned arm=0;arm<2;++arm){std::ofstream file(std::string(name)+"-r"+std::to_string(rep)+"-"+std::to_string(arm)+".bin",std::ios::binary);file.write(reinterpret_cast<const char*>(values[arm].data()),values[arm].size());Require(bool(file),"Cannot save mask");}
  }
  Require(source_hash==gufo::crypto::Sha256Hex(f.scores.Read())&&pos_hash==gufo::crypto::Sha256Hex(f.pos.Read()),"Selector input changed");
  Hip(hipEventDestroy(begin));Hip(hipEventDestroy(end));return pass;
}
int main(){
  std::cout<<std::boolalpha<<std::setprecision(17);
  try{
    Fixture f;bool pass=true;
    for(unsigned n:{511u,512u,513u,4095u,4096u,4097u})pass=Case(f,("boundary"+std::to_string(n)).c_str(),n,0,false)&&pass;
    pass=Case(f,"decode32",8178,0,true)&&pass;
    pass=Case(f,"decode64",16360,0,true)&&pass;
    pass=Case(f,"decode128",32731,0,true)&&pass;
    pass=Case(f,"capacity",33440,0,false)&&pass;
    pass=Case(f,"ties128",32731,1,true)&&pass;
    pass=Case(f,"zeros128",32731,2,false)&&pass;
    pass=Case(f,"ramp128",32731,3,false)&&pass;
    pass=Case(f,"clipped128",32731,4,false)&&pass;
    pass=Case(f,"near-ties128",32731,5,false)&&pass;
    pass=Case(f,"subnormal513",513,6,false)&&pass;
    std::cout<<"{\"event\":\"complete\",\"pass\":"<<pass<<",\"model_inference\":false}\n";return pass?0:1;
  }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
