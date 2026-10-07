// SPDX-License-Identifier: MIT
// Compare retained attention with transient, lossless V tiling; packing is timed.
// No model files, dispatch promotion, changed masks or reordered arithmetic.
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
#include <hip/hip_runtime.h>
#include <hip/hip_fp16.h>
namespace gufo::models::qwen38_flash_next::rocm {
namespace {
#include "experiments/q2-attention-v-control.inc"
#include "experiments/q2-attention-v-blocks.inc"
}
}
namespace q = gufo::models::qwen38_flash_next::rocm;
static void Require(bool ok, const char* msg) { if (!ok) throw std::runtime_error(msg); }
static void Hip(hipError_t e) { if(e!=hipSuccess) throw std::runtime_error(hipGetErrorString(e)); }
struct Device {
  void *storage{},*data{}; size_t bytes; bool allocation_end;
  explicit Device(size_t n,bool end=false):bytes(n),allocation_end(end) {
    Hip(hipMalloc(&storage,n+(end?64:128))); data=static_cast<uint8_t*>(storage)+64;
    Hip(hipMemset(storage,0xa7,64)); if(!end) Hip(hipMemset(static_cast<uint8_t*>(data)+n,0xa7,64));
  }
  ~Device(){if(storage){const auto rc=hipFree(storage);(void)rc;}}
  Device(const Device&)=delete; Device& operator=(const Device&)=delete;
  std::vector<uint8_t> Read() const {
    std::array<uint8_t,128> guard{}; guard.fill(0xa7);
    Hip(hipMemcpy(guard.data(),storage,64,hipMemcpyDeviceToHost));
    if(!allocation_end) Hip(hipMemcpy(guard.data()+64,static_cast<const uint8_t*>(data)+bytes,64,hipMemcpyDeviceToHost));
    Require(std::all_of(guard.begin(),guard.end(),[](auto b){return b==0xa7;}),"Device guard changed");
    std::vector<uint8_t> out(bytes);Hip(hipMemcpy(out.data(),data,bytes,hipMemcpyDeviceToHost));return out;
  }
};
constexpr unsigned heads=24,kv_heads=2,dim=256,ratio=4,budget=512,words=1045;
struct Inputs {
  unsigned n,pos; std::vector<float> query,gate; std::vector<__half> keys,values;
  std::vector<uint32_t> mask; Device qd,gd,kd,vd,md;
  
