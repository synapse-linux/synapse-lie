// SPDX-License-Identifier: MIT
// Typed projection witnesses for final qualification, HOST NOT-INFERENCE.
#include "src/core/json.hpp"
#include "src/core/json_schema_lexeme.hpp"
#include "gufo_schema_string.hpp"
#include <cassert>
#include <iostream>
#include <string>
#include <vector>
int main() {
  using gufo::json::parse;
  using gufo::sampling::JsonSchemaLexeme;
  const auto schema = parse(R"({"pattern":"^[ab]+$","minLength":1,"maxLength":2})");
  const auto saved = schema.dump();
  const auto p = JsonSchemaLexeme::String(schema);
  for (const auto &text : std::vector<std::string>{"\"a\"", "\"ab\"", "\"ba\"", "\"b\""})
    assert(p->Check(text).complete);
  for (const auto &text : std::vector<std::string>{"\"\"", "\"c\"", "\"aba\""})
    assert(!p->Check(text).complete);
  assert(schema.dump() == saved);
  const auto empty = JsonSchemaLexeme::String(parse("{}"));
  const auto bounded = JsonSchemaLexeme::String(parse(R"({"maxLength":1})"));
  assert(empty->Check("\"AA\"").complete && !bounded->Check("\"AA\"").complete);
  assert(bounded->Check("\"\\ud83d\\ude00\"").complete);
  const struct { const char *schema, *diagnostic; bool empty; } cases[] = {
    {R"({"maxLength":-1})", "JSON Schema: string lengths must be nonnegative integers up to 1048576", false},
    {R"({"minLength":2,"maxLength":1,"pattern":false})", "JSON Schema: minLength exceeds maxLength", true},
    {R"({"pattern":"[","format":false})", "JSON Schema: format must be a string", false},
    {R"({"pattern":"[","format":"unsupported"})", "JSON Schema: unsupported string format", false},
    {R"({"minLength":254,"format":"hostname"})", "JSON Schema: string predicates and lengths have no matching value", true}
  };
  for (const auto &c : cases) {
    bool caught = false;
    try { JsonSchemaLexeme::String(parse(c.schema)); }
    catch (const gufo::sampling::JsonSchemaEmpty &e) {
      assert(c.empty && std::string(e.what()) == c.diagnostic); caught = true;
    } catch (const std::invalid_argument &e) {
      assert(!c.empty && std::string(e.what()) == c.diagnostic); caught = true;
    }
    assert(caught);
  }
  std::cout << "Native schema string typed projections/reuse: HOST NOT-INFERENCE\n";
}
