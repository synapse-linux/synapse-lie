// SPDX-License-Identifier: MIT
// Borrowed body callback/exception translation; Visit sequencing is C17.
#ifndef LIE_GUFO_SCHEMA_VISIT_HPP
#define LIE_GUFO_SCHEMA_VISIT_HPP
#include "gufo_schema_transform.hpp"
#include "lie/schema_visit.h"
#include <type_traits>
namespace lie_gufo {
template<class F> uint32_t visit_rule(lie_schema_memo *memo,
    lie_grammar_builder *builder,const SchemaValue &node,size_t depth,F &&body) {
  using Callback=std::remove_reference_t<F>;
  struct State {
    Callback *callback;std::exception_ptr failure;
    static lie_schema_status invoke(void *p,lie_schema_node n,size_t d,uint32_t *out,lie_schema_error *) noexcept {
      auto &s=*static_cast<State *>(p);
      try { *out=(*s.callback)(schema_value(n),d);return LIE_SCHEMA_OK; }
      catch (const gufo::sampling::JsonSchemaEmpty &) { s.failure=std::current_exception();return LIE_SCHEMA_EMPTY; }
      catch (...) { s.failure=std::current_exception();return LIE_SCHEMA_CALLBACK; }
    }
  };
  State state{&body,{}};lie_schema_body_access access;
  lie_schema_body_access_init(&access);access.context=&state;access.body=State::invoke;
  uint32_t result=0;lie_schema_error error{};
  const auto rc=lie_schema_visit_rule(memo,builder,&node,depth,access,&result,&error);
  // EMPTY from the body is intentionally consumed by the C visit. Failures
  // from committing that empty rule still propagate through builder status.
  if (rc!=LIE_SCHEMA_OK) {
    if (state.failure && rc==LIE_SCHEMA_CALLBACK) std::rethrow_exception(state.failure);
    schema_check(rc,error);
  }
  return result;
}
} // namespace lie_gufo
#endif