  Inputs(unsigned rows,unsigned start,bool tiny):n(rows),pos(start),query(size_t(n)*heads*dim),gate(query.size()),
    keys(size_t(pos+n)*kv_heads*dim),values(keys.size()),mask(size_t(n)*words),
    qd(query.size()*4,true),gd(gate.size()*4,true),kd(keys.size()*2,true),vd(values.size()*2,true),md(mask.size()*4,true) {
    Require(n>0 && pos+n<=133760,"Attention bounds changed");
    uint32_t rng=713; auto random=[&](){rng=rng*1664525u+1013904223u;return float(int(rng>>16)-32768)/32768.f;};
    for(auto& x:query)x=random()*(tiny?0.0000319f:0.8f);
    for(auto& x:gate)x=random()*0.6f;
    for(auto& x:keys)x=__float2half_rn(random()*0.7f);
    for(auto& x:values)x=__float2half_rn(random()*0.8f);
    for(unsigned t=0;t<n;++t){
      const unsigned complete=(pos+t+1)/ratio; Require(complete>budget,"Sparse fixture below budget");
      unsigned stride=257;while(std::gcd(stride,complete)!=1)++stride;
      // Nearby queries share part of their selection, then diverge. Every
      // query has exactly512 distinct complete blocks; its natural tail is
      // handled by the unchanged kernel. The mask layout stays1045 words.
      const unsigned base=((t/4)*103+(t%4)*71)%complete;
      for(unsigned j=0;j<budget;++j){const unsigned b=(base+j*stride)%complete;mask[size_t(t)*words+b/32]|=1u<<(b%32);}
    }
    Hip(hipMemcpy(qd.data,query.data(),qd.bytes,hipMemcpyHostToDevice));
    Hip(hipMemcpy(gd.data,gate.data(),gd.bytes,hipMemcpyHostToDevice));
    Hip(hipMemcpy(kd.data,keys.data(),kd.bytes,hipMemcpyHostToDevice));
    Hip(hipMemcpy(vd.data,values.data(),vd.bytes,hipMemcpyHostToDevice));
    Hip(hipMemcpy(md.data,mask.data(),md.bytes,hipMemcpyHostToDevice));
  }
  void Unchanged() const {
    for(const auto& pair:std::array<std::pair<const Device*,const void*>,5>{{
        {&qd,query.data()},{&gd,gate.data()},{&kd,keys.data()},
        {&vd,values.data()},{&md,mask.data()}}}) {
      const auto raw=pair.first->Read();
      Require(std::memcmp(raw.data(),pair.second,raw.size())==0,"Attention input changed");
    }
  }
};
static void Pack(const Inputs& in,Device& packed,hipStream_t stream) {
  const size_t vectors=packed.bytes/sizeof(uint4);
  q::PackAttentionVBlocksKernel<<<(vectors+255)/256,256,0,stream>>>(
      static_cast<const uint4*>(in.vd.data),static_cast<uint4*>(packed.data),in.pos+in.n);
  Hip(hipGetLastError());
}
static void CheckPacked(const Inputs& in,const Device& packed) {
  const auto raw=packed.Read(); const unsigned context=in.pos+in.n;
  const unsigned padded=(context+3)&~3u;
  const std::array<uint8_t,32> zero{};
  for(unsigned k=0;k<padded;++k) for(unsigned h=0;h<kv_heads;++h)
    for(unsigned slice=0;slice<16;++slice) {
      const size_t src=(size_t(k)*kv_heads+h)*dim+slice*16;
      const size_t dst=(((size_t(k/4)*kv_heads+h)*16+slice)*4+k%4)*16;
      const void* expected=k<context ? static_cast<const void*>(in.values.data()+src) : zero.data();
      Require(std::memcmp(raw.data()+dst*2,expected,32)==0,"V block packing changed bits");
    }
}
static void Launch(bool candidate,const Inputs& in,const Device& packed,Device& out,hipStream_t stream) {
  const dim3 grid((in.n+3)/4,kv_heads);
  const bool late=in.pos>=65536;
#define LAUNCH(KERNEL,LATE,VALUES) hipLaunchKernelGGL((q::KERNEL<4,16,true,LATE>),grid,dim3(256),0,stream, \
    static_cast<const float*>(in.qd.data),static_cast<const float*>(in.gd.data), \
    static_cast<const __half*>(in.kd.data),static_cast<const __half*>(VALUES.data), \
    static_cast<const uint32_t*>(in.md.data),words,static_cast<float*>(out.data),in.pos,in.n,0)
  if(candidate) {
    if(late) { LAUNCH(WmmaCausalAttentionVBlocksKernel,true,packed); }
    else { LAUNCH(WmmaCausalAttentionVBlocksKernel,false,packed); }
  } else {
    if(late) { LAUNCH(WmmaCausalAttentionKernel,true,in.vd); }
    else { LAUNCH(WmmaCausalAttentionKernel,false,in.vd); }
  }
