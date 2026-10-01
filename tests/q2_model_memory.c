/* SPDX-License-Identifier: MIT */
#include "q2_model_memory.h"
#include <stdatomic.h>
#include <stddef.h>
#define GIB (UINT64_C(1) << 30)
static atomic_uint_fast64_t charged;
static atomic_int active;
int lie_q2_test_memory_plan(uint64_t non_ple, uint64_t f32, uint64_t tensors,
                           uint64_t ple, lie_q2_test_memory *out) {
    if (!out) return 0;
    *out = (lie_q2_test_memory){0};
    /* First-test scope: the inspected single-file antirez Q2, no MTP/vision.
     * These bounds make every following sum/product representable. */
    if (!non_ple || non_ple > 64 * GIB || f32 > non_ple || f32 % 4 ||
        !tensors || tensors > 4096 || ple != UINT64_C(102400491520)) return 0;
    out->ple_addressed = ple;
    out->weight_upper = non_ple + f32 / 2 + tensors * 4096;
    out->required_available = out->weight_upper;
    return 1;
}
int lie_q2_test_memory_start(const lie_q2_test_memory *p, uint64_t available) {
    /* Single owner, once, before any HIP/library initialization. No reset. */
    if (!p || !p->weight_upper || p->weight_upper > 80 * GIB ||
        p->allocation_limit || p->host_allowance || p->system_reserve ||
        p->required_available != p->weight_upper ||
        p->required_available > available || atomic_load(&active)) return 0;
    atomic_store(&charged, 0);
    atomic_store(&active, 1);
    return 1;
}
int lie_q2_test_memory_charge(uint64_t bytes) {
    if (atomic_load(&active) != 1) return 0;
    uint_fast64_t used = atomic_load(&charged);
    do {
        if (bytes > UINT64_MAX - used) {
            atomic_store(&active, -1); /* Accounting overflow; no retry. */
            return 0;
        }
    } while (!atomic_compare_exchange_weak(&charged, &used, used + bytes));
    return 1;
}
int lie_q2_test_memory_active(void) { return atomic_load(&active) == 1; }
uint64_t lie_q2_test_memory_charged(void) { return atomic_load(&charged); }
