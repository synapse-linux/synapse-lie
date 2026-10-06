// SPDX-License-Identifier: MIT
// Private typed projections over native construction; pending final tests.
#include "src/core/json.hpp"
#include "src/core/json_constraint.hpp"
#include "gufo_schema_transform.hpp"
#include <cassert>
#include <iostream>
#include <string>
int main() {
  using gufo::json::Value;
  const auto original = gufo::json::parse(R"({"a":[1,2],"text":"A\u0000B"})");
  const auto before = original.dump();
  Value retained;
  {
    lie_gufo::SchemaArena arena;
    auto d = arena.description();
    lie_schema_node copy = nullptr;
    assert(d.access.clone(d.access.context, &original, &copy) == LIE_SCHEMA_OK);
    const auto &value = lie_gufo::schema_value(copy);
    assert(value.dump() == before && value.raw() != original.raw());
    lie_schema_node object = nullptr;
    const lie_schema_value shape{.kind = LIE_SCHEMA_OBJECT};
    assert(d.access.create(d.access.context, &shape, &object) == LIE_SCHEMA_OK);
    assert(d.access.put(d.access.context, object, {"copied", 6}, copy) == LIE_SCHEMA_OK);
    retained = arena.take(object);
    assert(retained["copied"].dump() == before);
    assert(original.dump() == before);
    const auto left = Value(0.3), right = Value(0.2);
    lie_schema_node multiple = nullptr;
    assert(d.access.multiple(d.access.context, &left, &right, &multiple) == LIE_SCHEMA_OK);
    assert(lie_gufo::schema_value(multiple).as_double() == 0.6);
  }
  assert(retained["copied"].dump() == before && original.dump() == before);
  for (unsigned kind = 0; kind < 3; ++kind) {
    lie_gufo::SchemaArena arena;
    const auto d = arena.description();
    lie_schema_node ignored = nullptr;
    const Value invalid(0.0), positive(0.2);
    lie_schema_status rc;
    if (kind == 0)
      rc = d.access.format(d.access.context, {"unsupported-format", 18}, &ignored);
    else if (kind == 1)
      rc = d.access.multiple(d.access.context, &invalid, &positive, &ignored);
    else
      rc = arena.invoke([](auto &) { throw 314; });
    assert(rc == LIE_SCHEMA_CALLBACK && !ignored);
    bool caught = false;
    try { arena.check(rc, {}); }
    catch (const std::invalid_argument &e) {
      assert(kind < 2 && std::string(e.what()).find("JSON Schema:") == 0); caught = true;
    } catch (int value) { assert(kind == 2 && value == 314); caught = true; }
    assert(caught);
  }
  std::cout << "Native schema arena: typed copy/transfer/refusal; HOST NOT-INFERENCE\n";
}
