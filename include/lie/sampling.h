/* SPDX-License-Identifier: MIT */
/* Model-neutral, caller-owned dense sampling. No device or protocol dependency. */
#ifndef LIE_SAMPLING_H
#define LIE_SAMPLING_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_SAMPLING_ABI 1u
typedef enum {
  LIE_SAMPLING_OK, LIE_SAMPLING_INVALID, LIE_SAMPLING_NO_FINITE,
  LIE_SAMPLING_RESOURCE, LIE_SAMPLING_NONFINITE
} lie_sampling_status;
/* Preserve the provider's C++ default initialization without changing C layout. */
#ifdef __cplusplus
#define LIE_SAMPLING_ZERO = 0
#else
#define LIE_SAMPLING_ZERO
#endif
typedef struct lie_sampling_penalty {
  uint32_t token LIE_SAMPLING_ZERO;
  uint32_t generated_count LIE_SAMPLING_ZERO;
  uint32_t repeated LIE_SAMPLING_ZERO;
} lie_sampling_penalty;
typedef struct lie_sampling_probability {
  uint32_t token LIE_SAMPLING_ZERO;
  double value LIE_SAMPLING_ZERO;
} lie_sampling_probability;
#undef LIE_SAMPLING_ZERO
typedef struct {
  uint32_t abi_version, struct_bytes;
  float temperature;
  int32_t top_k;
  float top_p, min_p;
  size_t min_keep;
  float repeat_penalty, frequency_penalty, presence_penalty;
} lie_sampling_options;
typedef struct {
  const float *logits;
  size_t count;
  /* Strictly ascending token IDs; generated counts do not include the prompt. */
  const lie_sampling_penalty *penalties;
  size_t penalty_count;
  const float *bias;
  size_t bias_count;
  /* Optional already-compiled grammar mask: zero forbids that vocabulary ID. */
  const uint8_t *allowed;
  size_t allowed_count;
} lie_sampling_row;
/* Growth preserves existing entries and returns live, suitably aligned storage.
 * The callback must not throw or retain a pointer borrowed from a row. Clients
 * enforce their own allocation budget; the library never allocates or frees. */
typedef int (*lie_sampling_grow)(void *, size_t, lie_sampling_probability **,
                                size_t *);
typedef struct {
  lie_sampling_probability *entries;
  size_t capacity;
  lie_sampling_grow grow;
  void *context;
} lie_sampling_workspace;
void lie_sampling_options_init(lie_sampling_options *);
lie_sampling_status lie_sampling_options_validate(const lie_sampling_options *);
double lie_sampling_penalize(double, float repeat, float frequency,
                            float presence, uint32_t repeated,
                            uint32_t generated_count);
lie_sampling_status lie_sampling_greedy(const lie_sampling_row *,
                                       const lie_sampling_options *, uint32_t *);
/* Order: penalties/bias, temperature, top-k, top-p, min-p. Equal ranked logits
 * retain ascending token IDs; the unfiltered linear path retains vocabulary
 * order. Returned probabilities sum to one within floating-point rounding.
 * Failure publishes count zero; workspace contents may have changed. */
lie_sampling_status lie_sampling_build(const lie_sampling_row *,
                                      const lie_sampling_options *,
                                      lie_sampling_workspace *, size_t *count);
/* Explicit request-owned xorshift64* state. Zero receives a fixed nonzero state.
 * Singleton distributions consume no draw. Invalid input never advances RNG. */
uint64_t lie_sampling_next_random(uint64_t *);
double lie_sampling_uniform(uint64_t *);
lie_sampling_status lie_sampling_draw(const lie_sampling_probability *, size_t,
                                     uint64_t *, uint32_t *);
#ifdef __cplusplus
}
#endif
#endif
