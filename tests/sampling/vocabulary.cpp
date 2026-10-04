// SPDX-License-Identifier: MIT
// Full 248320-entry row witnesses, compactly hashed; not a model forward.
#include "src/core/sampling.hpp"
#include <bit>
#include <cmath>
#include <cstdio>
#include <vector>
static void retain(uint64_t& hash,uint64_t value) {
  for(unsigned i=0;i<8;++i){hash^=(value>>(i*8))&255;hash*=UINT64_C(1099511628211);}
}
int main() {
  using namespace gufo::sampling;
  std::vector<float> logits(248320);
  for(unsigned geometry=0;geometry<6;++geometry)
    for(unsigned filter=0;filter<4;++filter) {
    for(size_t i=0;i<logits.size();++i) {
      if(geometry==0)logits[i]=0;
      else if(geometry==1)logits[i]=float(std::sin(i*.17)*3);
      else if(geometry==2)logits[i]=float(i%127)/7;
      else if(geometry==3)logits[i]=float(logits.size()-i)/8192;
      else if(geometry==4)logits[i]=float(i<logits.size()/2?i:logits.size()-i)/8192;
      else logits[i]=float((i*8191)%logits.size())/8192;
    }
    SamplingConfig c;c.seed=77;c.temperature=.7f;
    if(filter==1)c.top_p=.95f;
    if(filter==2){c.top_k=32;c.top_p=.8f;c.min_p=.1f;}
    if(filter==3){c.min_p=.9f;c.min_keep=5;}
    SamplerState sampler(c);
    auto d=sampler.Distribution(logits);uint64_t hash=UINT64_C(14695981039346656037);
    for(auto p:d.entries()){retain(hash,p.token);retain(hash,std::bit_cast<uint64_t>(p.value));}
    uint64_t rng=77;
    for(unsigned draw=0;draw<64;++draw){retain(hash,d.Sample(&rng));retain(hash,rng);}
    std::printf("geometry=%u filter=%u count=%zu hash=%016llx rng=%llu\n",
      geometry,filter,d.entries().size(),(unsigned long long)hash,(unsigned long long)rng);
  }
  std::puts("FULL_VOCABULARY_HOST_WITNESSES_NOT_INFERENCE");
}
