// SPDX-License-Identifier: MIT
// Complete pinned/ON/OFF token-mask/accept-state witnesses; NOT-INFERENCE.
#include "src/core/json_constraint.hpp"
#include <cassert>
#include <cstdio>
#include <thread>
using namespace gufo::sampling;
static void state_witness(const JsonConstraint &g,const JsonConstraint::State &s) {
  std::printf("state=%zu complete=%d\n",s.size(),g.Complete(s));
  for (const auto &f:s) {
    std::printf("symbols=");for (auto id:f.symbols)std::printf("%u,",id);
    std::printf(" lexeme=");for (unsigned char b:f.lexeme)std::printf("%02x",unsigned(b));
    std::printf("\n");
  }
}
int main() {
  std::vector<ConstraintVocabulary::Piece> pieces{{"ignored stop text",true},{"",false}};
  for (unsigned i=0;i<256;++i)pieces.push_back({std::string(1,char(i)),false});
  for (auto s:{"{}","{\"s\":\"","\"}","123","-0.1",".5","1e-3","true","null","é","😀",
    "\\uD83D","\\uDE00","<tool_call>","</tool_call>","</think>","{\"name\":\"f\",\"arguments\":","a","aa","aaa"})
    pieces.push_back({s,false});
  pieces.push_back({std::string(512,'a'),false});
  pieces.push_back({"\xc3",false});pieces.push_back({"\xa9",false});
  pieces.push_back({std::string("a\0b",3),false});pieces.push_back({"é",false});
  auto vocabulary=std::make_shared<ConstraintVocabulary>(pieces.size(),[&](uint32_t id){return pieces.at(id);});
  assert(vocabulary->size()==pieces.size());
  const char *schemas[]={
    R"({"type":"object","properties":{"s":{"type":"string","minLength":1,"maxLength":8}},"required":["s"],"additionalProperties":false})",
    R"({"type":"object","properties":{"s":{"type":"string","pattern":"^(a|é|😀){1,4}$"}},"required":["s"],"additionalProperties":false})",
    R"({"type":"object","properties":{"n":{"type":"number","minimum":-10,"maximum":10,"multipleOf":0.1}},"required":["n"],"additionalProperties":false})",
    R"({"type":"object","properties":{"n":{"type":"integer","minimum":0,"maximum":100}},"required":["n"],"additionalProperties":false})",
    R"({"type":"object","properties":{"s":{"type":"string","format":"date"}},"required":["s"],"additionalProperties":false})"};
  std::vector<std::shared_ptr<const JsonConstraint>> grammars{JsonConstraint::Object()};
  for (auto s:schemas)grammars.push_back(JsonConstraint::Compile(gufo::json::parse(s),true));
  grammars.push_back(JsonConstraint::WithReasoning(grammars[0]));
  for(bool required:{false,true})for(bool parallel:{false,true})
    grammars.push_back(JsonConstraint::WithTools(grammars[0],{{"f",grammars[1]}},required,parallel));
  const std::vector<std::string> texts={"{}","{\"s\":\"é😀\"}",R"({"s":"\uD83D\uDE00"})",
    "{\"n\":-0.3}","{\"n\":100}","{\"s\":\"2026-10-05\"}",
    "reason</think>{}","<tool_call>{\"name\":\"f\",\"arguments\":{\"s\":\"aa\"}}</tool_call>{}",
    "before<tool_call>{\"name\":\"f\",\"arguments\":{\"s\":\"é\"}}</tool_call>after"};
  size_t masks=0,accepts=0,oracle_checks=0;
  for(size_t gi=0;gi<grammars.size();++gi) {
    auto &g=*grammars[gi];TokenConstraint constraint;constraint.grammar=grammars[gi];constraint.vocabulary=vocabulary;
    for(size_t ti=0;ti<texts.size();++ti) {
      auto state=g.Start();
      for(size_t step=0;step<=texts[ti].size();++step) {
        std::printf("grammar=%zu text=%zu step=%zu\n",gi,ti,step);state_witness(g,state);
        try {
          auto mask=constraint.Allowed(state);++masks;
          auto repeated=constraint.Allowed(state);assert(repeated.get()==mask.get());
          assert(*mask==vocabulary->Allowed(g,state));
          std::printf("mask=");for(auto bit:*mask)std::printf("%u",unsigned(bit));std::printf("\n");
          for(size_t id=0;id<pieces.size();++id) {
            if(!g.Complete(state)) {
              bool expected=false;
              if(!pieces[id].stop && !pieces[id].text.empty()) {
                auto next=state;for(unsigned char byte:pieces[id].text)next=g.Advance(next,byte);
                expected=!next.empty();
              }
              assert((*mask)[id]==expected);++oracle_checks;
            }
            if((*mask)[id]) {
              std::printf("accept=%zu\n",id);state_witness(g,vocabulary->Accept(g,state,id));++accepts;
            }
          }
        } catch(const std::runtime_error &e) { std::printf("refused=%s\n",e.what()); }
        if(step<texts[ti].size())state=g.Advance(state,static_cast<unsigned char>(texts[ti][step]));
      }
    }
  }
  // Actual shared-cache callers race miss/compile/publish; retain old snapshots.
  TokenConstraint shared;shared.grammar=grammars[0];shared.vocabulary=vocabulary;
  std::vector<JsonConstraint::State> states;
  std::vector<std::shared_ptr<const std::vector<uint8_t>>> retained;
  std::vector<std::vector<uint8_t>> expected;
  for(size_t n=1;n<=24;++n) {
    auto state=shared.grammar->Start();
    auto text=std::string("{\"n\":")+std::to_string(n);
    for(unsigned char b:text)state=shared.grammar->Advance(state,b);
    states.push_back(state);expected.push_back(vocabulary->Allowed(*shared.grammar,state));
    retained.push_back(shared.Allowed(state));
  }
  std::vector<std::thread> workers;
  for(size_t lane=0;lane<4;++lane)workers.emplace_back([&,lane]{
    for(size_t i=0;i<96;++i) {
      const size_t index=(i*7+lane)%states.size();
      assert(*shared.Allowed(states[index])==expected[index]);
    }
  });
  for(auto &worker:workers)worker.join();
  for(size_t i=0;i<retained.size();++i)assert(*retained[i]==expected[i]);
  std::printf("GRAMMARS=%zu PIECES=%zu MASKS=%zu ACCEPTS=%zu TOKEN_ORACLES=%zu CACHE_THREADS=4 CACHE_QUERIES=384 RETAINED_SNAPSHOTS=24 HOST_NOT_INFERENCE\n",
    grammars.size(),pieces.size(),masks,accepts,oracle_checks);
}
