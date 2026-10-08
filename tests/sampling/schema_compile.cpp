// SPDX-License-Identifier: MIT
// Exact prompt bytes/shared lifetime and schema immutability, never inference.
#include "src/core/json.hpp"
#include "src/core/json_constraint.hpp"
#include "gufo_schema_compile.hpp"
#include <cassert>
#include <iostream>
#include <string>
#include <string_view>
// Written for final qualification; retains the preceding stdout witness.
static void compiler_controls() {
  for (unsigned kind = 0; kind < 5; ++kind) {
    lie_gufo::Compiler compiler;
    unsigned calls = 0;
    bool caught = false;
    try {
      compiler.initialize([&]() -> uint32_t {
        ++calls;
        if (kind == 0) throw std::invalid_argument("bootstrap-invalid");
        if (kind == 1) throw std::runtime_error("bootstrap-runtime");
        if (kind == 2) throw std::bad_alloc();
        if (kind == 3) throw gufo::sampling::JsonSchemaEmpty("bootstrap-empty");
        throw 314;
      });
    } catch (const gufo::sampling::JsonSchemaEmpty &e) {
      assert(kind == 3 && std::string(e.what()) == "bootstrap-empty"); caught = true;
    } catch (const std::invalid_argument &e) {
      assert(kind == 0 && std::string(e.what()) == "bootstrap-invalid"); caught = true;
    } catch (const std::runtime_error &e) {
      assert(kind == 1 && std::string(e.what()) == "bootstrap-runtime"); caught = true;
    } catch (const std::bad_alloc &) { assert(kind == 2); caught = true; }
    catch (int value) { assert(kind == 4 && value == 314); caught = true; }
    assert(caught && calls == 1);
    caught = false;
    try { compiler.initialize([&] { ++calls; return LIE_GRAMMAR_LEXEME; }); }
    catch (const std::logic_error &e) {
      assert(std::string(e.what()) == "JSON Schema: invalid C17 compiler phase"); caught = true;
    }
    assert(caught && calls == 1);
  }
  lie_gufo::Lexemes lexemes;
  lie_gufo::SchemaCompilation compiled{};
  {
    lie_gufo::Compiler compiler;
    compiler.initialize([&] {
      lexemes.push_back(gufo::sampling::JsonSchemaLexeme::Whitespace());
      return LIE_GRAMMAR_LEXEME;
    });
    auto value = gufo::json::parse(R"({"description":"owned derived value"})");
    const auto &stored = compiler.store(std::move(value));
    assert(stored.member_str("description") == "owned derived value");
    auto schema = gufo::json::parse(R"({"type":"object"})");
    compiled = lie_gufo::schema_compile(schema, true, compiler, lexemes,
      [](const gufo::json::Value &, size_t) -> uint32_t {
        assert(!"Object-only compilation called a visitor"); return 0;
      });
  }
  size_t bytes = 0;
  const char *text = lie_schema_prompt_bytes(compiled.prompt.get(), &bytes);
  assert(std::string_view(text, bytes) == "Respond with a single valid JSON object.");
  lie_grammar_state *state = nullptr;
  assert(lie_grammar_start(compiled.program.get(), &state) == LIE_GRAMMAR_OK);
  lie_grammar_state_release(state);
  compiled = {}; // Retire program before its independently owned predicate table.
}
int main() {
  compiler_controls();
  using gufo::json::Value;
  using gufo::sampling::JsonConstraint;
  std::shared_ptr<const JsonConstraint> base, reasoning, tools;
  std::string expected;
  const char *identity = nullptr;
  {
    auto schema = gufo::json::parse(R"({"type":"object","properties":{"v":{"type":"integer"}},"required":["v"],"additionalProperties":false,"description":"A\u0000B\n\"\\Z"})");
    expected = "Respond with a single JSON object matching this JSON Schema:\n" + schema.dump();
    base = JsonConstraint::Compile(schema, false);
    assert(base->prompt() == expected);
    identity = base->prompt().data();
    reasoning = JsonConstraint::WithReasoning(base);
    tools = JsonConstraint::WithTools(base, {{std::string("echo\0bytes", 10), base}}, false, true);
    assert(reasoning->prompt().data() == identity && tools->prompt().data() == identity);
    assert(reasoning->prompt() == expected && tools->prompt() == expected);
    schema["description"] = "changed";
    assert(base->prompt() == expected && base->prompt().data() == identity);
  }
  base.reset(); reasoning.reset();
  assert(tools->prompt().data() == identity && tools->prompt() == expected);
  const auto object = JsonConstraint::Object();
  assert(object->prompt() == "Respond with a single valid JSON object.");
  const auto tool_only = JsonConstraint::WithTools(nullptr, {{"f", object}}, true, false);
  assert(tool_only->prompt().data() == object->prompt().data());
  assert(tool_only->prompt() == object->prompt());
  for (unsigned kind = 0; kind < 4; ++kind) {
    const auto schema = gufo::json::parse(R"({"type":"object"})");
    auto builder = lie_gufo::builder_create();
    lie_gufo::Lexemes lexemes;
    bool caught = false;
    try {
      (void)lie_gufo::schema_compile(schema, false, builder.get(), 0, lexemes,
        [kind](const Value &, size_t) -> uint32_t {
          if (kind == 0) throw std::invalid_argument("native-invalid");
          if (kind == 1) throw std::runtime_error("native-runtime");
          if (kind == 2) throw std::bad_alloc();
          throw gufo::sampling::JsonSchemaEmpty("native-empty");
        });
    } catch (const gufo::sampling::JsonSchemaEmpty &e) {
      assert(kind == 3 && std::string(e.what()) == "native-empty"); caught = true;
    } catch (const std::invalid_argument &e) {
      assert(kind == 0 && std::string(e.what()) == "native-invalid"); caught = true;
    } catch (const std::runtime_error &e) {
      assert(kind == 1 && std::string(e.what()) == "native-runtime"); caught = true;
    } catch (const std::bad_alloc &) { assert(kind == 2); caught = true; }
    assert(caught);
  }
  std::cout << "schema compile: exact schema/object prompts; shared reasoning/tool identity; input retirement/mutation preserved\n";
}
