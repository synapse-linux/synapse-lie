/* SPDX-License-Identifier: MIT */
/* HOST-only format oracle. Never links HIP or constructs an inference model. */
#include "attention.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>
int lie_attention_fixture_gpu(const lie_attention_fixture_plan *p, float *deep,
                              float *short_out, lie_attention_fixture_result *r) {
  *r = (lie_attention_fixture_result){.accepted = true, .short_accepted = true};
  strcpy(r->device_arch, "SYNTHETIC-HOST-NO-DEVICE");
  const size_t values = (size_t)p->spec.rows * LIE_ATTENTION_FIXTURE_WIDTH;
  for (size_t i = 0; i < values; ++i) short_out[i] = (float)(i % 17) / 16;
  if (p->spec.zero_query) {
    for (uint32_t row = 0; row < p->spec.rows; ++row) {
      float sum = 0; uint32_t count = 0, query = p->deep_start + row;
      for (uint32_t rank = 0; rank < p->block_count; ++rank) {
        uint32_t block = p->blocks[rank];
        if (block < (query + 1) / 4 && !(p->deep_mask[(size_t)row * p->deep_pitch + block / 32] &
            (UINT32_C(1) << (block % 32)))) continue;
        for (uint32_t tail = 0; tail < 4; ++tail) if (block * 4 + tail <= query) {
          sum += (float)((int)((rank * 4 + tail) % 31) - 15) / 16; ++count;
        }
      }
      for (uint32_t head = 0; head < 24; ++head)
        for (uint32_t dim = 0; dim < 256; ++dim) {
          float total = sum + (float)count * (float)((head / 12) * 3 + dim % 11) / 32;
          short_out[(size_t)row * LIE_ATTENTION_FIXTURE_WIDTH + head * 256 + dim] =
              count ? (total / (float)count) * .5f : 0;
        }
    }
  }
  if (!LIE_LONG_CONTEXT_WMMA && p->deep_pitch > 2048) {
    r->accepted = false; r->expected_refusal = true; r->output_unchanged = true; r->refusal = 2;
  } else memcpy(deep, short_out, values * sizeof(*deep));
  const char *fault = getenv("LIE_ATTENTION_FIXTURE_FAULT");
  if (fault && !strcmp(fault, "uniform") && p->spec.zero_query) {
    deep[0] = short_out[0] = 10; return 0;
  }
  if (!fault || p->spec.end != 16384) return 0;
  if (!strcmp(fault, "mismatch")) deep[0] += 1;
  else if (!strcmp(fault, "nan")) deep[0] = short_out[0] = NAN;
  else if (!strcmp(fault, "primary")) r->primary_error = 7;
  else if (!strcmp(fault, "cleanup")) r->cleanup_error = 8;
  else if (!strcmp(fault, "gpu")) r->gpu_execution = true;
  else if (!strcmp(fault, "refusal")) { r->accepted = false; r->expected_refusal = true; r->refusal = 2; }
  else if (!strcmp(fault, "short")) r->short_accepted = false;
  return r->primary_error || r->cleanup_error ? 1 : 0;
}
