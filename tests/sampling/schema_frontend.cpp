// SPDX-License-Identifier: MIT
// Production native Compile/Object versus retained helper, final HOST fixtures.
#include "src/core/json.hpp"
#include "src/core/json_constraint.hpp"
#include <cassert>
#include <iostream>
#include <string>
#include <vector>
namespace gufo::sampling {
std::shared_ptr<const JsonConstraint> LieSchemaVisitProbe(const json::Value &, const json::Value &,
  const std::vector<size_t> &, std::vector<uint32_t> &);
}
static bool accepts(const gufo::sampling::JsonConstraint &p, const std::string &text) {
  auto state = p.Start(); for (unsigned char c : text) state = p.Advance(state, c);
  return p.Complete(state);
}
int main() {
  using gufo::sampling::JsonConstraint;
  const auto schema = gufo::json::parse(R"({"type":"object","additionalProperties":false,"properties":{"s":{"type":"string","minLength":1,"pattern":"^[ab]+$"},"n":{"type":"number","multipleOf":0.3}},"required":["s","n"]})");
  const auto before = schema.dump();
  const auto production = JsonConstraint::Compile(schema, true);
  std::vector<uint32_t> ids;
  const auto helper = gufo::sampling::LieSchemaVisitProbe(schema, schema, {}, ids);
  assert(production->prompt() == helper->prompt() && schema.dump() == before);
  for (const auto &text : std::vector<std::string>{R"({"s":"ab","n":0.6})", R"({"s":"b","n":0.9})", R"({"s":"c","n":0.6})", R"({"s":"a","n":0.5})", "{}"})
    assert(accepts(*production, text) == accepts(*helper, text));
  assert(JsonConstraint::Compile(schema, true) == production);
  const auto object = JsonConstraint::Object();
  assert(accepts(*object, R"({"nested":[1,true,null,{"text":"x"}]})") && !accepts(*object, "[1]"));
  assert(object->prompt() == "Respond with a single valid JSON object.");
  bool rejected = false;
  try { JsonConstraint::Compile(gufo::json::parse(R"({"type":"object","additionalProperties":false,"properties":{"x":{"type":"string","minLength":2,"maxLength":1}},"required":["x"]})"), true); }
  catch (const std::invalid_argument &) { rejected = true; }
  assert(rejected);
  std::cout << "Native production schema frontend/helper parity: HOST NOT-INFERENCE\n";
}
