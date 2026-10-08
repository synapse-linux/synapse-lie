/* SPDX-License-Identifier: MIT */
#include "lie/steering_activation.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static lie_steering_activation initial(void) {
  lie_steering_activation p;
  memset(&p, 0xa5, sizeof(p));
  p.abi_version = LIE_STEERING_ACTIVATION_ABI;
  p.struct_bytes = sizeof(p);
  return p;
}
static void refusal(uint32_t w, uint32_t n, uint32_t b, float scale,
                    uint64_t available, uint64_t direction) {
  lie_steering_activation p = initial(), before = p;
  lie_error error = {{0}};
  assert(lie_steering_activation_prepare(w, n, b, scale, available, direction,
                                         &p, &error) == LIE_INVALID);
  assert(!memcmp(&p, &before, sizeof(p)) && error.message[0]);
}
int main(void) {
  /* Different model geometry, including a width not divisible by a GPU lane
   * group. Token-major, then independent HC branches, with one shared row d. */
  lie_steering_activation p = initial();
  assert(lie_steering_activation_prepare(5, 2, 3, -2.0f, 120, 20, &p,
                                         NULL) == LIE_OK);
  assert(p.width == 5 && p.tokens == 2 && p.branches == 3 && p.rows == 6);
  assert(p.elements == 30 && p.activation_bytes == 120 &&
         p.direction_bytes == 20 && p.scale == -2.0f);
  /* Every branch has exactly its own hidden-width slice; adjacent token rows
   * neither overlap nor alias the direction row. Last offset reaches the end. */
  uint64_t next = 0;
  for (uint32_t t = 0; t < p.tokens; ++t)
    for (uint32_t b = 0; b < p.branches; ++b) {
      const uint64_t offset = ((uint64_t)t * p.branches + b) * p.width;
      assert(offset == next);
      next = offset + p.width;
    }
  assert(next == p.elements);
  assert(lie_steering_activation_prepare(2560, 2048, 4, 1.0f,
           83886080, 10240, &p, NULL) == LIE_OK);
  assert(p.rows == 8192 && p.elements == 20971520);
  assert(lie_steering_activation_prepare(2560, 8, 1, 100.0f,
           81920, 10240, &p, NULL) == LIE_OK && p.rows == 8);
  assert(lie_steering_activation_prepare(5, 2, 3, -100.0f,
           UINT64_MAX, UINT64_MAX, &p, NULL) == LIE_OK && p.scale == -100.0f);
  assert(lie_steering_activation_prepare(5, 2, 3, -0.0f,
           120, 20, &p, NULL) == LIE_OK && p.scale == 0 && !signbit(p.scale));
  refusal(0, 1, 1, 0, UINT64_MAX, UINT64_MAX);
  refusal(1, 0, 1, 0, UINT64_MAX, UINT64_MAX);
  refusal(1, 1, 0, 0, UINT64_MAX, UINT64_MAX);
  refusal(5, 2, 3, 1, 119, 20);
  refusal(5, 2, 3, 1, 120, 19);
  refusal(5, 2, 3, 0, 119, 20); /* Zero does not accept malformed spans. */
  refusal(5, 2, 3, NAN, 120, 20);
  refusal(5, 2, 3, INFINITY, 120, 20);
  refusal(5, 2, 3, -INFINITY, 120, 20);
  refusal(5, 2, 3, nextafterf(100.0f, INFINITY), 120, 20);
  refusal(5, 2, 3, nextafterf(-100.0f, -INFINITY), 120, 20);
  refusal(1, UINT32_MAX, 1, 0, UINT64_MAX, UINT64_MAX);
  refusal(1, UINT32_MAX, UINT32_MAX, 0, UINT64_MAX, UINT64_MAX);
  refusal(UINT32_MAX, INT32_MAX, 1, 0, UINT64_MAX, UINT64_MAX);
  lie_steering_activation before = p;
  p.abi_version = 0;
  lie_steering_activation invalid = p;
  assert(lie_steering_activation_prepare(1, 1, 1, 0, 4, 4, &p,
                                         NULL) == LIE_INVALID);
  assert(!memcmp(&p, &invalid, sizeof(p)));
  p = before; --p.struct_bytes; invalid = p;
  assert(lie_steering_activation_prepare(1, 1, 1, 0, 4, 4, &p,
                                         NULL) == LIE_INVALID);
  assert(!memcmp(&p, &invalid, sizeof(p)));
  assert(lie_steering_activation_prepare(1, 1, 1, 0, 4, 4, NULL,
                                         NULL) == LIE_INVALID);
  puts("Steering activation span contract: PASS (host-only, no model forward)");
  return 0;
}
