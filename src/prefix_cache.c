/* SPDX-License-Identifier: MIT */
#include "prefix_cache.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
void lie_prefix_cache_init(lie_prefix_cache *c,uint64_t budget){memset(c,0,sizeof(*c));c->info.budget_bytes=budget;
    c->info.utility_policy=LIE_CACHE_UTILITY!=0;c->info.compression_enabled=lie_state_compression_enabled();}
static uint64_t touch(lie_prefix_cache *c){
    if(c->clock==UINT64_MAX){for(unsigned i=0;i<LIE_PREFIX_CACHE_ENTRIES;++i){c->entries[i].age=0;lie_retention_init(&c->entries[i].utility,0,false);}c->clock=0;}
    return ++c->clock;
}
static void remove_entry(lie_prefix_cache *c,unsigned i){
    lie_prefix_entry *e=&c->entries[i];if(!e->state)return;
    uint64_t bytes=lie_state_bytes(e->state);assert(c->info.retained_bytes>=bytes&&c->info.entries);
    c->info.retained_bytes-=bytes;c->info.expanded_bytes-=lie_state_expanded_bytes(e->state);
    --c->info.entries;lie_state_destroy(&e->state);e->age=0;
}
static bool extends(const lie_state *old,const int32_t *tokens,size_t n){
    const lie_state_layout *l=lie_state_description(old);
    return l&&tokens&&l->token_count<n&&!memcmp(lie_state_tokens(old),tokens,l->token_count*sizeof(*tokens));
}
static unsigned victim(lie_prefix_cache *c,const int32_t *tokens,size_t n,unsigned protected_slot){
    unsigned best=LIE_PREFIX_CACHE_ENTRIES;double score=0;
    for(unsigned i=0;i<LIE_PREFIX_CACHE_ENTRIES;++i){lie_prefix_entry *e=&c->entries[i];
        if(!e->state||i==protected_slot)continue;
        double value=lie_retention_score(&e->utility,c->clock,lie_state_description(e->state)->token_count,
                                         lie_state_bytes(e->state),LIE_CACHE_UTILITY&&extends(e->state,tokens,n));
        if(best==LIE_PREFIX_CACHE_ENTRIES||(LIE_CACHE_UTILITY?(value<score||(value==score&&e->age<c->entries[best].age)):
                                                              e->age<c->entries[best].age)){best=i;score=value;}
    }
    return best;
}
static bool continuation(lie_prefix_cache *c,const int32_t *tokens,size_t n){
    if(!LIE_CACHE_UTILITY)return false;
    for(unsigned i=0;i<LIE_PREFIX_CACHE_ENTRIES;++i)if(extends(c->entries[i].state,tokens,n))return true;
    return false;
}
static void installed(lie_prefix_cache *c,unsigned slot,lie_state *state,bool continued){
    lie_prefix_entry *e=&c->entries[slot];e->state=state;e->age=touch(c);lie_retention_init(&e->utility,c->clock,continued);
    c->info.retained_bytes+=lie_state_bytes(state);c->info.expanded_bytes+=lie_state_expanded_bytes(state);++c->info.entries;
    if(c->info.retained_bytes>c->info.peak_retained_bytes)c->info.peak_retained_bytes=c->info.retained_bytes;
}
void lie_prefix_cache_clear(lie_prefix_cache *c){for(unsigned i=0;i<LIE_PREFIX_CACHE_ENTRIES;++i)remove_entry(c,i);}
lie_state *lie_prefix_cache_find(lie_prefix_cache *c,const int32_t *tokens,size_t n){
    for(unsigned i=0;i<LIE_PREFIX_CACHE_ENTRIES;++i){lie_state *s=c->entries[i].state;const lie_state_layout *l=lie_state_description(s);
        if(l&&l->token_count==n&&!memcmp(lie_state_tokens(s),tokens,n*sizeof(*tokens)))return s;}
    return NULL;
}
void lie_prefix_cache_insert(lie_prefix_cache *c,lie_state *state){
    const lie_state_layout *l=lie_state_description(state);uint64_t bytes=lie_state_bytes(state);
    if(!l||bytes>c->info.budget_bytes||lie_state_restore_workspace(state)>c->info.budget_bytes-bytes||
       lie_prefix_cache_find(c,lie_state_tokens(state),l->token_count))return;
    bool continued=continuation(c,lie_state_tokens(state),l->token_count);
    unsigned slot=LIE_PREFIX_CACHE_ENTRIES;
    for(;;){unsigned oldest=victim(c,lie_state_tokens(state),l->token_count,LIE_PREFIX_CACHE_ENTRIES);
        for(unsigned i=0;i<LIE_PREFIX_CACHE_ENTRIES;++i){if(!c->entries[i].state)slot=i;
        }
        if(slot<LIE_PREFIX_CACHE_ENTRIES&&bytes<=c->info.budget_bytes-c->info.retained_bytes)break;
        assert(oldest<LIE_PREFIX_CACHE_ENTRIES);remove_entry(c,oldest);++c->info.evictions;
    }
    lie_state_retain(state);installed(c,slot,state,continued);
}
lie_status lie_prefix_cache_restore(lie_prefix_cache *c,lie_sequence *s,const int32_t *tokens,
                                    size_t n,uint32_t chunk,unsigned *reused,lie_error *error){
    if(!c||!s||!tokens||!n||!chunk||!reused)return LIE_INVALID;
    *reused=0;if(!c->info.budget_bytes)return LIE_OK;
    ++c->info.lookups;touch(c);unsigned best=LIE_PREFIX_CACHE_ENTRIES;size_t longest=0;
    for(unsigned i=0;i<LIE_PREFIX_CACHE_ENTRIES;++i){const lie_state_layout *l=lie_state_description(c->entries[i].state);
        /* Extending an unaligned checkpoint would change prefill chunk shapes.
         * Only an exact hit may reuse a short, non-chunk-aligned checkpoint. */
        if(l&&l->token_count<=n&&l->token_count>longest&&(l->token_count==n||l->token_count%chunk==0)&&
           !memcmp(tokens,lie_state_tokens(c->entries[i].state),l->token_count*sizeof(*tokens))){best=i;longest=l->token_count;}
    }
    if(best==LIE_PREFIX_CACHE_ENTRIES){++c->info.misses;return LIE_OK;}
    /* Expansion is a transient host allocation, admitted in the same budget.
     * Keep the selected checkpoint pinned while evicting only other entries. */
    uint64_t workspace=lie_state_restore_workspace(c->entries[best].state);
    while(workspace>c->info.budget_bytes-c->info.retained_bytes){
        unsigned evict=victim(c,NULL,0,best);
        if(evict==LIE_PREFIX_CACHE_ENTRIES){++c->info.misses;return LIE_OK;}
        remove_entry(c,evict);++c->info.evictions;
    }
    lie_status rc=lie_state_restore(s,c->entries[best].state,error);
    if(rc!=LIE_OK)return rc; /* A failed restoration is never a cache miss. */
    c->entries[best].age=touch(c);lie_retention_hit(&c->entries[best].utility,c->clock);
    ++c->info.hits;c->info.reused_tokens+=longest;*reused=(unsigned)longest;return LIE_OK;
}
lie_status lie_prefix_cache_capture(lie_prefix_cache *c,lie_sequence *s,const int32_t *tokens,
                                    size_t n,lie_error *error){
    if(!c->info.budget_bytes)return LIE_OK;
    for(unsigned i=0;i<LIE_PREFIX_CACHE_ENTRIES;++i){const lie_state_layout *l=lie_state_description(c->entries[i].state);
        if(l&&l->token_count==n&&!memcmp(tokens,lie_state_tokens(c->entries[i].state),n*sizeof(*tokens)))return LIE_OK;
    }
    lie_state_layout layout;uint64_t bytes=0;lie_status rc=lie_state_plan(s,&layout,&bytes,error);
    if(rc!=LIE_OK)return rc;
    if(layout.token_count!=n){if(error)snprintf(error->message,sizeof(error->message),"capture token frontier mismatch");return LIE_BACKEND_FAILED;}
    if(bytes>c->info.budget_bytes){++c->info.skipped;return LIE_OK;}
    bool continued=continuation(c,tokens,n);
    unsigned slot=LIE_PREFIX_CACHE_ENTRIES;
    for(;;){
        unsigned oldest=victim(c,tokens,n,LIE_PREFIX_CACHE_ENTRIES);
        for(unsigned i=0;i<LIE_PREFIX_CACHE_ENTRIES;++i){
            if(!c->entries[i].state)slot=i;
        }
        if(slot<LIE_PREFIX_CACHE_ENTRIES&&bytes<=c->info.budget_bytes-c->info.retained_bytes)break;
        assert(oldest<LIE_PREFIX_CACHE_ENTRIES);remove_entry(c,oldest);++c->info.evictions;
    }
    /* Evict before allocating: retained plus in-progress capture stays within
     * the same byte budget. No extra full-size staging snapshot is created. */
    lie_state *state=NULL;rc=lie_state_capture(s,&layout,c->info.budget_bytes-c->info.retained_bytes,&state,error);
    if(rc==LIE_RESOURCE_LIMIT){++c->info.skipped;return LIE_OK;}
    if(rc!=LIE_OK)return rc;
    if(memcmp(tokens,lie_state_tokens(state),n*sizeof(*tokens))){lie_state_destroy(&state);
        if(error)snprintf(error->message,sizeof(error->message),"captured token contents mismatch");
        return LIE_BACKEND_FAILED;
    }
    assert(lie_state_bytes(state)==bytes);
    if(c->info.compression_enabled){++c->info.compression_attempts;
        if(lie_state_compress(&state,c->info.budget_bytes-c->info.retained_bytes))++c->info.compressed_captures;}
    installed(c,slot,state,continued);++c->info.captures;
    return LIE_OK;
}
