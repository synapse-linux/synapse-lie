/* SPDX-License-Identifier: MIT */
/* Independent numeric control oracles and exhaustive selected hook refusals.
 * The codec is an explicit dictionary fixture, not production serialization. */
#include "lie/schema_number.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct node node;
struct node { lie_schema_value value; const char *keys[5]; const node *children[5]; };
typedef struct {
  size_t callbacks, refuse_callback, allocations, refuse_allocation, live;
  unsigned bad_serialization;
  bool wrong_parse, infinite_parse;
} fixture;
static size_t oracles, callback_refusals, allocation_refusals;
static const struct { double value; const char *text, *common; } dictionary[] = {
  {0,"0","0e0"}, {0.1,"0.1","1e-1"}, {0.15,"0.15","15e-2"},
  {0.2,"0.2","2e-1"}, {0.3,"0.3","3e-1"}, {0.6,"0.6","6e-1"},
  {1,"1","1e0"}, {1.2,"1.2","12e-1"}, {1.5,"1.5","15e-1"},
  {2,"2","2e0"}, {3,"3","3e0"}, {4,"4","4e0"},
  {-1,"-1",NULL}, {-2,"-2",NULL}, {-0.3,"-0.3",NULL}
};
static bool refused(fixture *f) { return ++f->callbacks == f->refuse_callback; }
static void *allocate(void *p, size_t bytes) {
  fixture *f=p;
  if (++f->allocations == f->refuse_allocation) return NULL;
  void *out=malloc(bytes); assert(out); ++f->live; return out;
}
static void release(void *p, void *value) {
  fixture *f=p; assert(f->live && value); --f->live; free(value);
}
static lie_schema_status describe(void *p, lie_schema_node value, lie_schema_value *out) {
  if (refused(p)) return LIE_SCHEMA_CALLBACK;
  *out=((const node *)value)->value; return LIE_SCHEMA_OK;
}
static lie_schema_status child(void *p, lie_schema_node value, size_t at,
    lie_schema_bytes *key, lie_schema_node *out) {
  if (refused(p)) return LIE_SCHEMA_CALLBACK;
  const node *n=value; assert(at<n->value.count);
  *key=(lie_schema_bytes){n->keys[at],strlen(n->keys[at])};
  *out=n->children[at]; return LIE_SCHEMA_OK;
}
static lie_schema_status serialize(void *p, double value, char *text, size_t capacity, size_t *bytes) {
  fixture *f=p;
  if (refused(f)) return LIE_SCHEMA_CALLBACK;
  if (f->bad_serialization) { *bytes=f->bad_serialization==1 ? 0 : capacity+1; return LIE_SCHEMA_OK; }
  const char *spelling=NULL;
  if (value==0 && signbit(value)) spelling="-0";
  else for (size_t i=0;i<sizeof(dictionary)/sizeof(*dictionary);++i)
    if (value==dictionary[i].value) { spelling=dictionary[i].text; break; }
  assert(spelling && strlen(spelling)<=capacity);
  *bytes=strlen(spelling); memcpy(text,spelling,*bytes); return LIE_SCHEMA_OK;
}
static lie_schema_status parse(void *p, lie_schema_bytes text, double *out) {
  fixture *f=p;
  if (refused(f)) return LIE_SCHEMA_CALLBACK;
  if (f->infinite_parse) { *out=INFINITY; return LIE_SCHEMA_OK; }
  if (f->wrong_parse) { *out=2; return LIE_SCHEMA_OK; }
  for (size_t i=0;i<sizeof(dictionary)/sizeof(*dictionary);++i) {
    const char *common=dictionary[i].common;
    if (common && strlen(common)==text.size && !memcmp(common,text.data,text.size)) {
      *out=dictionary[i].value; return LIE_SCHEMA_OK;
    }
  }
  assert(!"Unexpected dictionary parse input"); return LIE_SCHEMA_CALLBACK;
}
static lie_schema_number_description description(fixture *f) {
  lie_schema_number_description d; lie_schema_number_description_init(&d);
  d.transform.access.context=f; d.transform.access.describe=describe;
  d.transform.access.child=child;
  d.transform.allocator=(lie_grammar_allocator){f,allocate,release};
  d.conversion_context=f; d.serialize=serialize; d.parse=parse; return d;
}
static node number(double value) {
  node out={0}; out.value.kind=LIE_SCHEMA_NUMBER; out.value.number=value; return out;
}
static node object(void) { node out={0}; out.value.kind=LIE_SCHEMA_OBJECT; return out; }
static void field(node *parent, const char *name, const node *value) {
  size_t at=parent->value.count++; assert(at<5);
  parent->keys[at]=name; parent->children[at]=value;
}
static void constraints(void) {
  const char *keys[] = {"minimum","maximum","exclusiveMinimum","exclusiveMaximum","multipleOf"};
  for (size_t k=0;k<5;++k) for (unsigned bad=0;bad<4;++bad) {
    fixture f={0}; lie_schema_number_description d=description(&f);
    node schema=object(), value=number(bad==0 ? NAN : bad==1 ? INFINITY : -INFINITY);
    if (bad==3) value.value.kind=LIE_SCHEMA_STRING;
    field(&schema,keys[k],&value); lie_number_policy *out=(lie_number_policy *)&schema;
    lie_schema_error e={0};
    assert(lie_schema_number_create(&d,&schema,false,&out,&e)==LIE_SCHEMA_INVALID);
    assert(out==(lie_number_policy *)&schema && e.message && !strcmp(e.suffix," must be a finite number"));
    assert(e.detail.size==strlen(keys[k]) && !memcmp(e.detail.data,keys[k],e.detail.size));
    assert(!f.live); ++oracles;
  }
  for (unsigned i=0;i<3;++i) {
    fixture f={0}; lie_schema_number_description d=description(&f);
    node schema=object(), zero=number(i==0 ? 0 : i==1 ? -0.0 : -1);
    field(&schema,"multipleOf",&zero); lie_number_policy *out=NULL; lie_schema_error e={0};
    assert(lie_schema_number_create(&d,&schema,false,&out,&e)==LIE_SCHEMA_INVALID && !out);
    assert(!strcmp(e.message,"multipleOf must be positive")); ++oracles;
  }
  fixture f={0}; lie_schema_number_description d=description(&f);
  node schema=object(), low=number(1), high=number(2), step=number(0.3);
  field(&schema,"minimum",&low); field(&schema,"maximum",&high); field(&schema,"multipleOf",&step);
  lie_number_policy *policy=NULL; lie_schema_error e={0};
  assert(lie_schema_number_create(&d,&schema,false,&policy,&e)==LIE_SCHEMA_OK);
  const double values[]={0.6,1,1.2,1.5,2}; const bool expected[]={false,false,true,true,false};
  for (size_t i=0;i<5;++i) {
    node value=number(values[i]); bool accepted=!expected[i];
    assert(lie_schema_number_accept(&d,policy,&value,&accepted,&e)==LIE_SCHEMA_OK && accepted==expected[i]); ++oracles;
  }
  node other=object(); bool accepted=true;
  assert(lie_schema_number_accept(&d,policy,&other,&accepted,&e)==LIE_SCHEMA_OK && !accepted); ++oracles;
  lie_number_release(policy); assert(!f.live);
  low.value.number=3; policy=NULL;
  assert(lie_schema_number_create(&d,&schema,false,&policy,&e)==LIE_SCHEMA_EMPTY && !policy);
  assert(!strcmp(e.message,"numeric constraints describe an empty interval")); ++oracles;
  low.value.number=1; high.value.number=1.2; step.value.number=0.6;
  assert(lie_schema_number_create(&d,&schema,true,&policy,&e)==LIE_SCHEMA_EMPTY && !policy);
  assert(!strcmp(e.message,"numeric constraints contain no multipleOf value")); ++oracles;
  schema=object(); field(&schema,"minimum",&low); field(&schema,"exclusiveMinimum",&high);
  assert(lie_schema_number_create(&d,&schema,false,&policy,&e)==LIE_SCHEMA_OK);
  node value=number(1.2); accepted=true;
  assert(lie_schema_number_accept(&d,policy,&value,&accepted,&e)==LIE_SCHEMA_OK && !accepted);
  value.value.number=1.5;
  assert(lie_schema_number_accept(&d,policy,&value,&accepted,&e)==LIE_SCHEMA_OK && accepted);
  oracles+=2; lie_number_release(policy); assert(!f.live);
}
static void intersections(void) {
  const double left[]={0.1,0.2,0.15,1.2}, right[]={0.3,0.3,0.2,0.3}, expected[]={0.3,0.6,0.6,1.2};
  for (size_t i=0;i<4;++i) {
    fixture f={0}; lie_schema_number_description d=description(&f);
    node a=number(left[i]), b=number(right[i]); double out=-123; lie_schema_error e={0};
    assert(lie_schema_number_intersect(&d,&a,&b,&out,&e)==LIE_SCHEMA_OK && out==expected[i]);
    assert(!f.live); ++oracles;
  }
  fixture f={0}; lie_schema_number_description d=description(&f);
  node a=number(0.1), b=number(0.3); lie_schema_error e={0}; double out=-123;
  f.wrong_parse=true;
  assert(lie_schema_number_intersect(&d,&a,&b,&out,&e)==LIE_SCHEMA_INVALID && out==-123);
  assert(!strcmp(e.message,"combined multipleOf exceeds the exact schema-number range")); ++oracles;
  f.wrong_parse=false; f.infinite_parse=true;
  assert(lie_schema_number_intersect(&d,&a,&b,&out,&e)==LIE_SCHEMA_INVALID && out==-123 && !f.live); ++oracles;
  f.infinite_parse=false;
  for (size_t i=0;i<4;++i) {
    a=number(i==0 ? 0 : i==1 ? -1 : INFINITY);
    if (i==3) a.value.kind=LIE_SCHEMA_BOOL;
    assert(lie_schema_number_intersect(&d,&a,&b,&out,&e)==LIE_SCHEMA_INVALID && out==-123);
    assert(!strcmp(e.message,"multipleOf must be a positive finite number")); ++oracles;
  }
}
static bool completes(lie_grammar_program *program, const char *text) {
  lie_grammar_state *state=NULL;
  assert(lie_grammar_start(program,&state)==LIE_GRAMMAR_OK);
  for (size_t i=0;i<strlen(text);++i) {
    lie_grammar_state *next=NULL;
    assert(lie_grammar_advance(program,state,(uint8_t)text[i],&next)==LIE_GRAMMAR_OK);
    lie_grammar_state_release(state); state=next;
  }
  bool out=lie_grammar_complete(state); lie_grammar_state_release(state); return out;
}
static void literals(void) {
  const double values[]={-0.0,0.3,1.2}; const char *spellings[]={"-0","0.3","1.2"};
  for (size_t i=0;i<3;++i) {
    fixture f={0}; lie_schema_number_description d=description(&f);
    lie_builder_description bd; lie_builder_description_init(&bd);
    bd.allocator=d.transform.allocator; lie_grammar_builder *builder=NULL;
    assert(lie_builder_create(&bd,&builder)==LIE_BUILDER_OK);
    node value=number(values[i]); uint32_t id=UINT32_MAX; lie_schema_error e={0};
    assert(lie_schema_number_literal(&d,&value,builder,&id,&e)==LIE_SCHEMA_OK);
    lie_grammar_description grammar;
    assert(lie_builder_finish(builder,id,0,&grammar)==LIE_BUILDER_OK);
    lie_grammar_program *program=NULL;
    assert(lie_grammar_program_create(&grammar,&program)==LIE_GRAMMAR_OK);
    lie_builder_release(builder);
    assert(completes(program,spellings[i]) && !completes(program,"0.2") && !completes(program,""));
    lie_grammar_program_release(program); assert(!f.live); oracles+=3;
  }
  fixture f={0}; lie_schema_number_description d=description(&f);
  lie_builder_description bd; lie_builder_description_init(&bd);
  lie_grammar_builder *builder=NULL; assert(lie_builder_create(&bd,&builder)==LIE_BUILDER_OK);
  node value=object(); uint32_t id=UINT32_MAX; lie_schema_error e={0};
  assert(lie_schema_number_literal(&d,&value,builder,&id,&e)==LIE_SCHEMA_INVALID && id==UINT32_MAX);
  assert(!strcmp(e.message,"numeric literal requires a number")); ++oracles;
  value=number(INFINITY);
  assert(lie_schema_number_literal(&d,&value,builder,&id,&e)==LIE_SCHEMA_INVALID && id==UINT32_MAX);
  assert(!strcmp(e.message,"JSON numbers must be finite")); ++oracles;
  lie_builder_release(builder);
}
/* Every callback and every allocator call of each selected successful route
 * is refused independently. Setup callbacks/allocations are counted apart. */
