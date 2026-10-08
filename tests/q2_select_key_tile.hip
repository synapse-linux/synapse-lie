// SPDX-License-Identifier: MIT
// Exact selector scores plus original top-k consumer, synthetic GPU operators only.
#include <algorithm>
#include <bit>
#include <numeric>
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
#include "experiments/q2-select-key-tile.inc"
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
static constexpr unsigned pitch=33440, mask_words=1045, ratio=4, budget=512;
struct Inputs {
  unsigned n, pos, first;
  std::vector<float> query;
  std::vector<__half> keys;
  Device qd, kd, pd;
  std::string qhash,khash,phash;
  Inputs(unsigned rows,unsigned position,unsigned offset,unsigned pattern)
      : n(rows),pos(position),first(offset),query(size_t(n)*4*128),
        keys(size_t((pos+first+n)/ratio)*128),qd(query.size()*4),kd(keys.size()*2),pd(4) {
    Require(n>0 && (pos+first+n)/ratio<=pitch,"Invalid selector bounds");
    uint32_t rng=713;
    auto value=[&](){rng=rng*1664525u+1013904223u;return float(int(rng>>16)-32768)/32768.f;};
    for (auto& x:query) x=pattern==1 ? 0.f : value()*(pattern==2 ? 0.0000319f : 0.31f);
    for (auto& x:keys) x=__float2half_rn(value()*0.37f);
    Hip(hipMemcpy(qd.data,query.data(),qd.bytes,hipMemcpyHostToDevice));
    Hip(hipMemcpy(kd.data,keys.data(),kd.bytes,hipMemcpyHostToDevice));
    Hip(hipMemcpy(pd.data,&pos,4,hipMemcpyHostToDevice));
    qhash=Hash(qd);khash=Hash(kd);phash=Hash(pd);
  }
  void Unchanged() const {
    Require(Hash(qd)==qhash && Hash(kd)==khash && Hash(pd)==phash,"Selector input changed");
  }
};
struct State {
  Device scores,mask,key_tiles;
  explicit State(unsigned n):scores(size_t(n)*pitch*4),mask(size_t(n)*mask_words*4),key_tiles(size_t(pitch)*128*2) {}
  void Clear(){scores.Clear();key_tiles.Clear();Hip(hipMemset(mask.data,0xa5,mask.bytes));}
};
static void Launch(bool candidate,const Inputs& in,State& out,hipStream_t stream) {
  if (candidate) {
    const unsigned complete = (in.pos + in.first + in.n) / ratio;
    hipLaunchKernelGGL(q::PackSelectKeyTilesKernel,
      dim3((complete * 16 + 255) / 256), dim3(256), 0, stream,
      static_cast<const __half*>(in.kd.data), static_cast<__half*>(out.key_tiles.data), complete);
    hipLaunchKernelGGL(q::SelectScoreKeyTileKernel,
      dim3(in.n, (pitch + 255) / 256), dim3(256), 0, stream,
      static_cast<const float*>(in.qd.data), static_cast<const __half*>(out.key_tiles.data),
      static_cast<float*>(out.scores.data), in.n, static_cast<const uint32_t*>(in.pd.data),
      in.first, ratio, budget, pitch);
    hipLaunchKernelGGL(q::SelectMarkKernel, dim3(in.n), dim3(256), 0, stream,
      static_cast<uint32_t*>(out.mask.data), static_cast<const float*>(out.scores.data),
      static_cast<const uint32_t*>(in.pd.data), in.first, ratio, budget, mask_words, pitch);
  }
  else
    q::SelectBlocks(static_cast<const float*>(in.qd.data),
      static_cast<const __half*>(in.kd.data),static_cast<uint32_t*>(out.mask.data),
      static_cast<float*>(out.scores.data),in.n,static_cast<const uint32_t*>(in.pd.data),
      in.first,4,128,ratio,budget,mask_words,pitch,stream);
  Hip(hipGetLastError());
}
static float Score(const std::vector<uint8_t>& bytes,size_t i){float x;std::memcpy(&x,bytes.data()+4*i,4);return x;}
static uint32_t Word(const std::vector<uint8_t>& bytes,size_t i){uint32_t x;std::memcpy(&x,bytes.data()+4*i,4);return x;}
static bool Oracle(const Inputs& in,const State& out,const std::string& label,bool candidate) {
  const auto scores=out.scores.Read(),mask=out.mask.Read();
  if (candidate) {
    const auto packed=out.key_tiles.Read();
    const unsigned complete=(in.pos+in.first+in.n)/ratio;
    for (unsigned block=0;block<pitch;++block) {
      for (unsigned feature=0;feature<128;++feature) {
        const size_t index=size_t(block/8)*1024+(feature/8)*64+(block%8)*8+feature%8;
        uint16_t got,expected=0xffff;
        std::memcpy(&got,packed.data()+2*index,2);
        if (block<complete) std::memcpy(&expected,&in.keys[size_t(block)*128+feature],2);
        Require(got==expected,"Key tile bits or unused sentinel changed");
      }
    }
  }
  for (unsigned t=0;t<in.n;++t) {
    const unsigned complete=(in.pos+in.first+t+1)/ratio;
    for (unsigned b=0;b<pitch;++b) {
      const size_t offset=size_t(t)*pitch+b;
      if (complete>budget && b<complete) Require(std::isfinite(Score(scores,offset)),"Nonfinite or unwritten score");
      else Require(Word(scores,offset)==0xffffffffu,"Inactive score changed");
    }
    unsigned selected=0;
    for (unsigned w=0;w<mask_words;++w) {
      const auto bits=Word(mask,size_t(t)*mask_words+w);
      if (complete<=budget) Require(bits==0xffffffffu,"Non-sparse mask unwritten");
      else {
        selected+=std::popcount(bits);
        if (w*32>=complete) Require(bits==0,"Mask selected future key");
        else if ((w+1)*32>complete) Require((bits>>(complete-w*32))==0,"Mask tail selected future key");
      }
    }
    if (complete>budget) Require(selected==budget,"Top-k cardinality differs");
  }
  double error=0,norm=0,max_error=0,peak=0;unsigned samples=0;
  for (unsigned s=0;s<64;++s) {
    const unsigned t=s<2 ? s%(in.n) : s==2 ? in.n-1 : (s*31)%in.n;
    const unsigned complete=(in.pos+in.first+t+1)/ratio;
    if (complete<=budget) continue;
    const unsigned b=s==0 ? 0 : s==1 ? complete-1 : (s*997+71)%complete;
    double expected=0;
    for (unsigned h=0;h<4;++h) {
      double dot=0;
      for (unsigned j=0;j<128;++j) dot+=double(in.query[(size_t(t)*4+h)*128+j])*double(__half2float(in.keys[size_t(b)*128+j]));
      expected+=std::max(dot,0.0);
    }
    const double delta=double(Score(scores,size_t(t)*pitch+b))-expected;
    error+=delta*delta;norm+=expected*expected;
    max_error=std::max(max_error,std::abs(delta));peak=std::max(peak,std::abs(expected));++samples;
  }
  bool masks_exact=true;
  // Independent exact rank/tie rule from sampled full score rows.
  for (unsigned t : {0u,std::min(1u,in.n-1),std::min(31u,in.n-1),in.n-1}) {
    const unsigned complete=(in.pos+in.first+t+1)/ratio;
    if (complete<=budget) continue;
    std::vector<unsigned> ids(complete);std::iota(ids.begin(),ids.end(),0);
    std::partial_sort(ids.begin(),ids.begin()+budget,ids.end(),[&](unsigned a,unsigned b){
      const float av=Score(scores,size_t(t)*pitch+a),bv=Score(scores,size_t(t)*pitch+b);
      return av>bv || (av==bv && a<b);
    });
    std::vector<uint32_t> expected(mask_words,0);
    for (unsigned i=0;i<budget;++i) expected[ids[i]/32]|=uint32_t{1}<<(ids[i]%32);
    for (unsigned w=0;w<mask_words;++w) masks_exact=(expected[w]==Word(mask,size_t(t)*mask_words+w))&&masks_exact;
  }
  const double rrms=std::sqrt(error/std::max(norm,1e-300)),scaled=max_error/std::max(peak,1e-300);
  const bool pass=rrms<=2e-5 && scaled<=2e-5 && masks_exact;
  std::cout << "{\"event\":\"select_key_tile_oracle\",\"case\":\"" << label << "\",\"candidate\":" << candidate
    << ",\"samples\":" << samples << ",\"relative_rms\":" << rrms << ",\"scaled_error\":" << scaled
    << ",\"limit\":0.00002,\"sampled_topk_masks_exact\":" << masks_exact << ",\"pass\":" << pass << "}\n";
  return pass;
}
static bool Pair(const Device& a,const Device& b,const std::string& label,const char* field) {
  const auto av=a.Read(),bv=b.Read();const bool exact=av==bv;
  std::cout << "{\"event\":\"select_key_tile_replay\",\"case\":\"" << label << "\",\"field\":\"" << field
    << "\",\"bytes\":" << av.size() << ",\"reference_sha256\":\"" << gufo::crypto::Sha256Hex(av)
    << "\",\"candidate_sha256\":\"" << gufo::crypto::Sha256Hex(bv) << "\",\"exact\":" << exact << "}\n";
  if (!exact) for (unsigned arm=0;arm<2;++arm) {
    const auto& bytes=arm?bv:av;std::ofstream out(label+"-"+field+"-"+std::to_string(arm)+".bin",std::ios::binary);
    out.write(reinterpret_cast<const char*>(bytes.data()),bytes.size());Require(bool(out),"Cannot preserve disagreement");
  }
  return exact;
}
static bool Case(const std::string& name,unsigned n,unsigned pos,unsigned first,unsigned pattern,bool timed,hipStream_t stream) {
  Inputs in(n,pos,first,pattern);State a(n),b(n);std::array<State*,2> states{&a,&b};
  hipEvent_t begin{},end{};Hip(hipEventCreate(&begin));Hip(hipEventCreate(&end));bool pass=true;
  for (unsigned rep=0;rep<(timed?7u:1u);++rep) {
    const auto label=name+"-r"+std::to_string(rep);
    for (unsigned order=0;order<2;++order) {
      const unsigned arm=(rep+order)%2;auto& out=*states[arm];out.Clear();Hip(hipDeviceSynchronize());
      const auto start=std::chrono::steady_clock::now();Hip(hipEventRecord(begin,stream));
      Launch(arm,in,out,stream);Hip(hipEventRecord(end,stream));Hip(hipEventSynchronize(end));
      const auto stop=std::chrono::steady_clock::now();Hip(hipGetLastError());
      float ms=0;Hip(hipEventElapsedTime(&ms,begin,end));
      if (timed) {
        std::cout << "{\"event\":\"select_key_tile_timing\",\"case\":\"" << name << "\",\"rep\":" << rep << ",\"order\":" << order
          << ",\"candidate\":" << bool(arm) << ",\"warmup\":" << (rep<2) << ",\"iterations\":1,\"rows\":" << n
          << ",\"start_pos\":" << pos << ",\"first_token\":" << first << ",\"gpu_event_valid\":" << (std::isfinite(ms)&&ms>0) << ",\"gpu_event_us\":";
        if (std::isfinite(ms)) std::cout << double(ms)*1000;else std::cout << "null";
        std::cout << ",\"completed_wall_us\":" << std::chrono::duration<double,std::micro>(stop-start).count() << "}\n";
      }
      pass=Oracle(in,out,label,arm)&&pass;
    }
    pass=Pair(a.scores,b.scores,label,"scores")&&pass;pass=Pair(a.mask,b.mask,label,"mask")&&pass;
  }
  in.Unchanged();Hip(hipEventDestroy(end));Hip(hipEventDestroy(begin));
  std::cout << "{\"event\":\"select_key_tile_case\",\"case\":\"" << name << "\",\"rows\":" << n << ",\"start_pos\":" << pos
    << ",\"first_token\":" << first << ",\"inputs_unchanged\":true,\"guards_finite_written\":true}\n";
  return pass;
}
int main() {
  try {
    std::cout << std::boolalpha << std::defaultfloat << std::setprecision(12);
    hipStream_t stream{};Hip(hipStreamCreateWithFlags(&stream,hipStreamNonBlocking));
    bool pass=Case("budget-ties",7,2046,0,1,false,stream);
    pass=Case("one-tiny",1,129024,1899,2,false,stream)&&pass;
    pass=Case("three-tail",3,129024,1898,0,false,stream)&&pass;
    pass=Case("last-full32",512,28672,1536,0,true,stream)&&pass;
    pass=Case("last-full128",512,126976,1536,0,true,stream)&&pass;
    pass=Case("last-tail128",365,129024,1536,0,true,stream)&&pass;
    Hip(hipStreamSynchronize(stream));Hip(hipStreamDestroy(stream));
    std::cout << "{\"event\":\"select_key_tile_complete\",\"numerical_pass\":" << pass
      << ",\"timing_retained\":true,\"safe_completion\":true,\"model_inference\":false}\n";
    return pass?0:1;
  } catch(const std::exception& e){std::cerr << "FAIL: " << e.what() << '\n';return 2;}
}
