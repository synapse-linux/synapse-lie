/* SPDX-License-Identifier: MIT */
/* Independent finite byte-language and cache-order/lifetime/fault oracles. */
/* Synthetic host fixtures, NOT-INFERENCE. */
#include "lie/grammar_vocabulary.h"
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { size_t calls, fail_at, live, bytes, peak; } memory;
typedef union { size_t bytes; max_align_t alignment; } allocation;
static void *allocate(void *ctx,size_t bytes) {
  memory *m=ctx; ++m->calls;
  if (m->calls==m->fail_at) return NULL;
  allocation *p=malloc(sizeof(*p)+bytes);
  if (!p) return NULL;
  p->bytes=bytes; ++m->live; m->bytes+=bytes;
  if (m->bytes>m->peak) m->peak=m->bytes;
  return p+1;
}
static void release(void *ctx,void *ptr) {
  memory *m=ctx; allocation *p=(allocation *)ptr-1;
  assert(m->live && m->bytes>=p->bytes);
  --m->live; m->bytes-=p->bytes; free(p);
}
static lie_grammar_allocator hooks(memory *m) { return (lie_grammar_allocator){m,allocate,release}; }
static lie_grammar_program *language(memory *m) {
  static const lie_grammar_range rules[]={{0,1},{1,3}};
  static const lie_grammar_range sequences[]={{0,2},{2,0},{2,2},{4,2}};
  static const uint32_t symbols[]={1,LIE_GRAMMAR_TERMINAL|2,LIE_GRAMMAR_TERMINAL,1,LIE_GRAMMAR_TERMINAL|1,1};
  uint8_t classes[96]={0};
  for (unsigned i=0;i<3;++i) classes[i*32+('a'+i)/8]|=1u<<(('a'+i)%8);
  lie_grammar_description d; lie_grammar_description_init(&d);
  d.rules=rules; d.rule_count=2; d.sequences=sequences; d.sequence_count=4;
  d.symbols=symbols; d.symbol_count=6; d.classes=classes; d.class_count=3;
  if (m) d.allocator=hooks(m);
  lie_grammar_program *p=NULL;
  assert(lie_grammar_program_create(&d,&p)==LIE_GRAMMAR_OK);
  return p;
}
static bool oracle(const lie_token_piece *p,bool complete) {
  if (complete) return p->stop;
  if (p->stop || !p->length) return false;
  for (size_t i=0;i<p->length;++i)
    if (p->bytes[i]!='a' && p->bytes[i]!='b') return p->bytes[i]=='c' && i+1==p->length;
  return true;
}
static bool no_cache(const void *ctx,const lie_grammar_state *s) { (void)ctx;(void)s;return false; }
static size_t exhaustive(void) {
  lie_token_piece pieces[1400]; uint8_t text[1400][8]; size_t count=0;
  pieces[count++]=(lie_token_piece){(const uint8_t *)"ignored",7,true};
  pieces[count++]=(lie_token_piece){NULL,0,false};
  for (unsigned byte=0;byte<256;++byte) {
    text[count][0]=(uint8_t)byte;
    pieces[count]=(lie_token_piece){text[count],1,false}; ++count;
  }
  for (size_t n=2;n<=6;++n) {
    size_t words=1; for (size_t i=0;i<n;++i) words*=3;
    for (size_t word=0;word<words;++word) {
      size_t value=word;
      for (size_t i=0;i<n;++i) { text[count][i]=(uint8_t)('a'+value%3); value/=3; }
      pieces[count]=(lie_token_piece){text[count],n,false}; ++count;
    }
  }
  assert(count<=1400);
  lie_vocabulary_description d; lie_vocabulary_description_init(&d);
  d.pieces=pieces; d.count=count;
  lie_grammar_vocabulary *v=NULL;
  assert(lie_vocabulary_create(&d,&v)==LIE_GRAMMAR_OK);
  assert(lie_vocabulary_size(v)==count && lie_vocabulary_max_token_bytes(v)==6);
  lie_grammar_program *p=language(NULL);
  size_t checks=0;
  uint8_t mask[1400];
  for (unsigned len=0;len<=7;++len)
    for (unsigned bits=0;bits<(1u<<len);++bits) {
      lie_grammar_state *s=NULL;
      assert(lie_grammar_start(p,&s)==LIE_GRAMMAR_OK);
      for (unsigned i=0;i<len;++i) {
        lie_grammar_state *next=NULL;
        assert(lie_grammar_advance(p,s,(bits>>i)&1?'a':'b',&next)==LIE_GRAMMAR_OK);
        lie_grammar_state_release(s); s=next;
      }
      for (unsigned mode=0;mode<4;++mode) {
        lie_vocabulary_query q; lie_vocabulary_query_init(&q);
        if (mode==1) q.max_interned_states=0;
        if (mode==2) q.max_interned_states=2;
        if (mode==3) q.cache_transitions=no_cache;
        lie_vocabulary_stats stats;
        assert(lie_vocabulary_allowed(v,p,s,true,&q,mask,count,&stats)==LIE_GRAMMAR_OK);
        for (size_t i=0;i<count;++i) { assert(mask[i]==oracle(pieces+i,false)); ++checks; }
        if (mode==1 || mode==3) assert(stats.direct_nodes && !stats.interned_states);
      }
      if (!len) for (size_t i=0;i<count;++i) {
        lie_grammar_state *next=s;
        lie_grammar_status rc=lie_vocabulary_accept(v,p,s,(uint32_t)i,&next);
        bool ok=oracle(pieces+i,false);
        assert(rc==(ok?LIE_GRAMMAR_OK:LIE_GRAMMAR_NO_TOKEN));
        if (ok) {
          assert(lie_grammar_complete(next)==(pieces[i].bytes[pieces[i].length-1]=='c'));
          assert(lie_grammar_state_count(next)); lie_grammar_state_release(next);
        } else assert(next==s);
        ++checks;
      }
      lie_grammar_state *end=NULL;
      assert(lie_grammar_advance(p,s,'c',&end)==LIE_GRAMMAR_OK);
      assert(lie_vocabulary_allowed(v,p,end,true,NULL,mask,count,NULL)==LIE_GRAMMAR_OK);
      for (size_t i=0;i<count;++i) { assert(mask[i]==oracle(pieces+i,true)); ++checks; }
      lie_grammar_state *copy=NULL;
      assert(lie_vocabulary_accept(v,p,end,0,&copy)==LIE_GRAMMAR_OK);
      assert(!lie_grammar_state_compare(copy,end) && lie_grammar_state_hash(copy)==lie_grammar_state_hash(end));
      lie_grammar_state_release(copy); lie_grammar_state_release(end); lie_grammar_state_release(s);
    }
  lie_vocabulary_release(v); lie_grammar_program_release(p); return checks;
}
static size_t faults(size_t *peak) {
  memory m={0}; lie_grammar_program *p=language(&m);
  const lie_token_piece pieces[]={{(const uint8_t *)"a",1,false},{(const uint8_t *)"ab",2,false},
    {(const uint8_t *)"abc",3,false},{(const uint8_t *)"c",1,false},{NULL,0,true}};
  lie_vocabulary_description d; lie_vocabulary_description_init(&d);
  d.pieces=pieces; d.count=5; d.allocator=hooks(&m);
  lie_grammar_vocabulary *v=NULL;
  size_t before=m.calls;
  assert(lie_vocabulary_create(&d,&v)==LIE_GRAMMAR_OK);
  size_t creation=m.calls-before;
  lie_grammar_state *s=NULL;
  assert(lie_grammar_start(p,&s)==LIE_GRAMMAR_OK);
  uint8_t mask[5]; lie_vocabulary_stats stats;
  before=m.calls;
  assert(lie_vocabulary_allowed(v,p,s,true,NULL,mask,5,&stats)==LIE_GRAMMAR_OK);
  size_t query=m.calls-before,live=m.live;
  for (size_t i=1;i<=query;++i) {
    m.fail_at=m.calls+i; memset(mask,0x5a,5); memset(&stats,0x5a,sizeof(stats));
    lie_vocabulary_stats saved=stats;
    assert(lie_vocabulary_allowed(v,p,s,true,NULL,mask,5,&stats)==LIE_GRAMMAR_RESOURCE);
    for (size_t j=0;j<5;++j) assert(mask[j]==0x5a);
    assert(!memcmp(&stats,&saved,sizeof(stats)) && m.live==live);
    m.fail_at=0;
  }
  lie_vocabulary_query q; lie_vocabulary_query_init(&q);q.max_work=1;
  assert(lie_vocabulary_allowed(v,p,s,true,&q,mask,5,&stats)==LIE_GRAMMAR_MASK_WORK_LIMIT);
  assert(m.live==live && mask[0]==0x5a);
  lie_grammar_state *next=NULL;
  before=m.calls; assert(lie_vocabulary_accept(v,p,s,2,&next)==LIE_GRAMMAR_OK);
  size_t accept=m.calls-before; lie_grammar_state_release(next);
  for (size_t i=1;i<=accept;++i) {
    m.fail_at=m.calls+i; next=s;
    assert(lie_vocabulary_accept(v,p,s,2,&next)==LIE_GRAMMAR_RESOURCE && next==s && m.live==live);
    m.fail_at=0;
  }
  lie_vocabulary_release(v);live=m.live;
  for (size_t i=1;i<=creation;++i) {
    m.fail_at=m.calls+i; v=NULL;
    assert(lie_vocabulary_create(&d,&v)==LIE_GRAMMAR_RESOURCE && !v && m.live==live);
    m.fail_at=0;
  }
  d.limits.max_nodes=2;
  assert(lie_vocabulary_create(&d,&v)==LIE_GRAMMAR_VOCABULARY_LIMIT && !v && m.live==live);
  d.limits.max_nodes=4000000; d.limits.max_bytes=1;
  assert(lie_vocabulary_create(&d,&v)==LIE_GRAMMAR_INVALID && !v && m.live==live);
  lie_grammar_state_release(s);lie_grammar_program_release(p);
  assert(!m.live && !m.bytes); *peak=m.peak;
  return creation+query+accept;
}
typedef struct { size_t live, released; } payloads;
static void payload_release(void *ctx,void *value) {
  payloads *p=ctx;assert(p->live);--p->live;++p->released;free(value);
}
static void *payload_new(payloads *p) { void *v=malloc(1);assert(v);++p->live;return v; }
static void cache(void) {
  memory m={0};payloads values={0};lie_grammar_program *p=language(&m);
  lie_grammar_mask_cache *c=NULL;
  assert(lie_mask_cache_create(p,16,hooks(&m),payload_release,&values,&c)==LIE_GRAMMAR_OK);
  lie_grammar_state *keys[20]={0};
  const uint32_t symbol=LIE_GRAMMAR_TERMINAL;
  for (unsigned i=0;i<20;++i) {
    uint8_t byte=(uint8_t)i;
    const lie_grammar_frame f={&symbol,1,&byte,1};
    assert(lie_grammar_state_import(p,&f,1,keys+i)==LIE_GRAMMAR_OK);
  }
  for (unsigned i=0;i<20;++i) {
    void *v=payload_new(&values),*out=NULL;
    assert(lie_mask_cache_publish(c,keys[i],v,&out)==LIE_GRAMMAR_OK && out==v);
  }
  assert(lie_mask_cache_size(c)==16 && values.live==16 && values.released==4);
  for (unsigned i=0;i<20;++i) {
    void *out=NULL;assert(lie_mask_cache_find(c,keys[i],&out)==LIE_GRAMMAR_OK);
    assert((out!=NULL)==(i>=4));
  }
  void *existing=NULL;assert(lie_mask_cache_find(c,keys[19],&existing)==LIE_GRAMMAR_OK);
  void *duplicate=payload_new(&values),*out=NULL;
  assert(lie_mask_cache_publish(c,keys[19],duplicate,&out)==LIE_GRAMMAR_OK && out==existing);
  assert(lie_mask_cache_size(c)==15 && values.live==15 && values.released==6);
  duplicate=payload_new(&values);out=NULL;
  assert(lie_mask_cache_publish(c,keys[4],duplicate,&out)==LIE_GRAMMAR_OK && out==duplicate);
  assert(lie_mask_cache_size(c)==16);
  size_t before=m.calls;
  void *incoming=payload_new(&values);
  assert(lie_mask_cache_publish(c,keys[0],incoming,&out)==LIE_GRAMMAR_OK);
  size_t clone=m.calls-before;
  for (size_t i=1;i<=clone;++i) {
    incoming=payload_new(&values);out=existing;
    size_t live=m.live,count=lie_mask_cache_size(c),payload_live=values.live;
    m.fail_at=m.calls+i;
    assert(lie_mask_cache_publish(c,keys[1],incoming,&out)==LIE_GRAMMAR_RESOURCE);
    assert(out==existing && m.live==live && lie_mask_cache_size(c)==count && values.live==payload_live);
    m.fail_at=0;payload_release(&values,incoming);
  }
  lie_mask_cache_release(c);assert(!values.live);
  for (unsigned i=0;i<20;++i) lie_grammar_state_release(keys[i]);
  for (size_t i=1;i<=2;++i) {
    size_t live=m.live;m.fail_at=m.calls+i;c=NULL;
    assert(lie_mask_cache_create(p,16,hooks(&m),payload_release,&values,&c)==LIE_GRAMMAR_RESOURCE);
    assert(!c && m.live==live);m.fail_at=0;
  }
  lie_grammar_program_release(p);assert(!m.live);
}
static void deep_and_invalid(void) {
  uint8_t text[4097];memset(text,'a',sizeof(text));
  lie_token_piece pieces[]={{text,4096,false},{NULL,0,true}};
  lie_vocabulary_description d;lie_vocabulary_description_init(&d);d.pieces=pieces;d.count=2;
  lie_grammar_vocabulary *v=NULL;
  assert(lie_vocabulary_create(&d,&v)==LIE_GRAMMAR_OK);
  memset(text,'z',4096); /* Copied immutable pieces, not borrowed model strings. */
  lie_grammar_program *p=language(NULL);lie_grammar_state *s=NULL;
  assert(lie_grammar_start(p,&s)==LIE_GRAMMAR_OK);
  uint8_t mask[2];lie_vocabulary_stats stats;
  assert(lie_vocabulary_allowed(v,p,s,true,NULL,mask,2,&stats)==LIE_GRAMMAR_OK);
  assert(mask[0]==1 && mask[1]==0 && stats.peak_depth==4097 && stats.cache_hits>4000);
  assert(lie_vocabulary_accept(v,p,s,2,&s)==LIE_GRAMMAR_INVALID);
  lie_vocabulary_query q;lie_vocabulary_query_init(&q);q.max_interned_states=1;
  assert(lie_vocabulary_allowed(v,p,s,true,&q,mask,2,NULL)==LIE_GRAMMAR_INVALID);
  lie_grammar_state *dead=NULL;
  assert(lie_grammar_advance(p,s,'z',&dead)==LIE_GRAMMAR_OK);
  memset(mask,9,2);
  assert(lie_vocabulary_allowed(v,p,dead,true,NULL,mask,2,NULL)==LIE_GRAMMAR_NO_TOKEN && mask[0]==9);
  lie_grammar_state_release(dead);lie_grammar_state_release(s);lie_grammar_program_release(p);
  lie_vocabulary_release(v);v=NULL;pieces[0].length=4097;
  assert(lie_vocabulary_create(&d,&v)==LIE_GRAMMAR_INVALID && !v);
  pieces[0].stop=true;
  assert(lie_vocabulary_create(&d,&v)==LIE_GRAMMAR_OK && lie_vocabulary_max_token_bytes(v)==0);
  lie_vocabulary_release(v);
}
int main(void) {
  size_t checks=exhaustive(),peak=0,failure_points=faults(&peak);
  cache();deep_and_invalid();
  printf("Vocabulary/trie/intern/cache PASS: %zu independent token checks, %zu allocator refusal points, %zu fixture requested-payload peak bytes; NOT-INFERENCE\n",checks,failure_points,peak);
}
