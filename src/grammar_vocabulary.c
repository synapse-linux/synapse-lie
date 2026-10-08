/* SPDX-License-Identifier: MIT */
/* Copyright (c) 2026 gufo contributors. */
/* Attributed trie/mask/cache port from independently pinned Gufo f783fedb. */
#include "lie/grammar_vocabulary.h"
#include <stdlib.h>
#include <string.h>
#define NONE UINT32_MAX
#define TOKEN_MAX 1048576u
#define BYTE_MAX (64u * 1024u * 1024u)
#define NODE_MAX 4000000u
#define TEXT_MAX 4096u
#define INTERN_MAX 8192u

typedef struct { uint32_t offset, length, next; bool stop; } piece;
typedef struct { uint32_t first, last, tokens, last_token; } node;
typedef struct { uint32_t child, next; uint8_t byte; } edge;
struct lie_grammar_vocabulary {
  lie_grammar_allocator a;
  piece *pieces;
  uint8_t *bytes;
  node *nodes;
  edge *edges;
  size_t count, max_bytes, node_count, node_capacity, edge_count, edge_capacity;
};
static void *ordinary_allocate(void *ctx, size_t n) { (void)ctx; return malloc(n); }
static void ordinary_release(void *ctx, void *p) { (void)ctx; free(p); }
static bool allocator(lie_grammar_allocator *a) {
  if (!!a->allocate != !!a->release) return false;
  if (!a->allocate) *a = (lie_grammar_allocator){NULL, ordinary_allocate, ordinary_release};
  return true;
}
static void drop(lie_grammar_allocator a, void *p) { if (p) a.release(a.context, p); }
static bool grow(lie_grammar_allocator a, void **data, size_t *capacity,
                 size_t used, size_t need, size_t width, size_t limit) {
  if (need > limit || limit > SIZE_MAX / width) return false;
  if (need <= *capacity) return true;
  size_t n = *capacity ? *capacity : (limit < 8 ? limit : 8);
  while (n < need) n = n > limit / 2 ? limit : n * 2;
  void *p = a.allocate(a.context, n * width);
  if (!p) return false;
  if (used) memcpy(p, *data, used * width);
  drop(a, *data);
  *data = p; *capacity = n;
  return true;
}
void lie_vocabulary_description_init(lie_vocabulary_description *d) {
  if (d) *d = (lie_vocabulary_description){.abi_version=LIE_VOCABULARY_ABI,
    .struct_bytes=sizeof(*d), .limits={LIE_VOCABULARY_ABI,sizeof(d->limits),
      TOKEN_MAX,BYTE_MAX,TEXT_MAX,NODE_MAX}};
}
void lie_vocabulary_query_init(lie_vocabulary_query *q) {
  if (q) *q = (lie_vocabulary_query){LIE_VOCABULARY_ABI,sizeof(*q),2000000,INTERN_MAX,NULL,NULL};
}
void lie_vocabulary_release(lie_grammar_vocabulary *v) {
  if (!v) return;
  lie_grammar_allocator a=v->a;
  drop(a,v->edges); drop(a,v->nodes); drop(a,v->pieces); drop(a,v);
}
lie_grammar_status lie_vocabulary_create(const lie_vocabulary_description *d,
                                          lie_grammar_vocabulary **out) {
  if (!d || !out || d->abi_version!=LIE_VOCABULARY_ABI || d->struct_bytes!=sizeof(*d) ||
      d->limits.abi_version!=LIE_VOCABULARY_ABI || d->limits.struct_bytes!=sizeof(d->limits) ||
      !d->limits.max_tokens || d->limits.max_tokens>TOKEN_MAX ||
      !d->limits.max_bytes || d->limits.max_bytes>BYTE_MAX ||
      !d->limits.max_token_bytes || d->limits.max_token_bytes>TEXT_MAX ||
      !d->limits.max_nodes || d->limits.max_nodes>NODE_MAX || !d->count ||
      !d->pieces || d->count>d->limits.max_tokens || d->count>SIZE_MAX/sizeof(piece))
    return LIE_GRAMMAR_INVALID;
  lie_grammar_allocator a=d->allocator;
  if (!allocator(&a)) return LIE_GRAMMAR_INVALID;
  size_t bytes=0;
  for (size_t i=0;i<d->count;++i) {
    const lie_token_piece *p=d->pieces+i;
    if ((p->length && !p->bytes) || p->length>d->limits.max_bytes-bytes ||
        (!p->stop && p->length>d->limits.max_token_bytes)) return LIE_GRAMMAR_INVALID;
    bytes+=p->length;
  }
  if (bytes>SIZE_MAX-d->count*sizeof(piece)) return LIE_GRAMMAR_RESOURCE;
  lie_grammar_vocabulary *v=a.allocate(a.context,sizeof(*v));
  if (!v) return LIE_GRAMMAR_RESOURCE;
  *v=(lie_grammar_vocabulary){.a=a,.count=d->count};
  v->pieces=a.allocate(a.context,d->count*sizeof(piece)+bytes);
  if (!v->pieces) { lie_vocabulary_release(v); return LIE_GRAMMAR_RESOURCE; }
  v->bytes=(uint8_t *)(v->pieces+d->count);
  if (!grow(a,(void **)&v->nodes,&v->node_capacity,0,1,sizeof(node),d->limits.max_nodes)) {
    lie_vocabulary_release(v); return LIE_GRAMMAR_RESOURCE;
  }
  v->nodes[0]=(node){NONE,NONE,NONE,NONE}; v->node_count=1;
  size_t offset=0;
  lie_grammar_status rc=LIE_GRAMMAR_OK;
  for (size_t i=0;i<d->count && rc==LIE_GRAMMAR_OK;++i) {
    const lie_token_piece *p=d->pieces+i;
    v->pieces[i]=(piece){(uint32_t)offset,(uint32_t)p->length,NONE,p->stop};
    if (p->length) memcpy(v->bytes+offset,p->bytes,p->length);
    offset+=p->length;
    if (p->stop || !p->length) continue;
    if (p->length>v->max_bytes) v->max_bytes=p->length;
    uint32_t current=0;
    for (size_t j=0;j<p->length;++j) {
      uint32_t found=v->nodes[current].first;
      while (found!=NONE && v->edges[found].byte!=p->bytes[j]) found=v->edges[found].next;
      if (found!=NONE) { current=v->edges[found].child; continue; }
      if (v->node_count>=d->limits.max_nodes) { rc=LIE_GRAMMAR_VOCABULARY_LIMIT; break; }
      if (!grow(a,(void **)&v->nodes,&v->node_capacity,v->node_count,v->node_count+1,
                sizeof(node),d->limits.max_nodes) ||
          !grow(a,(void **)&v->edges,&v->edge_capacity,v->edge_count,v->edge_count+1,
                sizeof(edge),d->limits.max_nodes)) { rc=LIE_GRAMMAR_RESOURCE; break; }
      uint32_t e=(uint32_t)v->edge_count++,child=(uint32_t)v->node_count++;
      v->edges[e]=(edge){child,NONE,p->bytes[j]};
      v->nodes[child]=(node){NONE,NONE,NONE,NONE};
      node *parent=v->nodes+current;
      if (parent->last==NONE) parent->first=e; else v->edges[parent->last].next=e;
      parent->last=e; current=child;
    }
    if (rc!=LIE_GRAMMAR_OK) break;
    node *end=v->nodes+current;
    if (end->last_token==NONE) end->tokens=(uint32_t)i;
    else v->pieces[end->last_token].next=(uint32_t)i;
    end->last_token=(uint32_t)i;
  }
  if (rc!=LIE_GRAMMAR_OK) { lie_vocabulary_release(v); return rc; }
  *out=v; return LIE_GRAMMAR_OK;
}
size_t lie_vocabulary_size(const lie_grammar_vocabulary *v) { return v?v->count:0; }
size_t lie_vocabulary_max_token_bytes(const lie_grammar_vocabulary *v) { return v?v->max_bytes:0; }

