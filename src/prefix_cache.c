/* SPDX-License-Identifier: MIT */
#include "prefix_cache.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
void lie_prefix_cache_init(lie_prefix_cache *c,uint64_t budget){memset(c,0,sizeof(*c));c->info.budget_bytes=budget;}
static uint64_t touch(lie_prefix_cache *c){
    if(c->clock==UINT64_MAX){for(unsigned i=0;i<LIE_PREFIX_CACHE_ENTRIES;++i)c->entries[i].age=0;c->clock=0;}
    return ++c->clock;
}
static void remove_entry(lie_prefix_cache *c,unsigned i){
    lie_prefix_entry *e=&c->entries[i];if(!e->state)return;
    uint64_t bytes=lie_state_bytes(e->state);assert(c->info.retained_bytes>=bytes&&c->info.entries);
    c->info.retained_bytes-=bytes;--c->info.entries;lie_state_destroy(&e->state);e->age=0;
}
void lie_prefix_cache_clear(lie_prefix_cache *c){for(unsigned i=0;i<LIE_PREFIX_CACHE_ENTRIES;++i)remove_entry(c,i);}
lie_status lie_prefix_cache_restore(lie_prefix_cache *c,lie_sequence *s,const int32_t *tokens,
                                    size_t n,uint32_t chunk,unsigned *reused,lie_error *error){
    if(!c||!s||!tokens||!n||!chunk||!reused)return LIE_INVALID;
    *reused=0;if(!c->info.budget_bytes)return LIE_OK;
    ++c->info.lookups;unsigned best=LIE_PREFIX_CACHE_ENTRIES;size_t longest=0;
    for(unsigned i=0;i<LIE_PREFIX_CACHE_ENTRIES;++i){const lie_state_layout *l=lie_state_description(c->entries[i].state);
        /* Extending an unaligned checkpoint would change prefill chunk shapes.
         * Only an exact hit may reuse a short, non-chunk-aligned checkpoint. */
        if(l&&l->token_count<=n&&l->token_count>longest&&(l->token_count==n||l->token_count%chunk==0)&&
           !memcmp(tokens,lie_state_tokens(c->entries[i].state),l->token_count*sizeof(*tokens))){best=i;longest=l->token_count;}
    }
    if(best==LIE_PREFIX_CACHE_ENTRIES){++c->info.misses;return LIE_OK;}
    lie_status rc=lie_state_restore(s,c->entries[best].state,error);
    if(rc!=LIE_OK)return rc; /* A failed restoration is never a cache miss. */
    c->entries[best].age=touch(c);++c->info.hits;c->info.reused_tokens+=longest;*reused=(unsigned)longest;return LIE_OK;
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
    unsigned slot=LIE_PREFIX_CACHE_ENTRIES;
    for(;;){
        unsigned oldest=LIE_PREFIX_CACHE_ENTRIES;
        for(unsigned i=0;i<LIE_PREFIX_CACHE_ENTRIES;++i){
            if(!c->entries[i].state)slot=i;
            else if(oldest==LIE_PREFIX_CACHE_ENTRIES||c->entries[i].age<c->entries[oldest].age)oldest=i;
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
    assert(lie_state_bytes(state)==bytes);c->entries[slot]=(lie_prefix_entry){state,touch(c)};
    c->info.retained_bytes+=bytes;++c->info.entries;++c->info.captures;
    if(c->info.retained_bytes>c->info.peak_retained_bytes)c->info.peak_retained_bytes=c->info.retained_bytes;
    return LIE_OK;
}