static void refusals(void) {
  for (unsigned route=0;route<4;++route) for (unsigned which=0;which<2;++which) {
    size_t sites=0;
    for (size_t at=0;at<=sites;++at) {
      fixture f={0}; lie_schema_number_description d=description(&f);
      node schema=object(), step=number(0.1), value=number(0.3);
      field(&schema,"multipleOf",&step);
      lie_number_policy *policy=NULL, *output=(lie_number_policy *)&schema;
      lie_grammar_builder *builder=NULL;
      lie_builder_description bd; lie_builder_description_init(&bd);
      bd.allocator=d.transform.allocator;
      lie_schema_error e={0}; bool accepted=false; double result=-123; uint32_t id=UINT32_MAX;
      if (route==1) assert(lie_schema_number_create(&d,&schema,false,&policy,&e)==LIE_SCHEMA_OK);
      if (route==3) assert(lie_builder_create(&bd,&builder)==LIE_BUILDER_OK);
      const size_t setup_calls=f.callbacks, setup_allocations=f.allocations;
      if (at && which==0) f.refuse_callback=setup_calls+at;
      if (at && which==1) f.refuse_allocation=setup_allocations+at;
      lie_schema_status rc=route==0 ? lie_schema_number_create(&d,&schema,false,&output,&e) :
        route==1 ? lie_schema_number_accept(&d,policy,&value,&accepted,&e) :
        route==2 ? lie_schema_number_intersect(&d,&step,&value,&result,&e) :
        lie_schema_number_literal(&d,&value,builder,&id,&e);
      if (!at) {
        assert(rc==LIE_SCHEMA_OK);
        sites=which==0 ? f.callbacks-setup_calls : f.allocations-setup_allocations;
        if (route==0) lie_number_release(output);
        if (route==1) assert(accepted);
        if (route==2) assert(result==0.3);
      } else {
        assert(rc==(which==0 ? LIE_SCHEMA_CALLBACK : LIE_SCHEMA_RESOURCE));
        assert(route!=0 || output==(lie_number_policy *)&schema);
        assert(route!=1 || !accepted); assert(route!=2 || result==-123);
        assert(route!=3 || id==UINT32_MAX);
        if (which==0) ++callback_refusals; else ++allocation_refusals;
      }
      lie_number_release(policy); lie_builder_release(builder); assert(!f.live);
    }
  }
}
static void contracts(void) {
  fixture f={0}; lie_schema_number_description d=description(&f);
  node schema=object(), value=number(0.3); lie_schema_error e={0}; lie_number_policy *policy=NULL;
  lie_schema_number_description bad=d; bad.abi_version++;
  assert(lie_schema_number_create(&bad,&schema,false,&policy,&e)==LIE_SCHEMA_INVALID);
  bad=d; bad.struct_bytes--; assert(lie_schema_number_create(&bad,&schema,false,&policy,&e)==LIE_SCHEMA_INVALID);
  bad=d; bad.transform.allocator.release=NULL; assert(lie_schema_number_create(&bad,&schema,false,&policy,&e)==LIE_SCHEMA_INVALID);
  bad=d; bad.serialize=NULL; assert(lie_schema_number_create(&bad,&schema,false,&policy,&e)==LIE_SCHEMA_INVALID);
  assert(lie_schema_number_create(&d,NULL,false,&policy,&e)==LIE_SCHEMA_INVALID);
  assert(lie_schema_number_create(&d,&schema,false,NULL,&e)==LIE_SCHEMA_INVALID);
  assert(lie_schema_number_create(&d,&schema,false,&policy,&e)==LIE_SCHEMA_OK);
  bool accepted=false;
  for (unsigned i=1;i<=2;++i) {
    f.bad_serialization=i;
    assert(lie_schema_number_accept(&d,policy,&value,&accepted,&e)==LIE_SCHEMA_INVALID && !accepted);
  }
  f.bad_serialization=0; value.value.number=NAN;
  assert(lie_schema_number_accept(&d,policy,&value,&accepted,&e)==LIE_SCHEMA_INVALID && !accepted);
  assert(!strcmp(e.message,"JSON numbers must be finite"));
  lie_number_release(policy); assert(!f.live);
  field(&schema,"multipleOf",&value); policy=NULL;
  value.value.number=0.1; d.transform.max_work=1;
  assert(lie_schema_number_create(&d,&schema,false,&policy,&e)==LIE_SCHEMA_WORK_LIMIT && !policy);
  d=description(&f); d.number_work=1;
  assert(lie_schema_number_create(&d,&schema,true,&policy,&e)==LIE_SCHEMA_WORK_LIMIT && !policy && !f.live);
  lie_schema_number_description_init(NULL); oracles+=11;
}
int main(void) {
  constraints(); intersections(); literals(); refusals(); contracts();
  printf("C17 schema number: %zu independent oracles, %zu callback refusals, %zu allocation refusals; HOST_NOT_INFERENCE\n",
         oracles,callback_refusals,allocation_refusals);
}
