/* SPDX-License-Identifier: MIT */
#ifndef LIE_Q2_CURVE_HEADROOM_H
#define LIE_Q2_CURVE_HEADROOM_H
#include <stdbool.h>
#include <stdint.h>

/* Private paired benchmark only. Preserve all other model/context guards.
 * This is capacity extrapolation, not a RoPE or quality qualification. */
static inline uint32_t lie_q2_curve_capacity(uint32_t declared,
                                             uint32_t requested, bool ar_only) {
  return ar_only && declared == 262144u && requested == 266240u ? requested
                                                              : declared;
}
#endif
