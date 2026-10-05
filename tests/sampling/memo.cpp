// SPDX-License-Identifier: MIT
// Complete recursive-reference states from independently pinned/ON/OFF arms.
// Host grammar witnesses, not original-weight inference or measured GPU cost.
#include "src/core/json.hpp"
#include "src/core/json_constraint.hpp"
#include <cassert>
#include <iostream>
#include <string>
#include <vector>
using gufo::json::Value;
using gufo::sampling::JsonConstraint;
static size_t cases, transitions;
static Value parse(const char *text) { return gufo::json::parse(text); }
static void state(const JsonConstraint &g, const JsonConstraint::State &s) {
  std::cout << "state=" << s.size() << " complete=" << g.Complete(s) << '\n';
  for (const auto &frame : s) {
    std::cout << "symbols=";
    for (auto symbol : frame.symbols)
      std::cout << symbol << ',';
    std::cout << " lexeme=";
    static const char hex[] = "0123456789abcdef";
    for (unsigned char c : frame.lexeme)
      std::cout << hex[c >> 4] << hex[c & 15];
    std::cout << '\n';
  }
}
static void check(Value schema, const std::vector<std::string> &texts) {
  const auto before = schema.dump();
  for (bool strict : {false, true}) {
    std::cout << "schema=" << cases++ << " strict=" << strict << '\n';
    try {
      const auto g = JsonConstraint::Compile(schema, strict);
      for (const auto &text : texts) {
        std::cout << "input=" << text << '\n';
        auto s = g->Start();
        state(*g, s);
        for (unsigned char byte : text) {
          std::cout << "byte=" << unsigned(byte) << '\n';
          s = g->Advance(s, byte);
          state(*g, s);
          ++transitions;
        }
      }
    } catch (const std::invalid_argument &e) {
      std::cout << "INVALID " << e.what() << '\n';
    } catch (const std::runtime_error &e) {
      std::cout << "RUNTIME " << e.what() << '\n';
    }
    assert(schema.dump() == before);
  }
}
int main() {
  for (unsigned aliases : {1u, 2u, 8u, 64u}) {
    auto root = parse(
        R"({"type":"object","properties":{},"required":[],"additionalProperties":false,"$defs":{}})");
    root["description"] = Value("alias-" + std::to_string(aliases));
    root["$defs"]["leaf"] =
        parse(R"({"type":"integer","minimum":0,"maximum":3})");
    for (unsigned i = 0; i < aliases; ++i) {
      auto ref = Value::object();
      ref["$ref"] =
          Value(i + 1 == aliases ? "#/$defs/leaf"
                                 : "#/$defs/d" + std::to_string(i + 1));
      root["$defs"]["d" + std::to_string(i)] = ref;
    }
    for (const auto *key : {"a", "b", "c"}) {
      root["properties"][key] = parse(R"({"$ref":"#/$defs/d0"})");
      root["required"].push_back(Value(key));
    }
    check(root,
          {"{\"a\":1,\"b\":2,\"c\":3}", "{\"a\":4,\"b\":2,\"c\":3}", "{}"});
    root["properties"]["c"]["maximum"] = Value(1);
    root["description"] = Value("sibling-" + std::to_string(aliases));
    check(root, {"{\"a\":1,\"b\":2,\"c\":1}", "{\"a\":1,\"b\":2,\"c\":2}"});
  }
  const auto recursive = parse(
      R"({"type":"object","properties":{"head":{"$ref":"#/$defs/node"}},"required":["head"],"additionalProperties":false,"$defs":{"node":{"anyOf":[{"type":"null"},{"type":"object","properties":{"n":{"type":"integer"},"next":{"$ref":"#/$defs/node"}},"required":["n","next"],"additionalProperties":false}]}}})");
  for (unsigned depth : {0u, 1u, 4u, 16u}) {
    auto root = recursive;
    root["description"] = Value("recursive-" + std::to_string(depth));
    std::string text = "null";
    for (unsigned i = 0; i < depth; ++i)
      text = "{\"n\":" + std::to_string(i) + ",\"next\":" + text + "}";
    check(root, {"{\"head\":" + text + "}", "{\"head\":null}",
                 "{\"head\":{\"n\":1,\"next\":false}}"});
  }
  check(
      parse(
          R"({"type":"object","properties":{"v":{"$ref":"#/$defs/a"}},"required":["v"],"additionalProperties":false,"$defs":{"a":{"$ref":"#/$defs/b"},"b":{"$ref":"#/$defs/a"}}})"),
      {"{\"v\":0}"});
  check(
      parse(
          R"({"type":"object","properties":{"v":{"$ref":"#/$defs/a"}},"required":["v"],"additionalProperties":false,"$defs":{"a":{"anyOf":[{"$ref":"#/$defs/a"},{"type":"null"}]}}})"),
      {"{\"v\":null}"});
  check(
      parse(
          R"({"type":"object","properties":{"v":{"$ref":"#/$defs/a"}},"required":["v"],"additionalProperties":false,"$defs":{"a":{"type":"object","properties":{"next":{"$ref":"#/$defs/a"}},"required":["next"],"additionalProperties":false}}})"),
      {"{\"v\":{}}"});
  check(
      parse(
          R"({"type":"object","properties":{"v":{"$ref":"#/missing"}},"required":["v"],"additionalProperties":false})"),
      {"{}"});
  std::cout << "REFERENCE_MEMO_CASES=" << cases
            << " TRANSITIONS=" << transitions << " HOST_NOT_INFERENCE\n";
}
