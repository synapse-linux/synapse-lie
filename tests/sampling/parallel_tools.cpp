// SPDX-License-Identifier: MIT
// Exact r60 argument schema; synthetic vocabulary, no model/tokenizer/GPU.
#include "src/core/json_constraint.hpp"
#include <cassert>
#include <cstdio>
#include <string>
using namespace gufo::sampling;
int main() {
  const auto arguments = JsonConstraint::Compile(gufo::json::parse(
      R"({"type":"object","properties":{"key":{"type":"string","enum":["alpha","beta"]}},"required":["key"],"additionalProperties":false})"), true);
  const std::string alpha = R"(<tool_call>{"name":"get_value","arguments":{"key":"alpha"}}</tool_call>)";
  const std::string beta = R"(<tool_call>{"name":"get_value","arguments":{"key":"beta"}}</tool_call>)";
  const std::string pieces[] = {alpha, beta,
      R"(<tool_call>{"name":"get_value","arguments":{"key":"gamma"}}</tool_call>)",
      R"(<tool_call>{"name":"other","arguments":{"key":"alpha"}}</tool_call>)", ""};
  // Every intermediate byte prefix needs a genuine continuation vocabulary.
  // Complete-call pieces alone cannot represent the next byte inside a call.
  const ConstraintVocabulary vocabulary(261, [&](uint32_t token) {
    return ConstraintVocabulary::Piece{token < 256 ? std::string(1, char(token)) : pieces[token - 256], token == 260};
  });
  size_t prefixes = 0;
  for (bool plain : {false, true})
    for (bool required : {false, true})
      for (bool parallel : {false, true}) {
        const auto grammar = JsonConstraint::WithTools(plain ? nullptr : JsonConstraint::Object(),
            {{"get_value", arguments}}, required, parallel);
        auto state = grammar->Start();
        auto allowed = vocabulary.Allowed(*grammar, state);
        assert(allowed[256] && allowed[257] && !allowed[258] && !allowed[259]);
        assert(bool(allowed[260]) == (plain && !required));
        std::printf("plain=%d required=%d parallel=%d\n", plain, required, parallel);
        auto consume = [&](const std::string &text) {
          for (unsigned char byte : text) {
            state = grammar->Advance(state, byte);
            assert(!state.empty());
            const auto mask = vocabulary.Allowed(*grammar, state);
            std::printf("prefix=%zu complete=%d mask=", prefixes++, grammar->Complete(state));
            for (auto flag : mask) std::printf("%u", unsigned(flag));
            std::puts("");
          }
        };
        consume(alpha);
        assert(grammar->Complete(state));
        allowed = vocabulary.Allowed(*grammar, state);
        assert(allowed[260]); // Required means at least one, not exactly two.
        assert(bool(allowed[256]) == parallel && bool(allowed[257]) == parallel);
        assert(!allowed[258] && !allowed[259]);
        assert(vocabulary.Accept(*grammar, state, 260) == state);
        if (parallel) {
          consume(beta);
          assert(grammar->Complete(state) && vocabulary.Allowed(*grammar, state)[260]);
        } else {
          std::puts("SECOND_CALL_REFUSED_BY_PARALLEL_FALSE");
        }
      }
  std::printf("CASES=8 PREFIXES=%zu EXACT_SCHEMA_AND_STOP_MASK_HOST_NOT_INFERENCE\n", prefixes);
}
