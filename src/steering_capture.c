/* SPDX-License-Identifier: MIT */
#include "lie/steering_capture.h"
#include "lie/steering_direction.h"
#include <math.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
struct lie_steering_capture {
  lie_steering_capture_options options;
  lie_steering_capture_info info;
  bool sealed;
  float *attention, *ffn;
  unsigned char *seen;
};
static lie_status fail(lie_error *e, lie_status s, const char *message) {
  if (e) snprintf(e->message, sizeof(e->message), "%s", message);
  return s;
}
static lie_status ok(lie_error *e) { if (e) e->message[0] = 0; return LIE_OK; }
lie_status lie_steering_capture_create(const lie_steering_capture_options *o,
  lie_steering_capture **out, lie_error *e) {
  const unsigned supported = LIE_ACTIVATION_ATTENTION | LIE_ACTIVATION_FFN;
  if (!o || !out || *out || o->abi_version != LIE_STEERING_CAPTURE_ABI ||
      o->struct_bytes != sizeof(*o) || o->geometry.abi_version != LIE_ACTIVATION_OBSERVER_ABI ||
      o->geometry.struct_bytes != sizeof(o->geometry) || !o->geometry.layers ||
      !o->geometry.width || !o->geometry.ffn_branches || !o->components ||
      (o->components & ~supported) || (o->components & ~o->geometry.components) ||
      (o->geometry.components & ~supported) || o->token_position == UINT64_MAX || !o->max_bytes)
    return fail(e, LIE_INVALID, "invalid activation capture options or handle");
  const uint64_t matrices = !!(o->components & LIE_ACTIVATION_ATTENTION) +
    !!(o->components & LIE_ACTIVATION_FFN);
  const uint64_t count = (uint64_t)o->geometry.layers * o->geometry.width;
  const size_t header = (sizeof(lie_steering_capture) + _Alignof(float) - 1) /
    _Alignof(float) * _Alignof(float);
  if (o->geometry.layers > SIZE_MAX - header ||
      count > (SIZE_MAX - header - o->geometry.layers) / (matrices * sizeof(float)))
    return fail(e, LIE_RESOURCE_LIMIT, "activation capture geometry overflow");
  const size_t bytes = header + o->geometry.layers + (size_t)count * matrices * sizeof(float);
  if (bytes > o->max_bytes)
    return fail(e, LIE_RESOURCE_LIMIT, "activation capture exceeds host budget");
  lie_steering_capture *c = calloc(1, bytes);
  if (!c) return fail(e, LIE_RESOURCE_LIMIT, "cannot allocate activation capture");
  c->options = *o;
  c->info = (lie_steering_capture_info){.abi_version=LIE_STEERING_CAPTURE_ABI,
    .struct_bytes=sizeof(c->info), .expected_rows=matrices * o->geometry.layers,
    .requested_bytes=bytes};
  float *next = (float *)((unsigned char *)c + header);
  if (o->components & LIE_ACTIVATION_ATTENTION) { c->attention = next; next += count; }
  if (o->components & LIE_ACTIVATION_FFN) { c->ffn = next; next += count; }
  c->seen = (unsigned char *)next;
  *out = c;
  return ok(e);
}
lie_status lie_steering_capture_add(lie_steering_capture *c,
  const lie_activation_observation *row, lie_error *e) {
  if (!c || !row || c->sealed || row->abi_version != LIE_ACTIVATION_OBSERVER_ABI ||
      row->struct_bytes != sizeof(*row) ||
      (row->component != LIE_ACTIVATION_ATTENTION && row->component != LIE_ACTIVATION_FFN) ||
      !(c->options.components & row->component) || row->layers != c->options.geometry.layers ||
      row->width != c->options.geometry.width || row->layer >= row->layers ||
      row->token_position != c->options.token_position ||
      row->branches != (row->component == LIE_ACTIVATION_FFN ? c->options.geometry.ffn_branches : 1u) ||
      (uint64_t)row->width * row->branches != row->value_count ||
      !row->values || (c->seen[row->layer] & row->component))
    return fail(e, LIE_INVALID, "invalid or duplicate activation capture row");
  float *matrix = row->component == LIE_ACTIVATION_ATTENTION ? c->attention : c->ffn;
  lie_status status = lie_steering_direction_mean_branches(row->width, row->branches,
    row->values, row->value_count, matrix + (size_t)row->layer * row->width, row->width, e);
  if (status != LIE_OK) return status;
  c->seen[row->layer] |= (unsigned char)row->component;
  ++c->info.rows;
  return ok(e);
}
lie_status lie_steering_capture_finish(lie_steering_capture *c, lie_status status,
  uint64_t tokens, lie_error *e) {
  if (!c || c->sealed) return fail(e, LIE_INVALID, "activation capture already sealed or invalid");
  c->sealed = true;
  if (status != LIE_OK || tokens != c->options.token_position + 1 ||
      c->info.rows != c->info.expected_rows)
    return fail(e, status == LIE_OK ? LIE_INVALID : status, "prefill or activation capture incomplete");
  c->info.ready = 1;
  return ok(e);
}
lie_status lie_steering_capture_snapshot(const lie_steering_capture *c,
  lie_steering_capture_info *out, lie_error *e) {
  if (!c || !out || out->abi_version != LIE_STEERING_CAPTURE_ABI || out->struct_bytes != sizeof(*out))
    return fail(e, LIE_INVALID, "invalid activation capture snapshot");
  *out = c->info; return ok(e);
}
const float *lie_steering_capture_values(const lie_steering_capture *c, lie_activation_component component) {
  if (!c || !c->info.ready) return NULL;
  return component == LIE_ACTIVATION_ATTENTION ? c->attention : component == LIE_ACTIVATION_FFN ? c->ffn : NULL;
}
void lie_steering_capture_destroy(lie_steering_capture **out) {
  if (!out || !*out) return;
  free(*out); *out = NULL;
}
