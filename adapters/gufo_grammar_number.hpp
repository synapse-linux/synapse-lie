// SPDX-License-Identifier: MIT
// Private exceptions; numeric leaf control, binary64 codec and arithmetic are C17.
#ifndef LIE_GUFO_GRAMMAR_NUMBER_HPP
#define LIE_GUFO_GRAMMAR_NUMBER_HPP
#include "lie/grammar_number.h"
#include "gufo_schema_number.hpp"
#include "src/core/json_schema_lexeme.hpp"
#include <memory>
#include <string>
namespace lie_gufo {
inline void number_check(lie_number_status rc) {
  using gufo::sampling::JsonSchemaEmpty;
  switch (rc) {
  case LIE_NUMBER_OK: return;
  case LIE_NUMBER_RESOURCE: throw std::bad_alloc();
  case LIE_NUMBER_EMPTY_INTERVAL:
    throw JsonSchemaEmpty("JSON Schema: numeric constraints describe an empty interval");
  case LIE_NUMBER_EMPTY_GRID:
    throw JsonSchemaEmpty("JSON Schema: numeric constraints contain no multipleOf value");
  case LIE_NUMBER_WORK_LIMIT:
    throw std::runtime_error("JSON Schema: numeric work limit exceeded");
  default: throw std::invalid_argument("JSON Schema: invalid exact-decimal numeric constraint");
  }
}
inline lie_number_text number_text(std::string_view v) { return {v.data(), v.size()}; }
inline std::shared_ptr<const lie_number_policy> number_policy(const gufo::json::Value &schema, bool integer) {
  SchemaNumber number;
  return number.create(schema, integer);
}
inline gufo::json::Value number_intersect(const gufo::json::Value &a, const gufo::json::Value &b) {
  SchemaNumber number;
  return number.intersect(a, b);
}
inline bool number_accept(const lie_number_policy *policy, const gufo::json::Value &value) {
  SchemaNumber number;
  return number.accept(policy, value);
}
} // namespace lie_gufo
#endif