typedef struct {
  const lie_grammar_state *state;
  uint64_t hash;
  uint32_t *next;
  bool owned;
} interned;
typedef struct {
  uint32_t node, edge, id;
  const lie_grammar_state *state;
  bool owned, direct, entered;
} walk_frame;
typedef struct {
  const lie_grammar_vocabulary *v;
  const lie_grammar_program *p;
  lie_vocabulary_query q;
  interned *states;
  uint32_t *buckets;
  size_t count, capacity, bucket_count;
  lie_vocabulary_stats stats;
} traversal;
static size_t slot(const traversal *t, const lie_grammar_state *s, uint64_t hash) {
  size_t at=(size_t)hash&(t->bucket_count-1);
  while (t->buckets[at]!=NONE) {
    const interned *c=t->states+t->buckets[at];
    if (c->hash==hash && !lie_grammar_state_compare(c->state,s)) break;
    at=(at+1)&(t->bucket_count-1);
  }
  return at;
}
static bool intern_buckets(traversal *t, size_t need) {
  size_t n=t->bucket_count?t->bucket_count:4;
  while (n<need*2) n*=2;
  if (n==t->bucket_count) return true;
  uint32_t *buckets=t->v->a.allocate(t->v->a.context,n*sizeof(uint32_t));
  if (!buckets) return false;
  for (size_t i=0;i<n;++i) buckets[i]=NONE;
  for (size_t i=1;i<t->count;++i) {
    size_t at=(size_t)t->states[i].hash&(n-1);
    while (buckets[at]!=NONE) at=(at+1)&(n-1);
    buckets[at]=(uint32_t)i;
  }
  drop(t->v->a,t->buckets); t->buckets=buckets; t->bucket_count=n;
  return true;
}
static bool intern_init(traversal *t, const lie_grammar_state *root) {
  lie_grammar_allocator a=t->v->a;
  if (!grow(a,(void **)&t->states,&t->capacity,0,2,sizeof(interned),t->q.max_interned_states)) return false;
  t->states[0]=(interned){0};
  t->states[1]=(interned){.state=root,.hash=lie_grammar_state_hash(root)};
  t->count=2;
  return intern_buckets(t,t->count);
}
static bool cached(const traversal *t, const lie_grammar_state *s) {
  return !t->q.cache_transitions || t->q.cache_transitions(t->q.context,s);
}
static lie_grammar_status child_state(traversal *t, walk_frame *f, uint8_t byte,
  const lie_grammar_state **out, uint32_t *id, bool *owned, bool *direct) {
  lie_grammar_state *next=NULL;
  uint32_t known=NONE;
  if (!f->direct) {
    interned *current=t->states+f->id;
    if (!current->next) {
      current->next=t->v->a.allocate(t->v->a.context,256*sizeof(uint32_t));
      if (!current->next) return LIE_GRAMMAR_RESOURCE;
      for (unsigned i=0;i<256;++i) current->next[i]=NONE;
    }
    known=current->next[byte];
    if (known!=NONE) {
      ++t->stats.cache_hits;
      *out=known?t->states[known].state:NULL; *id=known; *owned=false;
      *direct=known && !cached(t,*out);
      return LIE_GRAMMAR_OK;
    }
  }
  lie_grammar_status rc=lie_grammar_advance(t->p,f->state,byte,&next);
  if (rc!=LIE_GRAMMAR_OK) return rc;
  ++t->stats.advances;
  if (!lie_grammar_state_count(next)) {
    lie_grammar_state_release(next);
    if (!f->direct) t->states[f->id].next[byte]=0;
    *out=NULL; *id=0; *owned=false; *direct=f->direct;
    return LIE_GRAMMAR_OK;
  }
  if (f->direct) {
    *out=next; *id=NONE; *owned=true; *direct=true;
    return LIE_GRAMMAR_OK;
  }
  uint64_t hash=lie_grammar_state_hash(next);
  size_t at=slot(t,next,hash);
  known=t->buckets[at];
  if (known==NONE && t->count>=t->q.max_interned_states) {
    *out=next; *id=NONE; *owned=true; *direct=true;
    return LIE_GRAMMAR_OK;
  }
  if (known==NONE) {
    if (!intern_buckets(t,t->count+1) ||
        !grow(t->v->a,(void **)&t->states,&t->capacity,t->count,t->count+1,
              sizeof(interned),t->q.max_interned_states)) {
      lie_grammar_state_release(next); return LIE_GRAMMAR_RESOURCE;
    }
    at=slot(t,next,hash);
    known=(uint32_t)t->count++;
    t->states[known]=(interned){.state=next,.hash=hash,.owned=true};
    t->buckets[at]=known;
  } else lie_grammar_state_release(next);
  t->states[f->id].next[byte]=known;
  *out=t->states[known].state; *id=known; *owned=false;
  *direct=!cached(t,*out);
  return LIE_GRAMMAR_OK;
}
lie_grammar_status lie_vocabulary_allowed(const lie_grammar_vocabulary *v,
  const lie_grammar_program *p, const lie_grammar_state *input, bool stop_only,
  const lie_vocabulary_query *query, uint8_t *output, size_t size, lie_vocabulary_stats *stats) {
  lie_vocabulary_query q;
  lie_vocabulary_query_init(&q);
  if (query) q=*query;
  if (!v || !p || !input || !output || size!=v->count || q.abi_version!=LIE_VOCABULARY_ABI ||
      q.struct_bytes!=sizeof(q) || !q.max_work || q.max_work==SIZE_MAX ||
      q.max_interned_states>INTERN_MAX || q.max_interned_states==1) return LIE_GRAMMAR_INVALID;
  uint8_t *mask=v->a.allocate(v->a.context,v->count);
  if (!mask) return LIE_GRAMMAR_RESOURCE;
  memset(mask,0,v->count);
  bool complete=lie_grammar_complete(input);
  if (complete) for (size_t i=0;i<v->count;++i) mask[i]=v->pieces[i].stop;
  traversal t={.v=v,.p=p,.q=q};
  walk_frame *stack=NULL;
  size_t depth=0;
  lie_grammar_status rc=LIE_GRAMMAR_OK;
  if (!complete || !stop_only) {
    stack=v->a.allocate(v->a.context,(v->max_bytes+1)*sizeof(walk_frame));
    if (!stack) rc=LIE_GRAMMAR_RESOURCE;
    bool direct=!q.max_interned_states || !cached(&t,input);
    if (rc==LIE_GRAMMAR_OK && !direct && !intern_init(&t,input)) rc=LIE_GRAMMAR_RESOURCE;
    if (rc==LIE_GRAMMAR_OK) {
      stack[0]=(walk_frame){.node=0,.edge=v->nodes[0].first,.id=direct?NONE:1,
                           .state=input,.direct=direct};
      depth=1;
    }
    while (depth && rc==LIE_GRAMMAR_OK) {
      walk_frame *f=stack+depth-1;
      if (!f->entered) {
        if (++t.stats.visited_nodes>q.max_work) { rc=LIE_GRAMMAR_MASK_WORK_LIMIT; break; }
        if (depth>t.stats.peak_depth) t.stats.peak_depth=depth;
        if (f->direct) ++t.stats.direct_nodes;
        for (uint32_t token=v->nodes[f->node].tokens;token!=NONE;token=v->pieces[token].next) mask[token]=1;
        f->entered=true;
      }
      if (f->edge==NONE) {
        if (f->owned) lie_grammar_state_release((lie_grammar_state *)f->state);
        --depth; continue;
      }
      const edge *e=v->edges+f->edge;
      f->edge=e->next;
      const lie_grammar_state *next=NULL;
      uint32_t id;
      bool owned,direct;
      rc=child_state(&t,f,e->byte,&next,&id,&owned,&direct);
      if (rc!=LIE_GRAMMAR_OK) break;
      if (next) {
        /* Every non-stop trie path is at most max_bytes long. */
        if (depth>=v->max_bytes+1) {
          if (owned) lie_grammar_state_release((lie_grammar_state *)next);
          rc=LIE_GRAMMAR_INVALID; break;
        }
        stack[depth++]=(walk_frame){.node=e->child,.edge=v->nodes[e->child].first,
          .id=id,.state=next,.owned=owned,.direct=direct};
      }
    }
  }
  for (size_t i=0;i<depth;++i)
    if (stack[i].owned) lie_grammar_state_release((lie_grammar_state *)stack[i].state);
  for (size_t i=0;i<t.count;++i) {
    if (t.states[i].owned) lie_grammar_state_release((lie_grammar_state *)t.states[i].state);
    drop(v->a,t.states[i].next);
  }
  t.stats.interned_states=t.count;
  drop(v->a,t.states); drop(v->a,t.buckets); drop(v->a,stack);
  if (rc==LIE_GRAMMAR_OK) {
    bool any=false;
    for (size_t i=0;i<v->count;++i) if (mask[i]) { any=true; break; }
    if (!any && (!complete || !stop_only)) rc=LIE_GRAMMAR_NO_TOKEN;
  }
  if (rc==LIE_GRAMMAR_OK) { memcpy(output,mask,v->count); if (stats) *stats=t.stats; }
  drop(v->a,mask); return rc;
}
lie_grammar_status lie_vocabulary_accept(const lie_grammar_vocabulary *v,
  const lie_grammar_program *p, const lie_grammar_state *input, uint32_t token,
  lie_grammar_state **out) {
  if (!v || !p || !input || !out || token>=v->count) return LIE_GRAMMAR_INVALID;
  const piece *piece=v->pieces+token;
  if (piece->stop && lie_grammar_complete(input)) return lie_grammar_state_clone(p,input,out);
  if (piece->stop || !piece->length) return LIE_GRAMMAR_NO_TOKEN;
  const lie_grammar_state *current=input;
  lie_grammar_state *owned=NULL;
  for (size_t i=0;i<piece->length;++i) {
    lie_grammar_state *next=NULL;
    lie_grammar_status rc=lie_grammar_advance(p,current,v->bytes[piece->offset+i],&next);
    lie_grammar_state_release(owned);
    if (rc!=LIE_GRAMMAR_OK) return rc;
    owned=next; current=next;
  }
  if (!lie_grammar_state_count(owned)) { lie_grammar_state_release(owned); return LIE_GRAMMAR_NO_TOKEN; }
  *out=owned; return LIE_GRAMMAR_OK;
}

