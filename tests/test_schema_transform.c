/* SPDX-License-Identifier: MIT */
/* Independent ordered-tree oracles and complete callback/allocation refusal. */
#include "lie/schema_transform.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct node node;
typedef struct { char key[128]; size_t bytes; node *value; } edge;
struct node { node *next; lie_schema_value value; char text[1024]; edge edges[16]; };
typedef struct { node *nodes; size_t calls,fail_at; } arena;
typedef union { max_align_t align; size_t bytes; } header;
typedef struct { size_t calls,fail_at,live,bytes,peak; } memory;
static size_t oracles,callback_refusals,allocation_refusals;
static void *alloc(void *p,size_t n) {
  memory *m=p; if (++m->calls==m->fail_at) return NULL;
  header *h=malloc(sizeof(*h)+n); assert(h); h->bytes=n; ++m->live; m->bytes+=n;
  if (m->bytes>m->peak) m->peak=m->bytes;
  return h+1;
}
static void dealloc(void *p,void *n) {
  memory *m=p; header *h=(header *)n-1; assert(m->live && m->bytes>=h->bytes);
  --m->live; m->bytes-=h->bytes; free(h);
}
static bool refusal(arena *a) { return ++a->calls==a->fail_at; }
static node *make(arena *a,lie_schema_kind kind,const char *text,size_t bytes,double number) {
  node *n=calloc(1,sizeof(*n)); assert(n && bytes<sizeof(n->text));
  n->next=a->nodes; a->nodes=n; n->value.kind=kind; n->value.number=number;
  if (bytes) memcpy(n->text,text,bytes);
  n->value.text=(lie_schema_bytes){n->text,bytes}; return n;
}
static node *str(arena *a,const char *s) { return make(a,LIE_SCHEMA_STRING,s,strlen(s),0); }
static node *num(arena *a,double n) { return make(a,LIE_SCHEMA_NUMBER,NULL,0,n); }
static node *obj(arena *a) { return make(a,LIE_SCHEMA_OBJECT,NULL,0,0); }
static node *arr(arena *a) { return make(a,LIE_SCHEMA_ARRAY,NULL,0,0); }
static void add(node *n,const char *key,size_t bytes,node *value) {
  assert(n->value.count<16 && bytes<128); edge *e=&n->edges[n->value.count++];
  if (bytes) memcpy(e->key,key,bytes);
  e->bytes=bytes; e->value=value;
}
static void field(node *n,const char *key,node *value) {
  for (size_t i=0;i<n->value.count;++i)
    if (n->edges[i].bytes==strlen(key) && !memcmp(n->edges[i].key,key,strlen(key))) {
      n->edges[i].value=value; return;
    }
  add(n,key,strlen(key),value);
}
static node *get(node *n,const char *key) {
  for (size_t i=0;i<n->value.count;++i) if (n->edges[i].bytes==strlen(key) && !memcmp(n->edges[i].key,key,strlen(key))) return n->edges[i].value;
  return NULL;
}
static void clear(arena *a) { while (a->nodes) { node *n=a->nodes; a->nodes=n->next; free(n); } }
static node *copy(arena *a,const node *n) {
  node *out=make(a,n->value.kind,n->value.text.data,n->value.text.size,n->value.number); out->value.boolean=n->value.boolean;
  for (size_t i=0;i<n->value.count;++i) add(out,n->edges[i].key,n->edges[i].bytes,copy(a,n->edges[i].value));
  return out;
}
static lie_schema_status describe(void *p,lie_schema_node n,lie_schema_value *v) {
  if (refusal(p)) return LIE_SCHEMA_CALLBACK;
  *v=((const node *)n)->value; return LIE_SCHEMA_OK;
}
static lie_schema_status invalid_describe(void *p,lie_schema_node n,lie_schema_value *v) {
  lie_schema_status rc=describe(p,n,v); if (!rc) v->kind=(lie_schema_kind)-1; return rc;
}
static lie_schema_status child(void *p,lie_schema_node n,size_t i,lie_schema_bytes *key,lie_schema_node *out) {
  if (refusal(p)) return LIE_SCHEMA_CALLBACK;
  const node *v=n; assert(i<v->value.count); *key=(lie_schema_bytes){v->edges[i].key,v->edges[i].bytes}; *out=v->edges[i].value; return LIE_SCHEMA_OK;
}
static lie_schema_status clone(void *p,lie_schema_node n,lie_schema_node *out) {
  if (refusal(p)) return LIE_SCHEMA_CALLBACK;
  *out=copy(p,n); return LIE_SCHEMA_OK;
}
static lie_schema_status create(void *p,const lie_schema_value *v,lie_schema_node *out) {
  if (refusal(p)) return LIE_SCHEMA_CALLBACK;
  node *n=make(p,v->kind,v->text.data,v->text.size,v->number); n->value.boolean=v->boolean; *out=n; return LIE_SCHEMA_OK;
}
static lie_schema_status put(void *p,lie_schema_node n,lie_schema_bytes key,lie_schema_node value) {
  if (refusal(p)) return LIE_SCHEMA_CALLBACK;
  node *target=(node *)n; node *v=copy(p,value);
  for (size_t i=0;i<target->value.count;++i) if (target->edges[i].bytes==key.size && !memcmp(target->edges[i].key,key.data,key.size)) { target->edges[i].value=v; return LIE_SCHEMA_OK; }
  add(target,key.data,key.size,v); return LIE_SCHEMA_OK;
}
static lie_schema_status append(void *p,lie_schema_node n,lie_schema_node value) {
  if (refusal(p)) return LIE_SCHEMA_CALLBACK;
  add((node *)n,NULL,0,copy(p,value)); return LIE_SCHEMA_OK;
}
static lie_schema_status format(void *p,lie_schema_bytes name,lie_schema_node *out) {
  if (refusal(p)) return LIE_SCHEMA_CALLBACK;
  node *n=obj(p); field(n,"pattern",make(p,LIE_SCHEMA_STRING,name.data,name.size,0)); *out=n; return LIE_SCHEMA_OK;
}
static lie_schema_status multiple(void *p,lie_schema_node l,lie_schema_node r,lie_schema_node *out) {
  if (refusal(p)) return LIE_SCHEMA_CALLBACK;
  unsigned a=(unsigned)((const node *)l)->value.number,b=(unsigned)((const node *)r)->value.number;
  if (!a || !b) return LIE_SCHEMA_EMPTY;
  unsigned n=a; while (n%b) n+=a; *out=num(p,n); return LIE_SCHEMA_OK;
}
static lie_schema_transform_description description(arena *a,memory *m) {
  lie_schema_transform_description d; lie_schema_transform_description_init(&d);
  d.access=(lie_schema_access){a,describe,child,clone,create,put,append,format,multiple};
  if (m) d.allocator=(lie_grammar_allocator){m,alloc,dealloc};
  return d;
}
static node *schema(arena *a,const char *type) { node *n=obj(a); field(n,"type",str(a,type)); return n; }
static node *joined(arena *a,node *root,node *l,node *r) {
  lie_schema_transform_description d=description(a,NULL); lie_schema_node out=NULL; lie_schema_error e={0};
  assert(lie_schema_conjoin(&d,root,l,r,0,&out,&e)==LIE_SCHEMA_OK); ++oracles; return (node *)out;
}
static void equality_and_references(void) {
  arena a={0}; memory m={0}; lie_schema_transform_description d=description(&a,&m); lie_schema_error e={0};
  node *l=obj(&a),*r=obj(&a); field(l,"a",num(&a,0)); field(l,"b",str(&a,"x")); field(r,"b",str(&a,"x")); field(r,"a",num(&a,-0.0));
  bool same=false; assert(lie_schema_equal(&d,l,r,&same,&e)==LIE_SCHEMA_OK && same); ++oracles;
  get(r,"b")->text[0]='y'; assert(lie_schema_equal(&d,l,r,&same,&e)==LIE_SCHEMA_OK && !same); ++oracles;
  node *root=obj(&a),*array=arr(&a),*nul=str(&a,"nul");
  field(root,"a/b~c",l); field(root,"",r); field(root,"arr",array); add(root,"x\0y",3,nul); add(array,NULL,0,l); add(array,NULL,0,r);
  const char *refs[]={"#","#/a~1b~0c","#/","#/arr/00","#/arr/1"}; node *expected[]={root,l,r,l,r};
  for (size_t i=0;i<5;++i) { lie_schema_node out=NULL; assert(lie_schema_reference(&d,root,str(&a,refs[i]),&out,&e)==LIE_SCHEMA_OK && out==expected[i]); ++oracles; }
  lie_schema_node out=NULL; assert(lie_schema_reference(&d,root,make(&a,LIE_SCHEMA_STRING,"#/x\0y",5,0),&out,&e)==LIE_SCHEMA_OK && out==nul); ++oracles;
  const char *bad[]={"","http://x","#x","#/a~","#/a~2","#/arr/2","#/arr/-1","#/arr/+0","#/arr/184467440737095516160","#/missing"};
  for (size_t i=0;i<10;++i) { out=l; assert(lie_schema_reference(&d,root,str(&a,bad[i]),&out,&e)==LIE_SCHEMA_INVALID && out==l); ++oracles; }
  node *deep_l=num(&a,1),*deep_r=num(&a,1);
  for (size_t i=0;i<4096;++i) { node *x=arr(&a),*y=arr(&a); add(x,NULL,0,deep_l); add(y,NULL,0,deep_r); deep_l=x; deep_r=y; }
  assert(lie_schema_equal(&d,deep_l,deep_r,&same,&e)==LIE_SCHEMA_OK && same); ++oracles;
  node *wide_l=num(&a,1),*wide_r=num(&a,1);
  for (size_t i=0;i<100;++i) {
    node *x=arr(&a),*y=arr(&a); add(x,NULL,0,num(&a,2)); add(y,NULL,0,num(&a,2));
    add(x,NULL,0,wide_l); add(y,NULL,0,wide_r); wide_l=x; wide_r=y;
  }
  m.calls=0; assert(lie_schema_equal(&d,wide_l,wide_r,&same,&e)==LIE_SCHEMA_OK && same); ++oracles;
  const size_t allocations=m.calls;
  for (size_t i=1;i<=allocations;++i) {
    m.calls=0; m.fail_at=i; same=false;
    assert(lie_schema_equal(&d,wide_l,wide_r,&same,&e)==LIE_SCHEMA_RESOURCE && !same && !m.live && !m.bytes); ++allocation_refusals;
  }
  assert(!m.live && !m.bytes); clear(&a);
}
static void conjunction_oracles(void) {
  arena a={0}; node *root=obj(&a);
  for (unsigned i=0;i<20;++i) for (unsigned j=0;j<20;++j) {
    node *l=schema(&a,"integer"),*r=schema(&a,"number"); field(l,"minimum",num(&a,i)); field(r,"minimum",num(&a,j));
    field(l,"maximum",num(&a,40-i)); field(r,"maximum",num(&a,40-j)); node *v=joined(&a,root,l,r);
    node *type=get(v,"type"); assert(type && type->value.kind==LIE_SCHEMA_STRING);
    assert(!strcmp(type->text,"integer")); assert(get(v,"minimum")->value.number==(i>j?i:j)); assert(get(v,"maximum")->value.number==40-(i>j?i:j)); oracles+=3;
  }
  node *l=schema(&a,"integer"),*r=schema(&a,"integer"),*le=arr(&a),*re=arr(&a),*lr=arr(&a),*rr=arr(&a);
  add(le,NULL,0,num(&a,1)); add(le,NULL,0,num(&a,2)); add(le,NULL,0,num(&a,2)); add(re,NULL,0,num(&a,2)); add(re,NULL,0,num(&a,3));
  field(l,"enum",le); field(r,"enum",re); node *v=joined(&a,root,l,r); assert(get(v,"enum")->value.count==2); ++oracles;
  add(lr,NULL,0,str(&a,"a")); add(rr,NULL,0,str(&a,"b")); add(rr,NULL,0,str(&a,"b")); field(l,"required",lr); field(r,"required",rr);
  v=joined(&a,root,l,r); assert(get(v,"required")->value.count==3 && lr->value.count==1); ++oracles;
  node *p=schema(&a,"string"),*q=schema(&a,"string"); field(p,"pattern",str(&a,"a")); field(q,"pattern",str(&a,"b"));
  v=joined(&a,root,p,q); assert(!strcmp(get(v,"pattern")->text,"(?=[\\s\\S]*(?:a))(?=[\\s\\S]*(?:b))")); ++oracles;
  node *any=obj(&a),*branches=arr(&a); add(branches,NULL,0,schema(&a,"string")); add(branches,NULL,0,schema(&a,"integer")); field(any,"anyOf",branches);
  v=joined(&a,root,any,schema(&a,"number")); assert(get(v,"anyOf")->value.count==1 && !strcmp(get(get(v,"anyOf")->edges[0].value,"type")->text,"integer")); ++oracles;
  node *leaf_any=obj(&a),*leaf_branches=arr(&a),*empty_leaf=schema(&a,"integer"),*live_leaf=schema(&a,"integer"),*target_leaf=schema(&a,"integer");
  field(empty_leaf,"multipleOf",num(&a,0)); field(live_leaf,"multipleOf",num(&a,2)); field(target_leaf,"multipleOf",num(&a,3));
  add(leaf_branches,NULL,0,empty_leaf); add(leaf_branches,NULL,0,live_leaf); field(leaf_any,"anyOf",leaf_branches);
  v=joined(&a,root,leaf_any,target_leaf); assert(get(v,"anyOf")->value.count==1 && get(get(v,"anyOf")->edges[0].value,"multipleOf")->value.number==6); ++oracles;
  node *defs=obj(&a),*base=schema(&a,"integer"),*ref=obj(&a); field(base,"minimum",num(&a,3)); field(defs,"a",base); field(root,"$defs",defs); field(ref,"$ref",str(&a,"#/$defs/a"));
  v=joined(&a,root,ref,l); assert(get(v,"minimum")->value.number==3); ++oracles;
  node *lo=schema(&a,"object"),*ro=schema(&a,"object"),*lp=obj(&a),*rp=obj(&a); node *no=make(&a,LIE_SCHEMA_BOOL,NULL,0,0);
  field(lp,"x",schema(&a,"number")); field(lp,"y",schema(&a,"string")); field(rp,"x",schema(&a,"integer")); field(rp,"z",schema(&a,"boolean"));
  field(lo,"properties",lp); field(ro,"properties",rp); field(lo,"additionalProperties",no); field(ro,"additionalProperties",no);
  v=joined(&a,root,lo,ro); assert(get(v,"properties")->value.count==1 && !strcmp(get(get(get(v,"properties"),"x"),"type")->text,"integer")); ++oracles;
  lie_schema_transform_description d=description(&a,NULL); lie_schema_error e={0}; lie_schema_node out=root;
  assert(lie_schema_conjoin(&d,root,schema(&a,"string"),schema(&a,"boolean"),0,&out,&e)==LIE_SCHEMA_EMPTY && out==root); ++oracles;
  node *cycle=obj(&a); field(cycle,"$ref",str(&a,"#")); out=root;
  assert(lie_schema_conjoin(&d,cycle,cycle,obj(&a),0,&out,&e)==LIE_SCHEMA_INVALID && out==root && !strcmp(e.message,"schema intersection exceeds its reference budget")); ++oracles;
  node *invalid=obj(&a); add(invalid,"bad\0key",7,num(&a,1)); assert(lie_schema_keys(&d,invalid,&e)==LIE_SCHEMA_INVALID && e.detail.size==7); ++oracles;
  /* Upstream conjunction reads object members only. Full schema admission
   * remains the visitor's job; malformed arrays must not invent properties. */
  node *bad_properties=obj(&a),*bad_members=arr(&a); add(bad_members,NULL,0,num(&a,1)); field(bad_properties,"properties",bad_members);
  v=joined(&a,root,obj(&a),bad_properties); assert(get(v,"properties")->value.kind==LIE_SCHEMA_OBJECT && !get(v,"properties")->value.count); ++oracles;
  clear(&a);
}
static void faults_and_limits(void) {
  arena input={0}; node *root=obj(&input),*l=schema(&input,"string"),*r=schema(&input,"string");
  field(l,"pattern",str(&input,"left")); field(r,"pattern",str(&input,"right"));
  field(l,"format",str(&input,"alpha")); field(r,"format",str(&input,"beta"));
  field(l,"multipleOf",num(&input,6)); field(r,"multipleOf",num(&input,8));
  node *lt=arr(&input),*rt=arr(&input); add(lt,NULL,0,str(&input,"string")); add(lt,NULL,0,str(&input,"null")); add(rt,NULL,0,str(&input,"string")); add(rt,NULL,0,str(&input,"null"));
  /* Different type-array order forces nested equality storage. */
  rt->edges[0].value=str(&input,"null"); rt->edges[1].value=str(&input,"string"); field(l,"type",lt); field(r,"type",rt);
  arena staging={0}; memory m={0}; lie_schema_transform_description d=description(&staging,&m); lie_schema_node out=NULL; lie_schema_error e={0};
  assert(lie_schema_conjoin(&d,root,l,r,0,&out,&e)==LIE_SCHEMA_OK); const size_t callbacks=staging.calls,allocations=m.calls; clear(&staging); assert(!m.live);
  for (size_t i=1;i<=callbacks;++i) {
    staging=(arena){.fail_at=i}; m=(memory){0}; d=description(&staging,&m); out=root;
    assert(lie_schema_conjoin(&d,root,l,r,0,&out,&e)==LIE_SCHEMA_CALLBACK && out==root && !m.live && !m.bytes); ++callback_refusals; clear(&staging);
  }
  for (size_t i=1;i<=allocations;++i) {
    staging=(arena){0}; m=(memory){.fail_at=i}; d=description(&staging,&m); out=root;
    assert(lie_schema_conjoin(&d,root,l,r,0,&out,&e)==LIE_SCHEMA_RESOURCE && out==root && !m.live && !m.bytes); ++allocation_refusals; clear(&staging);
  }
  staging=(arena){0}; m=(memory){.fail_at=1}; d=description(&staging,&m); node *ref=str(&input,"#/type"); out=root;
  assert(lie_schema_reference(&d,l,ref,&out,&e)==LIE_SCHEMA_RESOURCE && out==root && !m.live); ++allocation_refusals;
  m=(memory){0}; d=description(&staging,&m); d.max_work=1; out=root;
  assert(lie_schema_conjoin(&d,root,l,r,0,&out,&e)==LIE_SCHEMA_WORK_LIMIT && out==root); ++oracles;
  d=description(&staging,&m); d.max_pairs=1; bool same=true;
  assert(lie_schema_equal(&d,lt,rt,&same,&e)==LIE_SCHEMA_WORK_LIMIT && same); ++oracles;
  d=description(&staging,&m); d.abi_version++; assert(lie_schema_keys(&d,l,&e)==LIE_SCHEMA_INVALID); ++oracles;
  d=description(&staging,&m); d.allocator.release=NULL; assert(lie_schema_keys(&d,l,&e)==LIE_SCHEMA_INVALID); ++oracles;
  d=description(&staging,&m); d.access.describe=invalid_describe;
  same=true; assert(lie_schema_equal(&d,l,r,&same,&e)==LIE_SCHEMA_INVALID && same); ++oracles;
  assert(!strcmp(get(l,"pattern")->text,"left") && !strcmp(get(r,"pattern")->text,"right")); ++oracles;
  clear(&staging); clear(&input);
}
int main(void) {
  equality_and_references(); conjunction_oracles(); faults_and_limits();
  printf("SCHEMA_TREE_ORACLES=%zu CALLBACK_REFUSALS=%zu OWN_ALLOCATOR_REFUSALS=%zu ITERATIVE_EQUAL_DEPTH=4096 HOST_NOT_INFERENCE\n",oracles,callback_refusals,allocation_refusals);
  return 0;
}
