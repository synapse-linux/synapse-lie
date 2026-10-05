// SPDX-License-Identifier: MIT
// JSON value/span and error translation; decimal arithmetic lives in C17.
#ifndef LIE_GUFO_GRAMMAR_NUMBER_HPP
#define LIE_GUFO_GRAMMAR_NUMBER_HPP
#include "lie/grammar_number.h"
#include "src/core/json_schema_lexeme.hpp"
#include <array>
#include <cmath>
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
  lie_number_description d; lie_number_description_init(&d); d.integer = integer;
  std::array<std::string, 5> storage;
  lie_number_text *spans[] = {&d.minimum, &d.maximum, &d.exclusive_minimum, &d.exclusive_maximum, &d.multiple};
  const char *keys[] = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf"};
  for (size_t i = 0; i < 5; ++i) {
    const auto *entry = schema.find(keys[i]); if (!entry) continue;
    if (!entry->is_number() || !std::isfinite(entry->as_double()))
      throw std::invalid_argument("JSON Schema: " + std::string(keys[i]) + " must be a finite number");
    if (i == 4 && entry->as_double() <= 0)
      throw std::invalid_argument("JSON Schema: multipleOf must be positive");
    storage[i] = entry->dump(); *spans[i] = number_text(storage[i]);
  }
  lie_number_policy *p = nullptr; number_check(lie_number_create(&d, &p));
  return std::shared_ptr<const lie_number_policy>(p, lie_number_release);
}
inline gufo::json::Value number_intersect(const gufo::json::Value &a, const gufo::json::Value &b) {
  for (const auto *value : {&a, &b})
    if (!value->is_number() || !std::isfinite(value->as_double()) || value->as_double() <= 0)
      throw std::invalid_argument("JSON Schema: multipleOf must be a positive finite number");
  const auto left = a.dump(), right = b.dump();
  std::array<char, 8210> output{}; size_t bytes = 0;
  number_check(lie_number_intersect(number_text(left), number_text(right), nullptr, 0,
                                   output.data(), output.size(), &bytes));
  const auto text = std::string_view(output.data(), bytes);
  const auto result = gufo::json::parse(text);
  bool exact = false;
  if (result.is_number() && std::isfinite(result.as_double())) {
    const auto spelling = result.dump();
    number_check(lie_number_equal(number_text(spelling), number_text(text), &exact));
  }
  if (!exact)
    throw std::invalid_argument("JSON Schema: combined multipleOf exceeds the exact schema-number range");
  return result;
}
} // namespace lie_gufo
#endif
