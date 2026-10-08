// SPDX-License-Identifier: MIT
// Complete ordered JSON/refusal witnesses from pristine, selected C17 and OFF.
#include "src/core/json.hpp"
#include <cassert>
#include <iostream>
#include <string>
#include <vector>
namespace gufo::sampling {
json::Value LieSchemaConjoinProbe(const json::Value &,const json::Value &,const json::Value &,unsigned);
bool LieSchemaEqualProbe(const json::Value &,const json::Value &);
const json::Value *LieSchemaReferenceProbe(const json::Value &,const json::Value &);
void LieSchemaKeysProbe(const json::Value &);
}
using gufo::json::Value;
static size_t cases;
template<class F> static void witness(const char *kind,F f) {
  std::cout<<kind<<' '<<cases++<<' ';
  try { std::cout<<f(); }
  catch (const std::invalid_argument &e) { std::cout<<"INVALID "<<e.what(); }
  catch (const std::exception &e) { std::cout<<"ERROR "<<e.what(); }
  std::cout<<'\n';
}
static Value parse(const char *s) { return gufo::json::parse(s); }
static void join(const Value &root,const Value &l,const Value &r,unsigned depth=0) {
  const auto before_l=l.dump(),before_r=r.dump(),before_root=root.dump();
  witness("JOIN",[&]{ return gufo::sampling::LieSchemaConjoinProbe(root,l,r,depth).dump(); });
  assert(l.dump()==before_l && r.dump()==before_r && root.dump()==before_root);
}
int main() {
  const auto root=parse(R"({"$defs":{"n":{"type":"number","minimum":-2,"multipleOf":0.1},"a/b~c":{"type":"string"}},"choices":[{"type":"integer"},{"type":"null"}],"":{"type":"boolean"}})");
  const std::vector<Value> schemas={
    parse("{}"),parse(R"({"type":"number"})"),parse(R"({"type":"integer"})"),parse(R"({"type":"string"})"),parse(R"({"type":"boolean"})"),
    parse(R"({"type":["number","null"]})"),parse(R"({"type":["integer","null"]})"),
    parse(R"({"type":"number","minimum":-3,"maximum":7,"multipleOf":0.2})"),
    parse(R"({"type":"number","minimum":-1,"maximum":5,"multipleOf":0.3})"),
    parse(R"({"type":"number","exclusiveMinimum":1,"exclusiveMaximum":8})"),
    parse(R"({"type":"string","pattern":"a","minLength":1,"maxLength":8})"),
    parse(R"({"type":"string","pattern":"b","minLength":2,"maxLength":7})"),
    parse(R"({"type":"string","format":"date"})"),parse(R"({"type":"string","format":"date-time"})"),
    parse(R"({"type":"string","enum":["a","b","b"]})"),parse(R"({"type":"string","enum":["b","c"]})"),
    parse(R"({"type":"string","const":"a"})"),parse(R"({"type":"string","const":"b"})"),
    parse(R"({"type":"array","items":{"type":"integer"},"minItems":1,"maxItems":5})"),
    parse(R"({"type":"array","items":{"type":"number"},"minItems":2,"maxItems":4})"),
    parse(R"({"anyOf":[{"type":"integer"},{"type":"string"}]})"),
    parse(R"({"anyOf":[{"type":"number"},{"type":"boolean"}]})"),
    parse(R"({"$ref":"#/$defs/n","maximum":6})"),
    parse(R"({"type":"object","properties":{"a":{"type":"number"},"b":{"type":"string"}},"required":["a"],"additionalProperties":false})"),
    parse(R"({"type":"object","properties":{"b":{"type":"string","maxLength":3},"a":{"type":"integer"},"c":{"type":"null"}},"required":["a","b","b"],"additionalProperties":false})"),
    parse(R"({"type":"object","properties":{"a":{"type":"integer"},"c":{"type":"null"}},"additionalProperties":true})"),
    parse(R"({"title":"left","description":"old"})"),parse(R"({"title":"right","description":"new"})")};
  for (const auto &l:schemas) for (const auto &r:schemas) join(root,l,r);
  const std::vector<Value> malformed={parse("true"),parse(R"({"unsupported":1})"),parse(R"({"title":3})"),parse(R"({"description":[]})"),parse(R"({"anyOf":[]})"),parse(R"({"anyOf":1})"),parse(R"({"type":"number","minimum":"x"})"),parse(R"({"type":"string","pattern":3})"),parse(R"({"enum":1})"),parse(R"({"required":3})"),parse(R"({"properties":[]})"),parse(R"({"format":1})"),parse(R"({"$ref":"http://example"})"),parse(R"({"$ref":"#/absent"})")};
  auto invalid_inputs=malformed;
  invalid_inputs.push_back(parse(R"({"properties":[1,2]})"));
  invalid_inputs.push_back(parse(R"({"properties":"x"})"));
  invalid_inputs.push_back(parse(R"({"properties":false})"));
  for (const auto &v:invalid_inputs) {
    witness("KEYS",[&]{ gufo::sampling::LieSchemaKeysProbe(v); return std::string("OK"); });
    for (const auto &r:schemas) { join(root,v,r); join(root,r,v); }
  }
  const std::vector<Value> values={Value(),Value(false),Value(true),Value(0.0),Value(-0.0),Value(1.0),Value(9007199254740992.0),Value("1"),Value(std::string("a\0b",3)),parse("[]"),parse("[1,2]"),parse("[2,1]"),parse(R"({"a":1,"b":[2]})"),parse(R"({"b":[2],"a":1})"),parse(R"({"b":[3],"a":1})")};
  for (const auto &a:values) for (const auto &b:values) witness("EQUAL",[&]{ return gufo::sampling::LieSchemaEqualProbe(a,b) ? "1" : "0"; });
  const std::vector<Value> refs={Value("#"),Value("#/"),Value("#/$defs/n"),Value("#/$defs/a~1b~0c"),Value("#/choices/00"),Value("#/choices/1"),Value("#/choices/+0"),Value("#/choices/-0"),Value("#/choices/2"),Value("#/choices/184467440737095516160"),Value("#/$defs/a~2b"),Value("#/$defs/a~"),Value("#/missing"),Value("#x"),Value(""),Value(1)};
  for (const auto &r:refs) witness("REF",[&]{ return gufo::sampling::LieSchemaReferenceProbe(root,r)->dump(); });
  const auto cyclic=parse(R"({"$ref":"#"})"); join(cyclic,cyclic,parse("{}"));
  join(root,parse("{}"),parse("{}"),65);
  std::cout<<"COMPLETE_SCHEMA_CASES "<<cases<<" HOST_NOT_INFERENCE\n";
}
