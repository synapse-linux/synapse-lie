/* SPDX-License-Identifier: MIT */
#include "lie/steering_state.h"
#include <stdio.h>
#include <string.h>

static const unsigned char auxiliary[8] = {'L','I','E','D','I','R','1',0};
static lie_status fail(lie_error *e, lie_status rc, const char *text) {
  if (e) snprintf(e->message, sizeof(e->message), "%s", text);
  return rc;
}
static lie_status ok(lie_error *e) { if (e) e->message[0] = 0; return LIE_OK; }
static unsigned part(const lie_state_layout *l, uint32_t role) {
  for (unsigned i = 0; i < l->section_count; ++i)
    if (l->sections[i].role == role) return i;
  return l->section_count;
}
lie_status lie_steering_state_extend(const lie_state_layout *model,
                                    lie_state_layout *out, lie_error *e) {
  uint64_t bytes;
  if (!out || !lie_state_validate(model, &bytes) ||
      part(model, LIE_STATE_STEERING_POLICY) != model->section_count)
    return fail(e, LIE_INVALID, "invalid steering model layout");
  lie_state_layout l = *model;
  const bool scope = part(model, LIE_STATE_CACHE_SCOPE) != model->section_count;
  if (l.format == LIE_STATE_KVC) {
    l.format = LIE_STATE_KVC_AUX;
    const uint64_t n = sizeof(auxiliary);
    if (!lie_state_add(&l, LIE_STATE_AUXILIARY, 0, LIE_STATE_U8, 1, &n))
      return fail(e, LIE_RESOURCE_LIMIT, "steering auxiliary layout limit");
  }
  uint64_t n = LIE_STEERING_STATE_BYTES;
  if (!lie_state_add(&l, LIE_STATE_STEERING_POLICY, 0, LIE_STATE_U8, 1, &n))
    return fail(e, LIE_RESOURCE_LIMIT, "steering policy layout limit");
  n = 32;
  if (!scope && !lie_state_add(&l, LIE_STATE_CACHE_SCOPE, 0, LIE_STATE_U8, 1, &n))
    return fail(e, LIE_RESOURCE_LIMIT, "steering scope layout limit");
  if (!lie_state_validate(&l, &bytes))
    return fail(e, LIE_INVALID, "invalid extended steering layout");
  *out = l;
  return ok(e);
}
lie_status lie_steering_state_inspect(const lie_state_layout *outer, uint32_t format,
                                     lie_steering_state_view *out, lie_error *e) {
  uint64_t bytes;
  if (!out || out->abi_version != LIE_STEERING_STATE_BINDING_ABI ||
      out->struct_bytes != sizeof(*out) || format > LIE_STATE_KVC_AUX ||
      !lie_state_validate(outer, &bytes))
    return fail(e, LIE_INVALID, "invalid steering state view");
  lie_steering_state_view v = {.abi_version = LIE_STEERING_STATE_BINDING_ABI,
    .struct_bytes = sizeof(v), .model = *outer, .payload_bytes = bytes,
    .policy_offset = LIE_STEERING_STATE_NO_OFFSET,
    .scope_offset = LIE_STEERING_STATE_NO_OFFSET,
    .inserted_auxiliary_offset = LIE_STEERING_STATE_NO_OFFSET};
  unsigned i = part(outer, LIE_STATE_STEERING_POLICY);
  unsigned scope = part(outer, LIE_STATE_CACHE_SCOPE);
  if (scope != outer->section_count) v.scope_offset = outer->sections[scope].offset;
  if (i != outer->section_count) {
    if (i + 1 != outer->section_count &&
        !(i + 2 == outer->section_count && scope == i + 1))
      return fail(e, LIE_INVALID, "noncanonical steering state tail");
    v.policy_offset = outer->sections[i].offset;
    v.model.section_count = i;
    if (format == LIE_STATE_KVC) {
      if (v.model.format != LIE_STATE_KVC_AUX || !v.model.section_count)
        return fail(e, LIE_INVALID, "missing steering auxiliary boundary");
      const lie_state_section *a = &v.model.sections[v.model.section_count - 1];
      if (a->role != LIE_STATE_AUXILIARY || a->bytes != sizeof(auxiliary))
        return fail(e, LIE_INVALID, "invalid steering auxiliary boundary");
      v.inserted_auxiliary_offset = a->offset;
      --v.model.section_count;
      v.model.format = LIE_STATE_KVC;
    }
    if (v.model.format != format || !lie_state_validate(&v.model, &v.model_bytes))
      return fail(e, LIE_INVALID, "invalid steering model prefix");
    lie_state_layout canonical;
    lie_status rc = lie_steering_state_extend(&v.model, &canonical, e);
    if (rc != LIE_OK) return rc;
    if (!lie_state_layout_equal(outer, &canonical))
      return fail(e, LIE_INVALID, "steering state framing mismatch");
  } else {
    if (outer->format != format)
      return fail(e, LIE_INVALID, "foreign model state format");
    v.model_bytes = bytes;
  }
  /* Removed descriptor slots are not part of the public model view. */
  memset(v.model.sections + v.model.section_count, 0,
         (LIE_STATE_MAX_SECTIONS - v.model.section_count) * sizeof(v.model.sections[0]));
  *out = v;
  return ok(e);
}
lie_status lie_steering_state_plan(lie_steering_policy *p, const lie_state_layout *model,
                                  lie_state_layout *out, lie_error *e) {
  uint64_t bytes;
  if (!p || !out || !lie_state_validate(model, &bytes) ||
      part(model, LIE_STATE_STEERING_POLICY) != model->section_count)
    return fail(e, LIE_INVALID, "invalid steering capture plan");
  lie_steering_update *noop = NULL;
  lie_status rc = lie_steering_forward_prepare(p, model->token_count, model->token_count, &noop, e);
  if (rc != LIE_OK) return rc;
  lie_steering_policy_info info = {.abi_version = LIE_STEERING_POLICY_ABI,
                                  .struct_bytes = sizeof(info)};
  rc = lie_steering_policy_snapshot(p, &info, e);
  if (rc != LIE_OK) return rc;
  if (info.outstanding_updates)
    return fail(e, LIE_RESOURCE_LIMIT, "steering capture has outstanding plans");
  if (info.has_steered_history || info.settings.ffn != 0 || info.settings.attention != 0)
    return lie_steering_state_extend(model, out, e);
  *out = *model;
  return ok(e);
}
lie_status lie_steering_state_capture(lie_steering_policy *p, const lie_state_layout *outer,
  uint32_t format, const unsigned char semantic[32], void *raw, size_t bytes, lie_error *e) {
  if (!p || !semantic || !raw)
    return fail(e, LIE_INVALID, "invalid steering capture payload");
  lie_steering_state_view v = {.abi_version = LIE_STEERING_STATE_BINDING_ABI,
                              .struct_bytes = sizeof(v)};
  lie_status rc = lie_steering_state_inspect(outer, format, &v, e);
  if (rc != LIE_OK) return rc;
  if (bytes != v.payload_bytes)
    return fail(e, LIE_INVALID, "steering capture payload size mismatch");
  lie_state_layout expected;
  rc = lie_steering_state_plan(p, &v.model, &expected, e);
  if (rc != LIE_OK) return rc;
  if (!lie_state_layout_equal(outer, &expected))
    return fail(e, LIE_INVALID, "steering capture history changed");
  unsigned char frame[LIE_STEERING_STATE_BYTES], scope[32];
  if (v.policy_offset != LIE_STEERING_STATE_NO_OFFSET) {
    rc = lie_steering_policy_encode(p, frame, sizeof(frame), e);
    if (rc != LIE_OK) return rc;
  }
  rc = lie_steering_policy_cache_scope(p, semantic, scope, e);
  if (rc != LIE_OK) return rc;
  if (v.scope_offset == LIE_STEERING_STATE_NO_OFFSET && memcmp(scope, (unsigned char[32]){0}, 32))
    return fail(e, LIE_INVALID, "missing steering capture scope");
  unsigned char *payload = raw;
  if (v.inserted_auxiliary_offset != LIE_STEERING_STATE_NO_OFFSET)
    memcpy(payload + v.inserted_auxiliary_offset, auxiliary, sizeof(auxiliary));
  if (v.policy_offset != LIE_STEERING_STATE_NO_OFFSET)
    memcpy(payload + v.policy_offset, frame, sizeof(frame));
  if (v.scope_offset != LIE_STEERING_STATE_NO_OFFSET)
    memcpy(payload + v.scope_offset, scope, sizeof(scope));
  return ok(e);
}
lie_status lie_steering_state_prepare_restore(lie_steering_policy *p, const lie_state_layout *outer,
  uint32_t format, const unsigned char semantic[32], const void *raw, size_t bytes,
  lie_steering_update **out, unsigned char combined[32], lie_error *e) {
  if (!p || !semantic || !raw || !out || *out || !combined)
    return fail(e, LIE_INVALID, "invalid steering prefix restore");
  lie_steering_state_view v = {.abi_version = LIE_STEERING_STATE_BINDING_ABI,
                              .struct_bytes = sizeof(v)};
  lie_status rc = lie_steering_state_inspect(outer, format, &v, e);
  if (rc != LIE_OK) return rc;
  if (bytes != v.payload_bytes)
    return fail(e, LIE_INVALID, "steering restore payload size mismatch");
  const unsigned char *payload = raw;
  if (v.inserted_auxiliary_offset != LIE_STEERING_STATE_NO_OFFSET &&
      memcmp(payload + v.inserted_auxiliary_offset, auxiliary, sizeof(auxiliary)))
    return fail(e, LIE_INVALID, "invalid steering auxiliary marker");
  lie_steering_policy_info current = {.abi_version = LIE_STEERING_POLICY_ABI,
                                    .struct_bytes = sizeof(current)};
  rc = lie_steering_policy_snapshot(p, &current, e);
  if (rc != LIE_OK) return rc;
  unsigned char expected[32], staged[32];
  rc = lie_steering_policy_cache_scope(p, semantic, expected, e);
  if (rc != LIE_OK) return rc;
  lie_steering_update *u = NULL;
  const bool extended = v.policy_offset != LIE_STEERING_STATE_NO_OFFSET;
  rc = lie_steering_policy_prepare_restore(p, extended ? payload + v.policy_offset : NULL,
      extended ? LIE_STEERING_STATE_BYTES : 0, outer->token_count, &u, e);
  if (rc != LIE_OK) return rc;
  const lie_steering_settings *settings = lie_steering_update_settings(u);
  rc = lie_steering_update_cache_scope(u, semantic, staged, e);
  if (rc == LIE_OK && (settings->ffn != current.settings.ffn ||
      settings->attention != current.settings.attention || memcmp(staged, expected, 32) ||
      (v.scope_offset == LIE_STEERING_STATE_NO_OFFSET ?
        memcmp(staged, (unsigned char[32]){0}, 32) : memcmp(staged, payload + v.scope_offset, 32))))
    rc = fail(e, LIE_INVALID, "steering prefix settings/history/scope mismatch");
  if (rc != LIE_OK) { lie_steering_update_discard(&u); return rc; }
  *out = u;
  memcpy(combined, staged, sizeof(staged));
  return ok(e);
}
