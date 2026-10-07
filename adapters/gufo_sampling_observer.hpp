// SPDX-License-Identifier: MIT
// Borrowed diagnostic projection only; numerical operations stay unchanged.
#ifndef LIE_GUFO_SAMPLING_OBSERVER_HPP
#define LIE_GUFO_SAMPLING_OBSERVER_HPP
#include "lie/sampling_observer.h"
#include "src/models/qwen38_flash_next/mtp_sampling.hpp"
#include <vector>
namespace lie_gufo {
inline thread_local const lie_sampling_observer *sampling_observer = nullptr;
inline thread_local bool sampling_observer_callback = false;
class SamplingObservationScope {
public:
  explicit SamplingObservationScope(const lie_sampling_observer *observer)
      : previous_(sampling_observer) { sampling_observer = observer; }
  ~SamplingObservationScope() { sampling_observer = previous_; }
  SamplingObservationScope(const SamplingObservationScope &) = delete;
  SamplingObservationScope &operator=(const SamplingObservationScope &) = delete;
private:
  const lie_sampling_observer *previous_;
};
inline void sampling_observe(lie_sampling_observation &event,
    const gufo::sampling::SamplerState &sampler) {
  const auto *observer = sampling_observer;
  if (!observer) return;
  const auto history = sampler.history();
  event.history = history.data(); event.history_count = history.size();
  std::vector<lie_sampling_penalty> penalties;
  penalties.reserve(sampler.penalties().size());
  for (const auto &p : sampler.penalties())
    penalties.push_back({p.token, p.generated_count, p.repeated});
  event.penalties = penalties.data(); event.penalty_count = penalties.size();
  const auto mask = sampler.SamplingObservationAllowed();
  event.allowed = mask ? mask->data() : nullptr;
  event.allowed_count = mask ? mask->size() : 0;
  sampling_observer_callback = true;
  try { observer->observe(observer->context, &event); }
  catch (...) { sampling_observer_callback = false; throw; }
  sampling_observer_callback = false;
}
inline uint32_t observed_target_draw(gufo::sampling::SamplerState &sampler,
                                    std::span<const float> logits) {
  if (!sampling_observer) return sampler.Sample(logits);
  const auto before = sampler.SaveDrawState();
  const auto token = sampler.Sample(logits);
  lie_sampling_observation event{};
  event.abi_version = LIE_SAMPLING_OBSERVER_ABI; event.struct_bytes = sizeof(event);
  event.kind = LIE_SAMPLING_OBSERVE_TARGET_DRAW; event.token = token;
  event.rng_before = before.rng; event.rng_after = sampler.rng_state();
  event.deferred = before.pending.has_value();
  event.logits = logits.data(); event.logit_count = logits.size();
  sampling_observe(event, sampler);
  return token;
}
inline gufo::models::qwen38_flash_next::MtpProposal observed_mtp_proposal(
    const gufo::models::qwen38_flash_next::MtpCandidateLogits &candidates,
    const gufo::sampling::SamplerState &sampler, uint64_t *rng) {
  using gufo::models::qwen38_flash_next::SampleMtpProposal;
  if (!sampling_observer) return SampleMtpProposal(candidates, sampler, rng);
  const auto before = *rng;
  const auto proposal = SampleMtpProposal(candidates, sampler, rng);
  lie_sampling_observation event{};
  event.abi_version = LIE_SAMPLING_OBSERVER_ABI; event.struct_bytes = sizeof(event);
  event.kind = LIE_SAMPLING_OBSERVE_PROPOSAL; event.token = proposal.token;
  event.rng_before = before; event.rng_after = *rng;
  event.logits = candidates.logits.data(); event.logit_count = candidates.size;
  event.logit_ids = candidates.ids.data();
  event.proposal_ids = proposal.ids.data();
  event.proposal_probabilities = proposal.probabilities.data();
  event.proposal_count = proposal.size; event.proposal_token = proposal.token;
  event.proposal_probability = proposal.probability;
  sampling_observe(event, sampler);
  return proposal;
}
inline gufo::models::qwen38_flash_next::MtpVerification observed_mtp_verify(
    std::span<const float> logits,
    const gufo::models::qwen38_flash_next::MtpProposal &proposal,
    gufo::sampling::SamplerState &sampler) {
  using gufo::models::qwen38_flash_next::VerifyMtpProposal;
  if (!sampling_observer) return VerifyMtpProposal(logits, proposal, sampler);
  const auto before = sampler.rng_state();
  const auto result = VerifyMtpProposal(logits, proposal, sampler);
  lie_sampling_observation event{};
  event.abi_version = LIE_SAMPLING_OBSERVER_ABI; event.struct_bytes = sizeof(event);
  event.kind = LIE_SAMPLING_OBSERVE_VERIFICATION;
  event.token = result.token; event.accepted = result.accepted;
  event.rng_before = before; event.rng_after = sampler.rng_state();
  event.logits = logits.data(); event.logit_count = logits.size();
  event.proposal_ids = proposal.ids.data();
  event.proposal_probabilities = proposal.probabilities.data();
  event.proposal_count = proposal.size; event.proposal_token = proposal.token;
  event.proposal_probability = proposal.probability;
  sampling_observe(event, sampler);
  return result;
}
} // namespace lie_gufo
#endif
