/* SPDX-License-Identifier: MIT */
#ifndef LIE_BINARY64_H
#define LIE_BINARY64_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_BINARY64_ABI 1u
#define LIE_BINARY64_TEXT_CAPACITY 64u
typedef enum {
  LIE_BINARY64_OK, LIE_BINARY64_INVALID, LIE_BINARY64_RANGE,
  LIE_BINARY64_CAPACITY, LIE_BINARY64_TEXT_LIMIT, LIE_BINARY64_WORK_LIMIT
} lie_binary64_status;
typedef struct {
  uint32_t abi_version, struct_bytes;
  size_t max_text_bytes, max_work;
} lie_binary64_limits;
void lie_binary64_limits_init(lie_binary64_limits *);
/* Finite IEEE754 binary64 -> shortest round-trip decimal, choosing fixed on
 * equal fixed/scientific lengths and the closest spelling on ties. Lowercase
 * e, signed at-least-two-digit exponents and negative zero match the pinned
 * provider's default to_chars contract. Writes no NUL, preserves unused bytes.
 * No heap, locale, floating-environment mutation, thread/cache/model/device
 * operations. Refusal preserves both output bytes and length. */
lie_binary64_status lie_binary64_format(double, char *, size_t, size_t *);
/* Full JSON number span, optionally surrounded by JSON whitespace, -> nearest
 * binary64 with ties to even. Overflow and nonzero values rounded to zero
 * refuse; zero (including -0) succeeds. All digits participate: the exact
 * fallback retains800 significant digits plus a sticky tail, exceeding the
 *768-digit maximum of a binary64 rounding midpoint. No decimal truncation or
 * double-rounding. Limits are admission work/length bounds, not timings.
 * Input/output are disjoint; no pointers or allocator contexts are retained.
 * Refusal preserves output. NULL limits use bounded defaults. */
lie_binary64_status lie_binary64_parse(const char *, size_t,
                                      const lie_binary64_limits *, double *);
#ifdef __cplusplus
}
#endif
#endif
