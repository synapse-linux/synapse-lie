/* SPDX-License-Identifier: MIT */
#include "lie/steering.h"
#include <math.h>
#include <openssl/evp.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
  uint64_t limit, frontier, revision, epochs;
  bool work, history;
  lie_steering_settings settings, last;
  unsigned char digest[32], scope[32];
} policy_state;
struct lie_steering_policy {
  atomic_size_t references;
  atomic_uint updates;
  pthread_t owner;
  pthread_mutex_t gate;
  lie_steering_bank *bank;
  lie_steering_info bank_info;
  policy_state state;
};
struct lie_steering_update {
  lie_steering_policy *policy;
  uint64_t base_revision, base_frontier;
  bool advance, changed;
  policy_state next;
};
static lie_status fail(lie_error *e, lie_status rc, const char *message) {
  if (e)
    snprintf(e->message, sizeof(e->message), "%s", message);
  return rc;
}
static lie_status ok(lie_error *e) {
  if (e)
    e->message[0] = 0;
  return LIE_OK;
}
static bool active(lie_steering_settings s) {
  return s.ffn != 0 || s.attention != 0;
}
static bool same(lie_steering_settings a, lie_steering_settings b) {
  return a.ffn == b.ffn && a.attention == b.attention;
}
void lie_steering_settings_init(lie_steering_settings *s, bool bank) {
  if (s)
    *s = (lie_steering_settings){LIE_STEERING_POLICY_ABI, sizeof(*s),
                                 bank ? 1 : 0, 0};
}
static bool settings_valid(const lie_steering_settings *in, bool bank,
                           lie_steering_settings *out) {
  if (!in || in->abi_version != LIE_STEERING_POLICY_ABI ||
      in->struct_bytes != sizeof(*in) || !isfinite(in->ffn) ||
      !isfinite(in->attention) || fabsf(in->ffn) > 100 ||
      fabsf(in->attention) > 100 || (!bank && active(*in)))
    return false;
  *out = *in;
  if (out->ffn == 0)
    out->ffn = 0; /* Canonicalize negative zero in policy, not file data. */
  if (out->attention == 0)
    out->attention = 0;
  return true;
}
static void le64(unsigned char *p, uint64_t v) {
  for (unsigned i = 0; i < 8; ++i)
    p[i] = (unsigned char)(v >> (8 * i));
}
static void scale_bytes(unsigned char p[8], lie_steering_settings s) {
  uint32_t bits[2];
  memcpy(&bits[0], &s.ffn, 4);
  memcpy(&bits[1], &s.attention, 4);
  for (unsigned j = 0; j < 2; ++j)
    for (unsigned i = 0; i < 4; ++i)
      p[j * 4 + i] = (unsigned char)(bits[j] >> (8 * i));
}
static bool hash(const unsigned char *p, size_t bytes, unsigned char out[32]) {
  unsigned size = 0;
  return EVP_Digest(p, bytes, out, &size, EVP_sha256(), NULL) == 1 &&
         size == 32;
}
static bool node(const lie_steering_policy *p, const unsigned char previous[32],
                 uint64_t position, lie_steering_settings settings,
                 unsigned char out[32]) {
  static const char domain[] = "synapse-lie.steering-history.v1";
  unsigned char frame[sizeof(domain) + 32 + 32 + 8 + 8];
  size_t at = 0;
  memcpy(frame, domain, sizeof(domain));
  at += sizeof(domain);
  memcpy(frame + at, previous, 32);
  at += 32;
  memcpy(frame + at, p->bank_info.scope_sha256, 32);
  at += 32;
  le64(frame + at, position);
  at += 8;
  scale_bytes(frame + at, settings);
  return hash(frame, sizeof(frame), out);
}
static bool scope(const lie_steering_policy *p, policy_state *s) {
  memset(s->scope, 0, 32);
  if (!s->history && !active(s->settings))
    return true;
  unsigned char history[32];
  memcpy(history, s->digest, 32);
  /* Before the first forward, predict the uniform initial policy so its
   * prefix lookup identity agrees with capture after completed prefill. */
  if (!s->work && active(s->settings) &&
      !node(p, history, 0, s->settings, history))
    return false;
  static const char domain[] = "synapse-lie.steering-cache.v1";
  unsigned char frame[sizeof(domain) + 32 + 32 + 8];
  size_t at = 0;
  memcpy(frame, domain, sizeof(domain));
  at += sizeof(domain);
  memcpy(frame + at, p->bank_info.scope_sha256, 32);
  at += 32;
  memcpy(frame + at, history, 32);
  at += 32;
  scale_bytes(frame + at, s->settings);
  return hash(frame, sizeof(frame), s->scope);
}
lie_status lie_steering_policy_create(const lie_steering_policy_options *o,
                                      lie_steering_policy **out, lie_error *e) {
  lie_steering_settings settings;
  if (!o || !out || *out || o->abi_version != LIE_STEERING_POLICY_ABI ||
      o->struct_bytes != sizeof(*o) || !o->max_positions ||
      !settings_valid(&o->settings, o->bank != NULL, &settings))
    return fail(e, LIE_INVALID, "invalid steering policy admission");
  lie_steering_policy *p = calloc(1, sizeof(*p));
  if (!p)
    return fail(e, LIE_RESOURCE_LIMIT, "cannot allocate steering policy");
  if (pthread_mutex_init(&p->gate, NULL)) {
    free(p);
    return fail(e, LIE_RESOURCE_LIMIT, "cannot allocate steering policy gate");
  }
  p->bank_info = (lie_steering_info){.abi_version = LIE_STEERING_ABI,
                                     .struct_bytes = sizeof(lie_steering_info)};
  lie_status rc = LIE_OK;
  if (o->bank) {
    rc = lie_steering_bank_info(o->bank, &p->bank_info, e);
    if (rc == LIE_OK)
      rc = lie_steering_bank_retain(o->bank);
    if (rc == LIE_OK)
      p->bank = o->bank;
  }
  p->state = (policy_state){
      .limit = o->max_positions, .settings = settings, .last = settings};
  if (rc == LIE_OK && !scope(p, &p->state))
    rc = LIE_RESOURCE_LIMIT;
  if (rc != LIE_OK) {
    lie_steering_bank_release(&p->bank);
    pthread_mutex_destroy(&p->gate);
    free(p);
    return fail(e, rc, "cannot prepare steering policy identity");
  }
  p->owner = pthread_self();
  atomic_init(&p->references, 1);
  atomic_init(&p->updates, 0);
  *out = p;
  return ok(e);
}
lie_status lie_steering_policy_retain(lie_steering_policy *p) {
  if (!p)
    return LIE_INVALID;
  size_t count = atomic_load_explicit(&p->references, memory_order_relaxed);
  while (count && count < SIZE_MAX) {
    if (atomic_compare_exchange_weak_explicit(&p->references, &count, count + 1,
                                              memory_order_relaxed,
                                              memory_order_relaxed))
      return LIE_OK;
  }
  return count ? LIE_RESOURCE_LIMIT : LIE_INVALID;
}
void lie_steering_policy_release(lie_steering_policy **handle) {
  if (!handle || !*handle)
    return;
  lie_steering_policy *p = *handle;
  *handle = NULL;
  if (atomic_fetch_sub_explicit(&p->references, 1, memory_order_acq_rel) == 1) {
    lie_steering_bank_release(&p->bank);
    pthread_mutex_destroy(&p->gate);
    free(p);
  }
}
lie_status lie_steering_policy_snapshot(const lie_steering_policy *source,
                                        lie_steering_policy_info *out,
                                        lie_error *e) {
  if (!source || !out || out->abi_version != LIE_STEERING_POLICY_ABI ||
      out->struct_bytes != sizeof(*out))
    return fail(e, LIE_INVALID, "invalid steering policy snapshot");
  lie_steering_policy *p = (lie_steering_policy *)source;
  pthread_mutex_lock(&p->gate);
  policy_state s = p->state;
  *out = (lie_steering_policy_info){.abi_version = LIE_STEERING_POLICY_ABI,
                                    .struct_bytes = sizeof(*out),
                                    .max_positions = s.limit,
                                    .completed_positions = s.frontier,
                                    .revision = s.revision,
                                    .history_epochs = s.epochs,
                                    .bank_present = p->bank != NULL,
                                    .has_completed_work = s.work,
                                    .has_steered_history = s.history,
                                    .settings = s.settings,
                                    .last_completed_settings = s.last,
                                    .bank = p->bank_info};
  memcpy(out->history_sha256, s.digest, 32);
  memcpy(out->cache_scope_sha256, s.scope, 32);
  out->outstanding_updates =
      atomic_load_explicit(&p->updates, memory_order_relaxed);
  out->policy_bytes = sizeof(*p);
  out->staged_bytes =
      (uint64_t)out->outstanding_updates * sizeof(lie_steering_update);
  pthread_mutex_unlock(&p->gate);
  return ok(e);
}
static lie_status prepare(lie_steering_policy *p,
                          const lie_steering_settings *settings,
                          uint64_t maximum, bool advance,
                          lie_steering_update **out, lie_error *e) {
  if (!p || !out || *out)
    return fail(e, LIE_INVALID, "invalid steering update output");
  if (!pthread_equal(p->owner, pthread_self()))
    return fail(e, LIE_WRONG_OWNER, "steering device owner violation");
  lie_steering_settings next_settings;
  if (!advance && !settings_valid(settings, p->bank != NULL, &next_settings))
    return fail(e, LIE_INVALID, "invalid steering scales");
  pthread_mutex_lock(&p->gate);
  policy_state current = p->state;
  pthread_mutex_unlock(&p->gate);
  if (advance && (maximum <= current.frontier || maximum > current.limit))
    return fail(e, LIE_INVALID, "invalid steering target reservation");
  if (current.revision == UINT64_MAX)
    return fail(e, LIE_RESOURCE_LIMIT, "steering revision exhausted");
  if (atomic_load_explicit(&p->updates, memory_order_relaxed) >=
      LIE_STEERING_MAX_UPDATES)
    return fail(e, LIE_RESOURCE_LIMIT, "steering update capacity exhausted");
  lie_steering_update *u = calloc(1, sizeof(*u));
  if (!u)
    return fail(e, LIE_RESOURCE_LIMIT, "cannot allocate steering update");
  u->next = current;
  u->base_revision = current.revision;
  u->base_frontier = current.frontier;
  u->advance = advance;
  bool valid = true;
  if (advance) {
    if ((!current.work || !same(current.last, current.settings)) &&
        (current.history || active(current.settings))) {
      valid = node(p, current.digest, current.frontier, current.settings,
                   u->next.digest);
      u->next.history = true;
      ++u->next.epochs;
    }
    u->next.work = true;
    u->next.last = current.settings;
    u->next.frontier = maximum;
    u->changed = true;
  } else {
    u->next.settings = next_settings;
    u->changed = !same(current.settings, next_settings);
  }
  if (valid && u->changed)
    valid = scope(p, &u->next);
  lie_status rc = valid ? lie_steering_policy_retain(p) : LIE_RESOURCE_LIMIT;
  if (rc != LIE_OK) {
    free(u);
    return fail(e, rc, "cannot prepare steering update identity");
  }
  u->policy = p;
  atomic_fetch_add_explicit(&p->updates, 1, memory_order_relaxed);
  *out = u;
  return ok(e);
}
lie_status lie_steering_policy_prepare_change(lie_steering_policy *p,
                                              const lie_steering_settings *s,
                                              lie_steering_update **u,
                                              lie_error *e) {
  return prepare(p, s, 0, false, u, e);
}
lie_status lie_steering_policy_prepare_advance(lie_steering_policy *p,
                                               uint64_t maximum,
                                               lie_steering_update **u,
                                               lie_error *e) {
  return prepare(p, NULL, maximum, true, u, e);
}
const lie_steering_settings *
lie_steering_update_settings(const lie_steering_update *u) {
  return u ? &u->next.settings : NULL;
}
void lie_steering_update_discard(lie_steering_update **handle) {
  if (!handle || !*handle)
    return;
  lie_steering_update *u = *handle;
  *handle = NULL;
  if (!atomic_fetch_sub_explicit(&u->policy->updates, 1, memory_order_acq_rel))
    abort();
  lie_steering_policy_release(&u->policy);
  free(u);
}
lie_status lie_steering_update_commit(lie_steering_update **handle,
                                      uint64_t completed, lie_error *e) {
  if (!handle || !*handle)
    return fail(e, LIE_INVALID, "invalid steering commit handle");
  lie_steering_update *u = *handle;
  lie_steering_policy *p = u->policy;
  if (!pthread_equal(p->owner, pthread_self()))
    return fail(e, LIE_WRONG_OWNER, "steering device owner violation");
  if (completed < u->base_frontier || completed > u->next.frontier ||
      (!u->advance && completed != u->base_frontier))
    return fail(e, LIE_INVALID, "unconfirmed steering target frontier");
  pthread_mutex_lock(&p->gate);
  if (p->state.revision != u->base_revision ||
      p->state.frontier != u->base_frontier) {
    pthread_mutex_unlock(&p->gate);
    return fail(e, LIE_INVALID, "stale steering update");
  }
  if (u->changed && (!u->advance || completed > u->base_frontier)) {
    u->next.frontier = completed;
    u->next.revision = u->base_revision + 1;
    p->state = u->next;
  }
  pthread_mutex_unlock(&p->gate);
  lie_steering_update_discard(handle);
  return ok(e);
}
lie_status lie_steering_policy_cache_scope(const lie_steering_policy *source,
                                           const unsigned char semantic[32],
                                           unsigned char out[32],
                                           lie_error *e) {
  if (!source || !semantic || !out)
    return fail(e, LIE_INVALID, "invalid steering cache scope destination");
  lie_steering_policy *p = (lie_steering_policy *)source;
  unsigned char steering[32], zero[32] = {0};
  pthread_mutex_lock(&p->gate);
  memcpy(steering, p->state.scope, 32);
  pthread_mutex_unlock(&p->gate);
  if (!memcmp(steering, zero, 32)) {
    memmove(out, semantic, 32);
    return ok(e);
  }
  if (!memcmp(semantic, zero, 32)) {
    memcpy(out, steering, 32);
    return ok(e);
  }
  static const char domain[] = "synapse-lie.steering-semantic.v1";
  unsigned char frame[sizeof(domain) + 64], result[32];
  memcpy(frame, domain, sizeof(domain));
  memcpy(frame + sizeof(domain), steering, 32);
  memcpy(frame + sizeof(domain) + 32, semantic, 32);
  if (!hash(frame, sizeof(frame), result))
    return fail(e, LIE_RESOURCE_LIMIT,
                "cannot compose steering semantic scope");
  memcpy(out, result, 32);
  return ok(e);
}
