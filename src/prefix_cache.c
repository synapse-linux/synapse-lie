/* SPDX-License-Identifier: MIT */
#include "prefix_cache.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
void lie_prefix_cache_init(lie_prefix_cache *c,uint64_t budget){memset(c,0,sizeof(*c));c->info.budget_bytes=budget;
    c->info.index_budget_bytes=budget<16u*1024u*1024u?budget:16u*1024u*1024u;
    c->info.utility_policy=LIE_CACHE_UTILITY!=0;c->info.compression_enabled=lie_state_compression_enabled();}
static bool grow(lie_prefix_cache *c){
    unsigned n=c->capacity?c->capacity*2:8;
    if(n<c->capacity||(uint64_t)n*sizeof(lie_prefix_entry)>c->info.index_budget_bytes)return false;
    lie_prefix_entry *p=realloc(c->entries,(size_t)n*sizeof(*p));if(!p)return false;
    memset(p+c->capacity,0,(n-c->capacity)*sizeof(*p));c->entries=p;c->capacity=n;
    c->info.index_bytes=(uint64_t)n*sizeof(*p);return true;
}
static uint64_t metadata_bytes(const lie_cache_metadata *m){return m->text_bytes+m->trailer_bytes+(m->text_bytes?1:0);}
static uint64_t touch(lie_prefix_cache *c){
    if(c->clock==UINT64_MAX){for(unsigned i=0;i<c->capacity;++i){c->entries[i].age=0;lie_retention_init(&c->entries[i].utility,0,false);}c->clock=0;}
    return ++c->clock;
}
static void remove_entry(lie_prefix_cache *c,unsigned i){
    lie_prefix_entry *e=&c->entries[i];if(!e->state)return;
    uint64_t meta=metadata_bytes(&e->metadata),bytes=lie_state_bytes(e->state)+meta;assert(c->info.retained_bytes>=bytes&&c->info.entries);
    c->info.retained_bytes-=bytes;c->info.expanded_bytes-=lie_state_expanded_bytes(e->state)+meta;
    lie_cache_metadata_clear(&e->metadata);
    --c->info.entries;lie_state_destroy(&e->state);e->age=0;
}
static bool extends(const lie_state *old,const int32_t *tokens,size_t n){
    const lie_state_layout *l=lie_state_description(old);
    return l&&tokens&&l->token_count<n&&!memcmp(lie_state_tokens(old),tokens,l->token_count*sizeof(*tokens));
}
static unsigned victim(lie_prefix_cache *c,const int32_t *tokens,size_t n,const lie_cache_metadata *m,unsigned protected_slot){
    unsigned best=c->capacity;double score=0;
    for(unsigned i=0;i<c->capacity;++i){lie_prefix_entry *e=&c->entries[i];
        if(!e->state||i==protected_slot)continue;
        bool superseded=extends(e->state,tokens,n);
        if(m&&(m->text_bytes||e->metadata.text_bytes))superseded=(m->flags&6u)==(e->metadata.flags&6u)&&
            e->metadata.text_bytes&&e->metadata.text_bytes<m->text_bytes&&!memcmp(e->metadata.text,m->text,e->metadata.text_bytes);
        double value=lie_retention_score(&e->utility,lie_cache_now(),lie_state_description(e->state)->token_count,
                                         lie_state_bytes(e->state)+metadata_bytes(&e->metadata),superseded);
        if(best==c->capacity||(LIE_CACHE_UTILITY?(value<score||(value==score&&e->age<c->entries[best].age)):
                                                              e->age<c->entries[best].age)){best=i;score=value;}
    }
    return best;
}
static bool continuation(lie_prefix_cache *c,const int32_t *tokens,size_t n){
    if(!LIE_CACHE_UTILITY)return false;
    for(unsigned i=0;i<c->capacity;++i)if(extends(c->entries[i].state,tokens,n))return true;
    return false;
}
static void installed(lie_prefix_cache *c,unsigned slot,lie_state *state,bool continued){
    lie_prefix_entry *e=&c->entries[slot];e->state=state;e->age=touch(c);lie_retention_init(&e->utility,lie_cache_now(),continued);
    c->info.retained_bytes+=lie_state_bytes(state);c->info.expanded_bytes+=lie_state_expanded_bytes(state);++c->info.entries;
    if(c->info.retained_bytes>c->info.peak_retained_bytes)c->info.peak_retained_bytes=c->info.retained_bytes;
}
void lie_prefix_cache_clear(lie_prefix_cache *c){
    for(unsigned i=0;i<c->capacity;++i)remove_entry(c,i);
    free(c->entries);c->entries=NULL;c->capacity=0;c->info.index_bytes=0;
}
const lie_cache_metadata *lie_prefix_cache_record(lie_prefix_cache *c,const lie_state *s){
    for(unsigned i=0;i<c->capacity;++i)if(s&&c->entries[i].state==s)return &c->entries[i].metadata;
    return NULL;
}
bool lie_prefix_cache_metadata(lie_prefix_cache *c,lie_state *state,const lie_cache_metadata *m){
    if(!lie_cache_metadata_valid(m))return false;
    for(unsigned i=0;i<c->capacity;++i)if(c->entries[i].state==state){
        lie_prefix_entry *e=&c->entries[i];uint64_t old=metadata_bytes(&e->metadata),add=metadata_bytes(m);
        if(add>c->info.budget_bytes-c->info.retained_bytes+old)return false;
        lie_cache_metadata copy={0};if(!lie_cache_metadata_copy(&copy,m))return false;
        lie_cache_metadata_clear(&e->metadata);e->metadata=copy;
        if(!e->metadata.created_at)e->metadata.created_at=lie_cache_now();
        if(!e->metadata.last_used)e->metadata.last_used=e->metadata.created_at;
        e->utility=(lie_retention){.created=e->metadata.created_at,.touched=e->metadata.last_used,
            .hits=e->metadata.hits,.reason=e->metadata.reason};
        c->info.retained_bytes=c->info.retained_bytes-old+add;
        c->info.expanded_bytes=c->info.expanded_bytes-old+add;
        if(c->info.retained_bytes>c->info.peak_retained_bytes)c->info.peak_retained_bytes=c->info.retained_bytes;
        return true;
    }
    return false;
}
lie_state *lie_prefix_cache_match_text(lie_prefix_cache *c,const char *text,size_t bytes,uint32_t flags,const lie_cache_metadata **metadata){
    lie_prefix_entry *best=NULL;
    for(unsigned i=0;i<c->capacity;++i){lie_prefix_entry *e=&c->entries[i];
        if(e->state&&(e->metadata.flags&6u)==(flags&6u)&&e->metadata.text_bytes&&e->metadata.text_bytes<=bytes&&
           (!best||e->metadata.text_bytes>best->metadata.text_bytes)&&!memcmp(e->metadata.text,text,e->metadata.text_bytes))best=e;
    }
    if(metadata)*metadata=best?&best->metadata:NULL;
    return best?best->state:NULL;
}
lie_state *lie_prefix_cache_find(lie_prefix_cache *c,const int32_t *tokens,size_t n){
    for(unsigned i=0;i<c->capacity;++i){lie_state *s=c->entries[i].state;const lie_state_layout *l=lie_state_description(s);
        if(l&&l->token_count==n&&!memcmp(lie_state_tokens(s),tokens,n*sizeof(*tokens)))return s;}
    return NULL;
}
void lie_prefix_cache_insert(lie_prefix_cache *c,lie_state *state){
    const lie_state_layout *l=lie_state_description(state);uint64_t bytes=lie_state_bytes(state);
    if(!l||bytes>c->info.budget_bytes||lie_state_restore_workspace(state)>c->info.budget_bytes-bytes||
       lie_prefix_cache_find(c,lie_state_tokens(state),l->token_count))return;
    bool continued=continuation(c,lie_state_tokens(state),l->token_count);
    bool full=true;for(unsigned i=0;i<c->capacity;++i)if(!c->entries[i].state)full=false;
    if(full)(void)grow(c);
    if(!c->capacity){++c->info.skipped;return;}
    unsigned slot=c->capacity;
    for(;;){unsigned oldest=victim(c,lie_state_tokens(state),l->token_count,NULL,c->capacity);
        for(unsigned i=0;i<c->capacity;++i){if(!c->entries[i].state)slot=i;
        }
        if(slot<c->capacity&&bytes<=c->info.budget_bytes-c->info.retained_bytes)break;
        assert(oldest<c->capacity);remove_entry(c,oldest);++c->info.evictions;
    }
    lie_state_retain(state);installed(c,slot,state,continued);
}
lie_status lie_prefix_cache_restore_key(lie_prefix_cache *c,lie_sequence *s,const int32_t *tokens,
                                    size_t n,uint32_t chunk,uint32_t flags,unsigned *reused,lie_error *error){
    if(!c||!s||!tokens||!n||!chunk||!reused)return LIE_INVALID;
    *reused=0;if(!c->info.budget_bytes)return LIE_OK;
    ++c->info.lookups;touch(c);unsigned best=c->capacity;size_t longest=0;
    for(unsigned i=0;i<c->capacity;++i){const lie_state_layout *l=lie_state_description(c->entries[i].state);
        /* Extending an unaligned checkpoint would change prefill chunk shapes.
         * Only an exact hit may reuse a short, non-chunk-aligned checkpoint. */
        if(l&&(c->entries[i].metadata.flags&6u)==(flags&6u)&&l->token_count<=n&&l->token_count>longest&&(l->token_count==n||l->token_count%chunk==0)&&
           !memcmp(tokens,lie_state_tokens(c->entries[i].state),l->token_count*sizeof(*tokens))){best=i;longest=l->token_count;}
    }
    if(best==c->capacity){++c->info.misses;return LIE_OK;}
    /* Expansion is a transient host allocation, admitted in the same budget.
     * Keep the selected checkpoint pinned while evicting only other entries. */
    uint64_t workspace=lie_state_restore_workspace(c->entries[best].state);
    while(workspace>c->info.budget_bytes-c->info.retained_bytes){
        unsigned evict=victim(c,NULL,0,NULL,best);
        if(evict==c->capacity){++c->info.misses;return LIE_OK;}
        remove_entry(c,evict);++c->info.evictions;
    }
    lie_status rc=lie_state_restore(s,c->entries[best].state,error);
    if(rc!=LIE_OK)return rc; /* A failed restoration is never a cache miss. */
    c->entries[best].age=touch(c);lie_retention_hit(&c->entries[best].utility,lie_cache_now());
    c->entries[best].metadata.hits=c->entries[best].utility.hits;c->entries[best].metadata.last_used=c->entries[best].utility.touched;
    ++c->info.hits;c->info.reused_tokens+=longest;*reused=(unsigned)longest;return LIE_OK;
}
lie_status lie_prefix_cache_restore(lie_prefix_cache *c,lie_sequence *s,const int32_t *tokens,
                                    size_t n,uint32_t chunk,unsigned *reused,lie_error *error){
    return lie_prefix_cache_restore_key(c,s,tokens,n,chunk,0,reused,error);
}
lie_status lie_prefix_cache_capture_ex(lie_prefix_cache *c,lie_sequence *s,const int32_t *tokens,
                                    size_t n,const lie_cache_metadata *metadata,lie_error *error){
    if(!c->info.budget_bytes)return LIE_OK;
    for(unsigned i=0;i<c->capacity;++i){const lie_state_layout *l=lie_state_description(c->entries[i].state);
        if(l&&l->token_count==n&&!memcmp(tokens,lie_state_tokens(c->entries[i].state),n*sizeof(*tokens))){
            if(metadata){lie_cache_metadata m=*metadata;
                m.hits=c->entries[i].metadata.hits;m.created_at=c->entries[i].metadata.created_at;m.last_used=c->entries[i].metadata.last_used;
                if(!lie_prefix_cache_metadata(c,c->entries[i].state,&m))++c->info.skipped;}
            return LIE_OK;
        }
    }
    lie_state_layout layout;uint64_t bytes=0;lie_status rc=lie_state_plan(s,&layout,&bytes,error);
    if(rc!=LIE_OK)return rc;
    if(layout.token_count!=n){if(error)snprintf(error->message,sizeof(error->message),"capture token frontier mismatch");return LIE_BACKEND_FAILED;}
    uint64_t extra=metadata?metadata_bytes(metadata):0;
    if(metadata&&!lie_cache_metadata_valid(metadata))return LIE_INVALID;
    if(bytes>c->info.budget_bytes||extra>c->info.budget_bytes-bytes){++c->info.skipped;return LIE_OK;}
    bytes+=extra;
    bool continued=continuation(c,tokens,n);
    bool full=true;for(unsigned i=0;i<c->capacity;++i)if(!c->entries[i].state)full=false;
    if(full)(void)grow(c);
    if(!c->capacity){++c->info.skipped;return LIE_OK;}
    unsigned slot=c->capacity;
    for(;;){
        unsigned oldest=victim(c,tokens,n,metadata,c->capacity);
        for(unsigned i=0;i<c->capacity;++i){
            if(!c->entries[i].state)slot=i;
        }
        if(slot<c->capacity&&bytes<=c->info.budget_bytes-c->info.retained_bytes)break;
        assert(oldest<c->capacity);remove_entry(c,oldest);++c->info.evictions;
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
    assert(lie_state_bytes(state)+extra==bytes);
    if(c->info.compression_enabled){++c->info.compression_attempts;
        if(lie_state_compress(&state,c->info.budget_bytes-c->info.retained_bytes))++c->info.compressed_captures;}
    installed(c,slot,state,continued);
    if(metadata&&!lie_prefix_cache_metadata(c,state,metadata)){remove_entry(c,slot);++c->info.skipped;return LIE_OK;}
    ++c->info.captures;
    return LIE_OK;
}

lie_status lie_prefix_cache_capture(lie_prefix_cache *c,lie_sequence *s,const int32_t *tokens,size_t n,lie_error *error){
    return lie_prefix_cache_capture_ex(c,s,tokens,n,NULL,error);
}
