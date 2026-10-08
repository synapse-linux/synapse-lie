/* SPDX-License-Identifier: MIT */
/* Root admission follows independently pinned Gufo; see gufo-NOTICE. */
#include "lie/schema_root.h"
#include "schema_internal.h"
#include <string.h>

void lie_schema_root_description_init(lie_schema_root_description *d) {
  if (!d) return;
  memset(d, 0, sizeof(*d));
  d->abi_version = LIE_SCHEMA_ROOT_ABI;
  d->struct_bytes = sizeof(*d);
  d->max_references = 262144;
  lie_schema_transform_description_init(&d->reader);
  lie_schema_body_access_init(&d->visit);
}
static lie_schema_status admit(const lie_schema_root_description *d,
    lie_schema_node schema, lie_schema_error *error) {
  lie_schema_context c = {&d->reader, 0, error};
  lie_schema_memo *seen = NULL;
  lie_schema_node root = schema, reference = NULL;
  lie_schema_status rc;
#define TRY(call) do { rc = (call); if (rc) goto done; } while (0)
  for (;;) {
    TRY(lie_schema_internal_field(&c, root, "$ref", &reference));
    if (!reference) break;
    if (!seen) {
      lie_schema_memo_description md;
      lie_schema_memo_description_init(&md);
      md.max_entries = d->max_references;
      md.allocator = d->reader.allocator;
      TRY(lie_schema_memo_create(&md, &seen));
    }
    uint32_t ignored = 0;
    bool hit = false;
    TRY(lie_schema_memo_get(seen, root, &ignored, &hit));
    if (hit) {
      rc = lie_schema_internal_fail(&c, LIE_SCHEMA_INVALID,
                                    "root reference cycle");
      goto done;
    }
    rc = lie_schema_memo_assign(seen, root, 0);
    if (rc == LIE_SCHEMA_WORK_LIMIT)
      rc = lie_schema_internal_fail(&c, rc,
                                    "root reference identity limit exceeded");
    if (rc) goto done;
    TRY(lie_schema_internal_reference(&c, schema, reference, &root));
  }
  lie_schema_value value;
  TRY(lie_schema_internal_describe(&c, root, &value));
  if (value.kind != LIE_SCHEMA_OBJECT) goto invalid_root;
  lie_schema_node type = NULL, any = NULL;
  TRY(lie_schema_internal_field(&c, root, "type", &type));
  if (!type) goto invalid_root;
  TRY(lie_schema_internal_describe(&c, type, &value));
  if (value.kind != LIE_SCHEMA_STRING || value.text.size != 6 ||
      memcmp(value.text.data, "object", 6)) goto invalid_root;
  TRY(lie_schema_internal_field(&c, root, "anyOf", &any));
  if (any) goto invalid_root;
  rc = LIE_SCHEMA_OK;
  goto done;
invalid_root:
  rc = lie_schema_internal_fail(&c, LIE_SCHEMA_INVALID,
                                "the root must have type object");
done:
  lie_schema_memo_release(seen);
  return rc;
#undef TRY
}
lie_schema_status lie_schema_root_rule(const lie_schema_root_description *d,
    lie_schema_node schema, bool object_only, lie_grammar_builder *b,
    uint32_t whitespace, uint32_t *out, lie_schema_error *error) {
  if (!d || d->abi_version != LIE_SCHEMA_ROOT_ABI ||
      d->struct_bytes != sizeof(*d) || !b || !out ||
      !lie_schema_internal_valid(&d->reader) || !d->max_references ||
      d->max_references > 262144 ||
      (!object_only && (!schema || !d->visit.body ||
       d->visit.abi_version != LIE_SCHEMA_VISIT_ABI ||
       d->visit.struct_bytes != sizeof(d->visit)))) return LIE_SCHEMA_INVALID;
  uint32_t body = 0;
  lie_schema_status rc;
  if (error) *error = (lie_schema_error){0};
  if (object_only) {
    rc = lie_schema_internal_builder_error(
        lie_builder_generic_object(b, 16, &body), error);
  } else {
    rc = admit(d, schema, error);
    if (rc) return rc;
    /* Root identity scratch is already retired before external compilation. */
    if (error) *error = (lie_schema_error){0};
    rc = d->visit.body(d->visit.context, schema, 0, &body, error);
  }
  if (rc) return rc;
  const uint32_t symbols[] = {whitespace, body, whitespace};
  uint32_t result = 0;
  rc = lie_schema_internal_builder_error(
      lie_builder_sequence_make(b, symbols, 3, &result), error);
  if (rc) return rc;
  *out = result;
  return LIE_SCHEMA_OK;
}
