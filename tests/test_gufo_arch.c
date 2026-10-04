/* SPDX-License-Identifier: MIT */
#include "gufo_arch.h"
#include <stdlib.h>
#define CHECK(x) do { if (!(x)) abort(); } while (0)
int main(void) {
    CHECK(lie_gufo_arch_matches("gfx1150", "gfx1150"));
    CHECK(lie_gufo_arch_matches("gfx1151:xnack-", "gfx1151"));
    CHECK(!lie_gufo_arch_matches("gfx1151", "gfx1150"));
    CHECK(!lie_gufo_arch_matches("gfx1150", "gfx1151"));
    CHECK(!lie_gufo_arch_matches("gfx11500", "gfx1150"));
    CHECK(!lie_gufo_arch_matches("gfx115", "gfx1150"));
    CHECK(!lie_gufo_arch_matches("", "gfx1150"));
    CHECK(!lie_gufo_arch_matches(NULL, "gfx1150"));
    CHECK(!lie_gufo_arch_matches("gfx1150", NULL));
    CHECK(!lie_gufo_arch_matches("gfx1152", "gfx1152"));
    return 0;
}
