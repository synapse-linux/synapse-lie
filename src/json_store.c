/* SPDX-License-Identifier: MIT */
#include "lie/json_store.h"
#include <stdlib.h>
#include <string.h>

typedef enum { EMPTY, OWNED, TAKEN } state;
typedef struct { lie_json_value *root; state state; } slot;
struct lie_json_store {
  lie_json_store_description d;
  lie_json_store_info info;
  slot *slots;
  size_t capacity, occupied;
};
void lie_json_store_description_init(lie_json_store_description *d) {
  if (!d) return;
  memset(d,0,sizeof(*d));d->abi_version=LIE_JSON_STORE_ABI;d->struct_bytes=sizeof(*d);
  d->max_roots=262144u;d->max_owned_bytes=16u*1024u*1024u;
}
static void *allocate(lie_json_store *s,size_t bytes) {
  void *p=s->d.allocator.allocate ? s->d.allocator.allocate(s->d.allocator.context,bytes) : malloc(bytes);
  if (!p) return NULL;
  s->info.live_owned_bytes+=bytes;++s->info.allocations;
  if (s->info.live_owned_bytes>s->info.peak_owned_bytes)
    s->info.peak_owned_bytes=s->info.live_owned_bytes;
  return p;
}
static void retire(lie_json_store *s,void *p,size_t bytes) {
  if (!p) return;
  s->info.live_owned_bytes-=bytes;
  if (s->d.allocator.release) s->d.allocator.release(s->d.allocator.context,p);else free(p);
}
lie_json_store_status lie_json_store_create(const lie_json_store_description *in,
                                            lie_json_store **out) {
  lie_json_store_description d;if (in) d=*in;else lie_json_store_description_init(&d);
  if (!out || d.abi_version!=LIE_JSON_STORE_ABI || d.struct_bytes!=sizeof(d) ||
      !d.max_roots || d.max_owned_bytes<sizeof(lie_json_store) ||
      (!!d.allocator.allocate!=!!d.allocator.release)) return LIE_JSON_STORE_INVALID;
  lie_json_store *s=d.allocator.allocate ? d.allocator.allocate(d.allocator.context,sizeof(*s)) : malloc(sizeof(*s));
  if (!s) return LIE_JSON_STORE_RESOURCE;
  memset(s,0,sizeof(*s));s->d=d;s->info.live_owned_bytes=sizeof(*s);
  s->info.peak_owned_bytes=sizeof(*s);s->info.allocations=1;*out=s;return LIE_JSON_STORE_OK;
}
static size_t hash(const lie_json_value *root) {
  uintptr_t x=(uintptr_t)root;
  /* Ignore neither high address bits nor alignment; also valid on 32-bit C17. */
  x^=x>>16;x*=(uintptr_t)0x7feb352du;x^=x>>15;
  x*=(uintptr_t)0x846ca68bu;x^=x>>16;return (size_t)x;
}
static slot *find(slot *slots,size_t capacity,const lie_json_value *root) {
  if (!capacity) return NULL;
  size_t i=hash(root)&(capacity-1);slot *vacant=NULL;
  for (size_t steps=0;steps<capacity;++steps) {
    slot *p=&slots[i];
    if (p->state==EMPTY) return vacant ? vacant : p;
    if (p->state==OWNED && p->root==root) return p;
    if (p->state==TAKEN && !vacant) vacant=p;
    i=(i+1)&(capacity-1);
  }
  return vacant;
}
static lie_json_store_status reserve(lie_json_store *s) {
  if (s->capacity && s->occupied+1<=s->capacity/2) return LIE_JSON_STORE_OK;
  size_t capacity=s->capacity ? s->capacity : 16;
  if (s->info.live_roots+1>capacity/2) {
    if (capacity>SIZE_MAX/2) return LIE_JSON_STORE_LIMIT;
    capacity*=2;
  }
  if (capacity>SIZE_MAX/sizeof(slot)) return LIE_JSON_STORE_LIMIT;
  const size_t bytes=capacity*sizeof(slot);
  if (bytes>s->d.max_owned_bytes-s->info.live_owned_bytes) return LIE_JSON_STORE_LIMIT;
  slot *next=allocate(s,bytes);if (!next) return LIE_JSON_STORE_RESOURCE;
  memset(next,0,bytes);
  for (size_t i=0;i<s->capacity;++i) if (s->slots[i].state==OWNED)
    *find(next,capacity,s->slots[i].root)=s->slots[i];
  retire(s,s->slots,s->capacity*sizeof(slot));s->slots=next;
  s->capacity=capacity;s->occupied=s->info.live_roots;return LIE_JSON_STORE_OK;
}
lie_json_store_status lie_json_store_adopt(lie_json_store *s,lie_json_value *root) {
  if (!s || !lie_json_value_is_root(root)) return LIE_JSON_STORE_INVALID;
  slot *p=find(s->slots,s->capacity,root);
  if (p && p->state==OWNED) return LIE_JSON_STORE_INVALID;
  if (s->info.accepted_roots>=s->d.max_roots) return LIE_JSON_STORE_LIMIT;
  if (!p || p->state!=TAKEN) {
    const lie_json_store_status rc=reserve(s);if (rc!=LIE_JSON_STORE_OK) return rc;
  }
  p=find(s->slots,s->capacity,root);
  if (p->state==EMPTY) ++s->occupied;
  p->root=root;p->state=OWNED;++s->info.live_roots;++s->info.accepted_roots;
  return LIE_JSON_STORE_OK;
}
lie_json_store_status lie_json_store_take(lie_json_store *s,const lie_json_value *root,
                                         lie_json_value **out) {
  if (!s || !root || !out) return LIE_JSON_STORE_INVALID;
  slot *p=find(s->slots,s->capacity,root);
  if (!p || p->state!=OWNED) return LIE_JSON_STORE_INVALID;
  *out=p->root;p->root=NULL;p->state=TAKEN;--s->info.live_roots;
  return LIE_JSON_STORE_OK;
}
void lie_json_store_describe(const lie_json_store *s,lie_json_store_info *out) {
  if (!out) return;
  if (s) *out=s->info;else memset(out,0,sizeof(*out));
}
void lie_json_store_release(lie_json_store *s) {
  if (!s) return;
  for (size_t i=0;i<s->capacity;++i) if (s->slots[i].state==OWNED)
    lie_json_value_release(s->slots[i].root);
  retire(s,s->slots,s->capacity*sizeof(slot));
  const lie_grammar_allocator a=s->d.allocator;
  if (a.release) a.release(a.context,s);else free(s);
}
