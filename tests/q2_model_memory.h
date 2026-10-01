/* SPDX-License-Identifier: MIT */
#ifndef LIE_Q2_MODEL_MEMORY_H
#define LIE_Q2_MODEL_MEMORY_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Test-only role accounting, NOT measured residency or production admission.
 * All non-PLE tensors (even unused predictor tensors) are counted as uploads.
 * F32 tensors additionally carry a conservative F16 conversion copy.
 * Dedicated-machine policy: NO artificial allocation cap or fixed reserve.
 * allocation_limit/host_allowance/system_reserve are zero (disabled).
 * required_available is only the weight estimate; it is NOT a whole-run fit
 * guarantee. HIP errors stop the test. Cumulative requested bytes are merely
 * diagnostic, include freed/failed requests, and are NOT resident memory.
 * PLE stays disk-addressed: both readers require O_DIRECT, no fallback. */
typedef struct {
    uint64_t ple_addressed, weight_upper, allocation_limit;
    uint64_t host_allowance, system_reserve, required_available;
} lie_q2_test_memory;
int lie_q2_test_memory_plan(uint64_t non_ple, uint64_t f32, uint64_t tensors,
                           uint64_t ple, lie_q2_test_memory *out);
int lie_q2_test_memory_start(const lie_q2_test_memory *plan, uint64_t available);
int lie_q2_test_memory_charge(uint64_t bytes);
int lie_q2_test_memory_active(void);
uint64_t lie_q2_test_memory_charged(void);
#ifdef __cplusplus
}
#endif
#endif
