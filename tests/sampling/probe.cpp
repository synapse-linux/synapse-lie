// SPDX-License-Identifier: MIT
// Complete host witnesses for pinned reference, C17 bridge and build fallback.
#include "src/core/sampling.hpp"
#include <cmath>
#include <cstdio>
#include <cstring>
#include <limits>
#include <vector>
int main(int argc,char **argv) {
  bool biased=argc==2 && !std::strcmp(argv[1],"--bias");
  using namespace gufo::sampling;
  const uint32_t prompt[]={0,3,3,8,9};
  const uint32_t accepted[]={2,2,3,8};
  unsigned cases=0;
  for(size_t size:{size_t(1),size_t(17),size_t(1024),size_t(1025),size_t(4097)})
    for(unsigned geometry=0;geometry<4;++geometry)
      for(float temperature:{0.0f,.1f,.7f,1.0f,2.0f})
        for(unsigned filter=0;filter<6;++filter)
          for(unsigned penalized=0;penalized<2;++penalized) {
    std::vector<float> logits(size);
    for(size_t i=0;i<size;++i) {
      logits[i]=geometry==0?0.0f:geometry==1?float(i%11)-5.0f:
        geometry==2?float(i)/7.0f:float(std::sin(double(i)*.17)*3.0);
      if(geometry==3 && i%23==0)logits[i]=-std::numeric_limits<float>::infinity();
    }
    if(size==1)logits[0]=0;
    SamplingConfig c;c.seed=77;c.temperature=temperature;
    if(filter==1)c.top_k=1;
    if(filter==2){c.top_k=7;c.top_p=.75f;c.min_p=.05f;}
    if(filter==3)c.top_p=.999f;
    if(filter==4){c.top_p=.45f;c.min_p=.95f;c.min_keep=5;}
    if(filter==5){c.min_p=.99f;c.min_keep=2;}
    if(penalized){c.repeat_penalty=1.2f;c.repeat_last_n=3;c.frequency_penalty=.5f;c.presence_penalty=-.2f;}
#ifdef LIE_TEST_BIAS
    if(biased){c.logit_bias.resize(size);c.logit_bias[0]=4;
      c.logit_bias[size-1]=-4;if(size>1)c.logit_bias[1]=2;}
#else
    if(biased)return 2;
#endif
    SamplerState sampler(c,prompt);sampler.Accept(accepted);
    const auto distribution=sampler.Distribution(logits);
    std::printf("case=%u size=%zu geometry=%u filter=%u penalty=%u temp=%a\n",
      cases++,size,geometry,filter,penalized,double(temperature));
    for(const auto& p:distribution.entries())std::printf("p=%u:%a\n",p.token,p.value);
    for(unsigned draw=0;draw<16;++draw){
      auto token=sampler.Sample(logits);
      std::printf("draw=%u rng=%llu\n",token,(unsigned long long)sampler.rng_state());
    }
    SamplerState clone=sampler;clone.Accept(0);
    auto saved=clone.SaveDrawState();(void)clone.Uniform();clone.RestoreDrawState(saved);
    auto cloned_token=clone.Sample(logits);
    std::printf("clone=%u rng=%llu\n",cloned_token,(unsigned long long)clone.rng_state());
    uint32_t ids[]={0,0,(uint32_t)(size-1)};
    float q[]={.1f,.2f,.4f};
    for(unsigned draw=0;draw<4;++draw){
      auto residual=sampler.SampleResidual(logits,ids,q);
      std::printf("residual=%u rng=%llu\n",residual,(unsigned long long)sampler.rng_state());}
    uint64_t state=0;
    for(unsigned draw=0;draw<4;++draw){auto value=NextRandom(&state);
      std::printf("next=%llu state=%llu\n",(unsigned long long)value,(unsigned long long)state);}
  }
  std::printf("CASES=%u COMPLETE_HOST_WITNESSES_NOT_INFERENCE\n",cases);
}
