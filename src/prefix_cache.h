/* SPDX-License-Identifier: MIT */
#ifndef LIE_PREFIX_CACHE_H
#define LIE_PREFIX_CACHE_H
#include "lie/core.h"
#include "lie/state.h"
#include "retention.h"
#define LIE_PREFIX_CACHE_ENTRIES 8u
/* All mutations and transfers use the core device owner. A selected entry is
 * pinned by that synchronous owner interval; clients receive snapshots only.
 * Independent restored sequences never alias the immutable host payload. */
typedef struct { lie_state *state; uint64_t age; lie_retention utility; } lie_prefix_entry;
typedef struct {
    lie_prefix_entry entries[LIE_PREFIX_CACHE_ENTRIES];
    uint64_t clock;
    lie_prefix_cache_info info;
} lie_prefix_cache;
void lie_prefix_cache_init(lie_prefix_cache *,uint64_t budget);
void lie_prefix_cache_clear(lie_prefix_cache *);
lie_state *lie_prefix_cache_find(lie_prefix_cache *,const int32_t *,size_t);
void lie_prefix_cache_insert(lie_prefix_cache *,lie_state *);
lie_status lie_prefix_cache_restore(lie_prefix_cache *,lie_sequence *,const int32_t *,
                                    size_t tokens,uint32_t chunk,unsigned *reused,lie_error *);
lie_status lie_prefix_cache_capture(lie_prefix_cache *,lie_sequence *,const int32_t *,
                                    size_t tokens,lie_error *);
#endif