typedef struct { lie_grammar_state *key; void *value; } cache_entry;
struct lie_grammar_mask_cache {
  const lie_grammar_program *program;
  lie_grammar_allocator a;
  lie_grammar_payload_release release;
  void *context;
  cache_entry *entries;
  size_t count, capacity;
};
lie_grammar_status lie_mask_cache_create(const lie_grammar_program *p,size_t capacity,
  lie_grammar_allocator a,lie_grammar_payload_release release,void *context,
  lie_grammar_mask_cache **out) {
  if (!p || !out || !capacity || capacity>1024 || !release || !allocator(&a)) return LIE_GRAMMAR_INVALID;
  lie_grammar_mask_cache *c=a.allocate(a.context,sizeof(*c));
  if (!c) return LIE_GRAMMAR_RESOURCE;
  *c=(lie_grammar_mask_cache){.program=p,.a=a,.release=release,.context=context,.capacity=capacity};
  c->entries=a.allocate(a.context,capacity*sizeof(cache_entry));
  if (!c->entries) { drop(a,c); return LIE_GRAMMAR_RESOURCE; }
  *out=c; return LIE_GRAMMAR_OK;
}
static void retire(lie_grammar_mask_cache *c,size_t i) {
  lie_grammar_state_release(c->entries[i].key);
  c->release(c->context,c->entries[i].value);
  c->entries[i]=c->entries[--c->count];
}
void lie_mask_cache_release(lie_grammar_mask_cache *c) {
  if (!c) return;
  while (c->count) retire(c,c->count-1);
  drop(c->a,c->entries); drop(c->a,c);
}
size_t lie_mask_cache_size(const lie_grammar_mask_cache *c) { return c?c->count:0; }
lie_grammar_status lie_mask_cache_find(const lie_grammar_mask_cache *c,
  const lie_grammar_state *key,void **out) {
  if (!c || !key || !out) return LIE_GRAMMAR_INVALID;
  void *found=NULL;
  for (size_t i=0;i<c->count;++i)
    if (!lie_grammar_state_compare(c->entries[i].key,key)) { found=c->entries[i].value; break; }
  *out=found; return LIE_GRAMMAR_OK;
}
lie_grammar_status lie_mask_cache_publish(lie_grammar_mask_cache *c,
  const lie_grammar_state *key,void *value,void **out) {
  if (!c || !key || !value || !out) return LIE_GRAMMAR_INVALID;
  size_t victim=SIZE_MAX,duplicate=SIZE_MAX;
  if (c->count>=c->capacity) {
    victim=0;
    for (size_t i=1;i<c->count;++i)
      if (lie_grammar_state_compare(c->entries[i].key,c->entries[victim].key)<0) victim=i;
  }
  for (size_t i=0;i<c->count;++i)
    if (i!=victim && !lie_grammar_state_compare(c->entries[i].key,key)) { duplicate=i; break; }
  if (duplicate!=SIZE_MAX) {
    void *existing=c->entries[duplicate].value;
    if (victim!=SIZE_MAX) retire(c,victim);
    c->release(c->context,value); *out=existing; return LIE_GRAMMAR_OK;
  }
  lie_grammar_state *copy=NULL;
  lie_grammar_status rc=lie_grammar_state_clone(c->program,key,&copy);
  if (rc!=LIE_GRAMMAR_OK) return rc;
  if (victim!=SIZE_MAX) retire(c,victim);
  c->entries[c->count++]=(cache_entry){copy,value}; *out=value;
  return LIE_GRAMMAR_OK;
}
