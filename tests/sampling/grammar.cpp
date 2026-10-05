// SPDX-License-Identifier: MIT
// Complete byte-stack/lexeme/mask witnesses; independently pinned arms.
// Synthetic host grammar, NOT-INFERENCE.
#include "src/core/json_constraint.hpp"
#include <cstdio>
#include <string>
#include <vector>
using namespace gufo::sampling;
static void witness(const JsonConstraint &g, const JsonConstraint::State &s) {
  std::printf("state=%zu complete=%d\n", s.size(), g.Complete(s));
  for (const auto &f : s) {
    std::printf("stack=");
    for (auto symbol : f.symbols)
      std::printf("%u,", symbol);
    std::printf(" lexeme=");
    for (unsigned char byte : f.lexeme)
      std::printf("%02x", unsigned(byte));
    std::printf("\n");
  }
}
int main() {
  const char *schemas[] = {
    R"({"type":"object","properties":{"n":{"type":"number","minimum":0.1,"maximum":20,"multipleOf":0.1}},"required":["n"],"additionalProperties":false})",
    R"({"type":"object","properties":{"s":{"type":"string","minLength":1,"maxLength":8}},"required":["s"],"additionalProperties":false})",
    R"({"type":"object","properties":{"s":{"type":"string","pattern":"^(a|é|😀){1,3}$"}},"required":["s"],"additionalProperties":false})",
    R"({"type":"object","properties":{"a":{"type":"array","items":{"anyOf":[{"type":"integer"},{"type":"null"}]},"maxItems":3}},"required":["a"],"additionalProperties":false})",
    R"({"type":"object","properties":{"ok":{"type":"boolean","enum":[true]},"n":{"type":["string","null"],"enum":["x",null]}},"required":["ok","n"],"additionalProperties":false})",
    R"({"type":"object","properties":{"head":{"$ref":"#/$defs/node"}},"required":["head"],"additionalProperties":false,"$defs":{"node":{"anyOf":[{"type":"null"},{"type":"object","properties":{"n":{"type":"integer"},"next":{"$ref":"#/$defs/node"}},"required":["n","next"],"additionalProperties":false}]}}})"
  };
  std::vector<std::shared_ptr<const JsonConstraint>> grammars{JsonConstraint::Object()};
  for (auto schema : schemas)
    grammars.push_back(JsonConstraint::Compile(gufo::json::parse(schema), true));
  const auto arguments = grammars[2];
  grammars.push_back(JsonConstraint::WithReasoning(grammars[0]));
  for (bool required : {false, true})
    for (bool parallel : {false, true}) {
      auto plain = JsonConstraint::WithTools(nullptr, {{"f", arguments}}, required, parallel);
      grammars.push_back(plain);
      grammars.push_back(JsonConstraint::WithTools(grammars[0], {{"f", arguments}}, required, parallel));
      grammars.push_back(JsonConstraint::WithReasoning(plain));
    }
  std::vector<std::string> texts = {
    "{}", " \n{\"n\":0.3}\t", "{\"n\":20}", "{\"n\":20.1}", "{\"n\":-1}",
    "{\"n\":01}", "{\"s\":\"é😀\"}", "{\"s\":\"aaé\"}",
    R"({"s":"\uD83D\uDE00"})", R"({"s":"\uDE00"})",
    "{\"a\":[1,null,-2]}", "{\"a\":[1,2,3,4]}", "{\"ok\":true,\"n\":null}",
    "{\"head\":{\"n\":1,\"next\":{\"n\":2,\"next\":null}}}",
    "reason</think>{}", "reason</think><tool_call>{\"name\":\"f\",\"arguments\":{\"s\":\"x\"}}</tool_call>",
    "before<tool_call>{\"name\":\"f\",\"arguments\":{\"s\":\"x\"}}</tool_call>after",
    "<tool_call>{\"name\":\"f\",\"arguments\":{\"s\":\"x\"}}</tool_call><tool_call>{\"name\":\"f\",\"arguments\":{\"s\":\"é\"}}</tool_call>",
    "<tool_call>{\"name\":\"wrong\",\"arguments\":{\"s\":\"x\"}}</tool_call>",
    std::string(32, ' ') + "{}", std::string(33, ' ') + "{}",
    "{\"s\":\"" + std::string(64, 'a') + "\"}"};
  texts.push_back(std::string("{\"s\":\"\xc0\x80\"}"));
  auto vocabulary = std::make_shared<ConstraintVocabulary>(259, [](uint32_t token) {
    if (!token)
      return ConstraintVocabulary::Piece{"", true};
    if (token <= 256)
      return ConstraintVocabulary::Piece{std::string(1, char(token - 1)), false};
    return ConstraintVocabulary::Piece{token == 257 ? "<tool_call>" : "</think>", false};
  });
  size_t transitions = 0, masks = 0;
  for (size_t gi = 0; gi < grammars.size(); ++gi) {
    TokenConstraint constraint;
    constraint.grammar = grammars[gi];
    constraint.vocabulary = vocabulary;
    for (size_t ti = 0; ti < texts.size(); ++ti) {
      std::printf("grammar=%zu text=%zu\n", gi, ti);
      auto state = grammars[gi]->Start();
      witness(*grammars[gi], state);
      for (unsigned char byte : texts[ti]) {
        std::printf("byte=%02x\n", unsigned(byte));
        state = grammars[gi]->Advance(state, byte);
        witness(*grammars[gi], state);
        ++transitions;
        if (!state.empty()) {
          try {
            auto mask = constraint.Allowed(state);
            std::printf("mask=");
            for (auto allowed : *mask)
              std::printf("%u", unsigned(allowed));
            std::printf("\n");
          } catch (const std::runtime_error &e) {
            std::printf("mask-refused=%s\n", e.what());
          }
          ++masks;
        }
      }
    }
  }
  std::printf("GRAMMARS=%zu TEXTS=%zu TRANSITIONS=%zu MASKS=%zu COMPLETE_BYTE_GRAMMAR_HOST_NOT_INFERENCE\n",
              grammars.size(), texts.size(), transitions, masks);
}
