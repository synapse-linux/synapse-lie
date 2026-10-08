/* SPDX-License-Identifier: MIT */
/* Visit sequencing follows independently pinned Gufo; see gufo-NOTICE. */
#include "lie/schema_visit.h"
#include "schema_internal.h"
#include <string.h>
void lie_schema_body_access_init(lie_schema_body_access *access) {
  if (!access) return;
  memset(access,0,sizeof(*access));
  access->abi_version=LIE_SCHEMA_VISIT_ABI;
  access->struct_bytes=sizeof(*access);
}
lie_schema_status lie_schema_visit_rule(lie_schema_memo *memo,
    lie_grammar_builder *builder, lie_schema_node schema, size_t depth,
    lie_schema_body_access access, uint32_t *out, lie_schema_error *error) {
  if (!memo || !builder || !schema || !out ||
      access.abi_version!=LIE_SCHEMA_VISIT_ABI ||
      access.struct_bytes!=sizeof(access) || !access.body) return LIE_SCHEMA_INVALID;
  uint32_t id=0; bool hit=false;
  lie_schema_status rc=lie_schema_memo_get(memo,schema,&id,&hit);
  if (rc) return rc;
  if (hit) { *out=id; return LIE_SCHEMA_OK; }
  rc=lie_schema_internal_builder_error(lie_builder_new(builder,NULL,0,&id),error);
  if (rc) return rc;
  rc=lie_schema_memo_assign(memo,schema,id);
  if (rc) {
    if (rc==LIE_SCHEMA_WORK_LIMIT) {
      if (error) *error=(lie_schema_error){"compiled grammar exceeds the rule limit",{NULL,0},""};
      return LIE_SCHEMA_INVALID;
    }
    return rc;
  }
  uint32_t body=0;
  if (error) *error=(lie_schema_error){0};
  rc=access.body(access.context,schema,depth,&body,error);
  if (rc!=LIE_SCHEMA_OK && rc!=LIE_SCHEMA_EMPTY) return rc;
  if (error) *error=(lie_schema_error){0};
  const lie_builder_sequence sequence={&body,1};
  const lie_builder_status status=lie_builder_set(builder,id,
      rc==LIE_SCHEMA_EMPTY?NULL:&sequence,rc==LIE_SCHEMA_EMPTY?0:1);
  rc=lie_schema_internal_builder_error(status,error);
  if (rc) return rc;
  *out=id; return LIE_SCHEMA_OK;
}
