/* SPDX-License-Identifier: MIT */
#include "q2_hc_inject_scratch.h"
#include <stdio.h>

#define CHECK(expr) do { if (!(expr)) { \
    fprintf(stderr, "HC scratch check failed at line %d\n", __LINE__); \
    return 1; } } while (0)

int main(void) {
    float identity[2] = {0}, different[1] = {0};
    const size_t required = (size_t)2048 * 2560 * sizeof(float);
    lie_q2_hc_inject_scratch a = {identity, required};
    CHECK(lie_q2_hc_inject_capacity(2048, 1, 2560) == required);
    CHECK(lie_q2_hc_inject_capacity(2048, 8, 2560) == required * 8);
    CHECK(lie_q2_hc_inject_capacity(0, 8, 2560) == 0);
    CHECK(lie_q2_hc_inject_capacity(2048, 0, 2560) == 0);
    CHECK(lie_q2_hc_inject_capacity(2048, 8, 0) == 0);
    CHECK(lie_q2_hc_inject_capacity(SIZE_MAX, 2, 1) == 0);
    CHECK(lie_q2_hc_inject_capacity(SIZE_MAX / 2, 1, 3) == 0);
    CHECK(lie_q2_hc_inject_capacity(SIZE_MAX / 2, 1, 1) == 0);
    CHECK(lie_q2_hc_inject_can_borrow(&a, identity, 2048, 2560, 320, 4, false));
    CHECK(!lie_q2_hc_inject_can_borrow(&a, identity, 2048, 2560, 320, 4, true));
    CHECK(!lie_q2_hc_inject_can_borrow(&a, identity + 1, 2048, 2560, 320, 4, false));
    CHECK(!lie_q2_hc_inject_can_borrow(&a, different, 2048, 2560, 320, 4, false));
    CHECK(!lie_q2_hc_inject_can_borrow(&a, NULL, 2048, 2560, 320, 4, false));
    CHECK(!lie_q2_hc_inject_can_borrow(NULL, identity, 2048, 2560, 320, 4, false));
    for (uint32_t rows = 0; rows <= 4096; ++rows)
        CHECK(lie_q2_hc_inject_can_borrow(&a, identity, rows, 2560, 320, 4, false)
              == (rows == 2048));
    CHECK(!lie_q2_hc_inject_can_borrow(&a, identity, 2048, 2559, 320, 4, false));
    CHECK(!lie_q2_hc_inject_can_borrow(&a, identity, 2048, 2560, 319, 4, false));
    CHECK(!lie_q2_hc_inject_can_borrow(&a, identity, 2048, 2560, 320, 3, false));
    a.bytes = required - 1;
    CHECK(!lie_q2_hc_inject_can_borrow(&a, identity, 2048, 2560, 320, 4, false));
    a.bytes = SIZE_MAX;
    CHECK(lie_q2_hc_inject_can_borrow(&a, identity, 2048, 2560, 320, 4, false));
    a.base = NULL;
    CHECK(!lie_q2_hc_inject_can_borrow(&a, NULL, 2048, 2560, 320, 4, false));
    puts("PASS HC scratch identity and capacity; host policy only, no device access");
    return 0;
}
