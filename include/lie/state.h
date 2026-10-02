/* SPDX-License-Identifier: MIT */
#ifndef LIE_STATE_H
#define LIE_STATE_H
#include "lie/executor.h"
#include <stdbool.h>
#ifdef __cplusplus
extern "C" {
#endif
/* In-process prefix state, not a disk format or exact generation resume.
 * Core owns descriptors, allocation, immutable bytes and validation. Providers
 * only describe model components and perform completed transfers. No opaque
 * backend snapshot object or backend serializer crosses this boundary. */
#define LIE_STATE_ABI 1u
#define LIE_STATE_MAX_SECTIONS 256u
#define LIE_STATE_MAX_RANK 4u
typedef enum { LIE_STATE_U8=1, LIE_STATE_I32, LIE_STATE_F16, LIE_STATE_F32 } lie_state_dtype;
typedef enum {
    LIE_STATE_TOKENS=1, LIE_STATE_LOGITS, LIE_STATE_K, LIE_STATE_V,
    LIE_STATE_CONV, LIE_STATE_RECURRENT, LIE_STATE_PLE, LIE_STATE_NGRAM,
    LIE_STATE_INDEX, LIE_STATE_BLOCK_KEYS,
    LIE_STATE_MODEL_COMPONENT=65536
} lie_state_role;
typedef struct {
    uint32_t role, layer, dtype, rank;
    uint64_t shape[LIE_STATE_MAX_RANK];
    uint64_t bytes, offset;
} lie_state_section;
typedef struct {
    uint32_t abi_version, representation_version;
    uint32_t token_count, context_tokens, prefill_chunk, section_count;
    /* Unique live model/configuration domain. Not portable across model opens,
     * builds, devices or processes; SSD must validate a separate stable identity
     * before binding an imported checkpoint to this live domain. */
    uint64_t domain;
    uint32_t model_data[8]; /* Model-defined frontier metadata, version-qualified. */
    lie_state_section sections[LIE_STATE_MAX_SECTIONS];
} lie_state_layout;
typedef struct lie_state lie_state;

/* Provider entry points, all on the sequence's device owner. Describe never
 * mutates: source==NULL describes capture; source!=NULL describes a prospective
 * restore into an empty sequence, refusing unsupported/foreign states first.
 * Transfer failure after mutation poisons the provider; never retry as a miss.
 * Prefix restore preserves the destination's fresh sampler/RNG configuration. */
lie_status lie_sequence_state_describe(lie_sequence *, const lie_state_layout *source,
                                      lie_state_layout *out, lie_error *);
lie_status lie_sequence_state_read(lie_sequence *, const lie_state_layout *, void *, size_t, lie_error *);
lie_status lie_sequence_state_write(lie_sequence *, const lie_state_layout *, const void *, size_t, lie_error *);
int lie_backend_prefix_state_supported(void);

/* Common C17 implementation. Retained bytes include payload and descriptor
 * allocation; allocator/driver overhead is not an allocation-peak claim. */
lie_status lie_state_plan(lie_sequence *, lie_state_layout *, uint64_t *retained_bytes, lie_error *);
lie_status lie_state_capture(lie_sequence *, const lie_state_layout *, uint64_t budget,
                             lie_state **out, lie_error *);
lie_status lie_state_restore(lie_sequence *, const lie_state *, lie_error *);
void lie_state_destroy(lie_state **);
/* Immutable host state may be pinned by the bounded SSD worker. */
void lie_state_retain(lie_state *);
uint64_t lie_state_bytes(const lie_state *);
uint64_t lie_state_expanded_bytes(const lie_state *);
uint64_t lie_state_restore_workspace(const lie_state *);
bool lie_state_is_compressed(const lie_state *);
bool lie_state_compression_enabled(void);
const char *lie_state_compression_codec(void);
/* Optional lossless packing of a unique immutable state before publication.
 * peak_budget bounds the existing state + result + codec scratch. Failure or
 * insufficient savings leaves the original untouched; no lossy conversion.
 * A bounded probe may skip packing; accepted results halve retained bytes. */
bool lie_state_compress(lie_state **,uint64_t peak_budget);
const lie_state_layout *lie_state_description(const lie_state *);
const int32_t *lie_state_tokens(const lie_state *);
/* Shared layout builder/validator for model providers, CPU fixtures and core.
 * Every section is tightly packed and 8-byte aligned in the owned payload. */
int lie_state_add(lie_state_layout *, uint32_t role, uint32_t layer,
                  lie_state_dtype, uint32_t rank, const uint64_t *shape);
int lie_state_validate(const lie_state_layout *, uint64_t *payload_bytes);
int lie_state_layout_equal(const lie_state_layout *,const lie_state_layout *);
#ifdef __cplusplus
}
#endif
#endif
