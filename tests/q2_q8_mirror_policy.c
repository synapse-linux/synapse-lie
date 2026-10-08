/* SPDX-License-Identifier: MIT */
#include "experiments/q2_q8_mirror_policy.h"

#include <assert.h>
#include <stdio.h>

int main(void) {
    lie_q8_mirror_plan p;
    assert(lie_q8_mirror_admit(16384, 2560, 1, true, 0, NULL) == -1);
    assert(lie_q8_mirror_admit(16384, 2560, 1, true, 0, &p) == 1);
    assert(p.payload_bytes == 83886080 && p.allocation_bytes == 83890176);
    const size_t exact = LIE_Q8_MIRROR_BUDGET_BYTES - p.allocation_bytes;
    assert(lie_q8_mirror_admit(16384, 2560, 1, true, exact, &p) == 1);
    assert(p.next_mirror_bytes == LIE_Q8_MIRROR_BUDGET_BYTES);
    assert(lie_q8_mirror_admit(16384, 2560, 1, true, exact + 1, &p) == -1);
    assert(p.allocation_bytes == 0 && p.next_mirror_bytes == 0);
    assert(lie_q8_mirror_admit(13312, 2560, 1, true, SIZE_MAX, &p) == -1);
    assert(p.payload_bytes == 0);
    assert(lie_q8_mirror_admit(2560, 6144, 1, true, 0, &p) == 1);
    assert(p.payload_bytes == 31457280);
    assert(lie_q8_mirror_admit(16384, 2560, 2, true, 0, &p) == 0);
    assert(lie_q8_mirror_admit(16384, 2560, 1, false, 0, &p) == 0);
    assert(lie_q8_mirror_admit(16384, 2559, 1, true, 0, &p) == 0);
    assert(lie_q8_mirror_admit(640, 2560, 1, true, 0, &p) == 0);
    assert(lie_q8_mirror_admit(UINT32_MAX, UINT32_MAX, 1, true, 0, &p) == 0);
    assert(p.allocation_bytes == 0 && p.next_mirror_bytes == 0);

    size_t used = 0, payload = 0;
    for (unsigned layer = 0; layer < 48; ++layer) {
        const bool linear = layer % 4 != 3;
        assert(lie_q8_mirror_admit(linear ? 16384 : 13312, 2560, 1, true, used, &p) == 1);
        used = p.next_mirror_bytes;
        payload += p.payload_bytes;
        assert(lie_q8_mirror_admit(2560, 6144, 1, true, used, &p) == 1);
        used = p.next_mirror_bytes;
        payload += p.payload_bytes;
    }
    assert(payload == (size_t)5347737600ULL);
    assert(used == payload + 96 * LIE_Q8_MIRROR_TAIL_BYTES);
    puts("Q8 mirror C17 resource policy passes; no GPU or model inference");
    return 0;
}
