// SPDX-License-Identifier: MIT
// Complete normalization, type and finite-container witnesses from three arms.
#include "src/core/json.hpp"
#include "src/core/json_constraint.hpp"
#include <cassert>
#include <iostream>
#include <vector>
namespace gufo::sampling {
std::string LieSchemaValueProbe(const json::Value &, const json::Value &,
                                const json::Value &, size_t);
bool LieSchemaTypeProbe(const json::Value &, std::string_view);
} // namespace gufo::sampling
using gufo::json::Value;
static size_t cases;
template <class F> static void witness(const char *kind, F f) {
  std::cout << kind << ' ' << cases++ << ' ';
  try {
    std::cout << f();
  } catch (const std::invalid_argument &e) {
    std::cout << "INVALID " << e.what();
  } catch (const std::exception &e) {
    std::cout << "ERROR " << e.what();
  }
  std::cout << '\n';
}
static Value parse(const char *s) { return gufo::json::parse(s); }
static bool accepts(const gufo::sampling::JsonConstraint &g,
                    const std::string &text) {
  auto state = g.Start();
  for (unsigned char byte : text)
    state = g.Advance(state, byte);
  return g.Complete(state);
}
int main() {
  const auto root = parse(
      R"({"$defs":{"n":{"type":"number","minimum":-2},"s":{"type":"string","pattern":"^a"}}})");
  const std::vector<Value> schemas = {
      parse("{}"),
      parse(R"({"type":"number"})"),
      parse(R"({"type":"integer"})"),
      parse(R"({"type":"string"})"),
      parse(R"({"type":"boolean"})"),
      parse(R"({"type":"null"})"),
      parse(R"({"type":["number","null"]})"),
      parse(R"({"enum":[1,"a",null]})"),
      parse(R"({"const":-0.0})"),
      parse(R"({"type":"number","minimum":-1,"maximum":3,"multipleOf":0.5})"),
      parse(R"({"type":"string","minLength":2,"maxLength":3,"pattern":"a"})"),
      parse(R"({"type":"string","format":"date"})"),
      parse(
          R"({"type":"array","items":{"type":"integer"},"minItems":1,"maxItems":3})"),
      parse(
          R"({"type":"array","items":{"anyOf":[{"type":"null"},{"type":"string"}]}})"),
      parse(R"({"anyOf":[{"type":"integer"},{"type":"string"}]})"),
      parse(
          R"({"anyOf":[{"type":"number","minimum":3,"maximum":1},{"type":"number"}]})"),
      parse(R"({"$ref":"#/$defs/n","maximum":1})"),
      parse(R"({"$ref":"#/$defs/s"})"),
      parse(
          R"({"type":"object","properties":{"a":{"type":"number"},"b":{"type":"string"}},"required":["a"],"additionalProperties":false})"),
      parse(
          R"({"type":"object","properties":{"b":{"type":"string"},"a":{"type":"number"}}})"),
      parse(R"({"type":"object","additionalProperties":false})"),
      parse(R"({"type":"string","pattern":"["})"),
      parse(R"({"$ref":"#/absent"})")};
  std::vector<Value> values = {Value(),
                               Value(false),
                               Value(true),
                               Value(0.0),
                               Value(-0.0),
                               Value(1.0),
                               Value(1.5),
                               Value(-3),
                               Value("a"),
                               Value("é😀"),
                               Value(std::string("a\0b", 3)),
                               Value("2026-10-05"),
                               parse("[]"),
                               parse("[1,2]"),
                               parse("[1,2,3,4]"),
                               parse("[\"a\",null]"),
                               parse("{}"),
                               parse(R"({"b":"x","a":1})"),
                               parse(R"({"a":1,"b":"x","extra":true})")};
  for (const auto &schema : schemas)
    for (const auto &value : values) {
      const auto before = value.dump(), before_schema = schema.dump();
      witness("NORMAL", [&] {
        return gufo::sampling::LieSchemaValueProbe(root, schema, value, 0);
      });
      assert(value.dump() == before && schema.dump() == before_schema);
    }
  for (const auto &value : values)
    for (const char *type : {"number", "integer", "string", "boolean", "null",
                             "array", "object", "invalid"})
      witness("TYPE",
              [&] { return gufo::sampling::LieSchemaTypeProbe(value, type); });
  const auto cycle = parse(R"({"$ref":"#"})");
  witness("CYCLE", [&] {
    return gufo::sampling::LieSchemaValueProbe(cycle, cycle, Value(1), 0);
  });
  witness("DEPTH", [&] {
    return gufo::sampling::LieSchemaValueProbe(root, schemas[0], Value(1), 257);
  });
  Value control = Value::object();
  std::string escaped;
  for (int i = 0; i < 32; ++i)
    escaped += char(i);
  escaped += "\"\\/é😀";
  control.append_member(escaped, Value(std::string(400, 'a')));
  auto choices = Value::array();
  choices.push_back(control);
  choices.push_back(parse("[1,null,true,\"a\"]"));
  auto child = Value::object();
  child["enum"] = choices;
  auto parent = parse(
      R"({"type":"object","properties":{},"required":["value"],"additionalProperties":false})");
  parent["properties"]["value"] = child;
  const auto input = std::string("{\"value\":") + control.dump() + "}";
  witness("LITERAL", [&] {
    auto g = gufo::sampling::JsonConstraint::Compile(parent, true);
    return accepts(*g, input);
  });
  for (unsigned required = 0; required < 8; ++required) {
    auto object = parse(
        R"({"type":"object","properties":{"a":{"type":"integer"},"b":{"type":"integer"},"c":{"type":"integer"}},"required":[],"additionalProperties":false})");
    const char *names[] = {"a", "b", "c"};
    for (unsigned i = 0; i < 3; ++i)
      if (required & (1u << i))
        object["required"].push_back(Value(names[i]));
    for (bool strict : {false, true})
      witness("OBJECT", [&] {
        const auto grammar =
            gufo::sampling::JsonConstraint::Compile(object, strict);
        std::string accepted;
        for (unsigned subset = 0; subset < 8; ++subset) {
          auto v = Value::object();
          for (unsigned i = 0; i < 3; ++i)
            if (subset & (1u << i))
              v[names[i]] = Value(1);
          accepted += accepts(*grammar, v.dump()) ? '1' : '0';
        }
        return accepted;
      });
  }
  for (unsigned low = 0; low < 4; ++low)
    for (unsigned high = 0; high < 5; ++high)
      witness("ARRAY", [&] {
        auto parent = parse(
            R"({"type":"object","properties":{"a":{"type":"array","items":{"type":"integer"}}},"required":["a"],"additionalProperties":false})");
      parent["properties"]["a"]["minItems"] = Value(static_cast<double>(low));
      parent["properties"]["a"]["maxItems"] = Value(static_cast<double>(high));
        const auto grammar =
            gufo::sampling::JsonConstraint::Compile(parent, true);
        std::string accepted;
        for (unsigned n = 0; n < 7; ++n) {
          std::string text = "{\"a\":[";
          for (unsigned i = 0; i < n; ++i)
            text += (i ? ",1" : "1");
          text += "]}";
          accepted += accepts(*grammar, text) ? '1' : '0';
        }
        return accepted;
      });
  std::cout << "COMPLETE_VALUE_CASES " << cases << " HOST_NOT_INFERENCE\n";
}
