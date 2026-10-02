/* SPDX-License-Identifier: MIT */
#include "retention.h"
#include <math.h>
static double recent(const lie_retention *p,uint64_t clock){
    uint64_t used=p->touched?p->touched:p->created;
    if(!used)return 0;
    uint64_t elapsed=clock>used?clock-used:0;
    double h=p->hits*exp2(-(double)elapsed/(double)LIE_CACHE_HALF_LIFE_SECONDS);
    return h<0.01?0:h;
}
void lie_retention_init(lie_retention *p,uint64_t clock,bool continuation){
    *p=(lie_retention){.touched=clock,.created=clock,.reason=continuation?LIE_CACHE_CONTINUED:LIE_CACHE_COLD};
}
void lie_retention_hit(lie_retention *p,uint64_t clock){
    if(p->hits<UINT32_MAX)++p->hits;
    p->touched=clock;
}
double lie_retention_score(const lie_retention *p,uint64_t clock,uint64_t tokens,uint64_t bytes,bool superseded){
    if(!LIE_CACHE_UTILITY)return 0;
    if(!bytes||!tokens)return 0;
    double h=recent(p,clock),value=(1+h)*(double)tokens/(double)bytes;
    if(p->reason==LIE_CACHE_COLD||p->reason==LIE_CACHE_EVICT||p->reason==LIE_CACHE_SHUTDOWN)value*=2;
    if(p->reason==LIE_CACHE_CONTINUED&&superseded)value*=0.05+0.45*h/(h+1);
    return value;
}
const char *lie_retention_policy(void){return LIE_CACHE_UTILITY?"ds4-time-token-byte-utility-v1":"lru";}
