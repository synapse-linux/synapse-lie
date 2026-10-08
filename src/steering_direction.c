/* SPDX-License-Identifier: MIT */
#include "lie/steering_direction.h"
#include <float.h>
#include <math.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

_Static_assert(sizeof(float) == 4 && FLT_RADIX == 2 && FLT_MANT_DIG == 24 &&
  FLT_MAX_EXP == 128 && sizeof(double) == 8 && DBL_MANT_DIG == 53 &&
  DBL_MAX_EXP == 1024, "Direction learning requires IEEE754 binary32/binary64");
struct lie_steering_direction {
  lie_steering_direction_info info;
  size_t count;
  double *sum, *correction, *norm;
  float *values;
};
static lie_status refuse(lie_error *e, lie_status status, const char *message) {
  if (e) snprintf(e->message, sizeof(e->message), "%s", message);
  return status;
}
static lie_status success(lie_error *e) {
  if (e) e->message[0] = 0;
  return LIE_OK;
}
static bool span(const void *p, size_t values, uintptr_t *end) {
  if (!p || values > SIZE_MAX / sizeof(float)) return false;
  const uintptr_t start = (uintptr_t)p;
  size_t bytes = values * sizeof(float);
  if (bytes > UINTPTR_MAX - start) return false;
  *end = start + bytes;
  return true;
}
static void accumulate(double value, double *sum, double *correction) {
  const double next = *sum + value;
  *correction += fabs(*sum) >= fabs(value) ? (*sum - next) + value : (value - next) + *sum;
  *sum = next;
}
lie_status lie_steering_direction_create(const lie_steering_direction_options *o,
  lie_steering_direction **out, lie_error *e) {
  if (!o || !out || *out || o->abi_version != LIE_STEERING_DIRECTION_ABI ||
      o->struct_bytes != sizeof(*o) || !o->layers || !o->width ||
      !o->max_pairs || !o->max_bytes)
    return refuse(e, LIE_INVALID, "invalid direction learning options or handle");
  const size_t alignment = _Alignof(double);
  const size_t header = (sizeof(lie_steering_direction) + alignment - 1) / alignment * alignment;
  uint64_t count = (uint64_t)o->layers * o->width;
  uint64_t norms = (uint64_t)o->layers * sizeof(double);
  if (norms > SIZE_MAX - header ||
      count > (SIZE_MAX - header - norms) / (2 * sizeof(double) + sizeof(float)))
    return refuse(e, LIE_RESOURCE_LIMIT, "direction learning geometry overflow");
  size_t bytes = header + (size_t)norms + (size_t)count * (2 * sizeof(double) + sizeof(float));
  if ((uint64_t)bytes > o->max_bytes)
    return refuse(e, LIE_RESOURCE_LIMIT, "direction learning exceeds host budget");
  lie_steering_direction *d = calloc(1, bytes);
  if (!d) return refuse(e, LIE_RESOURCE_LIMIT, "cannot allocate direction learner");
  d->count = (size_t)count;
  d->sum = (double *)((unsigned char *)d + header);
  d->correction = d->sum + d->count;
  d->norm = d->correction + d->count;
  d->values = (float *)(d->norm + o->layers);
  d->info = (lie_steering_direction_info){
    .abi_version=LIE_STEERING_DIRECTION_ABI, .struct_bytes=sizeof(d->info),
    .layers=o->layers, .width=o->width, .max_pairs=o->max_pairs,
    .bank_bytes=count*sizeof(float), .requested_bytes=bytes, .max_bytes=o->max_bytes};
  *out = d;
  return success(e);
}
lie_status lie_steering_direction_add_pair(lie_steering_direction *d,
  const float *target, const float *contrast, size_t values, lie_error *e) {
  uintptr_t target_end, contrast_end;
  if (!d || d->info.ready || values != d->count ||
      !span(target, values, &target_end) || !span(contrast, values, &contrast_end))
    return refuse(e, LIE_INVALID, "invalid direction activation pair");
  if (d->info.pairs == d->info.max_pairs)
    return refuse(e, LIE_RESOURCE_LIMIT, "direction activation pair limit reached");
  for (size_t i = 0; i < values; ++i)
    if (!isfinite(target[i]) || !isfinite(contrast[i]))
      return refuse(e, LIE_INVALID, "nonfinite direction activation");
  /* Each difference is computed before accumulation. FP64 can represent the
   * bounded F32 magnitudes even at UINT64_MAX pairs. No host pointer survives. */
  for (size_t i = 0; i < values; ++i)
    accumulate((double)target[i] - (double)contrast[i], &d->sum[i], &d->correction[i]);
  ++d->info.pairs;
  return success(e);
}
lie_status lie_steering_direction_finish(lie_steering_direction *d, lie_error *e) {
  if (!d || d->info.ready || !d->info.pairs)
    return refuse(e, LIE_INVALID, "direction learning requires unpublished pairs");
  for (uint32_t layer = 0; layer < d->info.layers; ++layer) {
    double norm = 0;
    const size_t offset = (size_t)layer * d->info.width;
    for (uint32_t i = 0; i < d->info.width; ++i)
      norm = hypot(norm, d->sum[offset + i] + d->correction[offset + i]);
    if (!isfinite(norm) || norm == 0)
      return refuse(e, LIE_INVALID, "direction layer has zero or nonfinite norm");
    d->norm[layer] = norm;
  }
  for (uint32_t layer = 0; layer < d->info.layers; ++layer) {
    const size_t offset = (size_t)layer * d->info.width;
    for (uint32_t i = 0; i < d->info.width; ++i)
      d->values[offset + i] = (float)((d->sum[offset + i] + d->correction[offset + i]) / d->norm[layer]);
  }
  d->info.ready = 1;
  return success(e);
}
lie_status lie_steering_direction_snapshot(const lie_steering_direction *d,
  lie_steering_direction_info *out, lie_error *e) {
  if (!d || !out || out->abi_version != LIE_STEERING_DIRECTION_ABI ||
      out->struct_bytes != sizeof(*out))
    return refuse(e, LIE_INVALID, "invalid direction learning snapshot");
  *out = d->info;
  return success(e);
}
const float *lie_steering_direction_values(const lie_steering_direction *d) {
  return d && d->info.ready ? d->values : NULL;
}
void lie_steering_direction_destroy(lie_steering_direction **out) {
  if (!out || !*out) return;
  free(*out);
  *out = NULL;
}
lie_status lie_steering_direction_mean_branches(uint32_t width, uint32_t branches,
  const float *input, size_t input_values, float *output, size_t output_values,
  lie_error *e) {
  uintptr_t input_end, output_end;
  if (!width || !branches || (uint64_t)width * branches != input_values ||
      output_values != width || !span(input, input_values, &input_end) ||
      !span(output, output_values, &output_end) ||
      ((uintptr_t)input < output_end && (uintptr_t)output < input_end))
    return refuse(e, LIE_INVALID, "invalid or overlapping branch activation spans");
  for (size_t i = 0; i < input_values; ++i)
    if (!isfinite(input[i]))
      return refuse(e, LIE_INVALID, "nonfinite branch activation");
  for (uint32_t i = 0; i < width; ++i) {
    double sum = 0, correction = 0;
    for (uint32_t branch = 0; branch < branches; ++branch) {
      accumulate(input[(size_t)branch * width + i], &sum, &correction);
    }
    double mean = (sum + correction) / branches;
    /* A finite-input mean is a convex combination. Clip only possible FP64
     * rounding beyond its F32 endpoints before the final F32 conversion. */
    if (mean > FLT_MAX) mean = FLT_MAX;
    if (mean < -FLT_MAX) mean = -FLT_MAX;
    output[i] = (float)mean;
  }
  return success(e);
}