#undef LAUNCH
  Hip(hipGetLastError());
}
static float Float(const std::vector<uint8_t>& bytes,size_t i){float f;std::memcpy(&f,bytes.data()+i*4,4);return f;}
static bool Oracle(const Inputs& in,const std::vector<uint8_t>& out,const std::string& name,bool candidate){
  std::vector<unsigned> rows{0,in.n/2,in.n-1};std::sort(rows.begin(),rows.end());rows.erase(std::unique(rows.begin(),rows.end()),rows.end());
  double worst=0;size_t samples=0;
  for(unsigned t:rows) for(unsigned h:{0u,11u,12u,23u}){
    std::vector<unsigned> selected;std::vector<double> score;double peak=-INFINITY;
    for(unsigned k=0;k<=in.pos+t;++k){
      const unsigned b=k/ratio,tail=(in.pos+t+1)/ratio*ratio;
      if(k<tail && !(in.mask[size_t(t)*words+b/32]&(1u<<(b%32))))continue;
      selected.push_back(k);const size_t qb=(size_t(t)*heads+h)*dim,kb=(size_t(k)*kv_heads+h/12)*dim;
      double s=0;for(unsigned d=0;d<dim;++d)s+=double(in.query[qb+d])*double(__half2float(in.keys[kb+d]));
      score.push_back(s/16);peak=std::max(peak,s/16);
    }
    double sum=0;for(double& s:score){s=std::exp(s-peak);sum+=s;}
    for(unsigned d:{0u,1u,31u,127u,128u,255u}){
      double v=0;for(size_t k=0;k<selected.size();++k)v+=score[k]*double(__half2float(in.values[(size_t(selected[k])*kv_heads+h/12)*dim+d]));
      const size_t i=(size_t(t)*heads+h)*dim+d;
      const double expected=v/sum/(1+std::exp(-double(in.gate[i])));
      worst=std::max(worst,std::abs(double(Float(out,i))-expected));++samples;
    }
  }
  // Existing upstream WMMA comparison uses an absolute1e-2 bound. Report
  // independent sampled FP64 errors for both unchanged specializations.
  const bool pass=worst<=1e-2;
  std::cout<<"{\"event\":\"attention_v_blocks_oracle\",\"case\":\""<<name<<"\",\"candidate\":"<<candidate<<",\"samples\":"<<samples<<",\"max_absolute_error\":"<<worst<<",\"limit\":0.01,\"pass\":"<<pass<<"}\n";
  return pass;
}
static bool Case(const char* name,unsigned n,unsigned pos,bool tiny,bool timed,hipStream_t stream) {
  Inputs in(n,pos,tiny);
  Device packed(size_t((in.pos+in.n+3)&~3u)*kv_heads*dim*2,true),a(in.qd.bytes),b(in.qd.bytes);
  std::array<Device*,2> outputs{&a,&b};bool pass=true;
  Pack(in,packed,stream);Hip(hipStreamSynchronize(stream));CheckPacked(in,packed);
  hipEvent_t begin{},middle{},end{};
  Hip(hipEventCreate(&begin));Hip(hipEventCreate(&middle));Hip(hipEventCreate(&end));
  for(unsigned rep=0;rep<(timed?8u:1u);++rep) {
    std::array<std::vector<uint8_t>,2> values;
    for(unsigned order=0;order<2;++order) {
      const unsigned arm=(rep+order)%2;auto& out=*outputs[arm];
      Hip(hipMemset(out.data,0xff,out.bytes));Hip(hipDeviceSynchronize());
      const auto start=std::chrono::steady_clock::now();Hip(hipEventRecord(begin,stream));
      if(arm) Pack(in,packed,stream);
      Hip(hipEventRecord(middle,stream));Launch(arm,in,packed,out,stream);
      Hip(hipEventRecord(end,stream));Hip(hipEventSynchronize(end));
      const auto stop=std::chrono::steady_clock::now();float ms=0,pack_ms=0,consumer_ms=0;
      Hip(hipEventElapsedTime(&ms,begin,end));Hip(hipEventElapsedTime(&pack_ms,begin,middle));
      Hip(hipEventElapsedTime(&consumer_ms,middle,end));
      if(timed)std::cout<<"{\"event\":\"attention_v_blocks_timing\",\"case\":\""<<name
          <<"\",\"rep\":"<<rep<<",\"order\":"<<order<<",\"candidate\":"<<bool(arm)
          <<",\"warmup\":"<<(rep<2)<<",\"rows\":"<<n<<",\"start_pos\":"<<pos
          <<",\"gpu_event_valid\":"<<(std::isfinite(ms)&&ms>0)
          <<",\"complete_gpu_us\":"<<double(ms)*1000<<",\"packing_gpu_us\":"<<double(pack_ms)*1000
          <<",\"attention_gpu_us\":"<<double(consumer_ms)*1000
          <<",\"completed_wall_us\":"<<std::chrono::duration<double,std::micro>(stop-start).count()<<"}\n";
      values[arm]=out.Read();
      for(size_t i=0;i<out.bytes/4;++i)Require(std::isfinite(Float(values[arm],i)),"Nonfinite attention output");
      if(rep==0)pass=Oracle(in,values[arm],name,arm)&&pass;
    }
    const bool exact=values[0]==values[1];pass=exact&&pass;
    std::cout<<"{\"event\":\"attention_v_blocks_pair\",\"case\":\""<<name<<"\",\"rep\":"<<rep
        <<",\"bytes\":"<<a.bytes<<",\"exact\":"<<exact<<"}\n";
    if(!exact)for(unsigned arm=0;arm<2;++arm) {
      std::ofstream file(std::string("results/")+name+"-r"+std::to_string(rep)+"-"+std::to_string(arm)+".bin",std::ios::binary);
      file.write(reinterpret_cast<const char*>(values[arm].data()),values[arm].size());
      Require(bool(file),"Cannot preserve output");
    }
  }
  in.Unchanged();CheckPacked(in,packed);
  std::cout<<"{\"event\":\"attention_v_blocks_case\",\"case\":\""<<name
      <<"\",\"immutable_inputs\":true,\"packed_bits_exact\":true,\"guards_finite_written\":true"
      <<",\"temporary_bytes\":"<<packed.bytes<<"}\n";
  Hip(hipEventDestroy(begin));Hip(hipEventDestroy(middle));Hip(hipEventDestroy(end));return pass;
}
int main() {
  std::cout<<std::boolalpha<<std::setprecision(17);
  try {
    hipStream_t stream{};Hip(hipStreamCreateWithFlags(&stream,hipStreamNonBlocking));bool pass=true;
    pass=Case("full32",2048,28672,false,true,stream)&&pass;
    pass=Case("full128",2048,126976,false,true,stream)&&pass;
    pass=Case("tail128",1901,129024,false,false,stream)&&pass;
    pass=Case("tiny-tail",3,4093,true,false,stream)&&pass;
    Hip(hipStreamDestroy(stream));
    std::cout<<"{\"event\":\"complete\",\"pass\":"<<pass<<",\"model_inference\":false}\n";return pass?0:1;
  } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 2;}
}
