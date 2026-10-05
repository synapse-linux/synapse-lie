// SPDX-License-Identifier: MIT
// Private views/storage/leaf and exception adapters; body policy is C17.
#ifndef LIE_GUFO_SCHEMA_BODY_HPP
#define LIE_GUFO_SCHEMA_BODY_HPP
#include "gufo_schema_values.hpp"
#include "lie/schema_body.h"
namespace lie_gufo {
template <class V, class K, class N, class R> struct SchemaBodyCallbacks {
  using State = SchemaBodyCallbacks;
  SchemaValues *values;
  V *visit;
  K *keep;
  N *normalize;
  R *rule;
  std::exception_ptr failure;
  template <class F> lie_schema_status protect(F f) noexcept {
    failure = {};
    try {
      f();
      return LIE_SCHEMA_OK;
    } catch (const gufo::sampling::JsonSchemaEmpty &) {
      failure = std::current_exception();
      return LIE_SCHEMA_EMPTY;
    } catch (...) {
      failure = std::current_exception();
      return LIE_SCHEMA_CALLBACK;
    }
  }
  static lie_schema_status visit_node(void *p, lie_schema_node n, size_t d,
                                      uint32_t *out) noexcept {
    auto &s = *static_cast<State *>(p);
    return s.protect([&] { *out = (*s.visit)(schema_value(n), d); });
  }
  static lie_schema_status keep_node(void *p, lie_schema_node n,
                                     lie_schema_node *out) noexcept {
    auto &s = *static_cast<State *>(p);
    return s.protect([&] { *out = &(*s.keep)(schema_value(n)); });
  }
  static lie_schema_status
  normalize_value(void *p, lie_schema_node base, lie_schema_node n,
                  lie_schema_normalized *out) noexcept {
    auto &s = *static_cast<State *>(p);
    return s.protect([&] {
      const auto v = (*s.normalize)(schema_value(base), schema_value(n));
      if (!v) {
        *out = {false, nullptr};
        return;
      }
      const auto d = s.values->description();
      lie_schema_node owned = nullptr;
      lie_schema_error e{};
      s.values->check(
          d.transform.access.clone(d.transform.access.context, &*v, &owned), e);
      *out = {true, owned};
    });
  }
  static lie_schema_status route(void *p, lie_schema_node n, size_t d,
                                 lie_schema_route r, lie_schema_bytes name,
                                 uint32_t *out) noexcept {
    auto &s = *static_cast<State *>(p);
    return s.protect([&] {
      *out = (*s.rule)(schema_value(n), d, r,
                       std::string_view(name.data, name.size));
    });
  }
};
template <class V, class K, class N, class R>
uint32_t schema_body(const SchemaValue &root, const SchemaValue &schema,
                     size_t depth, lie_grammar_builder *builder,
                     uint32_t whitespace, lie_schema_container_counts &counts,
                     size_t &enums, V visit, K keep, N normalize, R rule) {
  SchemaArena staging;
  SchemaValues values;
  using State = SchemaBodyCallbacks<V, K, N, R>;
  State state{&values, &visit, &keep, &normalize, &rule, {}};
  lie_schema_body_description d;
  lie_schema_body_description_init(&d);
  d.transform = staging.description();
  d.values = values.description();
  d.append_member = SchemaArena::append_member;
  d.compile = {&state, State::visit_node, State::keep_node,
               State::normalize_value};
  d.rules = {&state, State::route};
  uint32_t out = 0;
  lie_schema_error e{};
  const auto rc =
      lie_schema_compile_body(&d, &root, &schema, depth, builder, whitespace,
                              &counts, &enums, &out, &e);
  if (state.failure &&
      (rc == LIE_SCHEMA_CALLBACK || (rc == LIE_SCHEMA_EMPTY && !e.message)))
    std::rethrow_exception(state.failure);
  staging.rethrow_if_failed(rc, e);
  values.rethrow_if_failed(rc, e);
  schema_check(rc, e);
  return out;
}
} // namespace lie_gufo
#endif
