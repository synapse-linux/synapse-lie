/* SPDX-License-Identifier: MIT */
#include <assert.h>
#include <stdio.h>
#include "experiments/q2_compressed_cache.h"

static void invariant(const lie_cc *c) {
    uint32_t prev = LIE_CC_NONE, n = 0;
    bool unpinned = false;
    for (uint32_t i = c->head; i != LIE_CC_NONE; i = c->slots[i].next) {
        assert(i < c->capacity && ++n <= c->capacity);
        const lie_cc_slot *s = &c->slots[i];
        assert(s->prev == prev);
        if (!s->pinned) unpinned = true;
        else assert(c->active && !unpinned);
        assert(!s->pending || s->pinned);
        if (s->key != LIE_CC_NONE) {
            assert(s->key < c->keys && c->lookup[s->key] == i);
        }
        prev = i;
    }
    assert(n == c->capacity && prev == c->tail);
    for (uint32_t key = 0; key < c->keys; ++key) {
        assert(!c->requested[key]);
        uint32_t slot = c->lookup[key];
        assert(slot == LIE_CC_NONE || (slot < c->capacity && c->slots[slot].key == key));
    }
}

int main(void) {
    lie_cc c = {0};
    uint32_t slots[16], a[] = {1, 2, 3}, later_hit[] = {4, 1, 1};
    assert(lie_cc_init(&c, 8, 3) == 0);
    assert(lie_cc_begin(&c, a, 3, slots) == 0);
    assert(c.misses == 3 && !c.loads);
    invariant(&c);
    assert(lie_cc_begin(&c, later_hit, 3, slots) == -2);
    assert(lie_cc_finish(&c, true) == 0 && c.loads == 3);
    const uint32_t protected_slot = c.lookup[1];
    assert(lie_cc_begin(&c, later_hit, 3, slots) == 0);
    assert(slots[1] == protected_slot && slots[2] == protected_slot);
    assert(c.hits == 1 && c.misses == 4 && c.evictions == 1);
    invariant(&c);
    assert(lie_cc_finish(&c, false) == 0);
    assert(c.lookup[4] == LIE_CC_NONE && c.lookup[1] == protected_slot && c.failed_loads == 1);
    invariant(&c);
    const uint64_t evicted = c.evictions;
    uint32_t too_many[] = {0, 1, 2, 3}, invalid[] = {2, 8};
    assert(lie_cc_begin(&c, too_many, 4, slots) == -1);
    assert(lie_cc_begin(&c, invalid, 2, slots) == -1 && c.evictions == evicted);
    assert(lie_cc_finish(&c, true) == -1);
    invariant(&c);
    lie_cc_destroy(&c);

    /* Model-free payload fixture. Each key has a distinct immutable packed
     * triplet; simulated failed reads must never become a later cache hit. */
    assert(lie_cc_init(&c, 97, 13) == 0);
    uint32_t payload[13];
    for (uint32_t i = 0; i < 13; ++i) payload[i] = LIE_CC_NONE;
    uint32_t rng = 731;
    for (uint32_t rep = 0; rep < 30000; ++rep) {
        uint32_t keys[12];
        const size_t n = 1 + rep % 12;
        for (size_t i = 0; i < n; ++i) {
            rng = rng * 1664525u + 1013904223u;
            keys[i] = (rng >> 16) % 97;
        }
        assert(lie_cc_begin(&c, keys, n, slots) == 0);
        invariant(&c);
        bool success = rep % 19 != 0;
        for (size_t i = 0; i < n; ++i) {
            if (!c.slots[slots[i]].pending) assert(payload[slots[i]] == keys[i]);
            else payload[slots[i]] = success ? keys[i] : LIE_CC_NONE;
        }
        assert(lie_cc_finish(&c, success) == 0);
        invariant(&c);
    }
    assert(c.hits && c.misses && c.evictions && c.loads && c.failed_loads);
    lie_cc_destroy(&c);
    assert(lie_cc_init(&c, 0, 1) == -1 && lie_cc_init(&c, 1, 2) == -1);
    assert(lie_cc_init(&c, 1, 1) == 0);
    uint32_t only[] = {0};
    assert(lie_cc_begin(&c, only, 1, slots) == 0 && slots[0] == 0);
    assert(lie_cc_finish(&c, true) == 0);
    assert(lie_cc_begin(&c, only, 1, slots) == 0 && c.hits == 1);
    assert(lie_cc_finish(&c, true) == 0);
    invariant(&c);
    lie_cc_destroy(&c);
    puts("Compressed expert-cache policy: protected hits, failures, capacity and 30000 transactions passed.");
    return 0;
}
