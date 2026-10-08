/* SPDX-License-Identifier: MIT */
/* Independent finite-language and Unicode encoding oracles, HOST NOT-INFERENCE. */
#include "lie/grammar_string.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static lie_regex_program *program(lie_regex_description *d) {
  lie_regex_program *p=NULL; assert(lie_regex_create(d,&p)==LIE_REGEX_OK); return p;
}
static bool oracle(const uint32_t *next, unsigned accepting, unsigned active, unsigned min, unsigned max) {
  for (unsigned n=0;n<=max;++n) {
    if (n>=min && (active&accepting)) return true;
    unsigned expanded=0;
    for (unsigned s=0;s<3;++s) if (active&(1u<<s))
      for (unsigned c=0;c<2;++c) expanded|=1u<<next[s*2+c];
    active=expanded;
  }
  return false;
}
typedef struct { size_t calls,fail,alive,bytes,peak; } allocator;
static void *allocate(void *context,size_t bytes) {
  allocator *a=context; if (++a->calls==a->fail) return NULL;
  size_t *p=malloc(sizeof(size_t)+bytes); if (!p) return NULL;
  *p=bytes; ++a->alive; a->bytes+=bytes; if (a->bytes>a->peak) a->peak=a->bytes; return p+1;
}
static void release(void *context,void *ptr) {
  allocator *a=context; size_t *p=(size_t *)ptr-1;
  assert(a->alive && a->bytes>=*p); --a->alive; a->bytes-=*p; free(p);
}
static size_t literal(uint32_t cp,uint8_t *s) {
  if (cp<32) return (size_t)sprintf((char *)s,"\"\\u%04x\"",cp);
  size_t n=0; s[n++]='"';
  if (cp=='"'||cp=='\\') { s[n++]='\\';s[n++]=(uint8_t)cp; }
  else if (cp<0x80) s[n++]=(uint8_t)cp;
  else if (cp<0x800) { s[n++]=(uint8_t)(0xc0|(cp>>6));s[n++]=(uint8_t)(0x80|(cp&63)); }
  else if (cp<0x10000) { s[n++]=(uint8_t)(0xe0|(cp>>12));s[n++]=(uint8_t)(0x80|((cp>>6)&63));s[n++]=(uint8_t)(0x80|(cp&63)); }
  else { s[n++]=(uint8_t)(0xf0|(cp>>18));s[n++]=(uint8_t)(0x80|((cp>>12)&63));s[n++]=(uint8_t)(0x80|((cp>>6)&63));s[n++]=(uint8_t)(0x80|(cp&63)); }
  s[n++]='"'; return n;
}
int main(void) {
  size_t graphs=0,queries=0,scalars=0;
  lie_grammar_range classes[]={{0,1},{1,1}};
  lie_unicode_range ranges[]={{'a','a'},{'b','b'}};
  uint8_t accepting[3]; uint32_t next[6];
  lie_regex_description d; lie_regex_description_init(&d);
  d.classes=classes;d.class_count=2;d.ranges=ranges;d.range_count=2;
  d.accepting=accepting;d.state_count=3;d.transitions=next;
  /* All 729 binary-labelled three-state automata, all 8 accepting sets. */
  for (unsigned code=0;code<729;++code) {
    unsigned digits=code;
    for (unsigned i=0;i<6;++i) { next[i]=digits%3;digits/=3; }
    for (unsigned mask=0;mask<8;++mask) {
      for (unsigned i=0;i<3;++i) accepting[i]=(uint8_t)((mask>>i)&1);
      lie_regex_program *p=program(&d);++graphs;
      for (unsigned s=0;s<3;++s) {
        bool result;assert(lie_regex_accepting(p,s,&result)==LIE_REGEX_OK && result==!!accepting[s]);
        for (unsigned min=0;min<=6;++min) for (unsigned max=min;max<=6;++max) {
          assert(lie_regex_can_finish(p,s,min,max,&result)==LIE_REGEX_OK);
          assert(result==oracle(next,mask,1u<<s,min,max));++queries;
        }
        assert(lie_regex_can_advance(p,s,'a','b',2,3,&result)==LIE_REGEX_OK);
        assert(result==(oracle(next,mask,1u<<next[s*2],2,3)||oracle(next,mask,1u<<next[s*2+1],2,3)));++queries;
        for (unsigned c=0;c<2;++c) {
          uint32_t target=next[s*2+c],out;
          assert(lie_regex_advance(p,s,'a'+c,&out)==LIE_REGEX_OK);
          assert(out==(oracle(next,mask,1u<<target,0,3)?target:LIE_REGEX_DEAD));
        }
      }
      lie_regex_release(p);
    }
  }
  lie_grammar_range any_class={0,2};lie_unicode_range any_ranges[]={{0,0xd7ff},{0xe000,0x10ffff}};
  uint8_t yes=1;uint32_t loop=0;
  lie_regex_description_init(&d);d.classes=&any_class;d.class_count=1;d.ranges=any_ranges;d.range_count=2;
  d.accepting=&yes;d.state_count=1;d.transitions=&loop;lie_regex_program *any=program(&d);
  for (bool scalar=false;;scalar=true) {
    lie_string_policy p;lie_string_policy_init(&p);p.minimum=1;p.maximum=1;p.scalar_only=scalar;p.regex=any;
    assert(lie_string_policy_validate(&p)==LIE_STRING_OK);
    for (uint32_t cp=0;cp<=0x10ffff;++cp) {
      if (cp>=0xd800&&cp<=0xdfff) continue;
      uint8_t s[32];size_t n=literal(cp,s);lie_string_match m;
      assert(lie_string_check(&p,s,n,&m)==LIE_STRING_OK && m.complete && !m.prefix);
      if (cp<=0xffff) n=(size_t)sprintf((char *)s,"\"\\u%04x\"",cp);
      else n=(size_t)sprintf((char *)s,"\"\\u%04x\\u%04x\"",0xd800+((cp-0x10000)>>10),0xdc00+((cp-0x10000)&1023));
      assert(lie_string_check(&p,s,n,&m)==LIE_STRING_OK && m.complete && !m.prefix);++scalars;
    }
    const char *invalid[]={"\"\\uDC00\"","\"\\uD800\"","\"\\uD800\\uDBFF\"","\"\\x\"","\"aa\"","\"\xc0\x80\"","\"\xed\xa0\x80\"","\"\xf4\x90\x80\x80\""};
    for (size_t i=0;i<sizeof(invalid)/sizeof(*invalid);++i) {
      lie_string_match m;assert(lie_string_check(&p,(const uint8_t *)invalid[i],strlen(invalid[i]),&m)==LIE_STRING_OK && !m.complete && !m.prefix);
    }
    if (scalar) break;
  }
  lie_string_policy p;lie_string_policy_init(&p);p.regex=any;p.minimum=1;p.maximum=8;
  uint8_t state[20]={0},copy[20];size_t bytes=0;lie_string_match match;
  for (const char *s="\"aaa";*s;++s) assert(lie_string_advance(&p,state,&bytes,sizeof(state),(uint8_t)*s,&match)==LIE_STRING_OK && match.prefix);
  memcpy(copy,state,20);assert(lie_string_canonical(&p,copy,20,2)==LIE_STRING_OK);
  uint32_t fields[5];memcpy(fields,copy,20);assert(fields[1]==1);memcpy(fields,state,20);assert(fields[1]==3);
  lie_string_policy constrained=p;constrained.maximum=3;
  assert(lie_string_advance(&constrained,state,&bytes,20,'b',&match)==LIE_STRING_OK && !match.prefix && !match.complete);
  uint8_t original[20];memcpy(original,state,20);match=(lie_string_match){true,true};
  assert(lie_string_advance(&p,state,&bytes,19,'x',&match)==LIE_STRING_RESOURCE && match.complete && !memcmp(state,original,20));
  fields[4]=99;memcpy(copy,fields,20);match=(lie_string_match){true,true};size_t bad_length=20;
  assert(lie_string_advance(&p,copy,&bad_length,20,'x',&match)==LIE_STRING_PHASE && match.complete);
  fields[4]=2;fields[3]=255;memcpy(copy,fields,20);
  assert(lie_string_canonical(&p,copy,20,1)==LIE_STRING_STATE);
  assert(lie_string_canonical(&p,copy,19,1)==LIE_STRING_STATE);
  for (unsigned n=0;n<33;++n) { uint8_t count=(uint8_t)n;lie_string_match m=lie_string_whitespace(&count,' ');assert(m.complete==(n<32) && m.prefix==(n<31) && count==(n<32?n+1:n)); }
  uint8_t ws=0;assert(!lie_string_whitespace(&ws,'x').complete && !ws);
  lie_regex_release(any);
  /* Owned table copies, all constructor allocation failures, query refusal. */
  uint8_t accept_cycle[]={1,0,0};uint32_t cycle[]={1,2,0};
  any_class=(lie_grammar_range){0,1};any_ranges[0]=(lie_unicode_range){0,0xd7ff};
  lie_regex_description_init(&d);d.classes=&any_class;d.class_count=1;d.ranges=any_ranges;d.range_count=1;d.accepting=accept_cycle;d.state_count=3;d.transitions=cycle;
  for (size_t fail=1;fail<=3;++fail) {
    allocator a={.fail=fail};d.allocator=(lie_grammar_allocator){&a,allocate,release};
    lie_regex_program *out=(lie_regex_program *)(uintptr_t)1;
    assert(lie_regex_create(&d,&out)==LIE_REGEX_RESOURCE && out==(lie_regex_program *)(uintptr_t)1 && !a.alive && !a.bytes);
  }
  allocator a={0};d.allocator=(lie_grammar_allocator){&a,allocate,release};lie_regex_program *owned=program(&d);
  assert(a.alive==2 && lie_regex_maximum_suffix(owned)==2);
  cycle[0]=LIE_REGEX_DEAD;accept_cycle[0]=0;bool finish;
  assert(lie_regex_can_finish(owned,0,1000000,1000002,&finish)==LIE_REGEX_OK && finish);
  a.fail=a.calls+1;finish=true;
  assert(lie_regex_can_finish(owned,0,100,100,&finish)==LIE_REGEX_RESOURCE && finish && a.alive==2);
  a.fail=0;lie_string_policy_init(&p);p.regex=owned;p.minimum=100;p.maximum=200;
  assert(lie_string_policy_validate(&p)==LIE_STRING_OK);
  bytes=0;assert(lie_string_advance(&p,state,&bytes,20,'"',&match)==LIE_STRING_OK);
  memcpy(original,state,20);a.fail=a.calls+1;match=(lie_string_match){true,true};
  assert(lie_string_advance(&p,state,&bytes,20,'a',&match)==LIE_STRING_RESOURCE && match.complete && !memcmp(state,original,20));
  lie_regex_release(owned);assert(!a.alive && !a.bytes);
  cycle[0]=1;accept_cycle[0]=1;d.allocator=(lie_grammar_allocator){0};d.limits.max_work=34;owned=program(&d);finish=true;
  assert(lie_regex_can_finish(owned,0,100,100,&finish)==LIE_REGEX_WORK_LIMIT && finish);lie_regex_release(owned);
  d.limits.max_work=1;owned=(lie_regex_program *)(uintptr_t)1;
  assert(lie_regex_create(&d,&owned)==LIE_REGEX_WORK_LIMIT && owned==(lie_regex_program *)(uintptr_t)1);
  d.limits.max_work=256000000;d.limits.max_states=2;
  assert(lie_regex_create(&d,&owned)==LIE_REGEX_RESOURCE);
  d.limits.max_states=4096;any_ranges[0]=(lie_unicode_range){0xd800,0xdfff};
  assert(lie_regex_create(&d,&owned)==LIE_REGEX_INVALID);
  printf("DFA_GRAPHS=%zu REACHABILITY_QUERIES=%zu UNICODE_SCALARS=%zu ALLOCATOR_PEAK_BYTES=%zu HOST_NOT_INFERENCE\n",graphs,queries,scalars,a.peak);
}
