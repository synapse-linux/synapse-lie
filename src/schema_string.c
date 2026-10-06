/* SPDX-License-Identifier: MIT */
/* String leaf construction adapted from independently pinned MIT Gufo
 * json_schema_lexeme.cpp. C17 owns admission and composition; regex/Unicode/
 * format/lexeme modules retain their separately recorded ownership/provenance. */
#include "lie/schema_string.h"
#include "schema_internal.h"
#include <math.h>
#include <string.h>

#define TRY(call) do { lie_schema_status rc_ = (call); if (rc_) return rc_; } while (0)
static bool paired(lie_grammar_allocator a) { return !!a.allocate == !!a.release; }
static void inherit(lie_grammar_allocator *a, lie_grammar_allocator parent) {
  if (!a->allocate && !a->release) *a = parent;
}
void lie_schema_string_description_init(lie_schema_string_description *d) {
  if (!d) return;
  memset(d, 0, sizeof(*d));
  d->abi_version = LIE_SCHEMA_STRING_ABI; d->struct_bytes = sizeof(*d);
  lie_schema_transform_description_init(&d->transform);
  lie_grammar_unicode_description_init(&d->unicode);
  lie_regex_parser_description_init(&d->parser);
  lie_lexeme_description_init(&d->lexeme);
}
static bool valid(const lie_schema_string_description *d) {
  return d && d->abi_version == LIE_SCHEMA_STRING_ABI &&
    d->struct_bytes == sizeof(*d) && lie_schema_internal_valid(&d->transform) &&
    paired(d->unicode.compiler.allocator) && paired(d->parser.allocator) &&
    paired(d->lexeme.allocator);
}
static lie_schema_status fail(lie_schema_string_error *e, lie_schema_status rc,
    const char *message) {
  if (e) e->schema_error = (lie_schema_error){.message = message};
  return rc;
}
static lie_schema_status compiler_status(lie_schema_string_error *e,
    lie_regex_compile_status rc) {
  if (e) e->compiler_status = rc;
  if (!rc) return LIE_SCHEMA_OK;
  const char *reason;
  switch (rc) {
  case LIE_REGEX_COMPILE_RESOURCE: return fail(e, LIE_SCHEMA_RESOURCE, "regex allocation failed");
  case LIE_REGEX_COMPILE_EXPRESSION_LIMIT: reason = "regex expression budget exceeded"; break;
  case LIE_REGEX_COMPILE_DERIVATIVE_LIMIT: reason = "regex derivative budget exceeded"; break;
  case LIE_REGEX_COMPILE_STATE_LIMIT: reason = "compiled regex exceeds the state budget"; break;
  case LIE_REGEX_COMPILE_REPETITION: reason = "invalid regex repetition"; break;
  case LIE_REGEX_COMPILE_CLASS_LIMIT: reason = "regex character-class budget exceeded"; break;
  case LIE_REGEX_COMPILE_WORK_LIMIT: reason = "regex work limit exceeded"; break;
  default: reason = "invalid C17 regex compiler input"; break;
  }
  return fail(e, LIE_SCHEMA_INVALID, reason);
}
static lie_schema_status string_status(lie_schema_string_error *e, lie_string_status rc) {
  if (e) e->string_status = rc;
  switch (rc) {
  case LIE_STRING_OK: return LIE_SCHEMA_OK;
  case LIE_STRING_RESOURCE: return fail(e, LIE_SCHEMA_RESOURCE, "regex allocation failed");
  case LIE_STRING_WORK_LIMIT: return fail(e, LIE_SCHEMA_WORK_LIMIT, "regex work limit exceeded");
  case LIE_STRING_EMPTY_LENGTH: return fail(e, LIE_SCHEMA_EMPTY, "minLength exceeds maxLength");
  case LIE_STRING_EMPTY_PATTERN:
    return fail(e, LIE_SCHEMA_EMPTY, "string predicates and lengths have no matching value");
  default: return fail(e, LIE_SCHEMA_INVALID, "invalid C17 JSON string policy");
  }
}
static lie_schema_status lexeme_status(lie_schema_string_error *e, lie_lexeme_status rc) {
  if (e) e->lexeme_status = rc;
  switch (rc) {
  case LIE_LEXEME_OK: return LIE_SCHEMA_OK;
  case LIE_LEXEME_RESOURCE: return fail(e, LIE_SCHEMA_RESOURCE, "predicate allocation failed");
  case LIE_LEXEME_STRING_WORK: return fail(e, LIE_SCHEMA_WORK_LIMIT, "regex work limit exceeded");
  case LIE_LEXEME_STRING_EMPTY_LENGTH: return string_status(e, LIE_STRING_EMPTY_LENGTH);
  case LIE_LEXEME_STRING_EMPTY_PATTERN: return string_status(e, LIE_STRING_EMPTY_PATTERN);
  default: return fail(e, LIE_SCHEMA_INVALID, "invalid C17 JSON grammar predicate");
  }
}
lie_schema_status lie_schema_string_prepare(const lie_schema_string_description *d,
    lie_schema_node schema, lie_schema_string_plan *out, lie_schema_string_error *e) {
  if (e) *e = (lie_schema_string_error){0};
  if (!valid(d) || !schema || !out) return LIE_SCHEMA_INVALID;
  lie_schema_context c = {&d->transform, 0, e ? &e->schema_error : NULL};
  lie_schema_string_plan plan = {.abi_version = LIE_SCHEMA_STRING_ABI,
    .struct_bytes = sizeof(plan), .maximum = UINT32_MAX};
  const char *lengths[] = {"minLength", "maxLength"};
  for (size_t i = 0; i < 2; ++i) {
    lie_schema_node entry = NULL;
    TRY(lie_schema_internal_field(&c, schema, lengths[i], &entry));
    if (!entry) continue;
    lie_schema_value value;
    TRY(lie_schema_internal_describe(&c, entry, &value));
    if (value.kind != LIE_SCHEMA_NUMBER || !isfinite(value.number) ||
        value.number < 0 || value.number > 1048576 || floor(value.number) != value.number)
      return fail(e, LIE_SCHEMA_INVALID, "string lengths must be nonnegative integers up to 1048576");
    if (!i) plan.minimum = (uint32_t)value.number;
    else plan.maximum = (uint32_t)value.number;
  }
  if (plan.minimum > plan.maximum) {
    if (e) e->string_status = LIE_STRING_EMPTY_LENGTH;
    return fail(e, LIE_SCHEMA_EMPTY, "minLength exceeds maxLength");
  }
  const char *patterns[] = {"pattern", "format"};
  for (size_t i = 0; i < 2; ++i) {
    lie_schema_node entry = NULL;
    TRY(lie_schema_internal_field(&c, schema, patterns[i], &entry));
    if (!entry) continue;
    lie_schema_value value;
    TRY(lie_schema_internal_describe(&c, entry, &value));
    if (value.kind != LIE_SCHEMA_STRING) {
      if (e) e->schema_error = (lie_schema_error){"", {patterns[i], strlen(patterns[i])}, " must be a string"};
      return LIE_SCHEMA_INVALID;
    }
    if (!i) { plan.has_pattern = true; plan.pattern = value.text; }
    else {
      TRY(lie_schema_format_pattern(value.text, plan.format, sizeof(plan.format),
                                    &plan.format_bytes, e ? &e->schema_error : NULL));
      if (value.text.size == 8 && !memcmp(value.text.data, "hostname", 8) && plan.maximum > 253)
        plan.maximum = 253;
    }
  }
  *out = plan; return LIE_SCHEMA_OK;
}
static lie_schema_status program(const lie_schema_string_description *d,
    const lie_schema_string_plan *plan, lie_regex_program **out, lie_schema_string_error *e) {
  lie_grammar_unicode_description u = d->unicode;
  lie_regex_parser_description p = d->parser;
  inherit(&u.compiler.allocator, d->transform.allocator);
  inherit(&p.allocator, d->transform.allocator);
  /* An unrestricted language is sealed at infinite maximum, preserving its
   * use with different caller-owned min/max lengths and canonical mask keys. */
  u.compiler.maximum_length = plan->has_pattern || plan->format_bytes ? plan->maximum : UINT32_MAX;
  lie_grammar_unicode *unicode = NULL;
  lie_schema_status rc = compiler_status(e, lie_grammar_unicode_create(&u, &unicode));
  if (rc) return rc;
  lie_regex_compiler *compiler = lie_grammar_unicode_compiler(unicode);
  uint32_t conditions[2]; size_t count = 0;
  const lie_schema_bytes patterns[] = {plan->pattern, {plan->format, plan->format_bytes}};
  for (size_t i = 0; i < 2; ++i) {
    if ((!i && !plan->has_pattern) || (i && !plan->format_bytes)) continue;
    lie_regex_parse_error error = {0};
    lie_regex_parse_status parsed = lie_grammar_unicode_parse(unicode, patterns[i].data,
      patterns[i].size, &p, &conditions[count], &error);
    if (e) e->parse_error = error;
    if (parsed == LIE_REGEX_PARSE_COMPILER) rc = compiler_status(e, error.compiler_status);
    else if (parsed == LIE_REGEX_PARSE_RESOURCE) rc = fail(e, LIE_SCHEMA_RESOURCE, "regex parser allocation failed");
    else if (parsed) rc = fail(e, LIE_SCHEMA_INVALID, lie_regex_parse_reason(parsed));
    if (rc) goto done;
    ++count;
  }
  uint32_t root;
  rc = compiler_status(e, lie_regex_combine(compiler, LIE_REGEX_INTERSECTION, conditions, count, &root));
  if (!rc) rc = compiler_status(e, lie_regex_seal(compiler, root, out));
done:
  lie_grammar_unicode_release(unicode); return rc;
}
lie_schema_status lie_schema_string_unrestricted(const lie_schema_string_description *d,
    lie_regex_program **out, lie_schema_string_error *e) {
  if (e) *e = (lie_schema_string_error){0};
  if (!valid(d) || !out) return LIE_SCHEMA_INVALID;
  const lie_schema_string_plan plan = {.maximum = UINT32_MAX};
  return program(d, &plan, out, e);
}
lie_schema_status lie_schema_string_compile(const lie_schema_string_description *d,
    const lie_schema_string_plan *plan, const lie_regex_program *unrestricted,
    lie_grammar_lexeme **out, lie_schema_string_error *e) {
  if (e) *e = (lie_schema_string_error){0};
  if (!valid(d) || !plan || !out || plan->abi_version != LIE_SCHEMA_STRING_ABI ||
      plan->struct_bytes != sizeof(*plan) || plan->format_bytes > sizeof(plan->format) ||
      (plan->has_pattern && plan->pattern.size && !plan->pattern.data)) return LIE_SCHEMA_INVALID;
  const bool scalar = !plan->has_pattern && !plan->format_bytes;
  lie_regex_program *owned = NULL;
  const lie_regex_program *regex = scalar ? unrestricted : NULL;
  lie_schema_status rc = LIE_SCHEMA_OK;
  if (!regex) {
    rc = program(d, plan, &owned, e);
    if (rc) return rc;
    regex = owned;
  }
  lie_string_policy policy; lie_string_policy_init(&policy);
  policy.minimum = plan->minimum; policy.maximum = plan->maximum;
  policy.scalar_only = scalar; policy.regex = regex;
  /* Initial ordering is already admitted by prepare. Remaining inversion is
   * the format/hostname language narrowing checked after compilation. */
  if (policy.minimum > policy.maximum) rc = string_status(e, LIE_STRING_EMPTY_PATTERN);
  else rc = string_status(e, lie_string_policy_validate(&policy));
  if (!rc) {
    lie_lexeme_description lexeme = d->lexeme;
    inherit(&lexeme.allocator, d->transform.allocator);
    rc = lexeme_status(e, lie_lexeme_string_create(&lexeme, &policy, out));
  }
  lie_regex_release(owned); return rc;
}
lie_schema_status lie_schema_string_create(const lie_schema_string_description *d,
    lie_schema_node schema, lie_grammar_lexeme **out, lie_schema_string_error *e) {
  if (!out) return LIE_SCHEMA_INVALID;
  lie_schema_string_plan plan;
  TRY(lie_schema_string_prepare(d, schema, &plan, e));
  return lie_schema_string_compile(d, &plan, NULL, out, e);
}
