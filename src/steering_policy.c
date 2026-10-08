/* SPDX-License-Identifier: MIT */
#include "lie/steering.h"
#include <float.h>
#include <errno.h>
#include <math.h>
#include <openssl/evp.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
_Static_assert(sizeof(float) == 4 && FLT_RADIX == 2 && FLT_MANT_DIG == 24 &&
               FLT_MAX_EXP == 128, "Steering metadata requires IEEE754 binary32");

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
  bool advance, changed, restore;
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
lie_status lie_steering_forward_prepare(lie_steering_policy *p,
  uint64_t actual, uint64_t maximum, lie_steering_update **u, lie_error *e) {
  if (!p || !u || *u)
    return fail(e, LIE_INVALID, "invalid steering forward output");
  if (!pthread_equal(p->owner, pthread_self()))
    return fail(e, LIE_WRONG_OWNER, "steering device owner violation");
  if (actual != p->state.frontier)
    return fail(e, LIE_BACKEND_FAILED, "model and steering frontiers diverged");
  if (maximum < actual || maximum > p->state.limit)
    return fail(e, LIE_INVALID, "invalid steering forward reservation");
  if (maximum == actual) return ok(e);
  return prepare(p, NULL, maximum, true, u, e);
}
lie_status lie_steering_forward_complete(lie_steering_policy *p,
  lie_steering_update **u, uint64_t actual, lie_error *e) {
  if (!p || !u)
    return fail(e, LIE_INVALID, "invalid steering forward completion");
  if (!pthread_equal(p->owner, pthread_self()))
    return fail(e, LIE_WRONG_OWNER, "steering device owner violation");
  if (*u) {
    if ((*u)->policy != p || !(*u)->advance || (*u)->restore)
      return fail(e, LIE_INVALID, "foreign or non-forward steering plan");
    return lie_steering_update_commit(u, actual, e);
  }
  return actual == p->state.frontier ? ok(e) :
    fail(e, LIE_BACKEND_FAILED, "unreserved model steering advance");
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
  if (u->restore ? completed != u->next.frontier :
      (completed < u->base_frontier || completed > u->next.frontier ||
       (!u->advance && completed != u->base_frontier)))
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

/* Steering metadata v1. All offsets are protocol fields, independent of C
 * padding, destination capacity/revision and target model/platform. The digest
 * detects corruption; model/input/payload identity belongs to the state owner. */
static void le32(unsigned char *p, uint32_t v) {
  for (unsigned i = 0; i < 4; ++i) p[i] = (unsigned char)(v >> (8 * i));
}
static uint32_t read32(const unsigned char *p) {
  uint32_t v = 0;
  for (unsigned i = 0; i < 4; ++i) v |= (uint32_t)p[i] << (8 * i);
  return v;
}
static uint64_t read64(const unsigned char *p) {
  uint64_t v = 0;
  for (unsigned i = 0; i < 8; ++i) v |= (uint64_t)p[i] << (8 * i);
  return v;
}
static bool all_zero(const unsigned char *p, size_t bytes) {
  for (size_t i = 0; i < bytes; ++i) if (p[i]) return false;
  return true;
}
static bool metadata_hash(const unsigned char state[160], unsigned char out[32]) {
  static const char domain[] = "synapse-lie.steering-state.v1";
  unsigned char frame[sizeof(domain) + 160];
  memcpy(frame, domain, sizeof(domain));
  memcpy(frame + sizeof(domain), state, 160);
  return hash(frame, sizeof(frame), out);
}
static bool read_settings(const unsigned char *p, bool bank,
                           lie_steering_settings *out) {
  uint32_t ffn = read32(p), attention = read32(p + 4);
  /* The encoder canonicalizes zero; aliases must not produce other wire IDs. */
  if (ffn == UINT32_C(0x80000000) || attention == UINT32_C(0x80000000))
    return false;
  lie_steering_settings s;
  lie_steering_settings_init(&s, false);
  memcpy(&s.ffn, &ffn, 4);
  memcpy(&s.attention, &attention, 4);
  return settings_valid(&s, bank, out);
}
lie_status lie_steering_policy_encode(const lie_steering_policy *source,
  unsigned char *out, size_t capacity, lie_error *e) {
  if (!source || !out)
    return fail(e, LIE_INVALID, "invalid steering state output");
  if (capacity < LIE_STEERING_STATE_BYTES)
    return fail(e, LIE_BUFFER_SMALL, "steering state output is too small");
  lie_steering_policy *p = (lie_steering_policy *)source;
  if (!pthread_equal(p->owner, pthread_self()))
    return fail(e, LIE_WRONG_OWNER, "steering device owner violation");
  if (atomic_load_explicit(&p->updates, memory_order_relaxed))
    return fail(e, LIE_RESOURCE_LIMIT, "unconfirmed steering update during capture");
  pthread_mutex_lock(&p->gate);
  policy_state s = p->state;
  pthread_mutex_unlock(&p->gate);
  unsigned char frame[LIE_STEERING_STATE_BYTES] = {0};
  memcpy(frame, "LIESTP1", 8);
  le32(frame + 8, 1);
  le32(frame + 12, LIE_STEERING_STATE_BYTES);
  le32(frame + 16, (p->bank ? 1u : 0u) | (s.work ? 2u : 0u) |
                         (s.history ? 4u : 0u));
  le64(frame + 24, s.frontier);
  le64(frame + 32, s.epochs);
  scale_bytes(frame + 40, s.settings);
  scale_bytes(frame + 48, s.work ? s.last : s.settings);
  memcpy(frame + 56, p->bank_info.scope_sha256, 32);
  memcpy(frame + 88, s.digest, 32);
  memcpy(frame + 120, s.scope, 32);
  if (!metadata_hash(frame, frame + 160))
    return fail(e, LIE_RESOURCE_LIMIT, "cannot checksum steering state");
  memcpy(out, frame, sizeof(frame));
  return ok(e);
}
lie_status lie_steering_policy_prepare_restore(lie_steering_policy *p,
  const unsigned char *state, size_t bytes, uint64_t completed,
  lie_steering_update **out, lie_error *e) {
  if (!p || !out || *out || (bytes ? !state : state != NULL))
    return fail(e, LIE_INVALID, "invalid steering restore output or span");
  if (!pthread_equal(p->owner, pthread_self()))
    return fail(e, LIE_WRONG_OWNER, "steering device owner violation");
  pthread_mutex_lock(&p->gate);
  policy_state current = p->state;
  pthread_mutex_unlock(&p->gate);
  if (current.frontier || current.work || current.history ||
      completed > current.limit ||
      atomic_load_explicit(&p->updates, memory_order_relaxed))
    return fail(e, LIE_INVALID, "steering restore requires an idle pristine destination");
  policy_state next = current;
  if (bytes) {
    unsigned char want[32];
    if (bytes != LIE_STEERING_STATE_BYTES || memcmp(state, "LIESTP1", 8) ||
        read32(state + 8) != 1 || read32(state + 12) != LIE_STEERING_STATE_BYTES ||
        read32(state + 16) > 7 || !all_zero(state + 20, 4) ||
        !all_zero(state + 152, 8) ||
        !metadata_hash(state, want) || memcmp(want, state + 160, 32))
      return fail(e, LIE_INVALID, "invalid steering state framing or checksum");
    const uint32_t flags = read32(state + 16);
    const bool bank = (flags & 1u) != 0;
    next.work = (flags & 2u) != 0;
    next.history = (flags & 4u) != 0;
    next.frontier = read64(state + 24);
    next.epochs = read64(state + 32);
    if (bank != (p->bank != NULL) ||
        memcmp(state + 56, p->bank_info.scope_sha256, 32) ||
        !read_settings(state + 40, bank, &next.settings) ||
        !read_settings(state + 48, bank, &next.last) ||
        next.frontier != completed || next.work != (completed != 0) ||
        next.history != (next.epochs != 0) || next.epochs > completed ||
        (next.history && (!bank || !next.work || all_zero(state + 88, 32))) ||
        (!next.history && !all_zero(state + 88, 32)) ||
        (!next.work && !same(next.last, next.settings)) ||
        (next.work && !next.history && active(next.last)) ||
        (next.epochs == 1 && !active(next.last)))
      return fail(e, LIE_INVALID, "incompatible steering bank, history or frontier");
    memcpy(next.digest, state + 88, 32);
    if (!scope(p, &next))
      return fail(e, LIE_RESOURCE_LIMIT, "cannot prepare restored steering scope");
    if (memcmp(next.scope, state + 120, 32))
      return fail(e, LIE_INVALID, "steering state scope differs from its policy");
  } else {
    if (active(current.settings))
      return fail(e, LIE_INVALID, "unsteered legacy state requires zero steering scales");
    next.frontier = completed;
    next.work = completed != 0;
    next.last = next.settings;
  }
  if (current.revision == UINT64_MAX)
    return fail(e, LIE_RESOURCE_LIMIT, "steering revision exhausted");
  lie_steering_update *u = calloc(1, sizeof(*u));
  if (!u)
    return fail(e, LIE_RESOURCE_LIMIT, "cannot allocate steering restore update");
  lie_status rc = lie_steering_policy_retain(p);
  if (rc != LIE_OK) {
    free(u);
    return fail(e, rc, "cannot pin steering restore policy");
  }
  u->policy = p;
  u->base_revision = current.revision;
  u->base_frontier = current.frontier;
  u->next = next;
  u->restore = u->changed = true;
  atomic_fetch_add_explicit(&p->updates, 1, memory_order_relaxed);
  *out = u;
  return ok(e);
}
static lie_status compose_scope(const unsigned char steering[32],
                                 const unsigned char semantic[32],
                                 unsigned char out[32], lie_error *e) {
  if (!semantic || !out)
    return fail(e, LIE_INVALID, "invalid steering cache scope destination");
  unsigned char zero[32] = {0};
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
lie_status lie_steering_policy_cache_scope(const lie_steering_policy *source,
  const unsigned char semantic[32], unsigned char out[32], lie_error *e) {
  if (!source)
    return fail(e, LIE_INVALID, "invalid steering cache policy");
  lie_steering_policy *p = (lie_steering_policy *)source;
  unsigned char steering[32];
  pthread_mutex_lock(&p->gate);
  memcpy(steering, p->state.scope, 32);
  pthread_mutex_unlock(&p->gate);
  return compose_scope(steering, semantic, out, e);
}
lie_status lie_steering_update_cache_scope(const lie_steering_update *u,
  const unsigned char semantic[32], unsigned char out[32], lie_error *e) {
  if (!u)
    return fail(e, LIE_INVALID, "invalid steering update scope");
  if (!pthread_equal(u->policy->owner, pthread_self()))
    return fail(e, LIE_WRONG_OWNER, "steering device owner violation");
  return compose_scope(u->next.scope, semantic, out, e);
}
void lie_steering_model_options_init(lie_steering_model_options *o) {
  if (!o) return;
  *o = (lie_steering_model_options){.abi_version = LIE_STEERING_MODEL_ABI,
    .struct_bytes = sizeof(*o), .vector_budget_bytes = LIE_STEERING_DEFAULT_VECTOR_BUDGET};
  lie_steering_settings_init(&o->defaults, true);
}
int lie_steering_model_option(lie_steering_model_options *o,const char *key,const char *value){
  if(!key)return 0;
  bool file=!strcmp(key,"--dir-steering-file"),ffn=!strcmp(key,"--dir-steering-ffn");
  if(!file&&!ffn&&strcmp(key,"--dir-steering-attn"))return 0;
  if(!LIE_DIRECTIONAL_STEERING||!o||o->abi_version!=LIE_STEERING_MODEL_ABI||o->struct_bytes!=sizeof(*o)||
     o->defaults.abi_version!=LIE_STEERING_POLICY_ABI||o->defaults.struct_bytes!=sizeof(o->defaults)||!value||!*value)return -1;
  if(file){o->file=value;return 1;}
  if(strspn(value,"-+0123456789.eE")!=strlen(value))return -1;
  char *end;errno=0;float scale=strtof(value,&end);
  if(errno||end==value||*end||!isfinite(scale)||fabsf(scale)>100)return -1;
  if(scale==0)scale=0;
  if(ffn)o->defaults.ffn=scale;else o->defaults.attention=scale;
  return 1;
}
lie_status lie_steering_model_bank_load(const lie_steering_model_options *o,
  uint32_t layers, uint32_t width, lie_steering_bank **out, lie_error *e) {
  lie_steering_settings canonical;
  if (!o || o->abi_version != LIE_STEERING_MODEL_ABI ||
      o->struct_bytes != sizeof(*o) || !o->file || !*o->file ||
      !o->vector_budget_bytes || !settings_valid(&o->defaults, true, &canonical))
    return fail(e, LIE_INVALID, "invalid steering model admission");
  lie_steering_geometry g = {LIE_STEERING_ABI, sizeof(g), layers, width,
                             o->vector_budget_bytes};
  return lie_steering_bank_load(o->file, &g, out, e);
}
