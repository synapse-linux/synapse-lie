// SPDX-License-Identifier: MIT
// Complete type-route states/refusals from pinned/ON/OFF host grammar arms.
#include "src/core/json.hpp"
#include "src/core/json_constraint.hpp"
#include <cassert>
#include <iostream>
#include <string>
#include <vector>
using gufo::json::Value;
using gufo::sampling::JsonConstraint;
static size_t cases, transitions, compiled, accepted;
static void state(const JsonConstraint &g,const JsonConstraint::State &s) {
  std::cout<<"state="<<s.size()<<" complete="<<g.Complete(s)<<'\n';
  for (const auto &f:s) {
    std::cout<<"symbols=";for (auto x:f.symbols) std::cout<<x<<',';
    std::cout<<" lexeme=";static const char hex[]="0123456789abcdef";
    for (unsigned char c:f.lexeme) {
      std::cout<<hex[c>>4]<<hex[c&15];
    }
    std::cout<<'\n';
  }
}
static void check(Value schema) {
  schema["description"]=Value("dispatch-"+std::to_string(cases));
  auto root=gufo::json::parse(R"({"type":"object","properties":{},"required":["v"],"additionalProperties":false})");
  root["properties"]["v"]=schema;
  const auto original=root.dump();
  const std::vector<std::string> texts={"null","true","false","0","-1","2.25","2.5","\"a\"","\"ab\"","\"b\"","[]","[1]","[1,2]","{}","{\"v\":1}","{\"v\":null}"};
  for (bool strict:{false,true}) {
    std::cout<<"case="<<cases++<<" strict="<<strict<<" schema="<<original<<'\n';
    try {
      const auto g=JsonConstraint::Compile(root,strict);++compiled;
      for (const auto &value:texts) {
        const auto text=std::string("{\"v\":")+value+"}";
        std::cout<<"input="<<text<<'\n';auto s=g->Start();state(*g,s);
        for (unsigned char byte:text) { std::cout<<"byte="<<unsigned(byte)<<'\n';s=g->Advance(s,byte);state(*g,s);++transitions; }
        accepted+=g->Complete(s);
      }
    } catch (const std::invalid_argument &e) { std::cout<<"INVALID "<<e.what()<<'\n'; }
      catch (const std::runtime_error &e) { std::cout<<"RUNTIME "<<e.what()<<'\n'; }
    assert(root.dump()==original);
  }
}
static Value base(const char *name) {
  auto s=Value::object();s["type"]=Value(name);
  if (std::string(name)=="object") { s["properties"]=gufo::json::parse(R"({"v":{"type":"integer"}})");s["additionalProperties"]=Value(false);s["required"]=gufo::json::parse(R"(["v"])"); }
  if (std::string(name)=="array") s["items"]=gufo::json::parse(R"({"type":"integer"})");
  return s;
}
int main() {
  const char *names[]={"null","boolean","integer","number","string","object","array","unknown",""};
  for (const char *name:names) {
    for (unsigned shape=0;shape<4;++shape) {
      auto s=base(name);
      if (shape) { auto types=Value::array();if (shape==3) types.push_back(Value("null"));types.push_back(Value(name));if (shape==2) types.push_back(Value("null"));s["type"]=types; }
      check(s);
    }
  }
  const char *keys[]={"minimum","maximum","exclusiveMinimum","exclusiveMaximum","multipleOf","pattern","format","minLength","maxLength","properties","required","additionalProperties","items","minItems","maxItems"};
  for (const char *name:names) for (const char *key:keys) {
    auto s=base(name);s[key]=Value(true);check(s);
  }
  for (const char *type:{"integer","number"}) for (const char *key:{"minimum","maximum","exclusiveMinimum","exclusiveMaximum","multipleOf"}) {
    auto s=base(type);s[key]=Value(0.25);check(s);
  }
  for (const char *source:{
    R"({"type":"string","pattern":"^a"})",R"({"type":"string","minLength":1,"maxLength":2})",
    R"({"type":"string","format":"date"})",R"({"type":"string","pattern":"["})",
    R"({"type":"array","items":{"type":"integer"},"minItems":1,"maxItems":2})",
    R"({"type":["integer","null"],"enum":[1,null,2]})",R"({"type":["null","string"],"const":"a"})",
    R"({"type":[]})",R"({"type":[1]})",R"({"type":["integer","string"]})",
    R"({"type":["null","null"]})",R"({"type":["null","integer","string"]})",
    R"({"type":["integer",false],"properties":{}})",R"({"type":"integer","pattern":"a","properties":{}})",
    R"({"type":"integer","properties":{},"pattern":"a"})",R"({"enum":[1]})",
    R"({"type":"number","minimum":2,"maximum":1})",R"({"type":"object","properties":{},"required":[],"additionalProperties":false})",
    R"({"type":["null","array"],"items":{"anyOf":[{"type":"integer"},{"type":"null"}]}})"}) check(gufo::json::parse(source));
  assert(compiled>=80 && accepted>=160);
  std::cout<<"SCHEMA_DISPATCH_CASES="<<cases<<" TRANSITIONS="<<transitions<<" COMPILED="<<compiled<<" ACCEPTED="<<accepted<<" HOST_NOT_INFERENCE\n";
}
