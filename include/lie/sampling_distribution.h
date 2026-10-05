/* SPDX-License-Identifier: MIT */
/* Model-neutral ordered/compact and speculative probability operations. */
#ifndef LIE_SAMPLING_DISTRIBUTION_H
#define LIE_SAMPLING_DISTRIBUTION_H
#include "lie/sampling.h"
#include <stdbool.h>
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_DISTRIBUTION_ABI 1u
#define LIE_PROPOSAL_UNITS (1u << 24)
typedef struct {
  uint32_t abi_version, struct_bytes;
  const float *logits;
  size_t count;
  /* NULL/zero uses vocabulary positions. Output IDs always index logits. */
  const uint32_t *token_ids;
  size_t token_id_count;
  const lie_sampling_penalty *penalties;
  size_t penalty_count;
} lie_sampling_ranked_row;
typedef struct {
  const uint32_t *ids;
  size_t id_count;
  const float *probabilities;
  size_t probability_count;
} lie_sampling_sparse_row;
typedef struct {
  uint32_t abi_version, struct_bytes;
  uint32_t *ids;
  float *probabilities;
  size_t capacity, count;
  uint32_t token;
  float probability;
} lie_sampling_proposal;
typedef struct {
  uint32_t abi_version, struct_bytes;
  const uint32_t *ids;
  const float *probabilities;
  size_t count;
  uint32_t token;
  float probability;
} lie_sampling_proposal_view;
void lie_sampling_ranked_row_init(lie_sampling_ranked_row *);
void lie_sampling_proposal_init(lie_sampling_proposal *);
void lie_sampling_proposal_view_init(lie_sampling_proposal_view *);
/* Borrowed sources must be disjoint from mutable workspaces/output. Growth
 * preserves live entries and all borrowed input. Caller owns storage/budgets;
 * this module allocates nothing, creates no thread and retains no pointer.
 * Refusal preserves in-place entries/counts, proposal/result and RNG; scratch
 * may change. Builder refusal publishes output count zero.
 * Checked normalization rejects duplicate IDs even when their mass is zero,
 * uses the input summation order and ranks probabilities/value then token ID.
 * Stable normalization trusts unique IDs, uses the supplied positive total
 * and retains input order. Both discard exact zero entries. */
lie_sampling_status
lie_sampling_distribution_checked(lie_sampling_probability *, size_t *count,
                                  lie_sampling_workspace *scratch);
lie_sampling_status lie_sampling_distribution_stable(lie_sampling_probability *,
                                                     size_t *count,
                                                     double total);
lie_sampling_status
lie_sampling_distribution_best(const lie_sampling_probability *, size_t count,
                               uint32_t *token);
double lie_sampling_distribution_probability(const lie_sampling_probability *,
                                             size_t count, uint32_t token);
/* Exact ranked reference order/rounding: penalties, top-k, top-p, min-p,
 * normalized softmax, then checked-constructor normalization/ranking.
 * It is distinct from the dense linear fast path. Bias/grammar are not added:
 * compiled grammar may already mask the borrowed logits. */
lie_sampling_status lie_sampling_distribution_ranked(
    const lie_sampling_ranked_row *, const lie_sampling_options *,
    lie_sampling_workspace *entries, lie_sampling_workspace *scratch,
    size_t *count);
/* Repeated draft IDs accumulate in original input order. Residual retains
 * target order. NO_FINITE denotes an empty p-q residual; drawing falls back
 * to target p. The combined draw consumes no RNG on refusal and no draw for
 * a singleton, exactly like an ordinary target draw. */
lie_sampling_status lie_sampling_distribution_residual(
    const lie_sampling_probability *, size_t target_count,
    const lie_sampling_sparse_row *, lie_sampling_workspace *draft,
    lie_sampling_workspace *residual, size_t *count);
lie_sampling_status lie_sampling_distribution_residual_draw(
    const lie_sampling_probability *, size_t target_count,
    const lie_sampling_sparse_row *, lie_sampling_workspace *draft,
    lie_sampling_workspace *residual, uint64_t *rng, uint32_t *token);
/* Proposal q uses exact F32 integer masses summing to 2^24, with rounding
 * remainder assigned to its first entry. Proposal creation ALWAYS consumes
 * one draw, including a singleton. Mapping converts logit positions to model
 * IDs; NULL/zero keeps positions. Verification validates exact exported masses,
 * draws once for acceptance and draws a residual only after rejection.
 * Model history, stop handling, rollback and deferred correction stay owned
 * by the existing inference controller. */
lie_sampling_status
lie_sampling_proposal_quantize(const lie_sampling_probability *, size_t count,
                               const uint32_t *token_ids, size_t token_id_count,
                               uint64_t *rng, lie_sampling_proposal *);
lie_sampling_status
lie_sampling_proposal_validate(const lie_sampling_proposal_view *,
                               size_t vocabulary);
lie_sampling_status lie_sampling_proposal_verify(
    const lie_sampling_probability *, size_t target_count, size_t vocabulary,
    const lie_sampling_proposal_view *, lie_sampling_workspace *draft,
    lie_sampling_workspace *residual, uint64_t *rng, uint32_t *token,
    bool *accepted);
#ifdef __cplusplus
}
#endif
#endif
