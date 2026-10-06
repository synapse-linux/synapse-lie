// SPDX-License-Identifier: MIT
// Borrowed root/visitor views and exception translation; root policy is C17.
#ifndef LIE_GUFO_SCHEMA_ROOT_HPP
#define LIE_GUFO_SCHEMA_ROOT_HPP
#include "gufo_schema_transform.hpp"
#include "lie/schema_root.h"
namespace lie_gufo {
template <class F>
uint32_t schema_root(const SchemaValue &schema, bool object_only,
    lie_grammar_builder *builder, uint32_t whitespace, F visit) {
  struct State {
    F *visit;
    std::exception_ptr failure;
    static lie_schema_status call(void *p, lie_schema_node n, size_t depth,
        uint32_t *out, lie_schema_error *) noexcept {
      auto &s = *static_cast<State *>(p);
      try { *out = (*s.visit)(schema_value(n), depth); return LIE_SCHEMA_OK; }
      catch (const gufo::sampling::JsonSchemaEmpty &) {
        s.failure = std::current_exception(); return LIE_SCHEMA_EMPTY;
      } catch (...) {
        s.failure = std::current_exception(); return LIE_SCHEMA_CALLBACK;
      }
    }
  } state{&visit, {}};
  lie_schema_root_description d;
  lie_schema_root_description_init(&d);
  d.reader = schema_reader();
  d.visit.context = &state;
  d.visit.body = State::call;
  uint32_t out = 0;
  lie_schema_error e{};
  const auto rc = lie_schema_root_rule(&d, &schema, object_only, builder,
                                      whitespace, &out, &e);
  if (state.failure && (rc == LIE_SCHEMA_CALLBACK || rc == LIE_SCHEMA_EMPTY))
    std::rethrow_exception(state.failure);
  schema_check(rc, e);
  return out;
}
} // namespace lie_gufo
#endif
