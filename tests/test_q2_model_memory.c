/* SPDX-License-Identifier: MIT */
#include "q2_model_memory.h"
#include <assert.h>
#include <stdio.h>
#define GIB (UINT64_C(1) << 30)
int main(void) {
    lie_q2_test_memory p;
    assert(!lie_q2_test_memory_charge(1));
    assert(!lie_q2_test_memory_plan(UINT64_MAX, 0, 1, 102400491520, &p));
    assert(p.allocation_limit == 0);
    assert(!lie_q2_test_memory_plan(GIB, GIB + 4, 1, 102400491520, &p));
    assert(!lie_q2_test_memory_plan(GIB, 3, 1, 102400491520, &p));
    assert(!lie_q2_test_memory_plan(GIB, 0, 4097, 102400491520, &p));
    assert(!lie_q2_test_memory_plan(GIB, 0, 1, 102400491519, &p));
    assert(!lie_q2_test_memory_plan(GIB, 0, 1, 102400491520, NULL));
    assert(lie_q2_test_memory_plan(40 * GIB, 4 * GIB, 1255, 102400491520, &p));
    assert(p.weight_upper == 42 * GIB + 1255 * 4096);
    assert(p.allocation_limit == 0 && p.host_allowance == 0 && p.system_reserve == 0);
    assert(p.required_available == p.weight_upper);
    assert(!lie_q2_test_memory_start(&p, p.required_available - 1));
    assert(!lie_q2_test_memory_active());
    assert(lie_q2_test_memory_start(&p, p.required_available));
    assert(!lie_q2_test_memory_start(&p, UINT64_MAX));
    /* No quota: this only counts requests, without allocating any memory. */
    assert(lie_q2_test_memory_charge(80 * GIB));
    assert(lie_q2_test_memory_charge(1));
    assert(lie_q2_test_memory_charged() == 80 * GIB + 1);
    assert(!lie_q2_test_memory_charge(UINT64_MAX));
    assert(!lie_q2_test_memory_active());
    assert(!lie_q2_test_memory_charge(0));
    assert(!lie_q2_test_memory_start(&p, UINT64_MAX));
    puts("Q2_TEST_MEMORY_ACCOUNTING_NO_QUOTA_CPU_PASS_NOT_RESIDENT_FIT");
    return 0;
}
