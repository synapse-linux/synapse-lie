/* SPDX-License-Identifier: MIT */
#ifndef LIE_Q2_COMPRESSED_CACHE_H
#define LIE_Q2_COMPRESSED_CACHE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

/* Model-local keys identify one layer/expert and its immutable gate/up/down
 * byte ranges. The caller owns GPU buffers and completion events. This C17
 * policy never reads model weights, performs inference, or assumes that
 * enqueueing a transfer makes its destination ready.
 *
 * Reference: antirez/ds4 0aaea5a238fb41a35106a551e73c8409dfb751ac,
 * cuda_stream_selected_cache_begin_load: protect every requested hit before
 * selecting victims; keep quantized bytes; publish only complete triplets.
 * The implementation below uses a direct key map and an intrusive LRU list.
 */
#define LIE_CC_NONE UINT32_MAX
typedef struct lie_cc_slot {
    uint32_t key, prev, next;
    bool pinned, pending;
} lie_cc_slot;

typedef struct lie_cc {
    uint32_t keys, capacity, head, tail;
    uint32_t *lookup;
    uint8_t *requested;
    lie_cc_slot *slots;
    bool active;
    uint64_t hits, misses, evictions, loads, failed_loads;
} lie_cc;

static inline void lie_cc_destroy(lie_cc *c) {
    if (!c) return;
    free(c->lookup); free(c->requested); free(c->slots);
    memset(c, 0, sizeof(*c));
}

/* Zero-initialize c before its first init. No allocation belongs to a model
 * until every metadata allocation succeeds. Reinitializing a live cache fails. */
static inline int lie_cc_init(lie_cc *c, uint32_t keys, uint32_t capacity) {
    if (!c || c->slots || c->lookup || c->requested || !keys || !capacity ||
        capacity > keys || keys == LIE_CC_NONE ||
        (uint64_t)keys * sizeof(uint32_t) > SIZE_MAX ||
        (uint64_t)capacity * sizeof(lie_cc_slot) > SIZE_MAX) return -1;
    c->lookup = (uint32_t *)malloc((size_t)keys * sizeof(uint32_t));
    c->requested = (uint8_t *)calloc(keys, 1);
    c->slots = (lie_cc_slot *)calloc(capacity, sizeof(lie_cc_slot));
    if (!c->lookup || !c->requested || !c->slots) {
        lie_cc_destroy(c); return -1;
    }
    c->keys = keys; c->capacity = capacity; c->head = 0; c->tail = capacity - 1;
    for (uint32_t i = 0; i < keys; ++i) c->lookup[i] = LIE_CC_NONE;
    for (uint32_t i = 0; i < capacity; ++i) {
        c->slots[i].key = LIE_CC_NONE;
        c->slots[i].prev = i ? i - 1 : LIE_CC_NONE;
        c->slots[i].next = i + 1 < capacity ? i + 1 : LIE_CC_NONE;
    }
    return 0;
}

static inline void lie_cc_touch(lie_cc *c, uint32_t i) {
    if (c->head == i) return;
    lie_cc_slot *s = &c->slots[i];
    if (s->prev != LIE_CC_NONE) c->slots[s->prev].next = s->next;
    if (s->next != LIE_CC_NONE) c->slots[s->next].prev = s->prev;
    else c->tail = s->prev;
    s->prev = LIE_CC_NONE; s->next = c->head;
    c->slots[c->head].prev = i; c->head = i;
}

/* Returns 0, -1 for invalid arguments/insufficient capacity, or -2 while an
 * earlier batch is still pinned. Invalid requests do not evict any entry.
 * Pending slots are visible only to this transaction, never as future hits. */
static inline int lie_cc_begin(lie_cc *c, const uint32_t *keys, size_t n,
                               uint32_t *slots_out) {
    if (!c || !c->slots || !keys || !slots_out || !n || n > c->keys) return -1;
    if (c->active) return -2;
    uint32_t unique = 0;
    for (size_t i = 0; i < n; ++i) {
        if (keys[i] >= c->keys) {
            for (size_t j = 0; j < i; ++j) c->requested[keys[j]] = 0;
            return -1;
        }
        if (!c->requested[keys[i]]) { c->requested[keys[i]] = 1; ++unique; }
    }
    if (unique > c->capacity) {
        for (size_t i = 0; i < n; ++i) c->requested[keys[i]] = 0;
        return -1;
    }
    c->active = true;
    /* Protect later hits before processing any earlier miss. */
    for (size_t i = 0; i < n; ++i) {
        uint32_t slot = c->lookup[keys[i]];
        if (slot != LIE_CC_NONE && !c->slots[slot].pinned) {
            c->slots[slot].pinned = true; ++c->hits;
            lie_cc_touch(c, slot);
        }
    }
    for (size_t i = 0; i < n; ++i) {
        uint32_t key = keys[i], slot = c->lookup[key];
        if (slot == LIE_CC_NONE) {
            slot = c->tail;
            /* Protected entries have moved to the head; each miss also moves
             * its new slot there. This preserves O(n) selection after pinning. */
            if (c->slots[slot].key != LIE_CC_NONE) {
                c->lookup[c->slots[slot].key] = LIE_CC_NONE; ++c->evictions;
            }
            c->slots[slot].key = key;
            c->slots[slot].pinned = c->slots[slot].pending = true;
            c->lookup[key] = slot; ++c->misses;
            lie_cc_touch(c, slot);
        }
        slots_out[i] = slot;
        c->requested[key] = 0;
    }
    return 0;
}

/* Call only after all selected transfers AND GPU consumers have completed.
 * Failure invalidates newly loaded slots; prior hits keep their valid bytes. */
static inline int lie_cc_finish(lie_cc *c, bool success) {
    if (!c || !c->active) return -1;
    for (uint32_t slot = c->head;
         slot != LIE_CC_NONE && c->slots[slot].pinned;
         slot = c->slots[slot].next) {
        lie_cc_slot *s = &c->slots[slot];
        if (s->pending) {
            if (success) ++c->loads;
            else {
                ++c->failed_loads; c->lookup[s->key] = LIE_CC_NONE;
                s->key = LIE_CC_NONE;
            }
        }
        s->pending = s->pinned = false;
    }
    c->active = false;
    return 0;
}

#endif
