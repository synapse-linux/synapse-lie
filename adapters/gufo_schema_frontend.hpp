// SPDX-License-Identifier: MIT
// Private owner/error/shared-handle projection over the native C17 frontend.
#ifndef LIE_GUFO_SCHEMA_FRONTEND_HPP
#define LIE_GUFO_SCHEMA_FRONTEND_HPP
#include "lie/schema_frontend.h"
#include "gufo_schema_compile.hpp"
#include "gufo_schema_string.hpp"
#include <utility>
namespace lie_gufo {
inline void frontend_schema_check(const lie_schema_frontend_error &e) {
  if (e.origin == LIE_FRONTEND_ERROR_STRING) schema_string_check(e.schema_status, e.string_error);
  if (e.origin == LIE_FRONTEND_ERROR_LEXEME) lexeme_check(e.lexeme_status);
  if (e.origin == LIE_FRONTEND_ERROR_ARENA) {
    if (e.schema_status == LIE_SCHEMA_RESOURCE || e.arena_error.value_status == LIE_JSON_VALUE_RESOURCE ||
        e.arena_error.store_status == LIE_JSON_STORE_RESOURCE) throw std::bad_alloc();
    if (e.arena_error.value_status == LIE_JSON_VALUE_NONFINITE)
      throw std::invalid_argument("JSON numbers must be finite");
    if (e.arena_error.value_status == LIE_JSON_VALUE_LIMIT)
      throw std::runtime_error("JSON value resource limit exceeded");
    if (e.arena_error.value_status != LIE_JSON_VALUE_OK)
      throw std::runtime_error("invalid C17 JSON value operation");
    if (e.arena_error.store_status == LIE_JSON_STORE_LIMIT)
      throw std::invalid_argument("JSON Schema: schema expansion exceeds its resource budget");
    if (e.arena_error.store_status != LIE_JSON_STORE_OK)
      throw std::logic_error("invalid schema root ownership operation");
  }
  if (e.schema_status == LIE_SCHEMA_INVALID && e.schema_error.message &&
      std::strcmp(e.schema_error.message, "JSON numbers must be finite") == 0)
    throw std::invalid_argument(e.schema_error.message);
  if (e.schema_status == LIE_SCHEMA_CALLBACK && e.schema_error.message &&
      (std::strcmp(e.schema_error.message, "JSON number serialization failed") == 0 ||
       std::strcmp(e.schema_error.message, "JSON parse error: bad number") == 0))
    throw std::runtime_error(e.schema_error.message);
  schema_check(e.schema_status, e.schema_error);
}
inline void frontend_check(lie_schema_frontend_status rc, const lie_schema_frontend_error &e) {
  if (rc == LIE_FRONTEND_OK) return;
  if (rc == LIE_FRONTEND_RESOURCE) throw std::bad_alloc();
  if (rc == LIE_FRONTEND_LEXEME) lexeme_check(e.lexeme_status);
  if (rc == LIE_FRONTEND_COMPILER) {
    if (e.origin == LIE_FRONTEND_ERROR_LEXEME) lexeme_check(e.lexeme_status);
    Compiler::check(e.compiler_status, e.compiler_error);
  }
  if (rc == LIE_FRONTEND_PUBLICATION) {
    const auto &p = e.compiler_error.compile_error;
    switch (e.compiler_error.compile_status) {
    case LIE_COMPILE_SCHEMA: frontend_schema_check(e); break;
    case LIE_COMPILE_BUILDER: builder_check(p.builder_status); break;
    case LIE_COMPILE_BINDING:
      if (e.origin == LIE_FRONTEND_ERROR_LEXEME) lexeme_check(e.lexeme_status);
      grammar_check(p.grammar_status); break;
    case LIE_COMPILE_PROGRAM: grammar_check(p.grammar_status); break;
    case LIE_COMPILE_RESOURCE: throw std::bad_alloc();
    case LIE_COMPILE_PROMPT_LIMIT: throw std::invalid_argument("JSON Schema: prompt resource budget exceeded");
    case LIE_COMPILE_JSON:
      if (p.json_status == LIE_JSON_VALUE_RESOURCE) throw std::bad_alloc();
      throw std::invalid_argument("JSON Schema: native prompt serialization refused");
    default: break;
    }
  }
  if (rc == LIE_FRONTEND_PHASE) throw std::logic_error("JSON Schema: invalid C17 frontend phase");
  throw std::invalid_argument("JSON Schema: invalid native frontend workflow");
}
class NativeSchemaFrontend {
  lie_schema_frontend *frontend_ = nullptr;
  lie_schema_frontend_output output_{};
public:
  NativeSchemaFrontend() {
    lie_schema_frontend_error e{};
    frontend_check(lie_schema_frontend_create(nullptr, &frontend_, &e), e);
  }
  ~NativeSchemaFrontend() {
    lie_schema_frontend_output_release(&output_); lie_schema_frontend_release(frontend_);
  }
  NativeSchemaFrontend(const NativeSchemaFrontend &) = delete;
  NativeSchemaFrontend &operator=(const NativeSchemaFrontend &) = delete;
  void compile(const SchemaValue &schema, bool strict, bool object_only) {
    lie_schema_frontend_error e{};
    frontend_check(lie_schema_frontend_compile(frontend_, object_only ? nullptr : schema.raw(),
      strict, object_only, &output_, &e), e);
  }
  uint32_t root() const noexcept { return output_.compilation.root; }
  std::shared_ptr<const lie_grammar_program> take_program() {
    return {std::exchange(output_.compilation.program, nullptr), lie_grammar_program_release};
  }
  std::shared_ptr<const lie_schema_prompt> take_prompt() {
    return {std::exchange(output_.compilation.prompt, nullptr), lie_schema_prompt_release};
  }
  LexemeTable take_lexemes() { return LexemeTable::adopt(std::exchange(output_.lexemes, nullptr)); }
};
} // namespace lie_gufo
#endif
