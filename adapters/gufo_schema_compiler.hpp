// SPDX-License-Identifier: MIT
// Private typed callback/root/exception projections; compilation state is C17.
#ifndef LIE_GUFO_SCHEMA_COMPILER_HPP
#define LIE_GUFO_SCHEMA_COMPILER_HPP
#include "lie/schema_compiler.h"
#include "gufo_schema_transform.hpp"
#include "gufo_grammar_builder.hpp"
#include <type_traits>
namespace lie_gufo {
class Compiler {
  lie_schema_compiler *compiler_ = nullptr;
  static void store_check(lie_json_store_status rc) {
    if (rc == LIE_JSON_STORE_OK) return;
    if (rc == LIE_JSON_STORE_RESOURCE) throw std::bad_alloc();
    if (rc == LIE_JSON_STORE_LIMIT)
      throw std::invalid_argument("JSON Schema: schema expansion exceeds its resource budget");
    throw std::logic_error("invalid schema root ownership operation");
  }
  static void check(lie_schema_compiler_status rc, const lie_schema_compiler_error &e) {
    switch (rc) {
    case LIE_COMPILER_OK: return;
    case LIE_COMPILER_RESOURCE: throw std::bad_alloc();
    case LIE_COMPILER_BUILDER: builder_check(e.builder_status); break;
    case LIE_COMPILER_MEMO:
      if (e.schema_status == LIE_SCHEMA_RESOURCE) throw std::bad_alloc();
      if (e.schema_status == LIE_SCHEMA_WORK_LIMIT)
        throw std::invalid_argument("JSON Schema: compiled grammar exceeds the rule limit");
      throw std::runtime_error("JSON Schema: invalid C17 reference memo");
    case LIE_COMPILER_STORE: store_check(e.store_status); break;
    case LIE_COMPILER_CHECKS: lexeme_check(e.lexeme_status); break;
    case LIE_COMPILER_CALLBACK: schema_check(e.schema_status, {}); break;
    case LIE_COMPILER_PHASE:
      throw std::logic_error("JSON Schema: invalid C17 compiler phase");
    default: break;
    }
    throw std::invalid_argument("JSON Schema: invalid C17 compiler context");
  }
public:
  Compiler() {
    lie_schema_compiler_error error{};
    check(lie_schema_compiler_create(nullptr, &compiler_, &error), error);
  }
  ~Compiler() { lie_schema_compiler_release(compiler_); }
  Compiler(const Compiler &) = delete;
  Compiler &operator=(const Compiler &) = delete;
  lie_grammar_builder *builder() const noexcept { return lie_schema_compiler_builder(compiler_); }
  lie_schema_memo *memo() const noexcept { return lie_schema_compiler_memo(compiler_); }
  lie_lexeme_memo *checks() const noexcept { return lie_schema_compiler_checks(compiler_); }
  const lie_builder_primitives &primitives() const noexcept { return *lie_schema_compiler_primitives(compiler_); }
  lie_schema_container_counts &containers() const noexcept { return *lie_schema_compiler_containers(compiler_); }
  size_t &enum_values() const noexcept { return *lie_schema_compiler_enum_values(compiler_); }
  template<class F> void initialize(F &&whitespace) {
    using Callback = std::remove_reference_t<F>;
    struct State {
      Callback *callback;
      std::exception_ptr failure;
      static lie_schema_status invoke(void *p, uint32_t *out) noexcept {
        auto &s = *static_cast<State *>(p);
        try { *out = (*s.callback)(); return LIE_SCHEMA_OK; }
        catch (...) { s.failure = std::current_exception(); return LIE_SCHEMA_CALLBACK; }
      }
    } state{&whitespace, {}};
    lie_schema_compiler_error error{};
    const auto rc = lie_schema_compiler_initialize(compiler_, &state, State::invoke, &error);
    if (state.failure) std::rethrow_exception(state.failure);
    check(rc, error);
  }
  const SchemaValue &store(SchemaValue value) {
    lie_json_value *root = nullptr;
    store_check(value.transfer_root(lie_schema_compiler_store(compiler_), &root));
    return SchemaValue::facade(root);
  }
  lie_schema_compile_status publish(const lie_schema_compile_description &d,
      lie_schema_node schema, const lie_json_value *native, bool object_only,
      lie_schema_compilation *out, lie_schema_compile_error *error) {
    lie_schema_compiler_error e{};
    const auto rc = lie_schema_compiler_publish(compiler_, &d, schema, native,
                                               object_only, out, &e);
    if (error) *error = e.compile_error;
    if (rc == LIE_COMPILER_PUBLICATION) return e.compile_status;
    check(rc, e);
    return LIE_COMPILE_OK;
  }
};
} // namespace lie_gufo
#endif
