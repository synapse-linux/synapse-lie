// SPDX-License-Identifier: MIT
// Complete states and ordered errors for definitions/refs/anyOf/finite bodies.
#include "src/core/json.hpp"
#include "src/core/json_constraint.hpp"
#include <cassert>
#include <iostream>
#include <string>
#include <vector>
#if LIE_C17_SAMPLING
#include "gufo_schema_body.hpp"
#endif
using gufo::json::Value;
using gufo::sampling::JsonConstraint;
static size_t cases, compiled, accepted, transitions;
static void state(const JsonConstraint &g, const JsonConstraint::State &s) {
  std::cout << "state=" << s.size() << " complete=" << g.Complete(s) << '\n';
  for (const auto &frame : s) {
    std::cout << "symbols=";
    for (auto v : frame.symbols)
      std::cout << v << ',';
    std::cout << " lexeme=";
    static const char hex[] = "0123456789abcdef";
    for (unsigned char byte : frame.lexeme)
      std::cout << hex[byte >> 4] << hex[byte & 15];
    std::cout << '\n';
  }
}
static void check(Value child) {
  auto root = gufo::json::parse(
      R"({"type":"object","properties":{},"required":["v"],"additionalProperties":false,"$defs":{"n":{"type":"integer","minimum":0,"maximum":3},"s":{"type":"string","pattern":"^a+$"},"o":{"type":"object","properties":{"n":{"$ref":"#/$defs/n"}},"required":["n"],"additionalProperties":false}}})");
  root["properties"]["v"] = child;
  const auto before = root.dump();
  for (bool strict : {false, true}) {
    std::cout << "case=" << cases++ << " strict=" << strict
              << " root=" << before << '\n';
    try {
      const auto g = JsonConstraint::Compile(root, strict);
      ++compiled;
      for (const char *value :
           {"null",      "true",      "false",
            "0",         "-1",        "1",
            "2",         "3",         "4",
            "1.5",       "\"a\"",     "\"aa\"",
            "\"b\"",     "[]",        "[1,2]",
            "[4]",       "{}",        "{\"n\":1}",
            "{\"n\":4}", "{\"x\":1}", "{\"b\":2,\"a\":1}"}) {
        const std::string input = std::string("{\"v\":") + value + "}";
        std::cout << "input=" << input << '\n';
        auto s = g->Start();
        state(*g, s);
        for (unsigned char byte : input) {
          std::cout << "byte=" << unsigned(byte) << '\n';
          s = g->Advance(s, byte);
          state(*g, s);
          ++transitions;
        }
        accepted += g->Complete(s);
      }
    } catch (const std::invalid_argument &e) {
      std::cout << "INVALID " << e.what() << '\n';
    } catch (const std::runtime_error &e) {
      std::cout << "RUNTIME " << e.what() << '\n';
    }
    assert(root.dump() == before);
  }
}
#if LIE_C17_SAMPLING
static void callback_exceptions() {
  for (unsigned hook = 0; hook < 4; ++hook)
    for (unsigned failure = 0; failure < 4; ++failure) {
      lie_builder_description bd;
      lie_builder_description_init(&bd);
      lie_grammar_builder *b = nullptr;
      assert(lie_builder_create(&bd, &b) == LIE_BUILDER_OK);
      const auto schema = gufo::json::parse(
          hook == 0   ? R"({"$defs":{"n":{"type":"null"}},"type":"null"})"
          : hook == 3 ? R"({"type":"null"})"
                      : R"({"type":"null","const":null})");
      const auto throwing = [failure]() {
        switch (failure) {
        case 0:
          throw std::invalid_argument("body-invalid");
        case 1:
          throw std::runtime_error("body-runtime");
        case 2:
          throw std::bad_alloc();
        default:
          throw gufo::sampling::JsonSchemaEmpty("body-empty");
        }
      };
      lie_schema_container_counts counts{};
      size_t enums = 0;
      bool caught = false;
      try {
        const auto id = lie_gufo::schema_body(
            schema, schema, 0, b, 0, counts, enums,
            [&](const Value &, size_t) -> uint32_t {
              if (hook == 0)
                throwing();
              uint32_t id = 0;
              lie_gufo::builder_check(lie_builder_literal(
                  b, reinterpret_cast<const uint8_t *>("null"), 4, &id));
              return id;
            },
            [&](const Value &v) -> const Value & {
              if (hook == 1)
                throwing();
              return v;
            },
            [&](const Value &, const Value &v) -> std::optional<Value> {
              if (hook == 2)
                throwing();
              return v;
            },
            [&](const Value &, size_t, lie_schema_route,
                std::string_view) -> uint32_t {
              if (hook == 3)
                throwing();
              return 0;
            });
        (void)id;
        assert(false);
      } catch (const gufo::sampling::JsonSchemaEmpty &e) {
        assert(failure == 3);
        assert(std::string(e.what()) ==
               (hook == 2 ? "JSON Schema: enum/const has no value satisfying "
                            "its constraints"
                          : "body-empty"));
        caught = true;
      } catch (const std::invalid_argument &e) {
        assert(failure == 0 && std::string(e.what()) == "body-invalid");
        caught = true;
      } catch (const std::runtime_error &e) {
        assert(failure == 1 && std::string(e.what()) == "body-runtime");
        caught = true;
      } catch (const std::bad_alloc &) {
        assert(failure == 2);
        caught = true;
      }
      assert(caught);
      lie_builder_release(b);
    }
}
#endif
int main() {
  for (
      const char *source :
      {R"({"$ref":"#/$defs/n"})",
       R"({"$ref":"#/$defs/n","minimum":2})",
       R"({"$ref":"#/$defs/n","type":"string"})",
       R"({"$ref":"#/$defs/missing"})",
       R"({"$ref":false})",
       R"({"$ref":"http://external"})",
       R"({"$ref":"#/$defs/s","enum":["a","aa","b"]})",
       R"({"$ref":"#/$defs/o"})",
       R"({"$ref":"#/$defs/n","title":"first","description":"meta"})",
       R"({"anyOf":[{"type":"null"},{"type":"integer","minimum":0,"maximum":3}]})",
       R"({"anyOf":[{"type":"integer"},{"type":"string"}],"type":"integer","enum":[1,2]})",
       R"({"anyOf":[{"$ref":"#/$defs/n"},{"type":"null"}],"type":["integer","null"],"minimum":2})",
       R"({"anyOf":[{"type":"integer","minimum":3,"maximum":1},{"type":"boolean"}]})",
       R"({"anyOf":[{"type":"integer","minimum":3,"maximum":1}]})",
       R"({"anyOf":[]})",
       R"({"anyOf":false})",
       R"({"anyOf":[false,{"type":"null"}]})",
       R"({"type":"integer","enum":[1,2,3]})",
       R"({"type":"integer","enum":[1,2],"const":2})",
       R"({"type":"integer","enum":[1,2],"const":3})",
       R"({"type":"integer","enum":[1,"a"]})",
       R"({"type":"integer","enum":[1.5]})",
       R"({"type":"number","enum":[1,1.5,-0.0],"minimum":0})",
       R"({"type":"string","enum":["a","aa","b"],"pattern":"^a+$"})",
       R"({"type":["null","string"],"enum":[null,"a"]})",
       R"({"type":"object","properties":{"a":{"type":"integer"},"b":{"type":"integer"}},"required":["a","b"],"additionalProperties":false,"const":{"b":2,"a":1}})",
       R"({"type":"array","items":{"type":"integer","maximum":3},"enum":[[],[1,2],[4]]})",
       R"({"type":"array","items":false,"enum":false})",
       R"({"type":"string","pattern":"[","enum":false})",
       R"({"type":"integer","minimum":5,"maximum":1,"enum":false})",
       R"({"type":"integer","enum":[]})",
       R"({"type":"integer","enum":false})",
       R"({"type":"integer","const":1,"title":"a"})",
       R"({"type":"null","$defs":{"a":{"type":"integer"},"b":{"type":"boolean"}}})",
       R"({"type":"null","$defs":{"a":{"type":"bogus"},"b":false}})",
       R"({"type":"null","$defs":false})",
       R"({"$ref":false,"$defs":false})",
       R"({"$defs":{"r":{"$ref":"#/properties/v/$defs/r"}},"$ref":"#/properties/v/$defs/r"})",
       R"({"type":"null","unexpected":true})"})
    check(gufo::json::parse(source));
  // The wire parser rejects duplicate keys. Opaque C/private value views may
  // still contain them, so construct those cases through the value API.
  for (const char *source : {R"({"$ref":"#/$defs/n","title":"first"})",
                             R"({"type":"integer","const":1,"title":"a"})"}) {
    auto duplicate = gufo::json::parse(source);
    duplicate.append_member("title", Value("second"));
    check(duplicate);
  }
  for (unsigned shape = 0; shape < 5; ++shape) {
    auto v = gufo::json::parse(R"({"type":"integer","enum":[]})");
    for (unsigned i = 0; i < (shape == 4 ? 1001u : 17u); ++i)
      v["enum"].push_back(Value(static_cast<int>(i)));
    if (shape == 1)
      v["const"] = Value(2);
    if (shape == 2)
      v["minimum"] = Value(10);
    if (shape == 3)
      v["maximum"] = Value(-1);
    check(v);
  }
  for (unsigned shape = 0; shape < 4; ++shape) {
    auto v = gufo::json::parse(R"({"type":"string","enum":[]})");
    for (unsigned i = 0; i < 251; ++i)
      v["enum"].push_back(Value(std::string(shape ? 61u : 1u, 'a')));
    if (shape == 2)
      v["const"] = Value("b");
    if (shape == 3)
      v["maxLength"] = Value(1);
    check(v);
  }
  for (unsigned shape = 0; shape < 3; ++shape) {
    auto v = gufo::json::parse(R"({"anyOf":[]})");
    for (unsigned i = 0; i < 20; ++i)
      v["anyOf"].push_back(
          gufo::json::parse(i % 2 ? R"({"type":"integer","enum":[0,1,3]})"
                                  : R"({"type":"null"})"));
    if (shape)
      v["type"] = Value("integer");
    if (shape == 2)
      v["minimum"] = Value(2);
    check(v);
  }
  assert(cases >= 90 && compiled >= 40 && accepted >= 80 &&
         transitions >= 10000);
#if LIE_C17_SAMPLING
  callback_exceptions();
#endif
  std::cout << "SCHEMA_BODY_CASES=" << cases << " COMPILED=" << compiled
            << " ACCEPTED=" << accepted << " TRANSITIONS=" << transitions
            << " HOST_NOT_INFERENCE\n";
}
