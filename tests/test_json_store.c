/* SPDX-License-Identifier: MIT */
#include "lie/json_store.h"
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static size_t checks, refusals;
#define CHECK(x) do { assert(x);++checks; } while (0)
typedef struct { size_t calls,fail,live,bytes,views; } heap;
typedef union { max_align_t align; size_t bytes; } block;
static void *allocate(void *context,size_t bytes) {
  heap *h=context;if (++h->calls==h->fail) return NULL;
  block *b=malloc(sizeof(*b)+bytes);assert(b);b->bytes=bytes;
  ++h->live;h->bytes+=bytes;return b+1;
}
static void release(void *context,void *p) {
  heap *h=context;block *b=(block *)p-1;CHECK(h->live && h->bytes>=b->bytes);
  --h->live;h->bytes-=b->bytes;free(b);
}
static bool start(void *context,lie_json_value *n,void *storage) {
  heap *h=context;memcpy(storage,&n,sizeof(n));++h->views;return true;
}
static void end(void *context,void *storage) {
  heap *h=context;lie_json_value *n=NULL;memcpy(&n,storage,sizeof(n));
  CHECK(n && h->views);--h->views;
}
static lie_json_value *root(heap *h) {
  lie_json_value_description d;lie_json_value_description_init(&d);
  d.allocator=(lie_grammar_allocator){h,allocate,release};d.view_bytes=sizeof(void *);
  d.view_context=h;d.view_initialize=start;d.view_release=end;
  const char text[]="{\"k\\u0000x\":[1,\"a\\u0000b\"]}";lie_json_value *n=NULL;
  CHECK(lie_json_value_parse(text,sizeof(text)-1,&d,NULL,&n,NULL,NULL)==LIE_JSON_VALUE_OK);
  return n;
}
static lie_json_store_description policy(heap *h) {
  lie_json_store_description d;lie_json_store_description_init(&d);
  d.allocator=(lie_grammar_allocator){h,allocate,release};return d;
}
static void empty(const heap *h) { CHECK(!h->live && !h->bytes && !h->views); }
static lie_json_store_info info(const lie_json_store *s) {
  lie_json_store_info i;lie_json_store_describe(s,&i);return i;
}
static void growth_and_handoff(void) {
  heap collection={0},values={0};const lie_json_store_description d=policy(&collection);
  lie_json_store *s=NULL;CHECK(lie_json_store_create(&d,&s)==LIE_JSON_STORE_OK);
  enum { N=1025 };lie_json_value *roots[N],*taken=NULL;
  for (size_t i=0;i<N;++i) {
    roots[i]=root(&values);const size_t before=values.calls;
    CHECK(lie_json_store_adopt(s,roots[i])==LIE_JSON_STORE_OK);
    CHECK(values.calls==before); /* adoption never clones a domain/view */
  }
  const lie_json_value *array=lie_json_value_find(roots[0],"k\0x",3);
  const lie_json_value *text=lie_json_value_at(array,false,1);void *view=lie_json_value_view(text);
  size_t bytes=0;CHECK(lie_json_value_is_root(roots[0]) && !lie_json_value_is_root(text));
  CHECK(!lie_json_value_is_root(NULL));
  CHECK(lie_json_store_adopt(s,roots[0])==LIE_JSON_STORE_INVALID);
  CHECK(lie_json_store_adopt(s,(lie_json_value *)(void *)text)==LIE_JSON_STORE_INVALID);
  CHECK(lie_json_store_take(s,text,&taken)==LIE_JSON_STORE_INVALID && !taken);
  const size_t calls=values.calls;
  CHECK(lie_json_store_take(s,roots[0],&taken)==LIE_JSON_STORE_OK && taken==roots[0]);
  CHECK(values.calls==calls && lie_json_value_view(text)==view);
  CHECK(info(s).live_roots==N-1 && info(s).accepted_roots==N);
  CHECK(info(s).live_owned_bytes==collection.bytes && info(s).peak_owned_bytes>collection.bytes);
  /* Exact output and views survive retirement of every other domain/store. */
  lie_json_store_release(s);empty(&collection);CHECK(values.views==4);
  const char *p=lie_json_value_string(text,&bytes);CHECK(bytes==3 && !memcmp(p,"a\0b",3));
  CHECK(lie_json_value_view(text)==view);lie_json_value_release(taken);empty(&values);
}
static void cycles_and_limits(void) {
  heap collection={0},values={0};lie_json_store_description d=policy(&collection);
  d.max_roots=2048;lie_json_store *s=NULL,*other=NULL;
  CHECK(lie_json_store_create(&d,&s)==LIE_JSON_STORE_OK);
  CHECK(lie_json_store_create(NULL,&other)==LIE_JSON_STORE_OK);
  lie_json_value *n=root(&values),*out=NULL;const size_t value_calls=values.calls;
  CHECK(lie_json_store_take(other,n,&out)==LIE_JSON_STORE_INVALID && !out);
  for (size_t i=0;i<d.max_roots;++i) {
    CHECK(lie_json_store_adopt(s,n)==LIE_JSON_STORE_OK);
    const size_t calls=collection.calls;
    CHECK(lie_json_store_take(s,n,&out)==LIE_JSON_STORE_OK && out==n);
    CHECK(collection.calls==calls && values.calls==value_calls);
    CHECK(lie_json_store_take(s,n,&out)==LIE_JSON_STORE_INVALID && out==n);
  }
  CHECK(collection.calls==2 && info(s).accepted_roots==d.max_roots);
  CHECK(lie_json_store_adopt(s,n)==LIE_JSON_STORE_LIMIT);++refusals;
  CHECK(lie_json_store_adopt(other,n)==LIE_JSON_STORE_OK);
  lie_json_store_release(s);empty(&collection);lie_json_store_release(other);empty(&values);
}
static void allocation_refusals(void) {
  size_t total=0;
  for (size_t fail=0;fail<=total || fail==0;++fail) {
    heap collection={0},values={0};collection.fail=fail;
    const lie_json_store_description d=policy(&collection);
    lie_json_store *s=NULL;lie_json_store_status rc=lie_json_store_create(&d,&s);
    if (rc!=LIE_JSON_STORE_OK) { CHECK(rc==LIE_JSON_STORE_RESOURCE && !s);++refusals;empty(&collection);continue; }
    lie_json_value *kept[129];size_t count=0;
    for (size_t i=0;i<129;++i) {
      lie_json_value *n=root(&values);const size_t views=values.views,calls=values.calls;
      const lie_json_store_info before=info(s);rc=lie_json_store_adopt(s,n);
      CHECK(values.views==views && values.calls==calls);
      if (rc==LIE_JSON_STORE_RESOURCE) {
        CHECK(info(s).live_roots==before.live_roots && info(s).accepted_roots==before.accepted_roots);
        /* Rejection retains caller ownership; all earlier roots still usable. */
        CHECK(lie_json_value_find(n,"k\0x",3));lie_json_value_release(n);++refusals;break;
      }
      CHECK(rc==LIE_JSON_STORE_OK);kept[count++]=n;
    }
    if (!fail) total=collection.calls;
    for (size_t i=0;i<count;++i) {
      lie_json_value *out=NULL;CHECK(lie_json_store_take(s,kept[i],&out)==LIE_JSON_STORE_OK && out==kept[i]);
      lie_json_value_release(out);
    }
    lie_json_store_release(s);empty(&collection);empty(&values);
  }
  CHECK(total>2);
}
static void descriptions_and_byte_limits(void) {
  lie_json_store_description d;lie_json_store_description_init(&d);
  lie_json_store *s=NULL;CHECK(lie_json_store_create(NULL,&s)==LIE_JSON_STORE_OK);
  const size_t context_bytes=info(s).live_owned_bytes;lie_json_store_release(s);
  heap values={0};lie_json_value *n=root(&values),*out=n;
  d.max_owned_bytes=context_bytes;CHECK(lie_json_store_create(&d,&s)==LIE_JSON_STORE_OK);
  CHECK(lie_json_store_adopt(s,n)==LIE_JSON_STORE_LIMIT && info(s).live_roots==0);++refusals;
  CHECK(lie_json_store_take(s,n,&out)==LIE_JSON_STORE_INVALID && out==n);
  lie_json_store_release(s);lie_json_value_release(n);empty(&values);
  lie_json_store *sentinel=(lie_json_store *)(uintptr_t)1;
  d.struct_bytes=0;CHECK(lie_json_store_create(&d,&sentinel)==LIE_JSON_STORE_INVALID);
  CHECK(sentinel==(lie_json_store *)(uintptr_t)1);
  lie_json_store_description_init(&d);d.allocator.allocate=allocate;
  CHECK(lie_json_store_create(&d,&sentinel)==LIE_JSON_STORE_INVALID);
  lie_json_store_description_init(&d);d.max_roots=0;
  CHECK(lie_json_store_create(&d,&sentinel)==LIE_JSON_STORE_INVALID);
  CHECK(lie_json_store_adopt(NULL,NULL)==LIE_JSON_STORE_INVALID);
  lie_json_store_describe(NULL,&(lie_json_store_info){0});lie_json_store_release(NULL);
}
static void growth_overlap_limit(void) {
  heap collection={0},values={0};lie_json_store_description d=policy(&collection);
  lie_json_store *s=NULL;CHECK(lie_json_store_create(&d,&s)==LIE_JSON_STORE_OK);
  const size_t context_bytes=info(s).live_owned_bytes;
  lie_json_value *sample=root(&values);CHECK(lie_json_store_adopt(s,sample)==LIE_JSON_STORE_OK);
  const size_t table_bytes=info(s).live_owned_bytes-context_bytes;
  lie_json_store_release(s);empty(&collection);empty(&values);
  /* The larger table alone fits, but simultaneous old/new tables do not. */
  d.max_owned_bytes=context_bytes+2*table_bytes;
  CHECK(lie_json_store_create(&d,&s)==LIE_JSON_STORE_OK);
  lie_json_value *kept[8];
  for (size_t i=0;i<8;++i) { kept[i]=root(&values);CHECK(lie_json_store_adopt(s,kept[i])==LIE_JSON_STORE_OK); }
  lie_json_value *rejected=root(&values);const size_t calls=collection.calls;
  CHECK(lie_json_store_adopt(s,rejected)==LIE_JSON_STORE_LIMIT);++refusals;
  CHECK(collection.calls==calls && info(s).live_roots==8 && info(s).accepted_roots==8);
  for (size_t i=0;i<8;++i) CHECK(lie_json_value_find(kept[i],"k\0x",3));
  lie_json_value_release(rejected);lie_json_store_release(s);empty(&collection);empty(&values);
}
int main(void) {
  growth_and_handoff();cycles_and_limits();allocation_refusals();descriptions_and_byte_limits();growth_overlap_limit();
  printf("HOST_ONLY json_store checks=%zu refusals=%zu zero_clone_handoff=pass\n",checks,refusals);
  return 0;
}
