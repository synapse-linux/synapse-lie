/* SPDX-License-Identifier: MIT */
/* Independent logical-value and allocation/view-fault ownership checks. */
#include "lie/json_value.h"
#include <assert.h>
#include <math.h>
#include <stdalign.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static size_t checks,allocation_refusals,view_refusals;
#define CHECK(x) do { assert(x);++checks; } while (0)
typedef union { max_align_t alignment;size_t bytes; } block;
typedef struct { size_t calls,fail,live,bytes,views,view_calls,view_fail; } heap;
static void *take(void *p,size_t n) {
  heap *h=p;if (++h->calls==h->fail) return NULL;
  block *b=malloc(sizeof(*b)+n);CHECK(b!=NULL);b->bytes=n;
  ++h->live;h->bytes+=n;return b+1;
}
static void give(void *p,void *bytes) {
  heap *h=p;block *b=(block *)bytes-1;
  CHECK(h->live && h->bytes>=b->bytes);--h->live;h->bytes-=b->bytes;free(b);
}
static bool start_view(void *p,lie_json_value *n,void *view) {
  heap *h=p;if (++h->view_calls==h->view_fail) return false;
  lie_json_value_slot *s=view;lie_json_value_slot_init(s);
  CHECK(lie_json_value_slot_bind(s,n,false)==LIE_JSON_VALUE_OK);
  ++h->views;return true;
}
static void end_view(void *p,void *view) {
  heap *h=p;lie_json_value_slot *s=view;
  CHECK(h->views && !s->owned);--h->views;lie_json_value_slot_release(s);
}
static lie_json_value_description policy(heap *h) {
  lie_json_value_description d;lie_json_value_description_init(&d);
  d.allocator=(lie_grammar_allocator){h,take,give};d.view_bytes=sizeof(lie_json_value_slot);
  d.view_context=h;d.view_initialize=start_view;d.view_release=end_view;return d;
}
typedef struct { char text[8192];size_t count; } output;
static bool write_output(void *p,const char *s,size_t n) {
  output *o=p;CHECK(n<sizeof(o->text)-o->count);
  memcpy(o->text+o->count,s,n);o->count+=n;o->text[o->count]='\0';return true;
}
/* Observe mathematical/lazy values through an independent ordinary tree clone.
 * Its default allocator is separate from the fault-injected allocator. */
