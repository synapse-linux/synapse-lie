// SPDX-License-Identifier: MIT
// Full history/penalty/draw witnesses; pristine, C17 and OFF arms.
// NOT-INFERENCE.
#include "src/core/sampling.hpp"
#include <cassert>
#include <cstdio>
#include <stdexcept>
#include <vector>
using namespace gufo::sampling;
static void witness(const SamplerState &s, unsigned profile, unsigned step) {
  std::printf("profile=%u step=%u rng=%llu\n", profile, step,
              static_cast<unsigned long long>(s.rng_state()));
  for (auto token : s.history())
    std::printf("h=%u\n", token);
  for (const auto &p : s.penalties())
    std::printf("p=%u:%u:%u\n", p.token, p.generated_count, p.repeated);
  auto draw = s.SaveDrawState();
  std::printf("pending=%d:%u\n", bool(draw.pending), draw.pending.value_or(0));
}
static void grammar_refusal() {
  auto grammar = JsonConstraint::Compile(
      gufo::json::parse(
          R"({"type":"object","properties":{"ok":{"type":"boolean","enum":[true]}},"required":["ok"],"additionalProperties":false})"),
      true);
  auto vocab = std::make_shared<ConstraintVocabulary>(3, [](uint32_t t) {
    return ConstraintVocabulary::Piece{t == 0   ? "{\"ok\":true}"
                                       : t == 1 ? "bad"
                                                : "",
                                       t == 2};
  });
  auto constraint = std::make_shared<TokenConstraint>();
  constraint->grammar = grammar;
  constraint->vocabulary = vocab;
  SamplingConfig c;
  c.seed = 73;
  c.constraint = constraint;
  c.frequency_penalty = .5f;
  c.repeat_penalty = 1.2f;
  const uint32_t prompt[] = {0};
  SamplerState s(c, prompt);
  s.DeferSample(0);
  const auto before = s.SaveDrawState();
  const uint32_t invalid[] = {0, 1};
  bool refused = false;
  try {
    s.Accept(invalid);
  } catch (const std::runtime_error &) {
    refused = true;
  }
  assert(refused && s.SaveDrawState().pending == before.pending);
  witness(s, 99, 0);
  const float logits[] = {1, 2, 3};
  assert(s.Sample(logits) == 0); /* Refusal preserved the initial grammar. */
  s.Accept(0);
  witness(s, 99, 1);
  assert(s.Distribution(logits).best_token() == 2);
  s.ResetHistory(prompt);
  witness(s, 99, 2);
  assert(s.Distribution(logits).best_token() == 0);
}
int main() {
  unsigned profile = 0, transitions = 0;
  const size_t windows[] = {0, 1, 2, 8, 64, 129};
  const size_t batches[] = {0, 1, 8, 32, 33, 257};
  std::vector<float> logits(67);
  for (size_t i = 0; i < logits.size(); ++i)
    logits[i] = float(i % 11) - 5;
  for (unsigned flags = 0; flags < 8; ++flags)
    for (auto window : windows) {
      SamplingConfig c;
      c.seed = 77;
      c.temperature = 1;
      c.repeat_last_n = window;
      if (flags & 1)
        c.repeat_penalty = 1.2f;
      if (flags & 2)
        c.frequency_penalty = .5f;
      if (flags & 4)
        c.presence_penalty = -.2f;
      std::vector<uint32_t> prompt(300), generated;
      for (size_t i = 0; i < prompt.size(); ++i)
        prompt[i] = (i * 7) % 67;
      SamplerState s(c, prompt);
      witness(s, profile, 0);
      for (unsigned step = 1; step <= 36; ++step) {
        std::vector<uint32_t> input(batches[step % 6]);
        for (size_t i = 0; i < input.size(); ++i)
          input[i] = (i * 13 + step) % 67;
        if (step % 11 == 0) {
          s.DeferSample(9);
          s.ResetHistory(input);
          assert(!s.SaveDrawState().pending);
          generated.clear();
          prompt = input;
        } else {
          s.Accept(input);
          generated.insert(generated.end(), input.begin(), input.end());
        }
        witness(s, profile, step);
        ++transitions;
        SamplerState clone(s), assigned;
        assigned = s;
        clone.DeferSample(9);
        assigned.CopyDrawStateFrom(clone);
        assert(clone.Sample(logits) == 9 && assigned.Sample(logits) == 9);
        clone.Accept(0);
        witness(clone, profile, step + 100);
        witness(s, profile, step + 200); /* Original was not mutated. */
        const auto built = BuildDistribution(logits, c, prompt, generated);
        for (const auto &p : built.entries())
          std::printf("free=%u:%a\n", p.token, p.value);
        const auto draw = s.SaveDrawState();
        (void)s.Uniform();
        s.RestoreDrawState(draw);
        const auto token = s.Sample(logits);
        std::printf("draw=%u rng=%llu\n", token,
                    static_cast<unsigned long long>(s.rng_state()));
        const uint32_t ids[] = {1, 9, 50};
        const float compact[] = {2, 0, 1};
        const auto compact_distribution = s.Distribution(compact, ids);
        for (const auto &p : compact_distribution.entries())
          std::printf("compact=%u:%a\n", p.token, p.value);
      }
      ++profile;
    }
  grammar_refusal();
  std::printf("PROFILES=%u TRANSITIONS=%u "
              "COMPLETE_HISTORY_HOST_WITNESSES_NOT_INFERENCE\n",
              profile, transitions);
}
