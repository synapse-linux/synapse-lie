/* SPDX-License-Identifier: MIT */
#include "lie/steering_direction.h"
#include <assert.h>
#include <float.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static lie_steering_direction_options options(uint32_t layers, uint32_t width) {
  return (lie_steering_direction_options){LIE_STEERING_DIRECTION_ABI,
    sizeof(lie_steering_direction_options), layers, width, 4, 4096};
}
static lie_steering_direction_info info(lie_steering_direction *d) {
  lie_steering_direction_info out = {.abi_version=LIE_STEERING_DIRECTION_ABI,
    .struct_bytes=sizeof(out)};
  assert(lie_steering_direction_snapshot(d, &out, NULL) == LIE_OK);
  return out;
}
static void close_to(float actual, double expected) {
  assert(fabs((double)actual - expected) < 2e-7);
}
static void analytic_and_borrowing(void) {
  lie_steering_direction *d = NULL;
  lie_steering_direction_options o = options(2, 2);
  assert(lie_steering_direction_create(&o, &d, NULL) == LIE_OK);
  assert(lie_steering_direction_values(d) == NULL && !info(d).ready);
  float target[] = {5, 7, -3, 4}, contrast[] = {2, 3, 0, 0};
  assert(lie_steering_direction_add_pair(d, target, contrast, 4, NULL) == LIE_OK);
  memset(target, 0, sizeof(target)); memset(contrast, 0, sizeof(contrast));
  assert(info(d).pairs == 1 && info(d).bank_bytes == 16);
  assert(lie_steering_direction_finish(d, NULL) == LIE_OK);
  const float *bank = lie_steering_direction_values(d);
  close_to(bank[0], .6); close_to(bank[1], .8);
  close_to(bank[2], -.6); close_to(bank[3], .8);
  float saved[4]; memcpy(saved, bank, sizeof(saved));
  assert(lie_steering_direction_add_pair(d, target, contrast, 4, NULL) == LIE_INVALID);
  assert(lie_steering_direction_finish(d, NULL) == LIE_INVALID);
  assert(!memcmp(saved, bank, sizeof(saved)) && info(d).pairs == 1 && info(d).ready);
  lie_steering_direction_info bad = info(d); --bad.struct_bytes;
  lie_steering_direction_info before = bad;
  assert(lie_steering_direction_snapshot(d, &bad, NULL) == LIE_INVALID);
  assert(!memcmp(&bad, &before, sizeof(bad)));
  lie_steering_direction_destroy(&d); assert(!d);
  lie_steering_direction_destroy(&d); lie_steering_direction_destroy(NULL);
}
static void refusal_and_recovery(void) {
  lie_steering_direction *d = NULL;
  lie_steering_direction_options o = options(2, 2); o.max_pairs = 2;
  assert(lie_steering_direction_create(&o, &d, NULL) == LIE_OK);
  assert(lie_steering_direction_finish(d, NULL) == LIE_INVALID);
  float target[] = {3, 4, 0, 0}, contrast[] = {0, 0, 0, 0};
  float invalid[] = {100, 100, 100, NAN};
  assert(lie_steering_direction_add_pair(d, invalid, contrast, 4, NULL) == LIE_INVALID);
  invalid[3] = INFINITY;
  assert(lie_steering_direction_add_pair(d, target, invalid, 4, NULL) == LIE_INVALID);
  assert(lie_steering_direction_add_pair(d, NULL, contrast, 4, NULL) == LIE_INVALID);
  assert(lie_steering_direction_add_pair(d, target, contrast, 3, NULL) == LIE_INVALID);
  assert(info(d).pairs == 0 && !lie_steering_direction_values(d));
  assert(lie_steering_direction_add_pair(d, target, contrast, 4, NULL) == LIE_OK);
  assert(lie_steering_direction_finish(d, NULL) == LIE_INVALID); /* Second layer is zero. */
  assert(info(d).pairs == 1 && !info(d).ready && !lie_steering_direction_values(d));
  float recovery[] = {0, 0, 0, -7};
  assert(lie_steering_direction_add_pair(d, recovery, contrast, 4, NULL) == LIE_OK);
  assert(lie_steering_direction_add_pair(d, target, contrast, 4, NULL) == LIE_RESOURCE_LIMIT);
  assert(info(d).pairs == 2);
  assert(lie_steering_direction_finish(d, NULL) == LIE_OK);
  const float *bank = lie_steering_direction_values(d);
  close_to(bank[0], .6); close_to(bank[1], .8);
  close_to(bank[2], 0); close_to(bank[3], -1);
  lie_steering_direction_destroy(&d);
}
static void signs_and_cancellation(void) {
  const float target[] = {7, 0}, contrast[] = {0, 24};
  lie_steering_direction *a = NULL, *b = NULL;
  lie_steering_direction_options o = options(1, 2);
  assert(lie_steering_direction_create(&o, &a, NULL) == LIE_OK);
  assert(lie_steering_direction_create(&o, &b, NULL) == LIE_OK);
  assert(lie_steering_direction_add_pair(a, target, contrast, 2, NULL) == LIE_OK);
  assert(lie_steering_direction_add_pair(b, contrast, target, 2, NULL) == LIE_OK);
  assert(lie_steering_direction_finish(a, NULL) == LIE_OK);
  assert(lie_steering_direction_finish(b, NULL) == LIE_OK);
  close_to(lie_steering_direction_values(a)[0], 7.0 / 25);
  close_to(lie_steering_direction_values(a)[1], -24.0 / 25);
  for (unsigned i = 0; i < 2; ++i)
    assert(lie_steering_direction_values(a)[i] == -lie_steering_direction_values(b)[i]);
  lie_steering_direction_destroy(&a); lie_steering_direction_destroy(&b);
  assert(lie_steering_direction_create(&o, &a, NULL) == LIE_OK);
  float zero[] = {0, 0}, large[] = {FLT_MAX, 0}, small[] = {1, 0}, opposite[] = {-FLT_MAX, 0};
  assert(lie_steering_direction_add_pair(a, large, zero, 2, NULL) == LIE_OK);
  assert(lie_steering_direction_add_pair(a, small, zero, 2, NULL) == LIE_OK);
  assert(lie_steering_direction_add_pair(a, opposite, zero, 2, NULL) == LIE_OK);
  assert(lie_steering_direction_finish(a, NULL) == LIE_OK);
  assert(lie_steering_direction_values(a)[0] == 1 && lie_steering_direction_values(a)[1] == 0);
  lie_steering_direction_destroy(&a);
}
static void budget_and_geometry(void) {
  lie_steering_direction *d = NULL;
  lie_steering_direction_options o = options(3, 5);
  assert(lie_steering_direction_create(&o, &d, NULL) == LIE_OK);
  const uint64_t required = info(d).requested_bytes;
  assert(required > info(d).bank_bytes && required <= o.max_bytes);
  lie_steering_direction_destroy(&d);
  o.max_bytes = required - 1;
  assert(lie_steering_direction_create(&o, &d, NULL) == LIE_RESOURCE_LIMIT && !d);
  o.max_bytes = required;
  assert(lie_steering_direction_create(&o, &d, NULL) == LIE_OK);
  lie_steering_direction *before = d;
  assert(lie_steering_direction_create(&o, &d, NULL) == LIE_INVALID && d == before);
  lie_steering_direction_destroy(&d);
  o = options(UINT32_MAX, UINT32_MAX); o.max_bytes = UINT64_MAX;
  assert(lie_steering_direction_create(&o, &d, NULL) == LIE_RESOURCE_LIMIT && !d);
  o = options(1, 2); o.width = 0;
  assert(lie_steering_direction_create(&o, &d, NULL) == LIE_INVALID && !d);
  o = options(1, 2); o.max_pairs = 0;
  assert(lie_steering_direction_create(&o, &d, NULL) == LIE_INVALID && !d);
  o = options(1, 2); o.abi_version = 0;
  assert(lie_steering_direction_create(&o, &d, NULL) == LIE_INVALID && !d);
  o = options(1, 2); --o.struct_bytes;
  assert(lie_steering_direction_create(&o, &d, NULL) == LIE_INVALID && !d);
  assert(lie_steering_direction_values(NULL) == NULL);
}
static void branch_mean(void) {
  const float rows[] = {3, -1, 7, 5, 1, 9, 7, 3, 11};
  float out[] = {100, 200, 300};
  assert(lie_steering_direction_mean_branches(3, 3, rows, 9, out, 3, NULL) == LIE_OK);
  assert(out[0] == 5 && out[1] == 1 && out[2] == 9);
  const float extreme[] = {FLT_MAX, -FLT_MAX, 1, -1, -FLT_MAX, FLT_MAX};
  assert(lie_steering_direction_mean_branches(2, 3, extreme, 6, out, 2, NULL) == LIE_OK);
  close_to(out[0], 1.0 / 3); close_to(out[1], -1.0 / 3);
  const float max_rows[] = {FLT_MAX, -FLT_MAX, FLT_MAX, -FLT_MAX};
  assert(lie_steering_direction_mean_branches(2, 2, max_rows, 4, out, 2, NULL) == LIE_OK);
  assert(out[0] == FLT_MAX && out[1] == -FLT_MAX);
  float invalid[] = {1, 2, 3, 4, 5, NAN};
  float saved[3]; memcpy(saved, out, sizeof(saved));
  assert(lie_steering_direction_mean_branches(3, 2, invalid, 6, out, 3, NULL) == LIE_INVALID);
  assert(!memcmp(saved, out, sizeof(saved)));
  assert(lie_steering_direction_mean_branches(3, 2, rows, 8, out, 3, NULL) == LIE_INVALID);
  assert(lie_steering_direction_mean_branches(3, 3, rows, 9, out, 2, NULL) == LIE_INVALID);
  assert(lie_steering_direction_mean_branches(0, 3, rows, 9, out, 3, NULL) == LIE_INVALID);
  assert(!memcmp(saved, out, sizeof(saved)));
  assert(lie_steering_direction_mean_branches(3, 2, invalid, 6, invalid + 1, 3, NULL) == LIE_INVALID);
  invalid[5] = 6;
  assert(lie_steering_direction_mean_branches(3, 2, invalid, 6, invalid + 1, 3, NULL) == LIE_INVALID);
  assert(lie_steering_direction_mean_branches(3, 2, NULL, 6, out, 3, NULL) == LIE_INVALID);
  assert(!memcmp(saved, out, sizeof(saved)));
}
int main(void) {
  analytic_and_borrowing(); refusal_and_recovery(); signs_and_cancellation();
  budget_and_geometry(); branch_mean();
  puts("Steering direction learning: PASS (CPU fixtures; no model forward or learned quality)");
  return 0;
}
