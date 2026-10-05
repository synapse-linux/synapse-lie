// SPDX-License-Identifier: MIT
// Encoded state/storage and exception translation; Unicode predicates are C17.
#ifndef LIE_GUFO_GRAMMAR_STRING_HPP
#define LIE_GUFO_GRAMMAR_STRING_HPP
#include "lie/grammar_string.h"
#include "src/core/json_schema_lexeme.hpp"
#include <array>
#include <cstring>
#include <string>
namespace lie_gufo {
inline void string_check(lie_string_status rc) {
  using gufo::sampling::JsonSchemaEmpty;
  switch (rc) {
  case LIE_STRING_OK: return;
  case LIE_STRING_RESOURCE: throw std::bad_alloc();
  case LIE_STRING_WORK_LIMIT: throw std::runtime_error("JSON Schema: regex work limit exceeded");
  case LIE_STRING_PHASE: throw std::logic_error("invalid JSON string matcher phase");
  case LIE_STRING_STATE: throw std::logic_error("invalid JSON string matcher state");
  case LIE_STRING_EMPTY_LENGTH: throw JsonSchemaEmpty("JSON Schema: minLength exceeds maxLength");
  case LIE_STRING_EMPTY_PATTERN: throw JsonSchemaEmpty("JSON Schema: string predicates and lengths have no matching value");
  default: throw std::invalid_argument("invalid C17 JSON string policy");
  }
}
inline gufo::sampling::JsonSchemaLexeme::Match string_advance(
  const lie_string_policy &p, std::string &encoded, uint8_t byte) {
  if (!encoded.empty() && encoded.size() != LIE_STRING_STATE_BYTES)
    throw std::logic_error("invalid JSON string matcher state");
  std::array<uint8_t,LIE_STRING_STATE_BYTES> state{};
  size_t size = encoded.size(); if (size) std::memcpy(state.data(),encoded.data(),size);
  lie_string_match m; string_check(lie_string_advance(&p,state.data(),&size,state.size(),byte,&m));
  encoded.assign(reinterpret_cast<const char *>(state.data()),size);
  return {m.prefix,m.complete};
}
inline gufo::sampling::JsonSchemaLexeme::Match string_match(
  const lie_string_policy &p, std::string_view text) {
  lie_string_match m; string_check(lie_string_check(&p,reinterpret_cast<const uint8_t *>(text.data()),text.size(),&m));
  return {m.prefix,m.complete};
}
inline void string_canonical(const lie_string_policy &p, std::string &encoded, size_t token_bytes) {
  string_check(lie_string_canonical(&p,reinterpret_cast<uint8_t *>(encoded.data()),encoded.size(),token_bytes));
}
} // namespace lie_gufo
#endif
