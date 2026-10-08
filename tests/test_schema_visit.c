/* SPDX-License-Identifier: MIT */
/* Independent recursive-language, publication-order and lifetime oracles. */
#include "lie/schema_visit.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef enum { LEAF, ALIAS, EMPTY, CHOICE, PREFIX } kind;
typedef struct node node;
struct node { kind kind;node *left,*right;uint8_t byte; };
typedef struct {
  lie_schema_memo *memo;lie_grammar_builder *builder;lie_schema_body_access access;
  size_t calls,fail;lie_schema_status refusal;bool check_alias_ids;
} context;
static size_t oracles,body_refusals,allocation_refusals;
static lie_schema_status body(void *p,lie_schema_node value,size_t depth,uint32_t *out,lie_schema_error *e) {
  context *c=p;const node *n=value;uint32_t placeholder=UINT32_MAX;bool hit=false;
  assert(lie_schema_memo_get(c->memo,value,&placeholder,&hit)==LIE_SCHEMA_OK && hit);
  if (c->check_alias_ids) assert(placeholder==c->calls);
  ++oracles;
  if (++c->calls==c->fail) { *out=UINT32_MAX;return c->refusal; }
  if (n->kind==LEAF) { *out=LIE_GRAMMAR_TERMINAL|n->byte;return LIE_SCHEMA_OK; }
  if (n->kind==EMPTY) { *out=UINT32_MAX;return LIE_SCHEMA_EMPTY; }
  uint32_t left=0,right=0;
  lie_schema_status rc=lie_schema_visit_rule(c->memo,c->builder,n->left,depth,c->access,&left,e);
  if (rc) return rc;
  if (n->kind==ALIAS) { *out=left;return LIE_SCHEMA_OK; }
  if (n->kind==CHOICE) {
    rc=lie_schema_visit_rule(c->memo,c->builder,n->right,depth,c->access,&right,e);
    if (rc) return rc;
  }
  uint32_t symbols[2]={n->kind==PREFIX?(LIE_GRAMMAR_TERMINAL|n->byte):left,n->kind==PREFIX?left:right};
  const lie_builder_status b=n->kind==PREFIX?lie_builder_sequence_make(c->builder,symbols,2,out):lie_builder_alternatives(c->builder,symbols,2,out);
  return b==LIE_BUILDER_OK?LIE_SCHEMA_OK:b==LIE_BUILDER_RESOURCE?LIE_SCHEMA_RESOURCE:LIE_SCHEMA_INVALID;
}
static context create(size_t entries) {
  context c={0};lie_schema_memo_description md;lie_schema_memo_description_init(&md);md.max_entries=entries;
  assert(lie_schema_memo_create(&md,&c.memo)==LIE_SCHEMA_OK);
  lie_builder_description bd;lie_builder_description_init(&bd);assert(lie_builder_create(&bd,&c.builder)==LIE_BUILDER_OK);
  lie_schema_body_access_init(&c.access);c.access.body=body;return c;
}
static void retire(context *c) { lie_builder_release(c->builder);lie_schema_memo_release(c->memo); }
static bool accepts(const lie_grammar_program *p,const char *text) {
  lie_grammar_state *s=NULL;assert(lie_grammar_start(p,&s)==LIE_GRAMMAR_OK);
  for (size_t i=0;text[i];++i) { lie_grammar_state *next=NULL;assert(lie_grammar_advance(p,s,(uint8_t)text[i],&next)==LIE_GRAMMAR_OK);lie_grammar_state_release(s);s=next; }
  const bool yes=lie_grammar_complete(s);lie_grammar_state_release(s);return yes;
}
static lie_builder_status finalize(context *c,uint32_t root,lie_grammar_program **out) {
  lie_grammar_description d;lie_builder_status rc=lie_builder_finish(c->builder,root,0,&d);
  if (!rc) assert(lie_grammar_program_create(&d,out)==LIE_GRAMMAR_OK);
  return rc;
}
static void aliases_and_hits(void) {
  for (size_t count=0;count<=128;count=count?count*2:1) {
    node nodes[129]={0};for (size_t i=0;i<count;++i) nodes[i]=(node){ALIAS,&nodes[i+1],NULL,0};nodes[count]=(node){LEAF,NULL,NULL,'z'};
    context c=create(256);c.access.context=&c;c.check_alias_ids=true;uint32_t root=UINT32_MAX;lie_schema_error e={0};
    assert(lie_schema_visit_rule(c.memo,c.builder,nodes,0,c.access,&root,&e)==LIE_SCHEMA_OK && root==0 && c.calls==count+1);
    size_t calls=c.calls;uint32_t again=UINT32_MAX;c.fail=c.calls+1;c.refusal=LIE_SCHEMA_CALLBACK;
    assert(lie_schema_visit_rule(c.memo,c.builder,nodes,SIZE_MAX,c.access,&again,&e)==LIE_SCHEMA_OK && again==root && c.calls==calls);
    lie_schema_memo_info info;assert(lie_schema_memo_inspect(c.memo,&info)==LIE_SCHEMA_OK && info.entries==count+1);
    lie_grammar_program *p=NULL;assert(finalize(&c,root,&p)==LIE_BUILDER_OK);
    assert(accepts(p,"z") && !accepts(p,"") && !accepts(p,"zz") && !accepts(p,"a"));
    again=UINT32_MAX;assert(lie_schema_visit_rule(c.memo,c.builder,nodes,0,c.access,&again,&e)==LIE_SCHEMA_OK && again==root);
    lie_grammar_program_release(p);retire(&c);oracles+=6;
  }
}
static void recursive_and_empty(void) {
  node leaf={LEAF,NULL,NULL,'z'},root={CHOICE,NULL,&leaf,0},prefix={PREFIX,&root,NULL,'a'};root.left=&prefix;
  context c=create(16);c.access.context=&c;uint32_t id=UINT32_MAX;lie_schema_error e={0};
  assert(lie_schema_visit_rule(c.memo,c.builder,&root,0,c.access,&id,&e)==LIE_SCHEMA_OK && c.calls==3);
  lie_grammar_program *p=NULL;assert(finalize(&c,id,&p)==LIE_BUILDER_OK);
  char text[36];for (unsigned n=0;n<=32;++n) { memset(text,'a',n);text[n]='z';text[n+1]=0;assert(accepts(p,text));text[n]='b';assert(!accepts(p,text));oracles+=2; }
  assert(!accepts(p,"") && !accepts(p,"a") && !accepts(p,"za"));oracles+=3;lie_grammar_program_release(p);retire(&c);
  node empty={EMPTY,NULL,NULL,0};root.left=&empty;root.right=&leaf;c=create(16);c.access.context=&c;
  assert(lie_schema_visit_rule(c.memo,c.builder,&root,0,c.access,&id,&e)==LIE_SCHEMA_OK);assert(finalize(&c,id,&p)==LIE_BUILDER_OK);
  assert(accepts(p,"z") && !accepts(p,"") && !accepts(p,"a"));lie_grammar_program_release(p);retire(&c);oracles+=3;
  c=create(16);c.access.context=&c;
  assert(lie_schema_visit_rule(c.memo,c.builder,&empty,0,c.access,&id,&e)==LIE_SCHEMA_OK);
  assert(finalize(&c,id,&p)==LIE_BUILDER_EMPTY);retire(&c);++oracles;
  node cycle={ALIAS,NULL,NULL,0};cycle.left=&cycle;c=create(16);c.access.context=&c;
  assert(lie_schema_visit_rule(c.memo,c.builder,&cycle,0,c.access,&id,&e)==LIE_SCHEMA_OK && c.calls==1);
  assert(finalize(&c,id,&p)==LIE_BUILDER_CYCLE);retire(&c);++oracles;
}
typedef union { max_align_t alignment;size_t bytes; } allocation;
typedef struct { size_t calls,fail,live; } memory;
static void *allocate(void *p,size_t bytes) {
  memory *m=p;if (++m->calls==m->fail) return NULL;
  allocation *a=malloc(sizeof(*a)+bytes);assert(a);a->bytes=bytes;++m->live;return a+1;
}
static void release(void *p,void *v) { memory *m=p;assert(m->live);--m->live;free((allocation *)v-1); }
static size_t faults(size_t fail,size_t refuse,lie_schema_status status) {
  node nodes[17]={0};for (size_t i=0;i<16;++i) nodes[i]=(node){ALIAS,&nodes[i+1],NULL,0};nodes[16]=(node){LEAF,NULL,NULL,'z'};
  memory m={.fail=fail};context c={.fail=refuse,.refusal=status,.check_alias_ids=true};
  lie_schema_memo_description md;lie_schema_memo_description_init(&md);md.allocator=(lie_grammar_allocator){&m,allocate,release};
  lie_schema_status rc=lie_schema_memo_create(&md,&c.memo);
  if (rc) { assert(rc==LIE_SCHEMA_RESOURCE);++allocation_refusals; }
  else {
    lie_builder_description bd;lie_builder_description_init(&bd);bd.allocator=md.allocator;
    lie_builder_status brc=lie_builder_create(&bd,&c.builder);
    if (brc) { assert(brc==LIE_BUILDER_RESOURCE);++allocation_refusals; }
    else {
      lie_schema_body_access_init(&c.access);c.access.body=body;c.access.context=&c;
      uint32_t id=UINT32_MAX;lie_schema_error e={0};rc=lie_schema_visit_rule(c.memo,c.builder,nodes,0,c.access,&id,&e);
      if (refuse) { assert(rc==status && id==UINT32_MAX && c.calls==refuse);++body_refusals; }
      else if (rc) { assert(rc==LIE_SCHEMA_RESOURCE && id==UINT32_MAX);++allocation_refusals; }
      else assert(id==0 && c.calls==17);
      lie_builder_release(c.builder);
    }
    lie_schema_memo_release(c.memo);
  }
  assert(m.live==0);return m.calls;
}
static void invalid_and_limits(void) {
  node leaf={LEAF,NULL,NULL,'x'},alias={ALIAS,&leaf,NULL,0};context c=create(1);c.access.context=&c;
  uint32_t id=UINT32_MAX;lie_schema_error e={0};lie_schema_body_access bad=c.access;bad.abi_version++;
  assert(lie_schema_visit_rule(c.memo,c.builder,&leaf,0,bad,&id,&e)==LIE_SCHEMA_INVALID && id==UINT32_MAX);
  bad=c.access;bad.struct_bytes--;assert(lie_schema_visit_rule(c.memo,c.builder,&leaf,0,bad,&id,&e)==LIE_SCHEMA_INVALID);
  bad=c.access;bad.body=NULL;assert(lie_schema_visit_rule(c.memo,c.builder,&leaf,0,bad,&id,&e)==LIE_SCHEMA_INVALID);
  assert(lie_schema_visit_rule(NULL,c.builder,&leaf,0,c.access,&id,&e)==LIE_SCHEMA_INVALID);
  assert(lie_schema_visit_rule(c.memo,NULL,&leaf,0,c.access,&id,&e)==LIE_SCHEMA_INVALID);
  assert(lie_schema_visit_rule(c.memo,c.builder,NULL,0,c.access,&id,&e)==LIE_SCHEMA_INVALID);
  assert(lie_schema_visit_rule(c.memo,c.builder,&leaf,0,c.access,NULL,&e)==LIE_SCHEMA_INVALID);
  assert(lie_schema_visit_rule(c.memo,c.builder,&alias,0,c.access,&id,&e)==LIE_SCHEMA_INVALID && id==UINT32_MAX && !strcmp(e.message,"compiled grammar exceeds the rule limit"));retire(&c);
  c=create(16);c.access.context=&c;lie_builder_description bd;lie_builder_description_init(&bd);bd.max_rules=1;
  lie_builder_release(c.builder);assert(lie_builder_create(&bd,&c.builder)==LIE_BUILDER_OK);
  assert(lie_schema_visit_rule(c.memo,c.builder,&alias,0,c.access,&id,&e)==LIE_SCHEMA_INVALID && id==UINT32_MAX && !strcmp(e.message,"compiled grammar exceeds the rule limit"));retire(&c);
  lie_schema_body_access_init(NULL);oracles+=9;
}
int main(void) {
  aliases_and_hits();recursive_and_empty();invalid_and_limits();
  size_t sites=faults(0,0,LIE_SCHEMA_OK);for (size_t i=1;i<=sites;++i) faults(i,0,LIE_SCHEMA_OK);
  for (size_t i=1;i<=17;++i) for (unsigned rc=LIE_SCHEMA_INVALID;rc<=LIE_SCHEMA_CALLBACK;++rc)
    if (rc!=LIE_SCHEMA_EMPTY) faults(0,i,(lie_schema_status)rc);
  printf("C17 schema visit: %zu independent oracles, %zu body refusals, %zu allocation refusals, %zu construction allocation sites\n",oracles,body_refusals,allocation_refusals,sites);
}
