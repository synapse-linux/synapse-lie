/* SPDX-License-Identifier: MIT */
/* Numeric leaf control adapted from the independently pinned MIT Gufo
 * json_schema_lexeme.cpp. Binary64 conversion uses a declared C17 codec hook;
 * ordered schema/finite/grid/LCM publication policy belongs to this C17 core. */
#include "lie/schema_number.h"
#include "schema_internal.h"
#include <math.h>
#include <string.h>

#define TRY(call) do { lie_schema_status rc_ = (call); if (rc_ != LIE_SCHEMA_OK) return rc_; } while (0)
typedef lie_schema_context context;
static lie_schema_status fail(context *c, lie_schema_status status, const char *message) {
  return lie_schema_internal_fail(c, status, message);
}
static bool valid(const lie_schema_number_description *d) {
  return d && d->abi_version == LIE_SCHEMA_NUMBER_ABI &&
    d->struct_bytes == sizeof(*d) && lie_schema_internal_valid(&d->transform) &&
    d->serialize;
}
static lie_schema_status numeric(context *c, lie_number_status status) {
  switch (status) {
  case LIE_NUMBER_OK: return LIE_SCHEMA_OK;
  case LIE_NUMBER_RESOURCE: return fail(c, LIE_SCHEMA_RESOURCE, "numeric allocation failed");
  case LIE_NUMBER_EMPTY_INTERVAL:
    return fail(c, LIE_SCHEMA_EMPTY, "numeric constraints describe an empty interval");
  case LIE_NUMBER_EMPTY_GRID:
    return fail(c, LIE_SCHEMA_EMPTY, "numeric constraints contain no multipleOf value");
  case LIE_NUMBER_WORK_LIMIT:
    return fail(c, LIE_SCHEMA_WORK_LIMIT, "numeric work limit exceeded");
  default:
    return fail(c, LIE_SCHEMA_INVALID, "invalid exact-decimal numeric constraint");
  }
}
static lie_schema_status spelling(const lie_schema_number_description *d,
    context *c, double value, char *text, lie_number_text *out) {
  if (!isfinite(value)) return fail(c, LIE_SCHEMA_INVALID, "JSON numbers must be finite");
  TRY(lie_schema_internal_tick(c, 1));
  size_t bytes = 0;
  TRY(d->serialize(d->conversion_context, value, text,
                   LIE_SCHEMA_NUMBER_TEXT_CAPACITY, &bytes));
  if (!bytes || bytes > LIE_SCHEMA_NUMBER_TEXT_CAPACITY)
    return fail(c, LIE_SCHEMA_INVALID, "invalid binary64 serialization result");
  *out = (lie_number_text){text, bytes};
  return LIE_SCHEMA_OK;
}
void lie_schema_number_description_init(lie_schema_number_description *d) {
  if (!d) return;
  memset(d, 0, sizeof(*d));
  d->abi_version = LIE_SCHEMA_NUMBER_ABI;
  d->struct_bytes = sizeof(*d);
  lie_schema_transform_description_init(&d->transform);
}
lie_schema_status lie_schema_number_create(const lie_schema_number_description *d,
    lie_schema_node schema, bool integer, lie_number_policy **out, lie_schema_error *e) {
  if (!valid(d) || !schema || !out) return LIE_SCHEMA_INVALID;
  context c = {&d->transform, 0, e};
  lie_number_description policy;
  lie_number_description_init(&policy);
  policy.integer = integer;
  if (d->number_work) policy.max_work = d->number_work;
  policy.allocator = d->transform.allocator;
  const char *keys[] = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf"};
  lie_number_text *fields[] = {&policy.minimum, &policy.maximum,
    &policy.exclusive_minimum, &policy.exclusive_maximum, &policy.multiple};
  char storage[5][LIE_SCHEMA_NUMBER_TEXT_CAPACITY];
  for (size_t i = 0; i < 5; ++i) {
    lie_schema_node entry = NULL;
    TRY(lie_schema_internal_field(&c, schema, keys[i], &entry));
    if (!entry) continue;
    lie_schema_value value;
    TRY(lie_schema_internal_describe(&c, entry, &value));
    if (value.kind != LIE_SCHEMA_NUMBER || !isfinite(value.number)) {
      if (e) *e = (lie_schema_error){"", {keys[i], strlen(keys[i])}, " must be a finite number"};
      return LIE_SCHEMA_INVALID;
    }
    if (i == 4 && value.number <= 0)
      return fail(&c, LIE_SCHEMA_INVALID, "multipleOf must be positive");
    TRY(spelling(d, &c, value.number, storage[i], fields[i]));
  }
  lie_number_policy *result = NULL;
  TRY(numeric(&c, lie_number_create(&policy, &result)));
  *out = result;
  return LIE_SCHEMA_OK;
}
lie_schema_status lie_schema_number_accept(const lie_schema_number_description *d,
    const lie_number_policy *policy, lie_schema_node node, bool *out, lie_schema_error *e) {
  if (!valid(d) || !policy || !node || !out) return LIE_SCHEMA_INVALID;
  context c = {&d->transform, 0, e};
  lie_schema_value value;
  TRY(lie_schema_internal_describe(&c, node, &value));
  bool accepted = false;
  if (value.kind == LIE_SCHEMA_NUMBER) {
    char storage[LIE_SCHEMA_NUMBER_TEXT_CAPACITY];
    lie_number_text text = {0};
    TRY(spelling(d, &c, value.number, storage, &text));
    TRY(numeric(&c, lie_number_accept(policy, text, &accepted)));
  }
  *out = accepted;
  return LIE_SCHEMA_OK;
}
lie_schema_status lie_schema_number_intersect(const lie_schema_number_description *d,
    lie_schema_node left, lie_schema_node right, double *out, lie_schema_error *e) {
  if (!valid(d) || !d->parse || !left || !right || !out) return LIE_SCHEMA_INVALID;
  context c = {&d->transform, 0, e};
  const lie_schema_node nodes[] = {left, right};
  lie_schema_value values[2];
  /* Preserve the original two-input validation before either conversion. */
  for (size_t i = 0; i < 2; ++i) {
    TRY(lie_schema_internal_describe(&c, nodes[i], &values[i]));
    if (values[i].kind != LIE_SCHEMA_NUMBER || !isfinite(values[i].number) || values[i].number <= 0)
      return fail(&c, LIE_SCHEMA_INVALID, "multipleOf must be a positive finite number");
  }
  char storage[2][LIE_SCHEMA_NUMBER_TEXT_CAPACITY];
  lie_number_text inputs[2] = {{0}};
  for (size_t i = 0; i < 2; ++i)
    TRY(spelling(d, &c, values[i].number, storage[i], &inputs[i]));
  char common[8210];
  size_t bytes = 0;
  TRY(numeric(&c, lie_number_intersect(inputs[0], inputs[1], &d->transform.allocator,
                                      d->number_work, common, sizeof(common), &bytes)));
  TRY(lie_schema_internal_tick(&c, 1));
  double result = 0;
  TRY(d->parse(d->conversion_context, (lie_schema_bytes){common, bytes}, &result));
  bool exact = false;
  if (isfinite(result)) {
    char serialized[LIE_SCHEMA_NUMBER_TEXT_CAPACITY];
    lie_number_text text = {0};
    TRY(spelling(d, &c, result, serialized, &text));
    TRY(numeric(&c, lie_number_equal_with_allocator(text,
      (lie_number_text){common, bytes}, &d->transform.allocator, &exact)));
  }
  if (!exact)
    return fail(&c, LIE_SCHEMA_INVALID, "combined multipleOf exceeds the exact schema-number range");
  *out = result;
  return LIE_SCHEMA_OK;
}
lie_schema_status lie_schema_number_literal(const lie_schema_number_description *d,
    lie_schema_node node, lie_grammar_builder *builder, uint32_t *out, lie_schema_error *e) {
  if (!valid(d) || !node || !builder || !out) return LIE_SCHEMA_INVALID;
  context c = {&d->transform, 0, e};
  lie_schema_value value;
  TRY(lie_schema_internal_describe(&c, node, &value));
  if (value.kind != LIE_SCHEMA_NUMBER)
    return fail(&c, LIE_SCHEMA_INVALID, "numeric literal requires a number");
  char storage[LIE_SCHEMA_NUMBER_TEXT_CAPACITY];
  lie_number_text text = {0};
  TRY(spelling(d, &c, value.number, storage, &text));
  uint32_t result = 0;
  TRY(lie_schema_internal_builder_error(
    lie_builder_literal(builder, (const uint8_t *)text.data, text.bytes, &result), e));
  *out = result;
  return LIE_SCHEMA_OK;
}
