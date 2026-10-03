// SPDX-License-Identifier: MIT
// Host-only sampler cost; generated logits, no weights or model computation.
#include "src/core/sampling.hpp"
#ifdef LIE_TRACK_ALLOCATIONS
#include "allocation_counter.hpp"
#endif
#include <algorithm>
#include <array>
#include <bit>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <new>
#include <stdexcept>
#include <vector>
namespace {
using namespace gufo::sampling;
void retain(std::uint64_t &hash,std::uint64_t value){
  for(unsigned i=0;i<8;++i){hash^=(value>>(i*8))&255;hash*=UINT64_C(1099511628211);}
}
std::uint64_t witness(const SamplingDistribution &distribution){
  std::uint64_t hash=UINT64_C(14695981039346656037),rng=77;
  for(auto p:distribution.entries()){retain(hash,p.token);retain(hash,std::bit_cast<std::uint64_t>(p.value));}
  for(unsigned i=0;i<64;++i){retain(hash,distribution.Sample(&rng));retain(hash,rng);}
  return hash;
}
SamplingConfig config(unsigned filter){
  SamplingConfig c;c.seed=77;c.temperature=.7f;
  if(filter==0)c.temperature=0;
  if(filter==2)c.top_p=.95f;
  if(filter==3){c.top_k=32;c.top_p=.8f;c.min_p=.1f;}
  if(filter==4){c.min_p=.9f;c.min_keep=5;}
  if(filter==5){c.top_k=32;c.repeat_penalty=1.2f;c.frequency_penalty=.2f;c.presence_penalty=.1f;}
  return c;
}
}
int main(int argc,char **argv){
  const bool quick=argc==2&&!std::strcmp(argv[1],"--quick");
  if(argc>2||(argc==2&&!quick)){std::fputs("Usage: sampling-cost [--quick]\n",stderr);return 2;}
  try{
    std::printf("{\"event\":\"identity\",\"schema\":\"synapse-lie.sampling-host.v1\",\"arm\":\"%s\",\"classification\":\"NOT-INFERENCE\",\"instrumented_allocations\":%s}\n",LIE_SAMPLING_ARM,
#ifdef LIE_TRACK_ALLOCATIONS
    "true"
#else
    "false"
#endif
    );
#ifdef LIE_TRACK_ALLOCATIONS
    lie_sampling_alloc_begin();
    void *plain=::operator new(17);
    void *aligned=::operator new(33,std::align_val_t{64});
    if(reinterpret_cast<std::uintptr_t>(aligned)%64)throw std::runtime_error("allocation alignment");
    ::operator delete(plain,std::size_t{17});
    ::operator delete(aligned,std::size_t{33},std::align_val_t{64});
    const auto fixture=lie_sampling_alloc_end();
    if(fixture.calls!=2||fixture.requested_bytes!=50||fixture.peak_live_bytes!=50||fixture.live_bytes)
      throw std::runtime_error("allocation counter fixture");
    std::puts("{\"event\":\"allocation_fixture\",\"calls\":2,\"requested_bytes\":50,\"peak_live_bytes\":50,\"live_bytes_after_retirement\":0}");
#endif
    unsigned cases=0;
    for(std::size_t vocabulary:std::array<std::size_t,3>{256,32768,248320})
      for(unsigned geometry=0;geometry<3;++geometry)
        for(unsigned filter=0;filter<6;++filter){
          std::vector<float> logits(vocabulary);
          for(std::size_t i=0;i<vocabulary;++i)logits[i]=geometry==0?0:geometry==1?float(std::sin(i*.17)*3):float(i%127)/7;
          std::array<TokenId,64> prompt{},generated{};
          for(unsigned i=0;i<64;++i){prompt[i]=(i*17)%vocabulary;generated[i]=(i*13)%vocabulary;}
          SamplerState sampler(config(filter),prompt);sampler.Accept(generated);
          std::uint64_t hash=0;std::size_t entries=0;
#ifdef LIE_TRACK_ALLOCATIONS
          lie_sampling_alloc_begin();
          {auto d=sampler.Distribution(logits);entries=d.entries().size();hash=witness(d);}
          const auto allocations=lie_sampling_alloc_end();
          if(allocations.live_bytes)throw std::runtime_error("unretired counted sampling allocation");
          std::printf("{\"event\":\"allocation\",\"vocabulary\":%zu,\"geometry\":%u,\"filter\":%u,\"entries\":%zu,\"witness\":\"%016llx\",\"calls\":%zu,\"requested_bytes\":%zu,\"peak_live_bytes\":%zu,\"live_bytes_after_retirement\":%zu}\n",vocabulary,geometry,filter,entries,(unsigned long long)hash,allocations.calls,allocations.requested_bytes,allocations.peak_live_bytes,allocations.live_bytes);
#else
          {auto d=sampler.Distribution(logits);entries=d.entries().size();hash=witness(d);}
          const unsigned iterations=quick?1:vocabulary==256?64:vocabulary==32768?8:3;
          const unsigned repetitions=quick?1:7,warmups=quick?0:1;
          std::array<double,7> ns{};std::uint64_t checksum=0,rng=77;
          for(unsigned rep=0;rep<repetitions+warmups;++rep){
            const auto begin=std::chrono::steady_clock::now();
            for(unsigned i=0;i<iterations;++i){auto d=sampler.Distribution(logits);checksum+=d.Sample(&rng);}
            const auto end=std::chrono::steady_clock::now();
            if(rep>=warmups)ns[rep-warmups]=std::chrono::duration<double,std::nano>(end-begin).count()/iterations;
          }
          const auto original=ns;
          for(unsigned i=1;i<repetitions;++i){
            const double value=ns[i];unsigned j=i;
            while(j&&ns[j-1]>value){ns[j]=ns[j-1];--j;}
            ns[j]=value;
          }
          std::printf("{\"event\":\"cost\",\"vocabulary\":%zu,\"geometry\":%u,\"filter\":%u,\"entries\":%zu,\"witness\":\"%016llx\",\"iterations_per_repetition\":%u,\"repetitions\":%u,\"median_ns\":%.17g,\"min_ns\":%.17g,\"max_ns\":%.17g,\"sample_ns\":[",vocabulary,geometry,filter,entries,(unsigned long long)hash,iterations,repetitions,ns[repetitions/2],ns[0],ns[repetitions-1]);
          for(unsigned i=0;i<repetitions;++i)std::printf("%s%.17g",i?",":"",original[i]);
          std::printf("],\"checksum\":%llu,\"final_rng\":%llu}\n",(unsigned long long)checksum,(unsigned long long)rng);
#endif
          ++cases;
        }
    std::printf("{\"event\":\"complete\",\"cases\":%u,\"exit_code\":0}\n",cases);
    return std::ferror(stdout)?1:0;
  }catch(const std::exception &e){std::fprintf(stderr,"Sampling host probe: %s\n",e.what());return 1;}
}
