/* SPDX-License-Identifier: MIT */
/* Independent type/keyword tables, ordered language and refusal oracles. */
#include "lie/schema_dispatch.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct node node;
struct node { lie_schema_value v; const char *keys[24]; node *children[24]; };
typedef struct { size_t calls, fail; unsigned malformed; } reader;
static size_t oracles, reader_refusals, rule_refusals, allocation_refusals;
static lie_schema_status describe(void *p, lie_schema_node n, lie_schema_value *v) {
  reader *r=p; if (++r->calls==r->fail) return LIE_SCHEMA_CALLBACK;
  *v=((const node *)n)->v;
  if (r->malformed==1) v->kind=(lie_schema_kind)-1;
  if (r->malformed==2) v->text=(lie_schema_bytes){NULL,1};
  return LIE_SCHEMA_OK;
}
static lie_schema_status child(void *p,lie_schema_node n,size_t i,lie_schema_bytes *key,lie_schema_node *out) {
  reader *r=p; if (++r->calls==r->fail) return LIE_SCHEMA_CALLBACK;
  const node *v=n; assert(i<v->v.count);
  *key=(lie_schema_bytes){v->keys[i],v->keys[i]?strlen(v->keys[i]):0}; *out=v->children[i];
  if (r->malformed==3) *out=NULL;
  if (r->malformed==4) *key=(lie_schema_bytes){NULL,1};
  return LIE_SCHEMA_OK;
}
static void field(node *n,const char *key,node *value) {
  assert(n->v.count<24);size_t i=n->v.count++;n->keys[i]=key;n->children[i]=value;
}
static node text(const char *s) { node n={.v={.kind=LIE_SCHEMA_STRING,.text={s,strlen(s)}}};return n; }
static lie_schema_transform_description description(reader *r) {
  lie_schema_transform_description d;lie_schema_transform_description_init(&d);
  d.access.context=r;d.access.describe=describe;d.access.child=child;return d;
}
/* Groups describe the specification, independently of implementation flags. */
static const char *const names[]={"null","boolean","integer","number","string","object","array","unknown",""};
static const char *const keys[]={"minimum","maximum","exclusiveMinimum","exclusiveMaximum","multipleOf","pattern","format","minLength","maxLength","properties","required","additionalProperties","items","minItems","maxItems"};
static const unsigned groups[]={1,1,1,1,1,2,2,2,2,4,4,4,8,8,8};
static const unsigned allowed[]={0,0,1,1,2,4,8,0,0};
static const char *const messages[]={"numeric constraint on a non-numeric schema","string constraint on a non-string schema","object keyword on a non-object schema","array keyword on a non-array schema"};
static lie_schema_route expected(size_t type,unsigned mask) {
  if (type==2) return mask&16?LIE_SCHEMA_ROUTE_INTEGER_LEXEME:LIE_SCHEMA_ROUTE_INTEGER;
  if (type==3 && (mask&31)) return LIE_SCHEMA_ROUTE_NUMBER_LEXEME;
  if (type==4 && (mask&480)) return LIE_SCHEMA_ROUTE_STRING_LEXEME;
  if (type==5) return LIE_SCHEMA_ROUTE_OBJECT;
  if (type==6) return LIE_SCHEMA_ROUTE_ARRAY;
  return LIE_SCHEMA_ROUTE_PRIMITIVE;
}
static void matrix(void) {
  reader r={0};lie_schema_transform_description d=description(&r);node null_type=text("null"),ignored={0};
  for (size_t type=0;type<sizeof(names)/sizeof(*names);++type)
    for (unsigned shape=0;shape<(type?3u:1u);++shape)
      for (unsigned mask=0;mask<512;++mask) {
        node s={.v={.kind=LIE_SCHEMA_OBJECT}},t=text(names[type]),pair={.v={.kind=LIE_SCHEMA_ARRAY}};
        if (shape) { field(&pair,NULL,shape==1?&t:&null_type);field(&pair,NULL,shape==1?&null_type:&t); }
        field(&s,"type",shape?&pair:&t);
        const char *failure=NULL;
        for (unsigned k=0;k<9;++k) if (mask&(1u<<k)) {
          field(&s,keys[k],&ignored);
          if (!failure && !(allowed[type]&groups[k])) failure=messages[k<5?0:1];
        }
        lie_schema_dispatch_plan p,before;memset(&p,0xa5,sizeof(p));memcpy(&before,&p,sizeof(p));lie_schema_error e={0};
        const lie_schema_status rc=lie_schema_dispatch_types(&d,&s,&p,&e);
        if (failure) { assert(rc==LIE_SCHEMA_INVALID && !strcmp(e.message,failure));assert(!memcmp(&p,&before,sizeof(p))); }
        else {
          assert(rc==LIE_SCHEMA_OK && p.abi_version==1 && p.struct_bytes==sizeof(p));
          assert(p.count==(shape?2u:1u));size_t i=shape==2?1:0;
          assert(p.names[i].size==strlen(names[type]) && !memcmp(p.names[i].data,names[type],p.names[i].size));
          assert(p.routes[i]==expected(type,mask));
          if (shape) assert(p.routes[1-i]==LIE_SCHEMA_ROUTE_PRIMITIVE);
        }
        ++oracles;
      }
  for (size_t type=0;type<9;++type) for (size_t k=0;k<15;++k) {
    node s={.v={.kind=LIE_SCHEMA_OBJECT}},t=text(names[type]);field(&s,"type",&t);field(&s,keys[k],&ignored);
    lie_schema_dispatch_plan p;lie_schema_error e={0};lie_schema_status rc=lie_schema_dispatch_types(&d,&s,&p,&e);
    assert(rc==((allowed[type]&groups[k])?LIE_SCHEMA_OK:LIE_SCHEMA_INVALID));++oracles;
  }
}
static void malformed_and_refusals(void) {
  reader r={0};lie_schema_transform_description d=description(&r);node s={.v={.kind=LIE_SCHEMA_OBJECT}},t=text("null"),pair={.v={.kind=LIE_SCHEMA_ARRAY}};
  lie_schema_dispatch_plan p,before;lie_schema_error e={0};
  memset(&p,0x39,sizeof(p));before=p;
  assert(lie_schema_dispatch_types(&d,&s,&p,&e)==LIE_SCHEMA_INVALID && !strcmp(e.message,"type must be a string or nullable type array"));
  field(&s,"type",&pair);
  assert(lie_schema_dispatch_types(&d,&s,&p,&e)==LIE_SCHEMA_INVALID && !memcmp(&p,&before,sizeof(p)));
  field(&pair,NULL,&t);field(&pair,NULL,&t);
  assert(lie_schema_dispatch_types(&d,&s,&p,&e)==LIE_SCHEMA_INVALID && !strcmp(e.message,"type unions must be nullable; use anyOf otherwise"));
  node bool_type=text("boolean");pair.children[1]=&bool_type;
  assert(lie_schema_dispatch_types(&d,&s,&p,&e)==LIE_SCHEMA_OK);
  const size_t calls=r.calls;r.calls=0;
  assert(lie_schema_dispatch_types(&d,&s,&p,&e)==LIE_SCHEMA_OK);const size_t sites=r.calls;assert(sites && sites<calls);
  for (size_t fail=1;fail<=sites;++fail) {
    r.calls=0;r.fail=fail;p=before;
    assert(lie_schema_dispatch_types(&d,&s,&p,&e)==LIE_SCHEMA_CALLBACK && !memcmp(&p,&before,sizeof(p)));++reader_refusals;
  }
  r.fail=0;
  for (unsigned malformed=1;malformed<=4;++malformed) {
    r.malformed=malformed;p=before;
    assert(lie_schema_dispatch_types(&d,&s,&p,&e)==LIE_SCHEMA_INVALID && !memcmp(&p,&before,sizeof(p)));++reader_refusals;
  }
  r.malformed=0;
  pair.children[1]->v.kind=LIE_SCHEMA_NUMBER;p=before;
  assert(lie_schema_dispatch_types(&d,&s,&p,&e)==LIE_SCHEMA_INVALID && !strcmp(e.message,"type members must be strings"));
  pair.children[1]->v.kind=LIE_SCHEMA_STRING;field(&pair,NULL,&t);
  assert(lie_schema_dispatch_types(&d,&s,&p,&e)==LIE_SCHEMA_INVALID && !strcmp(e.message,"type must be a string or nullable type array"));
  s.children[0]=&t;const char embedded[]={'n','u','l','l',0,'x'};t.v.text=(lie_schema_bytes){embedded,sizeof(embedded)};
  assert(lie_schema_dispatch_types(&d,&s,&p,&e)==LIE_SCHEMA_OK && p.routes[0]==LIE_SCHEMA_ROUTE_PRIMITIVE && p.names[0].size==sizeof(embedded));
  d.max_work=1;p=before;
  assert(lie_schema_dispatch_types(&d,&s,&p,&e)==LIE_SCHEMA_WORK_LIMIT && !memcmp(&p,&before,sizeof(p)));++reader_refusals;
  d.max_work=0;assert(lie_schema_dispatch_types(&d,&s,&p,&e)==LIE_SCHEMA_INVALID);
  d=description(&r);d.abi_version++;
  assert(lie_schema_dispatch_types(&d,&s,&p,&e)==LIE_SCHEMA_INVALID);
  assert(lie_schema_dispatch_types(NULL,&s,&p,&e)==LIE_SCHEMA_INVALID);
  d=description(&r);assert(lie_schema_dispatch_types(&d,NULL,&p,&e)==LIE_SCHEMA_INVALID);
  assert(lie_schema_dispatch_types(&d,&s,NULL,&e)==LIE_SCHEMA_INVALID);
  s.v.kind=LIE_SCHEMA_ARRAY;assert(lie_schema_dispatch_types(&d,&s,&p,&e)==LIE_SCHEMA_INVALID && !strcmp(e.message,"each schema must be an object"));
}
typedef union { max_align_t alignment;size_t bytes; } allocation;
typedef struct { size_t calls,fail,live; } memory;
static void *allocate(void *p,size_t bytes) {
  memory *m=p;if (++m->calls==m->fail) return NULL;
  allocation *a=malloc(sizeof(*a)+bytes);assert(a);a->bytes=bytes;++m->live;return a+1;
}
static void release(void *p,void *v) { memory *m=p;assert(m->live);--m->live;free((allocation *)v-1); }
typedef struct { lie_grammar_builder *builder;size_t calls,fail;lie_schema_status refusal;lie_schema_route seen[2]; } emitter;
static lie_schema_status rule(void *p,lie_schema_node n,size_t depth,lie_schema_route route,lie_schema_bytes name,uint32_t *out) {
  emitter *e=p;assert(n && depth==13 && name.size && e->calls<2);e->seen[e->calls]=route;
  if (++e->calls==e->fail) return e->refusal;
  const uint8_t literal=(uint8_t)('a'+e->calls-1);
  const lie_builder_status rc=lie_builder_literal(e->builder,&literal,1,out);
  return rc==LIE_BUILDER_OK?LIE_SCHEMA_OK:rc==LIE_BUILDER_RESOURCE?LIE_SCHEMA_RESOURCE:LIE_SCHEMA_INVALID;
}
static bool accepts(const lie_grammar_program *p,const char *text) {
  lie_grammar_state *s=NULL;assert(lie_grammar_start(p,&s)==LIE_GRAMMAR_OK);
  for (size_t i=0;i<strlen(text);++i) { lie_grammar_state *next=NULL;assert(lie_grammar_advance(p,s,(uint8_t)text[i],&next)==LIE_GRAMMAR_OK);lie_grammar_state_release(s);s=next; }
  const bool yes=lie_grammar_complete(s);lie_grammar_state_release(s);return yes;
}
static size_t emission(size_t fail,size_t refuse,lie_schema_status status) {
  reader rd={0};lie_schema_transform_description d=description(&rd);node s={.v={.kind=LIE_SCHEMA_OBJECT}},t=text("integer"),null_type=text("null"),pair={.v={.kind=LIE_SCHEMA_ARRAY}};
  field(&pair,NULL,&t);field(&pair,NULL,&null_type);field(&s,"type",&pair);
  lie_schema_dispatch_plan plan;lie_schema_error error={0};assert(lie_schema_dispatch_types(&d,&s,&plan,&error)==LIE_SCHEMA_OK);
  memory m={.fail=fail};lie_builder_description bd;lie_builder_description_init(&bd);bd.allocator=(lie_grammar_allocator){&m,allocate,release};
  lie_grammar_builder *b=NULL;lie_builder_status created=lie_builder_create(&bd,&b);size_t construction_calls=m.calls;
  if (created) { assert(created==LIE_BUILDER_RESOURCE);++allocation_refusals; }
  else {
    emitter e={.builder=b,.fail=refuse,.refusal=status};uint32_t root=UINT32_MAX;
    lie_schema_status rc=lie_schema_dispatch_rules(&plan,&s,13,b,(lie_schema_rule_access){&e,rule},&root,&error);
    construction_calls=m.calls;
    if (refuse) { assert(rc==status && root==UINT32_MAX && e.calls==refuse);++rule_refusals; }
    else if (rc) { assert(rc==LIE_SCHEMA_RESOURCE && root==UINT32_MAX);++allocation_refusals; }
    else {
      assert(e.calls==2 && e.seen[0]==LIE_SCHEMA_ROUTE_INTEGER && e.seen[1]==LIE_SCHEMA_ROUTE_PRIMITIVE);
      lie_grammar_description gd;assert(lie_builder_finish(b,root,0,&gd)==LIE_BUILDER_OK);
      lie_grammar_program *p=NULL;assert(lie_grammar_program_create(&gd,&p)==LIE_GRAMMAR_OK);
      assert(accepts(p,"a") && accepts(p,"b") && !accepts(p,"") && !accepts(p,"ab") && !accepts(p,"c"));lie_grammar_program_release(p);++oracles;
    }
    lie_schema_dispatch_plan broken=plan;broken.count=3;
    assert(lie_schema_dispatch_rules(&broken,&s,13,b,(lie_schema_rule_access){&e,rule},&root,NULL)==LIE_SCHEMA_INVALID);
    broken=plan;broken.abi_version++;
    assert(lie_schema_dispatch_rules(&broken,&s,13,b,(lie_schema_rule_access){&e,rule},&root,NULL)==LIE_SCHEMA_INVALID);
    broken=plan;broken.routes[1]=(lie_schema_route)-1;
    assert(lie_schema_dispatch_rules(&broken,&s,13,b,(lie_schema_rule_access){&e,rule},&root,NULL)==LIE_SCHEMA_INVALID);
    broken=plan;broken.names[1]=(lie_schema_bytes){NULL,1};
    assert(lie_schema_dispatch_rules(&broken,&s,13,b,(lie_schema_rule_access){&e,rule},&root,NULL)==LIE_SCHEMA_INVALID);
    lie_builder_release(b);
  }
  assert(m.live==0);return construction_calls;
}
int main(void) {
  matrix();malformed_and_refusals();
  /* Capture construction sites before finalization: its allocations belong to
   * the separately qualified builder. This exact dispatch path owns none. */
  const size_t calls=emission(0,0,LIE_SCHEMA_OK);
  for (size_t i=1;i<=calls;++i) emission(i,0,LIE_SCHEMA_OK);
  for (size_t i=1;i<=2;++i) for (unsigned s=LIE_SCHEMA_INVALID;s<=LIE_SCHEMA_CALLBACK;++s) emission(0,i,(lie_schema_status)s);
  printf("C17 schema dispatch: %zu independent oracles, %zu reader refusals, %zu leaf refusals, %zu builder allocation refusals\n",oracles,reader_refusals,rule_refusals,allocation_refusals);
}
