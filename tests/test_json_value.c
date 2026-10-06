/* SPDX-License-Identifier: MIT */
#include "lie/json_value.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static size_t checks,allocator_refusals,view_refusals,writer_refusals;
#define CHECK(x) do { assert(x);++checks; } while (0)
typedef struct {
  void *pointers[8192];size_t bytes[8192],live,live_bytes,calls,fail;
  size_t view_calls,view_fail,view_live;
} heap;
static void *take(void *context,size_t bytes) {
  heap *h=context;if (++h->calls==h->fail) return NULL;
  void *p=malloc(bytes);assert(p && h->live<8192);
  h->pointers[h->live]=p;h->bytes[h->live++]=bytes;h->live_bytes+=bytes;return p;
}
static void give(void *context,void *p) {
  heap *h=context;size_t i=0;while (i<h->live && h->pointers[i]!=p) ++i;
  CHECK(i<h->live);h->live_bytes-=h->bytes[i];--h->live;
  h->pointers[i]=h->pointers[h->live];h->bytes[i]=h->bytes[h->live];free(p);
}
static bool start_view(void *context,lie_json_value *node,void *storage) {
  heap *h=context;if (++h->view_calls==h->view_fail) return false;
  memcpy(storage,&node,sizeof(node));++h->view_live;return true;
}
static void end_view(void *context,void *storage) {
  heap *h=context;lie_json_value *n=NULL;memcpy(&n,storage,sizeof(n));
  CHECK(n!=NULL && h->view_live>0);--h->view_live;
}
static lie_json_value_description policy(heap *h) {
  lie_json_value_description d;lie_json_value_description_init(&d);
  d.allocator=(lie_grammar_allocator){h,take,give};d.view_bytes=sizeof(void *);
  d.view_context=h;d.view_initialize=start_view;d.view_release=end_view;return d;
}
typedef struct { char bytes[32768];size_t count,calls,fail; } output;
static bool write_output(void *context,const char *text,size_t bytes) {
  output *o=context;if (++o->calls==o->fail) return false;
  CHECK(bytes<sizeof(o->bytes)-o->count);memcpy(o->bytes+o->count,text,bytes);
  o->count+=bytes;o->bytes[o->count]='\0';return true;
}
static output dump(const lie_json_value *v) {
  output o={0};lie_json_value_sink s={&o,write_output};
  CHECK(lie_json_value_dump(v,&s)==LIE_JSON_VALUE_OK);return o;
}
static void expect(const lie_json_value *v,const char *text) {
  const output o=dump(v);CHECK(!strcmp(o.bytes,text));
}
static lie_json_value *parse(const char *text,const lie_json_value_description *d) {
  lie_json_value *v=NULL;CHECK(lie_json_value_parse(text,strlen(text),d,NULL,&v,NULL,NULL)==LIE_JSON_VALUE_OK);return v;
}
static void empty_heap(const heap *h) { CHECK(!h->live && !h->live_bytes && !h->view_live); }
static const char fixture[]="{\"k\\u0000x\":\"a\\u0000b\",\"rows\":[null,true,false,-0,1.25,{\"e\":\"\\b\\f\\n\\r\\t\\u0001\\\"\\\\\"}],\"unicode\":\"\\ud83d\\ude00\"}";
static void values(void) {
  heap h={0};
  lie_json_value_description d=policy(&h);lie_json_value *v=parse(fixture,&d);
  size_t count=0;const lie_json_value *s=lie_json_value_find(v,"k\0x",3);
  CHECK(s && !lie_json_value_find(v,"k",1));
  const char *bytes=lie_json_value_string(s,&count);CHECK(count==3 && !memcmp(bytes,"a\0b",3));
  CHECK(lie_json_value_type(v)==LIE_JSON_VALUE_OBJECT && lie_json_value_size(v)==3);
  const lie_json_value *rows=lie_json_value_find(v,"rows",4);
  CHECK(lie_json_value_array_size(rows)==6 && !lie_json_value_at(rows,false,6));
  CHECK(signbit(lie_json_value_number(lie_json_value_at(rows,false,3),1)));
  CHECK(lie_json_value_boolean(lie_json_value_at(rows,false,1),false));
  CHECK(lie_json_value_boolean(s,true) && lie_json_value_number(s,71)==71);
  const output canonical=dump(v);
  lie_json_value_info info;lie_json_value_describe(v,&info);
  CHECK(info.live_owned_bytes==h.live_bytes && info.live_nodes==h.view_live);
  CHECK(info.peak_owned_bytes>=info.live_owned_bytes);
  lie_json_value *copy=NULL;CHECK(lie_json_value_clone(v,&d,&copy)==LIE_JSON_VALUE_OK);
  expect(copy,canonical.bytes);
  lie_json_value *member=NULL;CHECK(lie_json_value_member(copy,"new",3,&member)==LIE_JSON_VALUE_OK);
  const lie_json_value *identity=member;
  CHECK(lie_json_value_assign(member,rows)==LIE_JSON_VALUE_OK && member==identity);
  CHECK(lie_json_value_array_size(member)==6);
  CHECK(lie_json_value_find(v,"new",3)==NULL);
  for (unsigned i=0;i<65;++i) {
    char key[32];const int n=snprintf(key,sizeof(key),"growth-%u",i);lie_json_value *added=NULL;
    CHECK(lie_json_value_member(copy,key,(size_t)n,&added)==LIE_JSON_VALUE_OK);
  }
  CHECK(lie_json_value_find(copy,"new",3)==identity);
  CHECK(lie_json_value_append_member(copy,"new",3,NULL,NULL)==LIE_JSON_VALUE_OK);
  CHECK(lie_json_value_find(copy,"new",3)==identity);
  CHECK(lie_json_value_assign(member,copy)==LIE_JSON_VALUE_OK); /* ancestor copy stages first */
  CHECK(lie_json_value_type(member)==LIE_JSON_VALUE_OBJECT);
  CHECK(lie_json_value_move_assign(member,copy)==LIE_JSON_VALUE_INVALID);
  lie_json_value *moved=NULL;CHECK(lie_json_value_move_clone(copy,&d,&moved)==LIE_JSON_VALUE_OK);
  CHECK(lie_json_value_type(copy)==LIE_JSON_VALUE_OBJECT && lie_json_value_size(copy)==0);
  CHECK(lie_json_value_size(moved)==70);
  lie_json_value_release(moved);lie_json_value_release(copy);lie_json_value_release(v);empty_heap(&h);
}
static void coercion_numbers(void) {
  lie_json_value *v=parse("[1]",NULL),*member=NULL;
  CHECK(lie_json_value_member(v,"x",1,&member)==LIE_JSON_VALUE_OK);
  CHECK(lie_json_value_array_size(v)==1 && lie_json_value_object_size(v)==1);expect(v,"{\"x\":null}");
  CHECK(lie_json_value_append(v,NULL,NULL)==LIE_JSON_VALUE_OK);
  CHECK(lie_json_value_array_size(v)==1 && lie_json_value_object_size(v)==1);expect(v,"[null]");
  CHECK(lie_json_value_member(v,"y",1,&member)==LIE_JSON_VALUE_OK);expect(v,"{\"y\":null}");
  CHECK(lie_json_value_set(member,LIE_JSON_VALUE_NUMBER,false,42,NULL,0)==LIE_JSON_VALUE_OK);
  CHECK(lie_json_value_size_number(member,7)==42);
  const double invalid[]={-1,0.5,NAN,INFINITY,ldexp(1.0,sizeof(size_t)*8)};
  for (size_t i=0;i<sizeof(invalid)/sizeof(*invalid);++i) {
    CHECK(lie_json_value_set(member,LIE_JSON_VALUE_NUMBER,false,invalid[i],NULL,0)==LIE_JSON_VALUE_OK);
    CHECK(lie_json_value_size_number(member,7)==7);
  }
  CHECK(lie_json_value_set(member,LIE_JSON_VALUE_NUMBER,false,INFINITY,NULL,0)==LIE_JSON_VALUE_OK);
  output o={0};lie_json_value_sink sink={&o,write_output};
  CHECK(lie_json_value_dump(v,&sink)==LIE_JSON_VALUE_NONFINITE);
  CHECK(lie_json_value_set(member,LIE_JSON_VALUE_STRING,false,0,"alias",5)==LIE_JSON_VALUE_OK);
  size_t n=0;const char *text=lie_json_value_string(member,&n);
  CHECK(lie_json_value_set(member,LIE_JSON_VALUE_STRING,false,0,text+1,n-1)==LIE_JSON_VALUE_OK);
  expect(v,"{\"y\":\"lias\"}");lie_json_value_release(v);
}
static void refusals(void) {
  heap h={0};lie_json_value_description d=policy(&h);lie_json_value *v=parse(fixture,&d);
  const size_t allocation_count=h.calls,view_count=h.view_calls;const output serialized=dump(v);
  lie_json_value_release(v);empty_heap(&h);
  for (size_t i=1;i<=allocation_count;++i) {
    heap f={0};f.fail=i;d=policy(&f);lie_json_value *sentinel=(lie_json_value *)(uintptr_t)1;
    CHECK(lie_json_value_parse(fixture,strlen(fixture),&d,NULL,&sentinel,NULL,NULL)==LIE_JSON_VALUE_RESOURCE);
    CHECK(sentinel==(lie_json_value *)(uintptr_t)1);empty_heap(&f);++allocator_refusals;
  }
  for (size_t i=1;i<=view_count;++i) {
    heap f={0};f.view_fail=i;d=policy(&f);lie_json_value *sentinel=(lie_json_value *)(uintptr_t)1;
    CHECK(lie_json_value_parse(fixture,strlen(fixture),&d,NULL,&sentinel,NULL,NULL)==LIE_JSON_VALUE_CALLBACK);
    CHECK(sentinel==(lie_json_value *)(uintptr_t)1);empty_heap(&f);++view_refusals;
  }
  for (size_t i=1;i<=serialized.calls;++i) {
    v=parse(fixture,NULL);output o={0};o.fail=i;lie_json_value_sink sink={&o,write_output};
    CHECK(lie_json_value_dump(v,&sink)==LIE_JSON_VALUE_CALLBACK);lie_json_value_release(v);++writer_refusals;
  }
  const char *invalid[]={"{\"a\":0,\"a\":1}","[0,]","\"\\ud800\"","\"\xc0\x80\"","1e999","{} trailing"};
  for (size_t i=0;i<sizeof(invalid)/sizeof(*invalid);++i) {
    heap f={0};d=policy(&f);lie_json_value *sentinel=(lie_json_value *)(uintptr_t)1;lie_json_parse_error error={0};
    CHECK(lie_json_value_parse(invalid[i],strlen(invalid[i]),&d,NULL,&sentinel,&error,NULL)==LIE_JSON_VALUE_SYNTAX);
    CHECK(error.message && sentinel==(lie_json_value *)(uintptr_t)1);empty_heap(&f);
  }
  /* Every copy/assign/append allocation refusal preserves both input trees. */
  for (unsigned operation=0;operation<4;++operation) {
    size_t calls=0;
    for (size_t failure=0;failure<=calls || failure==0;++failure) {
      heap f={0};d=policy(&f);lie_json_value *a=parse("{\"held\":7}",&d),*b=parse(fixture,&d),*out=NULL;
      const size_t before=f.calls;f.fail=failure ? before+failure : 0;
      lie_json_value_status rc;
      if (operation==0) rc=lie_json_value_clone(b,&d,&out);
      else if (operation==1) rc=lie_json_value_assign(a,b);
      else if (operation==2) rc=lie_json_value_append_member(a,"added",5,b,&out);
      else rc=lie_json_value_move_assign(a,b);
      if (!failure) { CHECK(rc==LIE_JSON_VALUE_OK);calls=f.calls-before; }
      else {
        CHECK(rc==LIE_JSON_VALUE_RESOURCE && out==NULL);expect(a,"{\"held\":7}");expect(b,serialized.bytes);++allocator_refusals;
      }
      if (operation==0 && out) lie_json_value_release(out);
      lie_json_value_release(a);lie_json_value_release(b);empty_heap(&f);
    }
  }
}
static void limits(void) {
  lie_json_value_description d;lie_json_value_description_init(&d);d.max_nodes=2;
  lie_json_value *v=parse("[null]",&d);CHECK(lie_json_value_append(v,NULL,NULL)==LIE_JSON_VALUE_LIMIT);expect(v,"[null]");lie_json_value_release(v);
  lie_json_value_description_init(&d);d.max_depth=2;v=parse("[[]]",&d);
  lie_json_value *child=(lie_json_value *)(void *)lie_json_value_at(v,false,0);
  CHECK(lie_json_value_append(child,NULL,NULL)==LIE_JSON_VALUE_LIMIT);expect(v,"[[]]");lie_json_value_release(v);
  lie_json_value_description_init(&d);d.max_work=1;v=parse("0",&d);output o={0};lie_json_value_sink sink={&o,write_output};
  CHECK(lie_json_value_set(v,LIE_JSON_VALUE_STRING,false,0,"xy",2)==LIE_JSON_VALUE_LIMIT);expect(v,"0");
  CHECK(lie_json_value_set(v,LIE_JSON_VALUE_NUMBER,false,100,NULL,0)==LIE_JSON_VALUE_OK);
  CHECK(lie_json_value_dump(v,&sink)==LIE_JSON_VALUE_LIMIT);lie_json_value_release(v);
  lie_json_value_description_init(&d);d.struct_bytes=0;v=(lie_json_value *)(uintptr_t)1;
  CHECK(lie_json_value_create(&d,&v)==LIE_JSON_VALUE_INVALID && v==(lie_json_value *)(uintptr_t)1);
  v=parse("null",NULL);CHECK(lie_json_value_set(v,(lie_json_value_kind)-1,false,0,NULL,0)==LIE_JSON_VALUE_INVALID);
  expect(v,"null");lie_json_value_release(v);
  /* Construct the full public depth bound without parser recursion. */
  lie_json_value_description_init(&d);CHECK(lie_json_value_create(&d,&v)==LIE_JSON_VALUE_OK);
  child=v;
  for (unsigned i=1;i<d.max_depth;++i) {
    CHECK(lie_json_value_set(child,LIE_JSON_VALUE_ARRAY,false,0,NULL,0)==LIE_JSON_VALUE_OK);
    lie_json_value *next=NULL;CHECK(lie_json_value_append(child,NULL,&next)==LIE_JSON_VALUE_OK);child=next;
  }
  CHECK(lie_json_value_append(child,NULL,NULL)==LIE_JSON_VALUE_LIMIT);
  lie_json_value *copy=NULL;CHECK(lie_json_value_clone(v,&d,&copy)==LIE_JSON_VALUE_OK);
  const output deep=dump(v),same=dump(copy);CHECK(!strcmp(deep.bytes,same.bytes));
  lie_json_value_release(copy);lie_json_value_release(v);
}
int main(void) {
  values();coercion_numbers();refusals();limits();
  printf("C17 JSON VALUES checks=%zu allocator_refusals=%zu view_refusals=%zu writer_refusals=%zu HOST_NOT_INFERENCE\n",
         checks,allocator_refusals,view_refusals,writer_refusals);return 0;
}
