// SPDX-License-Identifier: MIT
// HOST_ONLY: ownership/language controls, no model forward or performance claim.
#include "gufo_schema_transform.hpp"
#include <cassert>
#include <iostream>
using gufo::json::Value;
int main() {
  Value escaped=Value::object();const lie_json_value *identity=nullptr;
  {
    lie_gufo::SchemaStore store;
    Value source=Value::object();source["rows"]=Value::array();
    source["rows"].push_back(Value(std::string("a\0b",3)));
    identity=source.raw();const auto &borrowed=store.store(std::move(source));
    assert(borrowed.raw()==identity && borrowed.dump()=="{\"rows\":[\"a\\u0000b\"]}");
    const auto *row=borrowed.find("rows");const auto *child=&row->items()[0];
    for (unsigned i=0;i<2049;++i) store.store(Value(static_cast<std::size_t>(i)));
    assert(borrowed.raw()==identity && child->str()==std::string("a\0b",3));
    escaped=store.take(borrowed);assert(escaped.raw()==identity);
    bool refused=false;
    try { store.take(escaped); } catch (const std::logic_error &) { refused=true; }
    assert(refused);
  }
  assert(escaped.raw()==identity && escaped.dump()=="{\"rows\":[\"a\\u0000b\"]}");
  // Transfer refusal leaves the owning facade and output unchanged.
  lie_json_store_description policy;lie_json_store_description_init(&policy);policy.max_roots=1;
  lie_json_store *raw=nullptr;assert(lie_json_store_create(&policy,&raw)==LIE_JSON_STORE_OK);
  Value first(7),second(9);lie_json_value *out=nullptr;
  assert(first.transfer_root(raw,&out)==LIE_JSON_STORE_OK);const auto sentinel=out;
  assert(second.transfer_root(raw,&out)==LIE_JSON_STORE_LIMIT && out==sentinel && second.as_double()==9);
  auto &inline_view=const_cast<Value &>(Value::facade(sentinel));
  assert(inline_view.transfer_root(raw,&out)==LIE_JSON_STORE_INVALID && out==sentinel);
  lie_json_store_release(raw);
  // Transformer staging publishes an owned result with its exact native root.
  Value transformed;
  {
    lie_gufo::SchemaArena arena;const auto d=arena.description();lie_schema_node result=nullptr;
    lie_schema_value null_value{};null_value.kind=LIE_SCHEMA_NULL;
    assert(d.access.create(d.access.context,&null_value,&result)==LIE_SCHEMA_OK);
    assert(lie_gufo::schema_value(result).is_null());
    identity=lie_gufo::schema_value(result).raw();transformed=arena.take(result);
    assert(transformed.raw()==identity);
    lie_schema_node clone=nullptr;
    assert(d.access.clone(d.access.context,&escaped,&clone)==LIE_SCHEMA_OK);
    identity=lie_gufo::schema_value(clone).raw();transformed=arena.take(clone);
  }
  assert(transformed.raw()==identity && transformed.dump()==escaped.dump());
  std::cout<<"HOST_ONLY schema_store growth=2049 root_identity=pass refusal=pass staging_take=pass\n";
}
