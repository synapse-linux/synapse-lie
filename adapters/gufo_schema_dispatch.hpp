// SPDX-License-Identifier: MIT
// Typed views/callback and exception translation only; route policy is C17.
#ifndef LIE_GUFO_SCHEMA_DISPATCH_HPP
#define LIE_GUFO_SCHEMA_DISPATCH_HPP
#include "gufo_schema_transform.hpp"
#include "lie/schema_dispatch.h"
#include <string_view>
#include <type_traits>
namespace lie_gufo {
inline lie_schema_dispatch_plan dispatch_types(const SchemaValue &schema) {
  const auto d=schema_reader(); lie_schema_dispatch_plan out{}; lie_schema_error e{};
  schema_check(lie_schema_dispatch_types(&d,&schema,&out,&e),e); return out;
}
template<class F> uint32_t dispatch_rules(const lie_schema_dispatch_plan &plan,
    const SchemaValue &schema, size_t depth, lie_grammar_builder *builder, F &&rule) {
  using Callback=std::remove_reference_t<F>;
  struct State {
    Callback *callback; std::exception_ptr failure;
    static lie_schema_status invoke(void *p,lie_schema_node n,size_t d,
        lie_schema_route route,lie_schema_bytes name,uint32_t *out) noexcept {
      auto &s=*static_cast<State *>(p);
      try { *out=(*s.callback)(schema_value(n),d,route,std::string_view(name.data,name.size)); return LIE_SCHEMA_OK; }
      catch (const gufo::sampling::JsonSchemaEmpty &) { s.failure=std::current_exception(); return LIE_SCHEMA_EMPTY; }
      catch (...) { s.failure=std::current_exception(); return LIE_SCHEMA_CALLBACK; }
    }
  };
  State state{&rule,{}}; uint32_t out=0; lie_schema_error e{};
  const auto rc=lie_schema_dispatch_rules(&plan,&schema,depth,builder,{&state,State::invoke},&out,&e);
  if (state.failure) std::rethrow_exception(state.failure);
  schema_check(rc,e); return out;
}
} // namespace lie_gufo
#endif
