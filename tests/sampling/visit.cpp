// SPDX-License-Identifier: MIT
// Independent hit-before-depth and complete recursive grammar witnesses.
#include "src/core/json.hpp"
#include "src/core/json_constraint.hpp"
#include <cassert>
#include <cstdint>
#include <iostream>
#include <limits>
#include <string>
#include <vector>
#if LIE_C17_SAMPLING
#include "gufo_schema_visit.hpp"
#endif
namespace gufo::sampling {
std::shared_ptr<const JsonConstraint> LieSchemaVisitProbe(const json::Value &,
    const json::Value &,const std::vector<size_t> &,std::vector<uint32_t> &);
}
using gufo::json::Value;
using gufo::sampling::JsonConstraint;
static size_t cases,compiled,accepted,transitions;
static void state(const JsonConstraint &g,const JsonConstraint::State &s) {
  std::cout<<"state="<<s.size()<<" complete="<<g.Complete(s)<<'\n';
  for (const auto &frame:s) {
    std::cout<<"symbols=";for (auto v:frame.symbols) std::cout<<v<<',';
    std::cout<<" lexeme=";static const char hex[]="0123456789abcdef";
    for (unsigned char byte:frame.lexeme) std::cout<<hex[byte>>4]<<hex[byte&15];
    std::cout<<'\n';
  }
}
static void check(const char *child) {
  auto root=gufo::json::parse(R"({"type":"object","properties":{},"required":["v"],"additionalProperties":false,"$defs":{"shared":{"type":"integer","minimum":0,"maximum":3}}})");
  root["properties"]["v"]=gufo::json::parse(child);const auto before=root.dump();
  const std::vector<std::vector<size_t>> depths={{0},{0,17,std::numeric_limits<size_t>::max()},{16,17},{17}};
  for (const auto &sequence:depths) {
    std::cout<<"case="<<cases++<<" child="<<child<<" depths=";
    for (auto d:sequence) std::cout<<d<<',';
    std::cout<<'\n';std::vector<uint32_t> ids;
    try {
      const auto g=gufo::sampling::LieSchemaVisitProbe(root,*root.find("properties")->find("v"),sequence,ids);++compiled;
      assert(ids.size()==sequence.size());for (auto id:ids) assert(id==ids[0]);
      for (const char *value:{"0","1","3","4","1.5","true","null","\"a\"","\"aa\"","\"b\"","[]","[1]","{}","{\"n\":1}"}) {
        const std::string text=std::string("{\"v\":")+value+"}";
        std::cout<<"input="<<text<<'\n';auto s=g->Start();state(*g,s);
        for (unsigned char byte:text) { std::cout<<"byte="<<unsigned(byte)<<'\n';s=g->Advance(s,byte);state(*g,s);++transitions; }
        accepted+=g->Complete(s);
      }
    } catch (const std::invalid_argument &e) { std::cout<<"INVALID "<<e.what()<<'\n'; }
      catch (const std::runtime_error &e) { std::cout<<"RUNTIME "<<e.what()<<'\n'; }
    std::cout<<"ids=";for (auto id:ids) std::cout<<id<<',';std::cout<<'\n';assert(root.dump()==before);
  }
}
#if LIE_C17_SAMPLING
static void callback_exceptions() {
  for (unsigned failure=0;failure<4;++failure) {
    lie_schema_memo_description md;lie_schema_memo_description_init(&md);lie_schema_memo *memo=nullptr;
    assert(lie_schema_memo_create(&md,&memo)==LIE_SCHEMA_OK);
    lie_builder_description bd;lie_builder_description_init(&bd);lie_grammar_builder *builder=nullptr;
    assert(lie_builder_create(&bd,&builder)==LIE_BUILDER_OK);const Value node=Value::object();bool caught=false;
    try {
      const auto id=lie_gufo::visit_rule(memo,builder,node,0,[failure](const Value &,size_t)->uint32_t {
        switch (failure) {
        case 0:throw std::invalid_argument("callback-invalid");
        case 1:throw std::runtime_error("callback-runtime");
        case 2:throw std::bad_alloc();
        default:throw gufo::sampling::JsonSchemaEmpty("callback-empty");
        }
      });
      assert(failure==3 && id==0);lie_grammar_description d;assert(lie_builder_finish(builder,id,0,&d)==LIE_BUILDER_EMPTY);caught=true;
    } catch (const std::invalid_argument &e) { assert(failure==0 && std::string(e.what())=="callback-invalid");caught=true; }
      catch (const std::runtime_error &e) { assert(failure==1 && std::string(e.what())=="callback-runtime");caught=true; }
      catch (const std::bad_alloc &) { assert(failure==2);caught=true; }
    assert(caught);lie_builder_release(builder);lie_schema_memo_release(memo);
  }
}
#endif
int main() {
  for (const char *child:{
    R"({"type":"integer"})",R"({"type":"integer","minimum":0,"maximum":3})",
    R"({"type":"integer","minimum":0,"maximum":4,"multipleOf":2})",
    R"({"type":"number"})",R"({"type":"number","minimum":0,"maximum":3})",
    R"({"type":"string"})",R"({"type":"string","minLength":1,"maxLength":2})",
    R"({"type":"string","pattern":"^a+$"})",R"({"type":"boolean"})",R"({"type":"null"})",
    R"({"type":["integer","null"]})",R"({"type":["null","string"],"maxLength":2})",
    R"({"type":"array","items":{"type":"integer"},"maxItems":2})",
    R"({"type":"array","items":{"type":"integer"},"minItems":1,"maxItems":2})",
    R"({"type":"object","properties":{},"additionalProperties":false})",
    R"({"type":"object","properties":{"n":{"type":"integer"}},"required":["n"],"additionalProperties":false})",
    R"({"type":"integer","enum":[0,1,3]})",R"({"type":"string","const":"a"})",
    R"({"type":"string","enum":["a","b"],"pattern":"^a$"})",
    R"({"type":"integer","enum":[0],"minimum":1})",
    R"({"type":"integer","minimum":3,"maximum":1})",
    R"({"$ref":"#/$defs/shared"})",
    R"({"anyOf":[{"type":"null"},{"type":"integer","minimum":0,"maximum":3}]})",
    R"({"anyOf":[{"type":"integer","minimum":3,"maximum":1},{"type":"boolean"}]})",
    R"({"type":"bogus"})",R"({"type":"integer","pattern":"a"})",
    R"({"type":"array","items":false})",R"(false)"}) check(child);
  assert(cases==112 && compiled>=40 && accepted>=40 && transitions>=1000);
#if LIE_C17_SAMPLING
  callback_exceptions();
#endif
  std::cout<<"SCHEMA_VISIT_CASES="<<cases<<" COMPILED="<<compiled<<" ACCEPTED="<<accepted<<" TRANSITIONS="<<transitions<<" HOST_NOT_INFERENCE\n";
}
