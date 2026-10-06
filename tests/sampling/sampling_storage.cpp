// SPDX-License-Identifier: MIT
// Private native storage integration. HOST, no model forward or timing claim.
#include "src/core/sampling.hpp"
#include "src/models/qwen38_flash_next/mtp_sampling.hpp"
#include "gufo_sampling_storage.hpp"
#include "allocation_counter.hpp"
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <utility>
using namespace gufo::sampling;
static bool equal(std::span<const TokenPenalty> a, std::span<const TokenPenalty> b) {
  return a.size() == b.size() && std::equal(a.begin(), a.end(), b.begin(),
    [](const auto &x, const auto &y) { return x.token == y.token &&
      x.repeated == y.repeated && x.generated_count == y.generated_count; });
}
static bool equal(std::span<const Probability> a, std::span<const Probability> b) {
  return a.size() == b.size() && std::equal(a.begin(), a.end(), b.begin(),
    [](const auto &x, const auto &y) { return x.token == y.token && x.value == y.value; });
}
static void ownership() {
  lie_sampling_alloc_begin();
  {
    lie_gufo::ProbabilityStorage a, b;
    assert(!a.info().allocations && !b.info().allocations);
    auto w = a.workspace();
    assert(!w.grow(w.context, 2, &w.entries, &w.capacity));
    w.entries[0] = {2, .25}; w.entries[1] = {4, .75}; a.publish(2);
    const auto *identity = a.data(); b = a;
    assert(b.data() != identity && equal(a, b));
    b = std::move(a); assert(b.data() == identity && a.empty() && !a.data());
    a = b; assert(a.data() != identity && equal(a, b));
    auto moved = std::move(b); assert(moved.data() == identity && b.empty());
    moved = moved; moved = std::move(moved); assert(moved.data() == identity);
    lie_gufo::OwnedHistory h, copy;
    lie_sampling_history_options o; lie_sampling_history_options_init(&o);
    o.generated = true; o.repetition = true; o.repeat_last_n = 4;
    const std::array<uint32_t, 3> prompt{1, 2, 1}, generated{3, 4, 3};
    h.reset(o, prompt); h.accept(generated); copy = h;
    assert(equal(h.penalties(), copy.penalties()) && h.tokens().data() != copy.tokens().data());
    const auto *tokens = h.tokens().data(); copy = std::move(h);
    assert(copy.tokens().data() == tokens && h.tokens().empty());
    const std::array<uint32_t, 1> next{5}; copy.accept(next);
    assert(copy.tokens().back() == 5); h.reset(o, prompt); h.accept(next);
    assert(h.tokens().data() != copy.tokens().data());
  }
  const auto allocations = lie_sampling_alloc_end();
  // C++ wrapper bodies allocate nothing. C heap is checked by the native probe.
  assert(!allocations.calls && !allocations.live_bytes);
}
static void production() {
  SamplingConfig config; config.seed = 123; config.temperature = 1;
  config.repeat_penalty = 1.1F; config.frequency_penalty = .2F;
  config.presence_penalty = .1F; config.repeat_last_n = 4;
  const std::array<TokenId, 3> prompt{1, 2, 1};
  SamplerState s(config, prompt); s.Accept(3); s.DeferSample(4);
  const auto *identity = s.history().data(); const auto draw = s.SaveDrawState();
  auto copy = s;
  assert(copy.history().data() != identity && equal(s.penalties(), copy.penalties()));
  assert(copy.SaveDrawState().rng == draw.rng && copy.SaveDrawState().pending == draw.pending);
  auto moved = std::move(s); assert(moved.history().data() == identity && s.history().empty());
  s.ResetHistory(prompt); s.Accept(0); assert(moved.history().back() == 3);
  copy.Accept(5); assert(moved.history().back() == 3 && copy.history().back() == 5);
  std::array<float, 8> logits{0, 1, 2, 3, 4, 5, 6, 7};
  assert(moved.Sample(logits) == 4 && !moved.SaveDrawState().pending);
  lie_sampling_alloc_begin();
  {
    const auto distribution = moved.Distribution(logits);
    auto cloned = distribution; assert(equal(distribution.entries(), cloned.entries()));
    assert(distribution.entries().data() != cloned.entries().data());
    const auto *entries = cloned.entries().data(); auto transferred = std::move(cloned);
    assert(transferred.entries().data() == entries && cloned.entries().empty());
    const auto residual = transferred.SampleResidual({}, {}, moved.mutable_rng_state());
    assert(residual < logits.size());
  }
  const auto allocations = lie_sampling_alloc_end(); assert(!allocations.calls);
  const auto normalized = SamplingDistribution::FromNormalized({{2, .25}, {7, .75}});
  assert(normalized.probability(2) == .25 && normalized.probability(7) == .75);
  SamplingDistribution singleton({{4, 1.0}}); assert(singleton.best_token() == 4);
  using namespace gufo::models::qwen38_flash_next;
  MtpCandidateLogits candidates; candidates.size = 3;
  candidates.ids = {2, 5, 7}; candidates.logits = {2, 5, 7};
  auto p = SampleMtpProposal(candidates, moved, moved.mutable_rng_state());
  auto verification = VerifyMtpProposal(logits, p, moved);
  assert(verification.token < logits.size());
}
int main() {
  ownership(); production();
  std::puts("Native sampler storage projections/copy/move/MTP; HOST-NOT-INFERENCE");
}
