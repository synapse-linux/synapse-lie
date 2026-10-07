/* SPDX-License-Identifier: MIT */
#ifndef LIE_PREFILL_H
#define LIE_PREFILL_H
#include "lie/executor.h"

#define LIE_PREFILL_ABI 1u
#define LIE_PREFILL_DEFAULT_CHUNK 2048u
#define LIE_PREFILL_MAX_CHUNK 32768u
/* Reserved at model load; zero follows the initial core options.chunk.
 * A larger capacity consumes provider scratch even when the current chunk is
 * smaller. No allocation or numerical provider call occurs in a live setter. */
typedef struct {
    uint32_t abi_version, struct_bytes;
    uint32_t capacity_tokens;
} lie_prefill_options;
typedef struct {
    uint32_t abi_version, struct_bytes;
    uint32_t chunk_tokens, capacity_tokens;
    uint64_t revision;
} lie_prefill_info;
#ifdef __cplusplus
extern "C" {
#endif
void lie_prefill_options_init(lie_prefill_options *);
void lie_prefill_info_init(lie_prefill_info *);
/* Provider owner only, before any prefill. Bind the admitted chunk and copied
 * semantic scope (after image attachment, before steering composition). Scope
 * is retained in captures and independently checked before restore mutation.
 * Chunk must fit the model's immutable reservation. Refusal changes nothing. */
lie_status lie_sequence_configure_prefill(lie_sequence *, uint32_t chunk_tokens,
                                         const unsigned char semantic_scope[32], lie_error *);
#ifdef __cplusplus
}
#endif
#endif
