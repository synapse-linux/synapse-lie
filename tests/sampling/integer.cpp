// SPDX-License-Identifier: MIT
// Original/default-ON/OFF exact magnitude, ordered refusal and complete
// selected grammar state/mask witnesses. HOST NOT-INFERENCE.
#include "src/core/json.hpp"
#include "src/core/json_constraint.hpp"
#include <algorithm>
#include <array>
#include <cassert>
#include <charconv>
#include <cmath>
#include <iostream>
#include <limits>
#include <string>
#include <vector>
#if LIE_C17_SAMPLING
#include "lie/schema_integer.h"
#endif
namespace gufo::sampling {
uint32_t LieSchemaIntegerRuleProbe(const json::Value &);
}
using gufo::json::Value;
using gufo::sampling::JsonConstraint;
using gufo::sampling::ConstraintVocabulary;
static size_t cases, magnitude_cases, states, masks;
static std::string decimal(double value) {
  std::array<char, 512> text;
  auto [end, error] = std::to_chars(text.data(), text.data() + text.size(),
                                  std::abs(value), std::chars_format::fixed, 0);
  assert(error == std::errc{});
#if LIE_C17_SAMPLING
  std::array<char, 512> native; size_t bytes = 0;
  assert(lie_schema_integer_magnitude(value, native.data(), native.size(), &bytes) == LIE_SCHEMA_OK);
  assert(bytes == size_t(end - text.data()) && std::equal(text.data(), end, native.data()));
#endif
  ++magnitude_cases;
  return {text.data(), end};
}
static void state(const JsonConstraint &g, const JsonConstraint::State &s,
                  const ConstraintVocabulary &v, bool mask) {
  std::cout << "state=" << s.size() << " complete=" << g.Complete(s) << ' ';
  for (const auto &frame : s) {
    std::cout << '[';
    for (auto symbol : frame.symbols) std::cout << symbol << ',';
    std::cout << "]{";
    for (unsigned char byte : frame.lexeme) std::cout << unsigned(byte) << ',';
    std::cout << '}';
  }
  if (mask) {
    std::cout << " mask=";
    for (auto bit : v.Allowed(g, s)) std::cout << unsigned(bit);
    ++masks;
  }
  std::cout << '\n'; ++states;
}
static void check(const Value &leaf, const std::vector<std::string> &probes) {
  std::cout << "case=" << cases++ << ' ';
  try {
    const auto id = gufo::sampling::LieSchemaIntegerRuleProbe(leaf);
    std::cout << "rule=" << id << '\n';
    Value root = Value::object(); root["type"] = "object";
    root["properties"] = Value::object(); root["properties"]["v"] = leaf;
    root["required"] = Value::array(); root["required"].push_back("v");
    root["additionalProperties"] = false;
    const auto before = root.dump();
    const auto g = JsonConstraint::Compile(root, false);
    assert(root.dump() == before);
    std::cout << "prompt=" << g->prompt() << '\n';
    const ConstraintVocabulary v(257, [](uint32_t id) {
      return ConstraintVocabulary::Piece{id < 256 ? std::string(1, char(id)) : "", id == 256};
    });
    for (const auto &probe : probes) {
      const auto text = "{\"v\":" + probe + "}";
      std::cout << "input=" << text << '\n';
      auto s = g->Start(); state(*g, s, v, true);
      for (size_t i = 0; i < text.size(); ++i) {
        s = g->Advance(s, static_cast<unsigned char>(text[i]));
        state(*g, s, v, i == 0 || i == text.size() / 2 || i + 1 == text.size());
      }
    }
  } catch (const gufo::sampling::JsonSchemaEmpty &e) { std::cout << "EMPTY " << e.what() << '\n'; }
    catch (const std::invalid_argument &e) { std::cout << "INVALID " << e.what() << '\n'; }
    catch (const std::runtime_error &e) { std::cout << "RUNTIME " << e.what() << '\n'; }
}
int main() {
  for (int exponent = 0; exponent <= 1023; ++exponent)
    for (double significand : {1.0, 1.5, std::nextafter(2.0, 0.0)}) {
      const auto value = std::floor(std::ldexp(significand, exponent));
      std::cout << "magnitude=" << exponent << ':' << decimal(value) << '\n';
      assert(decimal(-value) == decimal(value));
    }
  const std::vector<std::string> small = {"-2", "-1", "-0", "0", "1", "2", "01", "1.0", "1e0"};
  auto leaf = Value::object(); leaf["type"] = "integer";
  check(leaf, small);
  for (double low : {-1.5, -1.0, -0.5, -0.0, 0.5, 1.0, 1.5})
    for (double high : {-1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5})
      for (unsigned flags = 0; flags < 4; ++flags) {
        auto schema = leaf;
        schema[flags & 2 ? "exclusiveMaximum" : "maximum"] = high;
        schema[flags & 1 ? "exclusiveMinimum" : "minimum"] = low;
        check(schema, small);
      }
  for (double value : {-10.0, -1.0, -0.0, 0.0, 1.0, 10.0, 9007199254740992.0,
                       1000000000000000128.0, 1e100, std::numeric_limits<double>::max()}) {
    auto digits = decimal(value);
    std::vector<std::string> probes = {digits, "-" + digits, digits + "0", "0", "-0"};
    if (value == 9007199254740992.0) probes.push_back("9007199254740993");
    for (const char *key : {"minimum", "exclusiveMinimum", "maximum", "exclusiveMaximum"}) {
      auto schema = leaf; schema[key] = value; check(schema, probes);
    }
    auto schema = leaf; schema["minimum"] = value; schema["maximum"] = value;
    check(schema, probes);
  }
  const std::vector<Value> invalid = {Value(), Value(true), Value("bad"), Value::array(),
      Value::object(), Value(std::numeric_limits<double>::infinity()),
      Value(-std::numeric_limits<double>::infinity()), Value(std::numeric_limits<double>::quiet_NaN())};
  for (const char *key : {"minimum", "exclusiveMinimum", "maximum", "exclusiveMaximum"})
    for (const auto &value : invalid) { auto schema = leaf; schema[key] = value; check(schema, small); }
  auto ordered = leaf;
  ordered["exclusiveMaximum"] = "last"; ordered["maximum"] = "third";
  ordered["exclusiveMinimum"] = "second"; ordered["minimum"] = "first";
  check(ordered, small);
  ordered["minimum"] = 0.0; check(ordered, small);
  ordered["exclusiveMinimum"] = -1.0; check(ordered, small);
  ordered["maximum"] = 1.0; check(ordered, small);
  std::cout << "INTEGER_COMPLETE cases=" << cases << " magnitudes=" << magnitude_cases
            << " states=" << states << " masks=" << masks << " HOST_NOT_INFERENCE\n";
}