static output observe(const lie_json_value_slot *s) {
  lie_json_value_slot copy;lie_json_value_slot_init(&copy);
  CHECK(lie_json_value_slot_copy(s,NULL,&copy)==LIE_JSON_VALUE_OK);
  output o={0};lie_json_value_sink sink={&o,write_output};
  CHECK(lie_json_value_dump(copy.value,&sink)==LIE_JSON_VALUE_OK);
  lie_json_value_slot_release(&copy);return o;
}
static void expect(const lie_json_value_slot *s,const char *text) {
  output o=observe(s);CHECK(strcmp(o.text,text)==0);
}
static void parsed(lie_json_value_slot *s,const char *text,const lie_json_value_description *d) {
  lie_json_value *n=NULL;
  CHECK(lie_json_value_parse(text,strlen(text),d,NULL,&n,NULL,NULL)==LIE_JSON_VALUE_OK);
  CHECK(lie_json_value_slot_bind(s,n,true)==LIE_JSON_VALUE_OK);
}
static void empty_heap(const heap *h) { CHECK(!h->live && !h->bytes && !h->views); }
static void independent_values(void) {
  static const struct { const char *text,*moved; } samples[]={
    {"null","null"},{"true","true"},{"false","false"},{"-0","-0"},
    {"42","42"},{"-13.5","-13.5"},{"\"a\\u0000b\"","\"\""},
    {"[1,{\"k\":\"v\"}]","[]"},{"{\"k\":[1,2],\"b\":true}","{}"}
  };
  for (size_t i=0;i<sizeof(samples)/sizeof(*samples);++i) {
    heap h={0};lie_json_value_description d=policy(&h);
    lie_json_value_slot a,b,c;lie_json_value_slot_init(&a);lie_json_value_slot_init(&b);lie_json_value_slot_init(&c);
    parsed(&a,samples[i].text,&d);lie_json_value *original=a.value;
    CHECK(lie_json_value_slot_copy(&a,&d,&b)==LIE_JSON_VALUE_OK && b.value!=a.value);
    expect(&a,samples[i].text);expect(&b,samples[i].text);
    size_t calls=h.calls;
    CHECK(lie_json_value_slot_move(&a,&d,&c)==LIE_JSON_VALUE_OK);
    CHECK(c.value==original && !a.value && h.calls==calls);
    expect(&a,samples[i].moved);expect(&c,samples[i].text);
    CHECK(lie_json_value_slot_assign(&b,&a,&d)==LIE_JSON_VALUE_OK);expect(&b,samples[i].moved);
    CHECK(lie_json_value_slot_ensure(&a,&d)==LIE_JSON_VALUE_OK);expect(&a,samples[i].moved);
    calls=h.calls;CHECK(lie_json_value_slot_assign(&a,&a,&d)==LIE_JSON_VALUE_OK);
    CHECK(lie_json_value_slot_move_assign(&a,&a,&d)==LIE_JSON_VALUE_OK && h.calls==calls);
    lie_json_value_slot_release(&a);lie_json_value_slot_release(&b);lie_json_value_slot_release(&c);empty_heap(&h);
  }
  lie_json_value_slot a,b;lie_json_value_slot_init(&a);lie_json_value_slot_init(&b);
  CHECK(lie_json_value_slot_type(&a)==LIE_JSON_VALUE_NULL && !a.value);
  CHECK(lie_json_value_slot_boolean(&a,true) && lie_json_value_slot_number(&a,7)==7);
  CHECK(lie_json_value_slot_size_number(&a,91)==91);
  CHECK(lie_json_value_slot_set(&a,NULL,LIE_JSON_VALUE_NUMBER,false,-0.0,NULL,0)==LIE_JSON_VALUE_OK);
  CHECK(lie_json_value_slot_move(&a,NULL,&b)==LIE_JSON_VALUE_OK);
  CHECK(signbit(lie_json_value_slot_number(&a,0)) && lie_json_value_slot_size_number(&a,9)==0);
  lie_json_value_slot_release(&b);
  static const double numbers[]={0,1,1.5,-1,9007199254740992.0};
  for (size_t i=0;i<sizeof(numbers)/sizeof(*numbers);++i) {
    CHECK(lie_json_value_slot_set(&a,NULL,LIE_JSON_VALUE_NUMBER,false,numbers[i],NULL,0)==LIE_JSON_VALUE_OK);
    CHECK(lie_json_value_slot_move(&a,NULL,&b)==LIE_JSON_VALUE_OK);
    CHECK(lie_json_value_slot_number(&a,0)==numbers[i]);
    size_t expected=numbers[i]==1.5 || numbers[i]<0 || numbers[i]>=ldexp(1.0,sizeof(size_t)*8) ? 99 : (size_t)numbers[i];
    CHECK(lie_json_value_slot_size_number(&a,99)==expected);lie_json_value_slot_release(&b);
  }
  output preserved=observe(&a);
  CHECK(lie_json_value_slot_set(&a,NULL,(lie_json_value_kind)-1,false,0,NULL,0)==LIE_JSON_VALUE_INVALID);
  CHECK(lie_json_value_slot_number(&a,0)==9007199254740992.0);
  expect(&a,preserved.text);lie_json_value_slot_release(&a);
  const double nonfinite[]={INFINITY,-INFINITY,NAN};
  for (size_t i=0;i<sizeof(nonfinite)/sizeof(*nonfinite);++i) {
    CHECK(lie_json_value_slot_set(&a,NULL,LIE_JSON_VALUE_NUMBER,false,nonfinite[i],NULL,0)==LIE_JSON_VALUE_OK);
    CHECK(lie_json_value_slot_move(&a,NULL,&b)==LIE_JSON_VALUE_OK);
    double value=lie_json_value_slot_number(&a,0);
    CHECK(i==2 ? isnan(value) : isinf(value) && !!signbit(value)==!!signbit(nonfinite[i]));
    CHECK(lie_json_value_slot_size_number(&a,17)==17);
    output o={0};lie_json_value_sink sink={&o,write_output};
    CHECK(lie_json_value_dump(b.value,&sink)==LIE_JSON_VALUE_NONFINITE);
    CHECK(lie_json_value_slot_ensure(&a,NULL)==LIE_JSON_VALUE_OK);
    CHECK(lie_json_value_dump(a.value,&sink)==LIE_JSON_VALUE_NONFINITE);
    lie_json_value_slot_release(&a);lie_json_value_slot_release(&b);
  }
}
static void borrowed_values(void) {
  heap h={0};lie_json_value_description d=policy(&h);
  lie_json_value_slot bank,a,b,c;lie_json_value_slot_init(&bank);lie_json_value_slot_init(&a);
  lie_json_value_slot_init(&b);lie_json_value_slot_init(&c);
  parsed(&bank,"{\"source\":{\"items\":[1,2]},\"target\":\"old\"}",&d);
  lie_json_value *source=NULL,*target=NULL;
  CHECK(lie_json_value_member(bank.value,"source",6,&source)==LIE_JSON_VALUE_OK);
  CHECK(lie_json_value_member(bank.value,"target",6,&target)==LIE_JSON_VALUE_OK);
  CHECK(lie_json_value_slot_bind(&a,source,false)==LIE_JSON_VALUE_OK);
  CHECK(lie_json_value_slot_bind(&b,target,false)==LIE_JSON_VALUE_OK);
  CHECK(lie_json_value_slot_move(&a,&d,&c)==LIE_JSON_VALUE_OK);
  CHECK(a.value==source && lie_json_value_slot_type(&a)==LIE_JSON_VALUE_OBJECT);
  expect(&a,"{}");expect(&c,"{\"items\":[1,2]}");
  CHECK(lie_json_value_slot_move_assign(&b,&c,&d)==LIE_JSON_VALUE_OK);
  CHECK(b.value==target && c.value!=NULL);expect(&b,"{\"items\":[1,2]}");expect(&c,"{}");
  CHECK(lie_json_value_slot_assign(&a,&b,&d)==LIE_JSON_VALUE_OK);expect(&a,"{\"items\":[1,2]}");
  CHECK(lie_json_value_slot_move_assign(&a,&b,&d)==LIE_JSON_VALUE_OK);
  expect(&a,"{\"items\":[1,2]}");expect(&b,"{}");
  CHECK(lie_json_value_slot_move_assign(&c,&a,&d)==LIE_JSON_VALUE_OK);
  expect(&c,"{\"items\":[1,2]}");expect(&a,"{}");
  lie_json_value *out=(lie_json_value *)(void *)&h;
  CHECK(lie_json_value_slot_disown(&a,&out)==LIE_JSON_VALUE_INVALID && out==(lie_json_value *)(void *)&h);
  CHECK(lie_json_value_slot_disown(&c,&c.value)==LIE_JSON_VALUE_INVALID);
  CHECK(lie_json_value_slot_disown(&c,&out)==LIE_JSON_VALUE_OK && !c.value);expect(&c,"{}");
  lie_json_value_release(out);
  CHECK(lie_json_value_slot_bind(&c,source,true)==LIE_JSON_VALUE_INVALID);
  CHECK(lie_json_value_slot_bind(&c,NULL,false)==LIE_JSON_VALUE_INVALID);
  CHECK(lie_json_value_slot_copy(&c,&d,&c)==LIE_JSON_VALUE_INVALID);
  CHECK(lie_json_value_slot_move(&c,&d,&c)==LIE_JSON_VALUE_INVALID);
  CHECK(lie_json_value_slot_move_assign(&a,&bank,&d)==LIE_JSON_VALUE_INVALID);
  expect(&a,"{}");expect(&bank,"{\"source\":{},\"target\":{}}");
  lie_json_value_slot_release(&c);
  CHECK(lie_json_value_slot_bind(&c,bank.value,false)==LIE_JSON_VALUE_OK);
  CHECK(lie_json_value_slot_move_assign(&c,&bank,&d)==LIE_JSON_VALUE_OK);
  expect(&bank,"{\"source\":{},\"target\":{}}");
  lie_json_value_slot_release(&a);lie_json_value_slot_release(&b);lie_json_value_slot_release(&c);
  lie_json_value_slot_release(&bank);empty_heap(&h);
}
typedef struct { size_t allocations,views; } counts;
static counts fault_operation(unsigned op,size_t fail,size_t view_fail) {
  heap h={0};lie_json_value_description d=policy(&h);
  lie_json_value_slot bank,source,target,a,b;
  lie_json_value_slot_init(&bank);lie_json_value_slot_init(&source);lie_json_value_slot_init(&target);
  lie_json_value_slot_init(&a);lie_json_value_slot_init(&b);
  parsed(&bank,"{\"source\":{\"items\":[1,2,3],\"text\":\"source bytes\"},\"target\":\"kept\"}",&d);
  parsed(&source,"{\"object\":{\"a\":1},\"array\":[2,3],\"text\":\"payload\"}",&d);
  lie_json_value *node=NULL;
  CHECK(lie_json_value_member(bank.value,"source",6,&node)==LIE_JSON_VALUE_OK);
  CHECK(lie_json_value_slot_bind(&a,node,false)==LIE_JSON_VALUE_OK);
  CHECK(lie_json_value_member(bank.value,"target",6,&node)==LIE_JSON_VALUE_OK);
  CHECK(lie_json_value_slot_bind(&b,node,false)==LIE_JSON_VALUE_OK);
  if (op==2) parsed(&target,"{\"keep\":17}",&d);
  if (op==6) {
    lie_json_value_slot_release(&source);
    CHECK(lie_json_value_slot_set(&source,&d,LIE_JSON_VALUE_NUMBER,false,9,NULL,0)==LIE_JSON_VALUE_OK);
    CHECK(lie_json_value_slot_move(&source,&d,&target)==LIE_JSON_VALUE_OK);
    lie_json_value_slot_release(&target);CHECK(!source.value);
  }
  lie_json_value_slot *from=op==4 || op==5 ? &a : &source;
  lie_json_value_slot *to=op==3 || op==5 || op==6 ? &b : &target;
  output before_from=observe(from),before_to=observe(to);
  size_t calls=h.calls,views=h.view_calls;
  h.fail=fail ? calls+fail : 0;h.view_fail=view_fail ? views+view_fail : 0;
  lie_json_value_status rc;
  switch (op) {
  case 0:rc=lie_json_value_slot_ensure(to,&d);break;
  case 1:rc=lie_json_value_slot_set(to,&d,LIE_JSON_VALUE_STRING,false,0,"new bytes",9);break;
  case 2:rc=lie_json_value_slot_assign(to,from,&d);break;
  case 3:rc=lie_json_value_slot_assign(to,from,&d);break;
  case 4:rc=lie_json_value_slot_move(from,&d,to);break;
  case 5:rc=lie_json_value_slot_move_assign(to,from,&d);break;
  case 6:rc=lie_json_value_slot_move_assign(to,from,&d);break;
  default:rc=lie_json_value_slot_copy(from,&d,to);break;
  }
  counts result={h.calls-calls,h.view_calls-views};
  if (fail || view_fail) {
    CHECK(rc==(fail ? LIE_JSON_VALUE_RESOURCE : LIE_JSON_VALUE_CALLBACK));
    expect(from,before_from.text);expect(to,before_to.text);
    if (fail) ++allocation_refusals;else ++view_refusals;
  } else CHECK(rc==LIE_JSON_VALUE_OK);
  lie_json_value_slot_release(&a);lie_json_value_slot_release(&b);lie_json_value_slot_release(&target);
  lie_json_value_slot_release(&source);lie_json_value_slot_release(&bank);empty_heap(&h);
  return result;
}
static void refusals(void) {
  for (unsigned op=0;op<8;++op) {
    counts c=fault_operation(op,0,0);
    for (size_t i=1;i<=c.allocations;++i) (void)fault_operation(op,i,0);
    for (size_t i=1;i<=c.views;++i) (void)fault_operation(op,0,i);
  }
  lie_json_value_slot a,b;lie_json_value_slot_init(&a);lie_json_value_slot_init(&b);
  lie_json_value_description d;lie_json_value_description_init(&d);d.abi_version=0;
  CHECK(lie_json_value_slot_ensure(&a,&d)==LIE_JSON_VALUE_INVALID && !a.value);
  CHECK(lie_json_value_slot_move(NULL,NULL,&a)==LIE_JSON_VALUE_INVALID);
  CHECK(lie_json_value_slot_copy(&a,NULL,NULL)==LIE_JSON_VALUE_INVALID);
  CHECK(lie_json_value_slot_assign(NULL,&a,NULL)==LIE_JSON_VALUE_INVALID);
  CHECK(lie_json_value_slot_type(NULL)==LIE_JSON_VALUE_NULL);
  CHECK(lie_json_value_slot_number(NULL,8)==8 && lie_json_value_slot_size_number(NULL,7)==7);
  CHECK(lie_json_value_slot_boolean(NULL,true));
  parsed(&a,"[1,2]",NULL);d.abi_version=LIE_JSON_VALUE_ABI;d.max_nodes=1;
  CHECK(lie_json_value_slot_copy(&a,&d,&b)==LIE_JSON_VALUE_LIMIT && !b.value);expect(&a,"[1,2]");
  CHECK(lie_json_value_slot_move(&a,&d,&b)==LIE_JSON_VALUE_OK);expect(&a,"[]");expect(&b,"[1,2]");
  lie_json_value_slot_release(&a);lie_json_value_slot_release(&b);
}
int main(void) {
  independent_values();borrowed_values();refusals();
  printf("JSON slot: %zu checks; %zu allocation and %zu view refusals; live allocations=0; HOST NOT-INFERENCE\n",
         checks,allocation_refusals,view_refusals);return 0;
}
