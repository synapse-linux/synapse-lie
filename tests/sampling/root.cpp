// SPDX-License-Identifier: MIT
// Complete immutable grammar states/masks and root refusal-order witnesses.
#include "src/core/json.hpp"
#include "src/core/json_constraint.hpp"
#include <cassert>
#include <iostream>
#include <string>
#include <vector>
#if LIE_C17_SAMPLING
#include "gufo_schema_root.hpp"
#endif
using gufo::json::Value;
using gufo::sampling::JsonConstraint;
using gufo::sampling::ConstraintVocabulary;
static size_t cases, compiled, accepted, transitions, masks, mask_refusals;
static void state(const JsonConstraint &g, const JsonConstraint::State &s,
                  const ConstraintVocabulary &v) {
  std::cout << "state=" << s.size() << " complete=" << g.Complete(s) << '\n';
  for (const auto &frame : s) {
    std::cout << "symbols=";
    for (auto symbol : frame.symbols) std::cout << symbol << ',';
    std::cout << " lexeme=";
    static const char hex[] = "0123456789abcdef";
    for (unsigned char byte : frame.lexeme) std::cout << hex[byte >> 4] << hex[byte & 15];
    std::cout << '\n';
  }
  try {
    const auto allowed = v.Allowed(g, s);
    std::cout << "mask=";
    for (auto bit : allowed) std::cout << unsigned(bit);
    std::cout << '\n';
  } catch (const std::runtime_error &e) {
    std::cout << "MASK_RUNTIME " << e.what() << '\n'; ++mask_refusals;
  }
  ++masks;
}
static void language(const JsonConstraint &g) {
  const ConstraintVocabulary v(257, [](uint32_t id) {
    return ConstraintVocabulary::Piece{id < 256 ? std::string(1, char(id)) : "", id == 256};
  });
  std::cout << "prompt=" << g.prompt() << '\n';
  for (const char *text : {"", "{}", " {} ", "[]", "null", "true", "{\"v\":0}",
       "{\"v\":1}", "{\"v\":3}", "{\"v\":4}", "{\"v\":null}", "{\"v\":\"a\"}",
       "{\"v\":\"b\"}", "{\"v\":[1,2]}", "{\"v\":{\"v\":null}}", "{\"unknown\":0}",
       "{\"v\":1,\"v\":2}", "{}{}"}) {
    std::cout << "input=" << text << '\n';
    auto s = g.Start(); state(g, s, v);
    for (unsigned char byte : std::string(text)) {
      std::cout << "byte=" << unsigned(byte) << '\n';
      s = g.Advance(s, byte); state(g, s, v); ++transitions;
    }
    accepted += g.Complete(s);
  }
}
static void check(Value root) {
  const auto before = root.dump();
  for (bool strict : {false, true}) {
    std::cout << "case=" << cases++ << " strict=" << strict << " root=" << before << '\n';
    try { const auto g = JsonConstraint::Compile(root, strict); ++compiled; language(*g); }
    catch (const std::invalid_argument &e) { std::cout << "INVALID " << e.what() << '\n'; }
    catch (const std::runtime_error &e) { std::cout << "RUNTIME " << e.what() << '\n'; }
    assert(root.dump() == before);
  }
}
#if LIE_C17_SAMPLING
static void exceptions() {
  for (unsigned failure = 0; failure < 4; ++failure) {
    const auto root = gufo::json::parse(R"({"type":"object"})");
    lie_builder_description bd; lie_builder_description_init(&bd);
    lie_grammar_builder *b = nullptr;
    assert(lie_builder_create(&bd, &b) == LIE_BUILDER_OK);
    bool caught = false;
    try {
      (void)lie_gufo::schema_root(root, false, b, 0,
        [failure](const Value &, size_t) -> uint32_t {
          if (failure == 0) throw std::invalid_argument("root-invalid");
          if (failure == 1) throw std::runtime_error("root-runtime");
          if (failure == 2) throw std::bad_alloc();
          throw gufo::sampling::JsonSchemaEmpty("root-empty");
        });
    } catch (const gufo::sampling::JsonSchemaEmpty &e) {
      assert(failure == 3 && std::string(e.what()) == "root-empty"); caught = true;
    } catch (const std::invalid_argument &e) {
      assert(failure == 0 && std::string(e.what()) == "root-invalid"); caught = true;
    } catch (const std::runtime_error &e) {
      assert(failure == 1 && std::string(e.what()) == "root-runtime"); caught = true;
    } catch (const std::bad_alloc &) { assert(failure == 2); caught = true; }
    assert(caught); lie_builder_release(b);
  }
}
#endif
int main() {
  for (const char *text : {
    R"({"type":"object","properties":{},"additionalProperties":false})",
    R"({"type":"object","properties":{"v":{"type":"integer","minimum":0,"maximum":3}},"required":["v"],"additionalProperties":false})",
    R"({"type":"object","properties":{"v":{"type":["integer","null"]}},"additionalProperties":false})",
    R"({"type":"object","properties":{},"additionalProperties":false,"anyOf":null})",
    R"({"type":"object","properties":{},"additionalProperties":false,"anyOf":[]})",
    R"({"type":["object"]})", R"({"type":["object","null"]})", R"({"type":"string"})",
    R"({"type":1})", R"({"type":null})", R"({})", R"(false)", R"([])", R"(null)",
    R"({"$ref":"#"})", R"({"$ref":"#","type":"object","unknown":true})",
    R"({"$ref":false})", R"({"$ref":"foreign"})", R"({"$ref":"#/absent"})",
    R"({"$ref":"#/~2"})", R"({"$ref":"#/~"})",
    R"({"$ref":"#/$defs/x","$defs":{"x":{"type":"object","properties":{},"additionalProperties":false}}})",
    R"({"$ref":"#/$defs/a~1b~0c","$defs":{"a/b~c":{"type":"object","properties":{},"additionalProperties":false}}})",
    R"({"$ref":"#/$defs/x","$defs":{"x":{"$ref":"#"}}})",
    R"({"$ref":"#/$defs/x","$defs":{"x":{"$ref":"#/$defs/x"}}})",
    R"({"$ref":"#/$defs/x","$defs":{"x":{"$ref":"#/$defs/y"},"y":{"$ref":"#/$defs/x"}}})",
    R"({"$ref":"#/$defs/x","$defs":{"x":{"type":"object","anyOf":null}}})",
    R"({"$ref":"#/$defs/x","$defs":{"x":{"type":"integer"}}})",
    R"({"$ref":"#/$defs/x","$defs":{"x":{"type":"object","properties":{"v":{"type":"integer"}},"required":["v"],"additionalProperties":false}},"description":"root siblings remain active"})",
    R"({"$ref":"#/$defs/x","$defs":{"x":{"type":"object","properties":{"v":{"type":"string","pattern":"^a$"}},"required":["v"],"additionalProperties":false}},"required":["v"]})",
    R"({"$ref":"#/$defs/x","$defs":{"x":{"type":"object","properties":{},"additionalProperties":false}},"unknown":true})",
    R"({"$ref":"#/x/0","x":[{"type":"object","properties":{},"additionalProperties":false}]})",
    R"({"$ref":"#/x/1","x":[{"type":"object"}]})",
    R"({"$ref":"#/x/-1","x":[{"type":"object"}]})",
    R"({"$ref":"#/x/00","x":[{"type":"object"}]})",
    R"({"type":"object","properties":{"v":{"anyOf":[{"type":"integer","minimum":3,"maximum":1},{"type":"null"}]}},"required":["v"],"additionalProperties":false})",
    R"({"type":"object","properties":{"v":{"anyOf":[{"type":"null"},{"$ref":"#"}]}},"required":["v"],"additionalProperties":false})"
  }) check(gufo::json::parse(text));
  for (size_t count : {1u, 2u, 4u, 8u, 16u, 32u}) {
    Value root = Value::object(); root["$ref"] = "#/$defs/n0";
    auto defs = Value::object();
    for (size_t i = 0; i < count; ++i) {
      auto node = Value::object(); node["$ref"] = "#/$defs/n" + std::to_string(i + 1);
      defs["n" + std::to_string(i)] = std::move(node);
    }
    defs["n" + std::to_string(count)] = gufo::json::parse(
        R"({"type":"object","properties":{},"additionalProperties":false})");
    root["$defs"] = std::move(defs); check(std::move(root));
  }
  std::cout << "object-only\n"; language(*JsonConstraint::Object());
#if LIE_C17_SAMPLING
  exceptions();
#endif
  assert(cases == 86 && compiled > 10 && masks > 1000 && transitions > 1000);
  std::cout << "SCHEMA_ROOT_CASES=" << cases << " COMPILED=" << compiled
            << " ACCEPTED=" << accepted << " TRANSITIONS=" << transitions
            << " MASKS=" << masks << " MASK_REFUSALS=" << mask_refusals
            << " HOST_NOT_INFERENCE\n";
}
