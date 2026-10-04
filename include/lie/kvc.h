/* SPDX-License-Identifier: MIT */
#ifndef LIE_KVC_H
#define LIE_KVC_H
#include "lie/executor.h"
#ifdef __cplusplus
extern "C" {
#endif
/* DS4 KVC v1 / payload ABI 2 interchange. This is not a model identity or a
 * live-state restore API. Tensor interpretation belongs to the model codec.
 * All spans are bytes (unaligned, little-endian), never native float pointers. */
#define LIE_KVC_HEADER_BYTES 52u
typedef struct { const unsigned char *data; size_t bytes; } lie_kvc_span;
typedef struct {
    uint8_t model_id, quant_bits, reason, flags;
    uint32_t tokens, hits, context_tokens;
    uint64_t created_at, last_used;
} lie_kvc_header;
typedef struct {
    lie_kvc_header header;
    lie_kvc_span text, payload, trailer;
} lie_kvc_view;
typedef int (*lie_kvc_cancel_fn)(void *);
typedef struct {
    uint64_t memory_bytes; /* Owned object + exact wire bytes; no hidden expansion. */
    uint32_t text_bytes, trailer_bytes;
    lie_kvc_cancel_fn cancelled;
    void *userdata;
} lie_kvc_limits;
typedef struct lie_kvc lie_kvc;
/* Defaults: 8 MiB text, 1 MiB opaque trailer. Total budget must be explicit. */
lie_kvc_limits lie_kvc_default_limits(uint64_t memory_bytes);
/* Borrowed immutable source must live through all uses of the returned view.
 * Failure leaves out unchanged. Unknown reason/flag/reserved bytes are retained
 * in owned records; they do not authorize interpreting client extensions. */
lie_status lie_kvc_parse(const void *, size_t, const lie_kvc_limits *, lie_kvc_view *, lie_error *);
/* Creates a canonical envelope (reserved bytes zero), copying all three spans.
 * Use read_fd/write_fd to preserve noncanonical reserved bytes of an input. */
lie_status lie_kvc_create(const lie_kvc_view *, const lie_kvc_limits *, lie_kvc **, lie_error *);
lie_status lie_kvc_read_fd(int, const lie_kvc_limits *, lie_kvc **, lie_error *);
/* Caller owns an empty, private, non-append regular destination. No fsync or
 * publication here; cancellation/I/O failure may leave a partial destination.
 * FD offsets are unchanged. Source file/record must be immutable during use.
 * Invoke completed I/O on the existing bounded I/O worker, not the HTTP loop. */
lie_status lie_kvc_write_fd(int, const lie_kvc *, const lie_kvc_limits *, lie_error *);
const lie_kvc_view *lie_kvc_get_view(const lie_kvc *);
lie_kvc_span lie_kvc_wire(const lie_kvc *);
uint64_t lie_kvc_memory_bytes(const lie_kvc *);
void lie_kvc_destroy(lie_kvc **);
/* SHA-1(text).kv, 44 bytes including NUL. A name, NOT an integrity checksum. */
lie_status lie_kvc_filename(lie_kvc_span text, char out[44], lie_error *);
#ifdef __cplusplus
}
#endif
#endif
