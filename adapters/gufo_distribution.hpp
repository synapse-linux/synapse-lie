// SPDX-License-Identifier: MIT
// Container/options/exception glue only; ordered probability work belongs to C.
#ifndef LIE_GUFO_DISTRIBUTION_HPP
#define LIE_GUFO_DISTRIBUTION_HPP
#include "gufo_sampling.hpp"
#include "lie/sampling_distribution.h"
#include "src/core/sampling.hpp"
namespace lie_gufo {
inline lie_sampling_workspace
distribution_storage(std::vector<gufo::sampling::Probability> &v) {
  return {v.data(), v.size(), dense_grow, &v};
}
inline void distribution_checked(std::vector<gufo::sampling::Probability> &v) {
  if (v.empty())
    throw std::invalid_argument("sampling distribution cannot be empty");
  std::vector<gufo::sampling::Probability> scratch;
  auto w = distribution_storage(scratch);
  size_t count = v.size();
  auto rc = lie_sampling_distribution_checked(v.data(), &count, &w);
  if (rc == LIE_SAMPLING_INVALID)
    throw std::invalid_argument("sampling distribution is malformed");
  if (rc == LIE_SAMPLING_NO_FINITE)
    throw std::invalid_argument("sampling distribution has no probability");
  dense_check(rc);
  v.resize(count);
}
inline void distribution_stable(std::vector<gufo::sampling::Probability> &v,
                                double total) {
  size_t count = v.size();
  auto rc = lie_sampling_distribution_stable(v.data(), &count, total);
  if (rc == LIE_SAMPLING_NONFINITE)
    throw std::runtime_error("logit softmax normalization failed");
  dense_check(rc);
  v.resize(count);
}
inline std::vector<gufo::sampling::Probability>
distribution_ranked(std::span<const float> logits,
                    const gufo::sampling::SamplingConfig &config,
                    std::span<const gufo::sampling::TokenPenalty> penalties,
                    std::span<const uint32_t> ids = {}) {
  config.Validate();
  auto options = dense_options(config);
  lie_sampling_ranked_row row;
  lie_sampling_ranked_row_init(&row);
  row.logits = logits.data();
  row.count = logits.size();
  row.penalties = penalties.data();
  row.penalty_count = penalties.size();
  row.token_ids = ids.data();
  row.token_id_count = ids.size();
  std::vector<gufo::sampling::Probability> entries, scratch;
  auto w = distribution_storage(entries), s = distribution_storage(scratch);
  size_t count = 0;
  dense_check(lie_sampling_distribution_ranked(&row, &options, &w, &s, &count));
  entries.resize(count);
  return entries;
}
inline uint32_t
distribution_residual(std::span<const gufo::sampling::Probability> entries,
                      std::span<const uint32_t> ids,
                      std::span<const float> probabilities, uint64_t *rng) {
  const lie_sampling_sparse_row q{ids.data(), ids.size(), probabilities.data(),
                                  probabilities.size()};
  std::vector<gufo::sampling::Probability> draft, residual;
  auto d = distribution_storage(draft), r = distribution_storage(residual);
  uint32_t token = 0;
  dense_check(lie_sampling_distribution_residual_draw(
      entries.data(), entries.size(), &q, &d, &r, rng, &token));
  return token;
}
inline void
proposal_quantize(std::span<const gufo::sampling::Probability> entries,
                  std::span<const uint32_t> mapping, uint64_t *rng,
                  std::span<uint32_t> ids, std::span<float> probabilities,
                  size_t *count, uint32_t *token, float *probability) {
  if (ids.size() != probabilities.size())
    throw std::invalid_argument("proposal output capacities differ");
  lie_sampling_proposal out;
  lie_sampling_proposal_init(&out);
  out.ids = ids.data();
  out.probabilities = probabilities.data();
  out.capacity = ids.size();
  dense_check(lie_sampling_proposal_quantize(entries.data(), entries.size(),
                                             mapping.data(), mapping.size(),
                                             rng, &out));
  *count = out.count;
  *token = out.token;
  *probability = out.probability;
}
inline lie_sampling_proposal_view
proposal_view(std::span<const uint32_t> ids,
              std::span<const float> probabilities, uint32_t token,
              float probability) {
  if (ids.size() != probabilities.size())
    throw std::invalid_argument("proposal input capacities differ");
  lie_sampling_proposal_view q;
  lie_sampling_proposal_view_init(&q);
  q.ids = ids.data();
  q.probabilities = probabilities.data();
  q.count = ids.size();
  q.token = token;
  q.probability = probability;
  return q;
}
inline std::pair<uint32_t, bool>
proposal_verify(std::span<const gufo::sampling::Probability> target,
                size_t vocabulary, std::span<const uint32_t> ids,
                std::span<const float> probabilities, uint32_t token,
                float probability, uint64_t *rng) {
  auto q = proposal_view(ids, probabilities, token, probability);
  std::vector<gufo::sampling::Probability> draft, residual;
  auto d = distribution_storage(draft), r = distribution_storage(residual);
  uint32_t out = 0;
  bool accepted = false;
  dense_check(lie_sampling_proposal_verify(target.data(), target.size(),
                                           vocabulary, &q, &d, &r, rng, &out,
                                           &accepted));
  return {out, accepted};
}
} // namespace lie_gufo
#endif
