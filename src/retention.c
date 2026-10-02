/* SPDX-License-Identifier: MIT */
#include "retention.h"
#include <math.h>
static double recent(const lie_retention *p,uint64_t clock){
    uint64_t elapsed=clock>=p->touched?clock-p->touched:UINT64_MAX;
    return elapsed>=65536?0:p->hits*exp2(-(double)elapsed/64.0);
}
void lie_retention_init(lie_retention *p,uint64_t clock,bool continuation){
    *p=(lie_retention){.touched=clock,.continuation=continuation};
}
void lie_retention_hit(lie_retention *p,uint64_t clock){
    if(!LIE_CACHE_UTILITY){p->touched=clock;return;}
    double h=recent(p,clock);p->hits=h<1048576?h+1:1048576;p->touched=clock;
}
double lie_retention_score(const lie_retention *p,uint64_t clock,uint64_t tokens,uint64_t bytes,bool superseded){
    if(!LIE_CACHE_UTILITY)return 0;
    if(!bytes||!tokens)return 0;
    double value=(1+recent(p,clock))*(double)tokens/(double)bytes;
    if(!p->continuation)value*=2;
    if(p->continuation&&superseded)value*=0.125;
    return value;
}
const char *lie_retention_policy(void){return LIE_CACHE_UTILITY?"decaying-token-byte-utility-v1":"lru";}
