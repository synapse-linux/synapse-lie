/* SPDX-License-Identifier: MIT */
#include "lie/rope.h"
#include <math.h>
#include <stddef.h>
#include <string.h>
_Static_assert(sizeof(float) == sizeof(uint32_t), "RoPE identity requires binary32 storage");
const char *lie_rope_profile_name(lie_rope_profile p) {
    switch(p) {
    case LIE_ROPE_NATIVE: return "native";
    case LIE_ROPE_YARN2: return "yarn2";
    case LIE_ROPE_YARN4: return "yarn4";
    }
    return NULL;
}
bool lie_rope_profile_parse(const char *name, lie_rope_profile *out) {
    if(!name || !out) return false;
    for(unsigned i=0;i<=LIE_ROPE_YARN4;++i)
        if(!strcmp(name,lie_rope_profile_name((lie_rope_profile)i))) {
            *out=(lie_rope_profile)i; return true;
        }
    return false;
}
bool lie_rope_plan_build(lie_rope_profile profile,uint32_t native,
                         uint32_t dim,double theta,lie_rope_plan *out) {
    if(!out || !lie_rope_profile_name(profile) || !native ||
       native>LIE_CONTEXT_LIMIT || !dim || (dim&1u) ||
       dim>LIE_ROPE_MAX_DIM || !isfinite(theta) || theta<=1.0) return false;
    unsigned factor=profile==LIE_ROPE_YARN2?2u:profile==LIE_ROPE_YARN4?4u:1u;
    if(native>LIE_CONTEXT_LIMIT/factor) return false;
    lie_rope_plan p={.abi_version=LIE_ROPE_PLAN_ABI,.native_context=native,
        .context_limit=native*factor,.rotary_dim=dim,.profile=profile,
        .attention_factor=(float)(1.0+0.1*log((double)factor))};
    const double two_pi=6.283185307179586476925286766559;
    double low=fmax(0.0,floor(dim*log(native/(32.0*two_pi))/(2.0*log(theta))));
    double high=fmin(dim-1.0,ceil(dim*log(native/two_pi)/(2.0*log(theta))));
    high=fmax(high,low+0.001);
    for(unsigned i=0;i<dim/2;++i) {
        double ramp=fmax(0.0,fmin(1.0,(i-low)/(high-low)));
        double frequency=pow(theta,-2.0*i/dim);
        if(factor!=1) frequency*=1.0-ramp+ramp/factor;
        p.inv_frequency[i]=(float)frequency;
        if(!isfinite(p.inv_frequency[i]) || p.inv_frequency[i]<=0) return false;
    }
    *out=p; return true;
}
uint64_t lie_rope_plan_domain(const lie_rope_plan *p) {
    if(!p || p->abi_version!=LIE_ROPE_PLAN_ABI ||
       !lie_rope_profile_name(p->profile) || p->rotary_dim>LIE_ROPE_MAX_DIM)
        return 0;
    uint64_t hash=UINT64_C(14695981039346656037);
    uint32_t fields[]={p->abi_version,p->native_context,p->context_limit,
        p->rotary_dim,(uint32_t)p->profile,0};
    memcpy(&fields[5],&p->attention_factor,4);
    for(size_t i=0;i<6+p->rotary_dim/2;++i) {
        uint32_t word;
        if(i<6) word=fields[i];
        else memcpy(&word,&p->inv_frequency[i-6],4);
        for(unsigned b=0;b<4;++b) {
            hash^=(word>>(8*b))&255u; hash*=UINT64_C(1099511628211);
        }
    }
    return hash;
}
