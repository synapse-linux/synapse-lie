/* SPDX-License-Identifier: MIT */
/* Type/keyword/route policy follows independently pinned Gufo; see NOTICE. */
#include "lie/schema_dispatch.h"
#include "schema_internal.h"
#include <string.h>
#define TRY(call) do { lie_schema_status rc_ = (call); if (rc_) return rc_; } while (0)
static bool is(lie_schema_bytes name, const char *text) {
  size_t n = strlen(text);
  return name.size == n && (!n || !memcmp(name.data, text, n));
}
static bool has(const lie_schema_dispatch_plan *p, const char *name) {
  for (size_t i = 0; i < p->count; ++i)
    if (is(p->names[i], name)) return true;
  return false;
}
enum { MINIMUM=1, MAXIMUM=2, EXCLUSIVE_MINIMUM=4, EXCLUSIVE_MAXIMUM=8,
       MULTIPLE=16, PATTERN=32, FORMAT=64, MIN_LENGTH=128, MAX_LENGTH=256 };
static unsigned constraint(lie_schema_bytes key) {
  static const char *const names[] = {"minimum", "maximum", "exclusiveMinimum",
    "exclusiveMaximum", "multipleOf", "pattern", "format", "minLength", "maxLength"};
  for (unsigned i=0; i<sizeof(names)/sizeof(*names); ++i)
    if (is(key,names[i])) return 1u<<i;
  return 0;
}
lie_schema_status lie_schema_dispatch_types(
    const lie_schema_transform_description *d, lie_schema_node schema,
    lie_schema_dispatch_plan *out, lie_schema_error *error) {
  if (!lie_schema_internal_valid(d) || !schema || !out) return LIE_SCHEMA_INVALID;
  lie_schema_context c={d,0,error};
  lie_schema_value v;
  TRY(lie_schema_internal_describe(&c,schema,&v));
  if (v.kind != LIE_SCHEMA_OBJECT)
    return lie_schema_internal_fail(&c,LIE_SCHEMA_INVALID,"each schema must be an object");
  lie_schema_node type=NULL;
  TRY(lie_schema_internal_field(&c,schema,"type",&type));
  lie_schema_dispatch_plan p={.abi_version=LIE_SCHEMA_DISPATCH_ABI,.struct_bytes=sizeof(p)};
  if (type) {
    lie_schema_value t;
    TRY(lie_schema_internal_describe(&c,type,&t));
    if (t.kind==LIE_SCHEMA_STRING) { p.count=1; p.names[0]=t.text; }
    else if (t.kind==LIE_SCHEMA_ARRAY && t.count && t.count<=2) {
      p.count=t.count;
      for (size_t i=0; i<t.count; ++i) {
        lie_schema_bytes ignored; lie_schema_node n;
        TRY(lie_schema_internal_child(&c,type,i,&ignored,&n));
        lie_schema_value item;
        TRY(lie_schema_internal_describe(&c,n,&item));
        if (item.kind!=LIE_SCHEMA_STRING)
          return lie_schema_internal_fail(&c,LIE_SCHEMA_INVALID,"type members must be strings");
        p.names[i]=item.text;
      }
      if (p.count==2 && ((unsigned)is(p.names[0],"null")+(unsigned)is(p.names[1],"null"))!=1)
        return lie_schema_internal_fail(&c,LIE_SCHEMA_INVALID,"type unions must be nullable; use anyOf otherwise");
    }
  }
  if (!p.count)
    return lie_schema_internal_fail(&c,LIE_SCHEMA_INVALID,"type must be a string or nullable type array");
  const bool object=has(&p,"object"), array=has(&p,"array");
  const bool numeric=has(&p,"integer") || has(&p,"number"), string=has(&p,"string");
  unsigned flags=0;
  for (size_t i=0; i<v.count; ++i) {
    lie_schema_bytes key; lie_schema_node ignored;
    TRY(lie_schema_internal_child(&c,schema,i,&key,&ignored));
    TRY(lie_schema_internal_tick(&c,key.size));
    if ((is(key,"properties") || is(key,"required") || is(key,"additionalProperties")) && !object)
      return lie_schema_internal_fail(&c,LIE_SCHEMA_INVALID,"object keyword on a non-object schema");
    if ((is(key,"items") || is(key,"minItems") || is(key,"maxItems")) && !array)
      return lie_schema_internal_fail(&c,LIE_SCHEMA_INVALID,"array keyword on a non-array schema");
    const unsigned flag=constraint(key); flags|=flag;
    if ((flag & (MINIMUM|MAXIMUM|EXCLUSIVE_MINIMUM|EXCLUSIVE_MAXIMUM|MULTIPLE)) && !numeric)
      return lie_schema_internal_fail(&c,LIE_SCHEMA_INVALID,"numeric constraint on a non-numeric schema");
    if ((flag & (PATTERN|FORMAT|MIN_LENGTH|MAX_LENGTH)) && !string)
      return lie_schema_internal_fail(&c,LIE_SCHEMA_INVALID,"string constraint on a non-string schema");
  }
  for (size_t i=0; i<p.count; ++i) {
    lie_schema_bytes name=p.names[i];
    if (is(name,"object")) p.routes[i]=LIE_SCHEMA_ROUTE_OBJECT;
    else if (is(name,"array")) p.routes[i]=LIE_SCHEMA_ROUTE_ARRAY;
    else if (is(name,"integer")) p.routes[i]=(flags&MULTIPLE) ? LIE_SCHEMA_ROUTE_INTEGER_LEXEME : LIE_SCHEMA_ROUTE_INTEGER;
    else if (is(name,"number") && (flags&(MINIMUM|MAXIMUM|EXCLUSIVE_MINIMUM|EXCLUSIVE_MAXIMUM|MULTIPLE))) p.routes[i]=LIE_SCHEMA_ROUTE_NUMBER_LEXEME;
    else if (is(name,"string") && (flags&(PATTERN|FORMAT|MIN_LENGTH|MAX_LENGTH))) p.routes[i]=LIE_SCHEMA_ROUTE_STRING_LEXEME;
    else p.routes[i]=LIE_SCHEMA_ROUTE_PRIMITIVE;
  }
  *out=p; return LIE_SCHEMA_OK;
}
static lie_schema_status builder_error(lie_builder_status rc, lie_schema_error *e) {
  const char *message="invalid C17 grammar construction";
  lie_schema_status status=LIE_SCHEMA_INVALID;
  switch (rc) {
  case LIE_BUILDER_OK: return LIE_SCHEMA_OK;
  case LIE_BUILDER_RESOURCE: status=LIE_SCHEMA_RESOURCE; break;
  case LIE_BUILDER_RULE_LIMIT: message="compiled grammar exceeds the rule limit"; break;
  case LIE_BUILDER_CYCLE: message="reference cycle does not consume input"; break;
  case LIE_BUILDER_EMPTY: status=LIE_SCHEMA_EMPTY; message="schema has no finite value"; break;
  case LIE_BUILDER_WORK_LIMIT: status=LIE_SCHEMA_WORK_LIMIT; message="construction work limit exceeded"; break;
  default: break;
  }
  if (e) *e=(lie_schema_error){message,{NULL,0},""};
  return status;
}
lie_schema_status lie_schema_dispatch_rules(
    const lie_schema_dispatch_plan *p, lie_schema_node schema, size_t depth,
    lie_grammar_builder *b, lie_schema_rule_access access, uint32_t *out,
    lie_schema_error *e) {
  if (!p || p->abi_version!=LIE_SCHEMA_DISPATCH_ABI || p->struct_bytes!=sizeof(*p) ||
      !p->count || p->count>2 || !schema || !b || !access.rule || !out) return LIE_SCHEMA_INVALID;
  for (size_t i=0; i<p->count; ++i)
    if ((p->names[i].size && !p->names[i].data) || (unsigned)p->routes[i]>LIE_SCHEMA_ROUTE_STRING_LEXEME)
      return LIE_SCHEMA_INVALID;
  uint32_t rules[2];
  for (size_t i=0; i<p->count; ++i) {
    const lie_schema_status rc=access.rule(access.context,schema,depth,p->routes[i],p->names[i],&rules[i]);
    if (rc) { if (e) *e=(lie_schema_error){0}; return rc; }
  }
  uint32_t result;
  TRY(builder_error(lie_builder_alternatives(b,rules,p->count,&result),e));
  *out=result; return LIE_SCHEMA_OK;
}
