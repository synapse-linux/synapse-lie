// SPDX-License-Identifier: MIT
// Native string construction; typed errors and caller-owned shared reuse only.
#ifndef LIE_GUFO_SCHEMA_STRING_HPP
#define LIE_GUFO_SCHEMA_STRING_HPP
#include "lie/schema_string.h"
#include "gufo_schema_transform.hpp"
#include "gufo_grammar_string.hpp"
#include "gufo_grammar_regex_compile.hpp"
#include <memory>
namespace lie_gufo {
inline void schema_string_check(lie_schema_status rc, const lie_schema_string_error &e) {
  if (rc == LIE_SCHEMA_OK) return;
  if (e.lexeme_status != LIE_LEXEME_OK) lexeme_check(e.lexeme_status);
  if (e.string_status != LIE_STRING_OK) string_check(e.string_status);
  if (e.compiler_status != LIE_REGEX_COMPILE_OK) regex_compile_check(e.compiler_status);
  if (e.parse_error.status != LIE_REGEX_PARSE_OK) {
    if (e.parse_error.status == LIE_REGEX_PARSE_RESOURCE) throw std::bad_alloc();
    if (e.parse_error.status == LIE_REGEX_PARSE_COMPILER)
      regex_compile_check(e.parse_error.compiler_status);
    throw std::invalid_argument("JSON Schema: " +
      std::string(lie_regex_parse_reason(e.parse_error.status)));
  }
  schema_check(rc, e.schema_error);
}
inline lie_grammar_lexeme *schema_string(const SchemaValue &schema) {
  lie_schema_string_description d; lie_schema_string_description_init(&d);
  d.transform = schema_reader();
  lie_schema_string_plan plan;
  lie_schema_string_error error{};
  schema_string_check(lie_schema_string_prepare(&d, &schema, &plan, &error), error);
  const lie_regex_program *unrestricted = nullptr;
  if (!plan.has_pattern && !plan.format_bytes) {
    static const auto retained = [] {
      lie_schema_string_description description;
      lie_schema_string_description_init(&description);
      description.transform = schema_reader();
      lie_regex_program *out = nullptr;
      lie_schema_string_error e{};
      schema_string_check(lie_schema_string_unrestricted(&description, &out, &e), e);
      return std::shared_ptr<const lie_regex_program>(out, lie_regex_release);
    }();
    unrestricted = retained.get();
  }
  lie_grammar_lexeme *out = nullptr;
  schema_string_check(lie_schema_string_compile(&d, &plan, unrestricted, &out, &error), error);
  return out;
}
} // namespace lie_gufo
#endif
