/* SPDX-License-Identifier: MIT */
/* Operator/configuration tests only. No model forward or context quality claim. */
#include "lie/rope.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
int main(void) {
    lie_rope_plan p,native,y2,y4;
    memset(&p,0xa5,sizeof(p)); lie_rope_plan old=p;
    assert(!lie_rope_plan_build((lie_rope_profile)99,262144,64,1e7,&p));
    assert(!memcmp(&p,&old,sizeof(p)));
    assert(!lie_rope_plan_build(LIE_ROPE_YARN4,262145,64,1e7,&p));
    assert(!lie_rope_plan_build(LIE_ROPE_NATIVE,262144,65,1e7,&p));
    assert(!lie_rope_plan_build(LIE_ROPE_NATIVE,262144,64,NAN,&p));
    assert(!lie_rope_plan_build(LIE_ROPE_NATIVE,262144,64,1,&p));
    assert(!lie_rope_plan_build(LIE_ROPE_NATIVE,0,64,1e7,&p));
    assert(!lie_rope_plan_build(LIE_ROPE_NATIVE,262144,258,1e7,&p));
    assert(!memcmp(&p,&old,sizeof(p)));
    assert(lie_rope_plan_build(LIE_ROPE_NATIVE,262144,64,1e7,&native));
    assert(lie_rope_plan_build(LIE_ROPE_YARN2,262144,64,1e7,&y2));
    assert(lie_rope_plan_build(LIE_ROPE_YARN4,262144,64,1e7,&y4));
    assert(native.context_limit==262144 && native.attention_factor==1);
    assert(y2.context_limit==524288 && y4.context_limit==1048576);
    /* Independent long-double oracle: wavelengths and their rotation-count
     * transition, rather than the production inverse-frequency computation. */
    const long double pi=acosl(-1.0L);
    long double low=floorl(32*logl(262144/(64*pi))/logl(1e7L));
    long double high=ceill(32*logl(262144/(2*pi))/logl(1e7L));
    assert(low==14 && high==22);
    for(unsigned profile=0;profile<3;++profile) {
        lie_rope_plan *plan=profile==0?&native:profile==1?&y2:&y4;
        unsigned factor=profile==0?1:profile==1?2:4;
        for(unsigned i=0;i<32;++i) {
            long double wavelength=powl(1e7L,(long double)i/32);
            long double extrapolation=i<=low?1:i>=high?0:(high-i)/(high-low);
            long double expected=(extrapolation+(1-extrapolation)/factor)/wavelength;
            assert(fabsl(plan->inv_frequency[i]/expected-1)<6e-8L);
            const unsigned positions[]={0,131072,262143,524287,1000000,1048575};
            for(unsigned j=0;j<6;++j) {
                long double angle=positions[j]*expected;
                long double scale=1+0.1L*logl(factor);
                long double c=cosl(angle)*scale,s=sinl(angle)*scale;
                assert(isfinite((double)c) && isfinite((double)s));
                assert(fabsl(c*c+s*s-scale*scale)<1e-15L);
            }
        }
    }
    assert(lie_rope_plan_domain(&native)!=lie_rope_plan_domain(&y2));
    assert(lie_rope_plan_domain(&y2)!=lie_rope_plan_domain(&y4));
    p=y4; assert(lie_rope_plan_domain(&p)==lie_rope_plan_domain(&y4));
    p.inv_frequency[15]*=1.001f;
    assert(lie_rope_plan_domain(&p)!=lie_rope_plan_domain(&y4));
    /* A second geometry exercises the shared numerical contract. */
    assert(lie_rope_plan_build(LIE_ROPE_YARN4,8192,128,10000,&p));
    assert(p.context_limit==32768 && p.rotary_dim==128);
    lie_rope_profile profile=LIE_ROPE_NATIVE;
    assert(lie_rope_profile_parse("yarn4",&profile) && profile==LIE_ROPE_YARN4);
    assert(!lie_rope_profile_parse("auto",&profile) && profile==LIE_ROPE_YARN4);
    puts("Static RoPE plan/operator contracts: PASS (NOT-INFERENCE)");
    return 0;
}
