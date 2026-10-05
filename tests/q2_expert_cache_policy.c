/* SPDX-License-Identifier: MIT */
#include <assert.h>
#include "experiments/q2_expert_cache_policy.h"
int main(void) {
    lie_q2_expert_cache_plan p;
    size_t used=0;
    unsigned count=0;
    for(unsigned i=0;i<48;++i) {
        int admitted=lie_q2_expert_cache_admit(i,48,512,2560,640,true,used,SIZE_MAX,&p);
        assert(admitted==(i%8==0));
        if(admitted) {used=p.next_cache_bytes;++count;}
    }
    assert(count==6 && used==(size_t)30199062528ULL);
    assert(lie_q2_expert_cache_admit(0,48,512,2560,640,true,0,SIZE_MAX,&p)==1);
    size_t need=p.layer_allocation_bytes;
    assert(lie_q2_expert_cache_admit(0,48,512,2560,640,true,0,need+LIE_Q2_EXPERT_CACHE_RESERVE-1,&p)==0);
    assert(lie_q2_expert_cache_admit(0,48,512,2560,640,true,0,need+LIE_Q2_EXPERT_CACHE_RESERVE,&p)==1);
    assert(lie_q2_expert_cache_admit(0,48,512,2560,640,true,SIZE_MAX,SIZE_MAX,&p)==0);
    assert(lie_q2_expert_cache_admit(0,48,512,2560,640,true,LIE_Q2_EXPERT_CACHE_BUDGET-need+1,SIZE_MAX,&p)==0);
    assert(lie_q2_expert_cache_admit(48,48,512,2560,640,true,0,SIZE_MAX,&p)==0);
    assert(lie_q2_expert_cache_admit(0,48,512,2560,640,false,0,SIZE_MAX,&p)==0);
    assert(lie_q2_expert_cache_admit(0,48,UINT32_MAX,UINT32_MAX,UINT32_MAX,true,0,SIZE_MAX,&p)==0);
    assert(lie_q2_expert_cache_admit(0,48,512,2560,640,true,0,SIZE_MAX,NULL)==-1);
    return 0;
}
