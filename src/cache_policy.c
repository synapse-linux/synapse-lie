/* SPDX-License-Identifier: MIT */
#include "lie/cache_policy.h"
#include <stdlib.h>
#include <string.h>
#include <time.h>
void lie_cache_policy_init(lie_cache_policy *p){
    if(p)*p=(lie_cache_policy){.enabled=true,.text_prefix=true,.capture_finish=true,
        .min_tokens=512,.cold_max_tokens=30000,.continued_interval_tokens=10000,
        .boundary_trim_tokens=32,.boundary_align_tokens=2048};
}
uint64_t lie_cache_now(void){time_t t=time(NULL);return t>0?(uint64_t)t:0;}
uint32_t lie_cache_store_len(const lie_cache_policy *p,uint32_t n){
    if((uint64_t)n>(uint64_t)p->min_tokens+p->boundary_trim_tokens){
        uint32_t stable=n-p->boundary_trim_tokens;
        if(p->boundary_align_tokens)stable-=stable%p->boundary_align_tokens;
        if(stable>=p->min_tokens)return stable;
    }
    return n;
}
uint32_t lie_cache_continued_step(const lie_cache_policy *p){
    uint64_t step=p->enabled?p->continued_interval_tokens:0;
    if(step&&p->boundary_align_tokens)step=((step+p->boundary_align_tokens-1)/p->boundary_align_tokens)*p->boundary_align_tokens;
    return step<=UINT32_MAX?(uint32_t)step:0;
}
bool lie_cache_metadata_valid(const lie_cache_metadata *m){
    return m&&m->reason<=LIE_CACHE_AGENT_SESSION&&!(m->flags&~15u)&&
        m->text_bytes<=LIE_CACHE_TEXT_MAX&&m->trailer_bytes<=LIE_CACHE_TRAILER_MAX&&
        (!m->text_bytes||m->text)&&(!m->trailer_bytes||m->trailer);
}
bool lie_cache_metadata_copy(lie_cache_metadata *out,const lie_cache_metadata *m){
    if(!out||!lie_cache_metadata_valid(m))return false;
    char *text=NULL;void *trailer=NULL;
    if(m->text_bytes){text=malloc(m->text_bytes+1);if(!text)return false;
        memcpy(text,m->text,m->text_bytes);text[m->text_bytes]=0;}
    if(m->trailer_bytes){trailer=malloc(m->trailer_bytes);if(!trailer){free(text);return false;}memcpy(trailer,m->trailer,m->trailer_bytes);}
    *out=*m;out->text=text;out->trailer=trailer;return true;
}
void lie_cache_metadata_clear(lie_cache_metadata *m){
    if(m){free((void *)m->text);free((void *)m->trailer);memset(m,0,sizeof(*m));}
}

const char *lie_cache_option_name(const char *key){
    static const struct { const char *old, *canonical; } aliases[]={
        {"--prefix-cache-mib","--kv-cache-ram-mb"},
        {"--prefix-ssd-dir","--kv-disk-dir"},
        {"--prefix-ssd-quota-mib","--kv-disk-space-mb"},
        {"--prefix-ssd-staging-mib","--kv-disk-staging-mb"},
        {"--state-ssd-mode","--kv-disk-mode"},
        {"--cache-policy","--kv-cache-policy"},
        {"--cache-min-tokens","--kv-cache-min-tokens"},
        {"--cache-cold-max-tokens","--kv-cache-cold-max-tokens"},
        {"--cache-continued-tokens","--kv-cache-continued-interval-tokens"},
        {"--cache-trim-tokens","--kv-cache-boundary-trim-tokens"},
        {"--cache-align-tokens","--kv-cache-boundary-align-tokens"},
        {"--cache-text-prefix","--kv-cache-text-prefix"},
        {"--cache-capture-finish","--kv-cache-capture-finish"}
    };
    for(size_t i=0;i<sizeof(aliases)/sizeof(aliases[0]);++i)
        if(!strcmp(key,aliases[i].old))return aliases[i].canonical;
    return key;
}

int lie_cache_policy_option(lie_cache_policy *p,const char *key,const char *value){
    key=lie_cache_option_name(key);
    if(!strcmp(key,"--kv-cache-policy")){
        if(strcmp(value,"ds4")&&strcmp(value,"legacy"))return -1;
        p->enabled=!strcmp(value,"ds4");return 1;
    }
    bool *flag=!strcmp(key,"--kv-cache-text-prefix")?&p->text_prefix:
        !strcmp(key,"--kv-cache-capture-finish")?&p->capture_finish:NULL;
    if(flag){if(strcmp(value,"on")&&strcmp(value,"off"))return -1;*flag=!strcmp(value,"on");return 1;}
    uint32_t *number=!strcmp(key,"--kv-cache-min-tokens")?&p->min_tokens:
        !strcmp(key,"--kv-cache-cold-max-tokens")?&p->cold_max_tokens:
        !strcmp(key,"--kv-cache-continued-interval-tokens")?&p->continued_interval_tokens:
        !strcmp(key,"--kv-cache-boundary-trim-tokens")?&p->boundary_trim_tokens:
        !strcmp(key,"--kv-cache-boundary-align-tokens")?&p->boundary_align_tokens:NULL;
    if(!number)return 0;
    uint64_t n=0;if(!*value)return -1;
    for(const char *c=value;*c;++c){if(*c<'0'||*c>'9'||n>(UINT32_MAX-(unsigned)(*c-'0'))/10u)return -1;n=n*10+(unsigned)(*c-'0');}
    *number=(uint32_t)n;return 1;
}
