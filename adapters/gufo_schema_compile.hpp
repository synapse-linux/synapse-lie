// SPDX-License-Identifier: MIT
// Typed callback/exception and shared-pointer translation; publication is C17.
#ifndef LIE_GUFO_SCHEMA_COMPILE_HPP
#define LIE_GUFO_SCHEMA_COMPILE_HPP
#include "gufo_schema_root.hpp"
#include "gufo_grammar_builder.hpp"
#include "lie/schema_compile.h"
namespace lie_gufo {
struct SchemaCompilation {
  uint32_t root;
  std::shared_ptr<const lie_grammar_program> program;
  std::shared_ptr<const lie_schema_prompt> prompt;
};
template<class F>
SchemaCompilation schema_compile(const SchemaValue &schema, bool object_only,
    lie_grammar_builder *builder, uint32_t whitespace, const Lexemes &lexemes, F visit) {
  struct State {
    F *visit;
    const Lexemes *lexemes;
    std::exception_ptr failure;
    static lie_schema_status body(void *p, lie_schema_node n, size_t depth,
        uint32_t *out, lie_schema_error *) noexcept {
      auto &s = *static_cast<State *>(p);
      try { *out = (*s.visit)(schema_value(n), depth); return LIE_SCHEMA_OK; }
      catch (const gufo::sampling::JsonSchemaEmpty &) {
        s.failure = std::current_exception(); return LIE_SCHEMA_EMPTY;
      } catch (...) {
        s.failure = std::current_exception(); return LIE_SCHEMA_CALLBACK;
      }
    }
    static size_t count(void *p) noexcept {
      return static_cast<State *>(p)->lexemes->size();
    }
    static lie_grammar_status bind(void *p, lie_grammar_predicates *out) noexcept {
      auto &s = *static_cast<State *>(p);
      try { *out = s.lexemes->predicates(); return LIE_GRAMMAR_OK; }
      catch (...) { s.failure = std::current_exception(); return LIE_GRAMMAR_PREDICATE; }
    }
  } state{&visit, &lexemes, {}};
  lie_schema_compile_description d;
  lie_schema_compile_description_init(&d);
  d.root.reader = schema_reader();
  d.root.visit.context = &state; d.root.visit.body = State::body;
  d.binding_context = &state; d.lexeme_count = State::count; d.bind = State::bind;
  lie_schema_compilation result{};
  lie_schema_compile_error error{};
  const auto rc = lie_schema_compile(&d, &schema, schema.raw(), object_only,
                                      builder, whitespace, &result, &error);
  if (state.failure) std::rethrow_exception(state.failure);
  switch (rc) {
  case LIE_COMPILE_OK: break;
  case LIE_COMPILE_SCHEMA: schema_check(error.schema_status, error.schema_error); break;
  case LIE_COMPILE_BUILDER: builder_check(error.builder_status); break;
  case LIE_COMPILE_BINDING: case LIE_COMPILE_PROGRAM: grammar_check(error.grammar_status); break;
  case LIE_COMPILE_RESOURCE: throw std::bad_alloc();
  case LIE_COMPILE_PROMPT_LIMIT: throw std::invalid_argument("JSON Schema: prompt resource budget exceeded");
  case LIE_COMPILE_JSON:
    if (error.json_status == LIE_JSON_VALUE_RESOURCE) throw std::bad_alloc();
    throw std::invalid_argument("JSON Schema: native prompt serialization refused");
  default: throw std::invalid_argument("JSON Schema: invalid C17 compilation workflow");
  }
  std::unique_ptr<lie_grammar_program, decltype(&lie_grammar_program_release)>
    program(result.program, lie_grammar_program_release);
  std::unique_ptr<lie_schema_prompt, decltype(&lie_schema_prompt_release)>
    prompt(result.prompt, lie_schema_prompt_release);
  return {result.root, std::shared_ptr<const lie_grammar_program>(std::move(program)),
          std::shared_ptr<const lie_schema_prompt>(std::move(prompt))};
}
} // namespace lie_gufo
#endif
