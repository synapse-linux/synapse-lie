/* SPDX-License-Identifier: MIT */
#include "q2_attention_capacity.h"
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

static void visible_bounds(void) {
    const uint32_t widths[] = {1, 3, 4, 16, 17, 96, 2048, 2049, 65536};
    for (uint32_t end = 1; end <= 266368; ++end) {
        const uint32_t needed = end / 128u + (end % 128u != 0);
        for (size_t i = 0; i < sizeof(widths) / sizeof(widths[0]); ++i) {
            if (widths[i] > end)
                continue;
            const uint32_t start = end - widths[i];
            const bool in_range = end <= 266240;
            assert(lie_q2_attention_mask_supported(start, widths[i], needed) == in_range);
            assert(lie_q2_attention_mask_supported(start, widths[i], 8192) == in_range);
            assert(!lie_q2_attention_mask_supported(start, widths[i], needed - 1));
        }
    }
    assert(lie_q2_attention_mask_supported(131072, 2048, 2080));
    assert(lie_q2_attention_mask_supported(262144, 4096, 2080));
    assert(!lie_q2_attention_mask_supported(262144, 4097, 2080));
    assert(!lie_q2_attention_mask_supported(262144, 4096, 2048));
    assert(!lie_q2_attention_mask_supported(UINT32_MAX, UINT32_MAX, UINT32_MAX));
    assert(!lie_q2_attention_mask_supported(UINT32_MAX, 1, UINT32_MAX));
    assert(!lie_q2_attention_mask_supported(0, 0, 2080));
}

/* Exercise the changed stripe coverage at every mask width. Each live word
 * must have exactly one thread/local-slot owner, including the ninth slot. */
static void scan_ownership(void) {
    unsigned seen[LIE_Q2_ATTENTION_MASK_WORDS];
    for (unsigned words = 1; words <= LIE_Q2_ATTENTION_MASK_WORDS; ++words) {
        memset(seen, 0, sizeof(seen));
        const unsigned stride = (words + 255) / 256;
        assert(stride <= LIE_Q2_ATTENTION_WORDS_PER_THREAD);
        for (unsigned tid = 0; tid < LIE_Q2_ATTENTION_SCAN_THREADS; ++tid) {
            for (unsigned j = 0; j < LIE_Q2_ATTENTION_WORDS_PER_THREAD; ++j) {
                const unsigned word = tid * stride + j;
                if (j < stride && word < words)
                    ++seen[word];
            }
        }
        for (unsigned word = 0; word < words; ++word)
            assert(seen[word] == 1);
        for (unsigned word = words; word < LIE_Q2_ATTENTION_MASK_WORDS; ++word)
            assert(seen[word] == 0);
    }
}

int main(void) {
    _Static_assert(LIE_Q2_ATTENTION_MASK_WORDS * 128 == LIE_Q2_ATTENTION_MAX_TOKENS,
                   "mask capacity must cover the declared visible extent");
    _Static_assert(LIE_Q2_ATTENTION_WORDS_PER_THREAD * 256 >= LIE_Q2_ATTENTION_MASK_WORDS,
                   "thread-local scan must cover every mask word");
    _Static_assert(LIE_Q2_ATTENTION_MASK_WORDS >= 4 * 512 + 4,
                   "shared storage must cover both compact list and bitset");
    visible_bounds();
    scan_ownership();
    puts("Attention capacity: visible extent, allocation pitch, overflow and scan ownership pass.");
    return 0;
}
