// SPDX-License-Identifier: MIT
// Host-only sampler/grammar checks against the verified source variant.
// No model forward, weights or GPU execution.
#include "src/core/sampling.hpp"
#include <cassert>
#include <cmath>
int main() {
  using namespace gufo::sampling;
  SamplingConfig config;
  config.logit_bias = {10, -10, 0};
  SamplerState sampler(config);
  const float logits[] = {0, 3, 0};
  assert(sampler.Sample(logits) == 0);
  const auto reporting = sampler.ReportingLogits(logits);
  assert(reporting[0] == 10 && reporting[1] == -7 && reporting[2] == 0);
  config.temperature = 1;
  SamplerState random(config);
  assert(random.Distribution(logits).probability(0) > .999);
  auto schema = gufo::json::parse(
      R"({"type":"object","properties":{"ok":{"type":"boolean","enum":[true]}},"required":["ok"],"additionalProperties":false})");
  auto grammar = JsonConstraint::Compile(schema, true);
  const std::string pieces[] = {"{",    "}",   "\"ok\"", ":",
                                "true", "bad", "",       "\"ok\":true"};
  auto vocabulary =
      std::make_shared<ConstraintVocabulary>(8, [&](uint32_t token) {
        return ConstraintVocabulary::Piece{pieces[token], token == 6};
      });
  auto state = grammar->Start();
  const unsigned tokens[] = {0, 2, 3, 4, 1};
  for (unsigned token : tokens) {
    auto allowed = vocabulary->Allowed(*grammar, state);
    assert(allowed[token] && !allowed[5] && !allowed[6]);
    state = vocabulary->Accept(*grammar, state, token);
    assert(!state.empty());
  }
  assert(grammar->Complete(state) && vocabulary->Allowed(*grammar, state)[6]);
  auto parameters = gufo::json::parse(
      R"({"type":"object","properties":{"path":{"type":"string","enum":["a"]}},"required":["path"],"additionalProperties":false})");
  auto tool = JsonConstraint::Compile(parameters, true);
  auto calls =
      JsonConstraint::WithTools(nullptr, {{"read", tool}}, true, false);
  auto tool_vocab =
      std::make_shared<ConstraintVocabulary>(3, [](uint32_t token) {
        return ConstraintVocabulary::Piece{
            token == 0 ? "<tool_call>{\"name\":\"read\",\"arguments\":{"
                         "\"path\":\"a\"}}</tool_call>"
            : token == 1 ? "wrong"
                         : "",
            token == 2};
      });
  auto start = calls->Start();
  auto allowed = tool_vocab->Allowed(*calls, start);
  assert(allowed[0] && !allowed[1] && !allowed[2]);
  auto completed = tool_vocab->Accept(*calls, start, 0);
  assert(calls->Complete(completed) &&
         tool_vocab->Allowed(*calls, completed)[2]);
}
