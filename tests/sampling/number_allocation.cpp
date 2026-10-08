// SPDX-License-Identifier: MIT
// Untimed C++ bridge allocation witness. C arithmetic scratch is separate.
#include "gufo_schema_number.hpp"
#include "allocation_counter.hpp"
#include <cassert>
#include <iostream>
int main() {
  using gufo::json::Value;
  auto schema=Value::object(); schema["multipleOf"]=0.1;
  lie_gufo::SchemaNumber setup;
  auto policy=setup.create(schema,false);
  const Value left(0.1), right(0.3);
  lie_builder_description bd; lie_builder_description_init(&bd);
  lie_grammar_builder *builder=nullptr;
  assert(lie_builder_create(&bd,&builder)==LIE_BUILDER_OK);
  lie_sampling_alloc_begin();
  {
    lie_gufo::SchemaNumber bridge;
    assert(bridge.accept(policy.get(),right));
    assert(bridge.intersect(left,right).as_double()==0.3);
    (void)bridge.literal(right,builder);
  }
  const auto count=lie_sampling_alloc_end();
  assert(count.calls==0 && count.requested_bytes==0 && count.live_bytes==0);
  lie_builder_release(builder);
  std::cout << "NUMERIC_BRIDGE_CPP_ALLOCATIONS=" << count.calls
            << " LIVE_BYTES=" << count.live_bytes
            << " C_WORKSPACES_SEPARATE HOST_NOT_INFERENCE\n";
}
