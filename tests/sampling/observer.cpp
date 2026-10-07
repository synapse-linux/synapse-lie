// SPDX-License-Identifier: MIT
// HOST-NOT-INFERENCE: observation lifetimes and unmodified numerical draws.
#include "gufo_sampling_observer.hpp"
#include "src/core/json.hpp"
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <stdexcept>
using namespace gufo::sampling;
namespace qfn = gufo::models::qwen38_flash_next;
struct Saved {
  lie_sampling_observation event{};
  std::vector<float> logits, probabilities;
  std::vector<uint32_t> mapping, history, proposal;
  std::vector<uint8_t> allowed;
  std::vector<lie_sampling_penalty> penalties;
  unsigned calls{};
};
static void save(void *context, const lie_sampling_observation *event) {
  auto &saved = *static_cast<Saved *>(context);
  assert(lie_gufo::sampling_observer_callback);
  assert(event->abi_version == LIE_SAMPLING_OBSERVER_ABI && event->struct_bytes == sizeof(*event));
  assert(event->logits && event->logit_count);
  saved.event = *event; ++saved.calls;
  saved.logits.assign(event->logits, event->logits + event->logit_count);
  saved.mapping.clear(); saved.allowed.clear(); saved.history.clear(); saved.penalties.clear();
  saved.proposal.clear(); saved.probabilities.clear();
  if (event->logit_ids) saved.mapping.assign(event->logit_ids, event->logit_ids + event->logit_count);
  if (event->allowed_count) saved.allowed.assign(event->allowed, event->allowed + event->allowed_count);
  if (event->history_count) saved.history.assign(event->history, event->history + event->history_count);
  if (event->penalty_count) saved.penalties.assign(event->penalties, event->penalties + event->penalty_count);
  if (event->proposal_count) {
    saved.proposal.assign(event->proposal_ids, event->proposal_ids + event->proposal_count);
    saved.probabilities.assign(event->proposal_probabilities, event->proposal_probabilities + event->proposal_count);
  }
  // Keep scalar fields; explicitly discard every borrowed pointer on return.
  saved.event.logits = nullptr; saved.event.logit_ids = nullptr; saved.event.allowed = nullptr;
  saved.event.history = nullptr; saved.event.penalties = nullptr;
  saved.event.proposal_ids = nullptr; saved.event.proposal_probabilities = nullptr;
}
static void target(void) {
  const std::vector<float> logits{.2f, 1.1f, -.4f, .8f, -.9f};
  const std::vector<uint32_t> prompt{1, 2, 1};
  for (unsigned profile = 0; profile < 6; ++profile) {
    SamplingConfig config; config.seed = 123; config.temperature = profile ? 1 : 0;
    config.top_k = profile == 2 ? 3 : 0; config.top_p = profile == 3 ? .8f : 1;
    config.min_p = profile == 1 ? .05f : 0;
    config.frequency_penalty = profile == 4 ? .4f : profile == 5 ? -.3f : 0;
    config.presence_penalty = profile == 4 ? .2f : profile == 5 ? -.1f : 0;
    SamplerState original(config, prompt), observed = original;
    Saved saved; const lie_sampling_observer observer{LIE_SAMPLING_OBSERVER_ABI, sizeof(observer), save, &saved};
    for (unsigned step = 0; step < 32; ++step) {
      const auto before = observed.rng_state();
      const auto expected = original.Sample(logits);
      uint32_t token;
      { lie_gufo::SamplingObservationScope scope(&observer); token = lie_gufo::observed_target_draw(observed, logits); }
      assert(!lie_gufo::sampling_observer && !lie_gufo::sampling_observer_callback);
      assert(token == expected && original.rng_state() == observed.rng_state());
      assert(saved.event.kind == LIE_SAMPLING_OBSERVE_TARGET_DRAW && saved.event.token == token);
      assert(saved.event.rng_before == before && saved.event.rng_after == observed.rng_state());
      assert(!saved.event.deferred && saved.logits == logits && saved.allowed.empty());
      assert(std::ranges::equal(saved.history, observed.history()));
      const auto penalties = observed.penalties(); assert(saved.penalties.size() == penalties.size());
      for (size_t i = 0; i < penalties.size(); ++i)
        assert(saved.penalties[i].token == penalties[i].token &&
               saved.penalties[i].generated_count == penalties[i].generated_count &&
               saved.penalties[i].repeated == penalties[i].repeated);
      original.Accept(token); observed.Accept(token);
    }
    assert(saved.calls == 32);
    auto fresh = original;
    assert(lie_gufo::observed_target_draw(fresh, logits) == original.Sample(logits));
    assert(saved.calls == 32); // Inactive observer does no capture work.
  }
}
static void proposal(void) {
  SamplingConfig config; config.temperature = 1; config.seed = 123; config.min_p = .05f;
  config.frequency_penalty = .4f; config.presence_penalty = .2f;
  const uint32_t initial[]{1, 3}; SamplerState sampler(config, initial); sampler.Accept(2);
  qfn::MtpCandidateLogits candidates; candidates.size = 4;
  candidates.ids = {3, 0, 2, 1}; candidates.logits = {1, .8f, -.2f, .3f};
  const float target[]{1, 2, .4f, -.5f};
  Saved saved; const lie_sampling_observer observer{LIE_SAMPLING_OBSERVER_ABI, sizeof(observer), save, &saved};
  unsigned accepted = 0, rejected = 0;
  for (uint64_t seed = 1; seed <= 64; ++seed) {
    auto expected_rng = seed, actual_rng = seed;
    const auto expected = qfn::SampleMtpProposal(candidates, sampler, &expected_rng);
    qfn::MtpProposal actual;
    { lie_gufo::SamplingObservationScope scope(&observer); actual = lie_gufo::observed_mtp_proposal(candidates, sampler, &actual_rng); }
    assert(actual_rng == expected_rng && actual.token == expected.token && actual.probability == expected.probability);
    assert(actual.ids == expected.ids && actual.probabilities == expected.probabilities && actual.size == expected.size);
    assert(saved.event.kind == LIE_SAMPLING_OBSERVE_PROPOSAL && saved.event.rng_before == seed && saved.event.rng_after == actual_rng);
    assert(saved.mapping == std::vector<uint32_t>(candidates.ids.begin(), candidates.ids.begin() + candidates.size));
    assert(saved.proposal == std::vector<uint32_t>(actual.ids.begin(), actual.ids.begin() + actual.size));
    assert(saved.probabilities == std::vector<float>(actual.probabilities.begin(), actual.probabilities.begin() + actual.size));
    double total = 0; for (const auto mass : saved.probabilities) total += mass; assert(total == 1);
    auto original = sampler, observed = sampler; original.SetRngState(seed); observed.SetRngState(seed);
    const auto result = qfn::VerifyMtpProposal(target, expected, original);
    qfn::MtpVerification verified;
    { lie_gufo::SamplingObservationScope scope(&observer); verified = lie_gufo::observed_mtp_verify(target, actual, observed); }
    assert(verified.token == result.token && verified.accepted == result.accepted && original.rng_state() == observed.rng_state());
    assert(saved.event.kind == LIE_SAMPLING_OBSERVE_VERIFICATION && saved.event.token == verified.token &&
           saved.event.accepted == verified.accepted && saved.event.rng_before == seed && saved.event.rng_after == observed.rng_state());
    if (verified.accepted) ++accepted; else ++rejected;
  }
  assert(accepted && rejected && saved.calls == 128);
}
static void grammar_and_deferred(void) {
  const std::string pieces[]{"{", "}", "\"ok\"", ":", "true", "wrong", "", "{\"ok\":true}"};
  auto constraint = std::make_shared<TokenConstraint>();
  constraint->grammar = JsonConstraint::Compile(gufo::json::parse(
      R"({"type":"object","properties":{"ok":{"type":"boolean","enum":[true]}},"required":["ok"],"additionalProperties":false})"), true);
  constraint->vocabulary = std::make_shared<ConstraintVocabulary>(8, [&](uint32_t token) {
    return ConstraintVocabulary::Piece{pieces[token], token == 6};
  });
  SamplingConfig config; config.temperature = 1; config.seed = 123; config.constraint = constraint;
  SamplerState sampler(config);
  const float logits[]{1, 2, 3, 4, 5, 6, 7, 8};
  Saved saved; const lie_sampling_observer observer{LIE_SAMPLING_OBSERVER_ABI, sizeof(observer), save, &saved};
  // Force q outside the initial target grammar: residual chooses an allowed ID.
  qfn::MtpProposal q; q.size = 1; q.ids[0] = q.token = 5; q.probabilities[0] = q.probability = 1;
  qfn::MtpVerification result;
  { lie_gufo::SamplingObservationScope scope(&observer); result = lie_gufo::observed_mtp_verify(logits, q, sampler); }
  assert(!result.accepted && saved.allowed.size() == 8 && saved.allowed[result.token]);
  assert(!saved.allowed[5] && !saved.allowed[6]);
  auto expected = sampler; expected.DeferSample(result.token); sampler.DeferSample(result.token);
  const auto before = sampler.rng_state();
  { lie_gufo::SamplingObservationScope scope(&observer); assert(lie_gufo::observed_target_draw(sampler, logits) == expected.Sample(logits)); }
  assert(saved.event.deferred && saved.event.rng_before == before && saved.event.rng_after == before);
  assert(sampler.rng_state() == expected.rng_state());
  sampler.Accept(result.token); // The saved mask remains owned and valid.
  assert(saved.allowed.size() == 8 && saved.allowed[result.token]);
  auto draft = sampler.WithoutConstraint();
  qfn::MtpCandidateLogits candidates; candidates.size = 2; candidates.ids = {0, 5}; candidates.logits = {1, 2};
  uint64_t rng = 9;
  { lie_gufo::SamplingObservationScope scope(&observer); (void)lie_gufo::observed_mtp_proposal(candidates, draft, &rng); }
  assert(saved.allowed.empty());
}
static void throwing_callback(void *, const lie_sampling_observation *) { throw std::runtime_error("owned observer failure"); }
static void exception_cleanup(void) {
  SamplerState sampler; const float logits[]{1, 2};
  const lie_sampling_observer observer{LIE_SAMPLING_OBSERVER_ABI, sizeof(observer), throwing_callback, nullptr};
  bool threw = false;
  try { lie_gufo::SamplingObservationScope scope(&observer); (void)lie_gufo::observed_target_draw(sampler, logits); }
  catch (const std::runtime_error &) { threw = true; }
  assert(threw && !lie_gufo::sampling_observer && !lie_gufo::sampling_observer_callback);
  assert(lie_gufo::observed_target_draw(sampler, logits) == 1);
}
int main() {
  target(); proposal(); grammar_and_deferred(); exception_cleanup();
  std::puts("SAMPLING_OBSERVER_LIFETIME_RNG_MASK_PROPOSAL_RESIDUAL_PASS_HOST_NOT_INFERENCE");
}
