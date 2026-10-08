/* SPDX-License-Identifier: MIT */
/* Synthetic retained-frontier witnesses only. No model forward or GPU. */
#include "lie/steering.h"
#include <assert.h>
#include <math.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static lie_steering_policy_info info(lie_steering_policy *p) {
  lie_steering_policy_info i = {.abi_version = LIE_STEERING_POLICY_ABI,
                               .struct_bytes = sizeof(i)};
  assert(lie_steering_policy_snapshot(p, &i, NULL) == LIE_OK);
  return i;
}
static void unchanged(lie_steering_policy_info a, lie_steering_policy_info b) {
  assert(a.completed_positions == b.completed_positions && a.revision == b.revision &&
         a.history_epochs == b.history_epochs && a.settings.ffn == b.settings.ffn &&
         a.settings.attention == b.settings.attention &&
         !memcmp(a.history_sha256, b.history_sha256, 32) &&
         !memcmp(a.cache_scope_sha256, b.cache_scope_sha256, 32));
}
static void hex_is(const unsigned char bytes[32], const char *expected) {
  for (unsigned i = 0; i < 32; ++i) {
    char text[3];
    snprintf(text, sizeof(text), "%02x", bytes[i]);
    assert(!memcmp(text, expected + 2 * i, 2));
  }
}
static lie_steering_bank *admission(void) {
  char path[] = "steering-forward-bank-XXXXXX";
  int fd = mkstemp(path);
  assert(fd >= 0);
  unsigned char bytes[] = {0,0,128,63, 0,0,0,64, 0,0,64,64, 0,0,128,64};
  assert(write(fd, bytes, sizeof(bytes)) == (ssize_t)sizeof(bytes));
  assert(!close(fd));
  lie_steering_model_options o;
  lie_steering_model_options_init(&o);
  assert(o.abi_version == LIE_STEERING_MODEL_ABI && o.struct_bytes == sizeof(o) && !o.file &&
         o.vector_budget_bytes == LIE_STEERING_DEFAULT_VECTOR_BUDGET &&
         o.defaults.ffn == 1 && o.defaults.attention == 0);
  lie_steering_bank *b = NULL;
  assert(lie_steering_model_bank_load(&o, 2, 2, &b, NULL) == LIE_INVALID && !b);
  o.file = path;
  lie_steering_model_options invalid = o;
  invalid.abi_version = 0;
  assert(lie_steering_model_bank_load(&invalid, 2, 2, &b, NULL) == LIE_INVALID && !b);
  invalid = o; invalid.struct_bytes--;
  assert(lie_steering_model_bank_load(&invalid, 2, 2, &b, NULL) == LIE_INVALID && !b);
  invalid = o; invalid.defaults.abi_version = 0;
  assert(lie_steering_model_bank_load(&invalid, 2, 2, &b, NULL) == LIE_INVALID && !b);
  invalid = o; invalid.defaults.struct_bytes--;
  assert(lie_steering_model_bank_load(&invalid, 2, 2, &b, NULL) == LIE_INVALID && !b);
  invalid = o; invalid.file = "";
  assert(lie_steering_model_bank_load(&invalid, 2, 2, &b, NULL) == LIE_INVALID && !b);
  invalid = o; invalid.vector_budget_bytes = 0;
  assert(lie_steering_model_bank_load(&invalid, 2, 2, &b, NULL) == LIE_INVALID && !b);
  invalid.vector_budget_bytes = 15;
  assert(lie_steering_model_bank_load(&invalid, 2, 2, &b, NULL) == LIE_RESOURCE_LIMIT && !b);
  float bad[] = {NAN, INFINITY, -INFINITY, 100.1f, -100.1f};
  for (unsigned i = 0; i < sizeof(bad) / sizeof(*bad); ++i) {
    invalid = o; invalid.defaults.ffn = bad[i];
    assert(lie_steering_model_bank_load(&invalid, 2, 2, &b, NULL) == LIE_INVALID && !b);
    invalid = o; invalid.defaults.attention = bad[i];
    assert(lie_steering_model_bank_load(&invalid, 2, 2, &b, NULL) == LIE_INVALID && !b);
  }
  assert(lie_steering_model_bank_load(NULL, 2, 2, &b, NULL) == LIE_INVALID && !b);
  assert(lie_steering_model_bank_load(&o, 0, 2, &b, NULL) == LIE_INVALID && !b);
  assert(lie_steering_model_bank_load(&o, 3, 2, &b, NULL) == LIE_INVALID && !b);
  assert(lie_steering_model_bank_load(&o, 2, 2, NULL, NULL) == LIE_INVALID);
  o.vector_budget_bytes = 16;
  assert(lie_steering_model_bank_load(&o, 2, 2, &b, NULL) == LIE_OK && b);
  lie_steering_bank *saved = b;
  assert(lie_steering_model_bank_load(&o, 2, 2, &b, NULL) == LIE_INVALID && b == saved);
  lie_steering_bank *other = NULL;
  assert(lie_steering_model_bank_load(&o, 1, 4, &other, NULL) == LIE_OK);
  lie_steering_info a = {.abi_version=LIE_STEERING_ABI,.struct_bytes=sizeof(a)}, c = a;
  assert(lie_steering_bank_info(b, &a, NULL) == LIE_OK &&
         lie_steering_bank_info(other, &c, NULL) == LIE_OK && a.bytes == 16 && c.bytes == 16);
  assert(!memcmp(a.file_sha256, c.file_sha256, 32) && memcmp(a.scope_sha256, c.scope_sha256, 32));
  lie_steering_bank_release(&other);
  assert(!unlink(path)); /* Owned immutable bank no longer depends on pathname. */
  return b;
}
typedef struct {lie_steering_policy *policy; lie_steering_update *plan;} other_args;
static void *wrong_owner(void *opaque) {
  other_args *a = opaque;
  lie_steering_update *u = NULL;
  assert(lie_steering_forward_prepare(a->policy, 6, 8, &u, NULL) == LIE_WRONG_OWNER && !u);
  u = a->plan;
  assert(lie_steering_forward_complete(a->policy, &u, 7, NULL) == LIE_WRONG_OWNER && u == a->plan);
  return NULL;
}
int main(void) {
  lie_steering_bank *b = admission();
  lie_steering_settings defaults;
  lie_steering_settings_init(&defaults, true);
  lie_steering_policy_options o = {LIE_STEERING_POLICY_ABI, sizeof(o), 8, b, defaults};
  lie_steering_policy *p = NULL, *other = NULL;
  assert(lie_steering_policy_create(&o, &p, NULL) == LIE_OK);
  assert(lie_steering_policy_create(&o, &other, NULL) == LIE_OK);
  lie_steering_bank_release(&b);
  lie_steering_update *u = NULL;
  lie_steering_policy_info initial = info(p);
  assert(lie_steering_forward_prepare(p, 1, 4, &u, NULL) == LIE_BACKEND_FAILED && !u);
  assert(lie_steering_forward_prepare(p, 0, 9, &u, NULL) == LIE_INVALID && !u);
  assert(lie_steering_forward_prepare(NULL, 0, 1, &u, NULL) == LIE_INVALID && !u);
  assert(lie_steering_forward_prepare(p, 0, 1, NULL, NULL) == LIE_INVALID);
  assert(lie_steering_forward_complete(p, NULL, 0, NULL) == LIE_INVALID);
  assert(lie_steering_forward_complete(NULL, &u, 0, NULL) == LIE_INVALID);
  assert(lie_steering_forward_prepare(p, 0, 0, &u, NULL) == LIE_OK && !u);
  assert(lie_steering_forward_complete(p, &u, 0, NULL) == LIE_OK && !u);
  assert(lie_steering_forward_complete(p, &u, 1, NULL) == LIE_BACKEND_FAILED && !u);
  unchanged(initial, info(p));
  assert(lie_steering_forward_prepare(p, 0, 8, &u, NULL) == LIE_OK && u);
  assert(lie_steering_forward_complete(p, &u, 3, NULL) == LIE_OK && !u);
  assert(info(p).completed_positions == 3 && info(p).history_epochs == 1);
  hex_is(info(p).history_sha256,"6554a977790bbfaf287479d291214cba22cfd11d83cce9d34de7bf346631d01f");
  lie_steering_policy_info pending = info(p);
  assert(lie_steering_forward_prepare(p, 3, 8, &u, NULL) == LIE_OK);
  /* A deferred sampled token/predictor/rejected drafts are not confirmed rows. */
  unchanged(pending, info(p));
  assert(lie_steering_forward_complete(p, &u, 6, NULL) == LIE_OK && !u);
  assert(info(p).completed_positions == 6 && info(p).history_epochs == 1);
  assert(!memcmp(info(p).cache_scope_sha256, initial.cache_scope_sha256, 32));
  lie_steering_policy_info before = info(p);
  assert(lie_steering_forward_prepare(p, 6, 8, &u, NULL) == LIE_OK);
  lie_steering_update_discard(&u); /* Failed model work publishes no metadata. */
  unchanged(before, info(p));
  assert(lie_steering_forward_prepare(p, 6, 5, &u, NULL) == LIE_INVALID && !u);
  assert(lie_steering_forward_prepare(p, 7, 8, &u, NULL) == LIE_BACKEND_FAILED && !u);
  assert(lie_steering_forward_prepare(p, 6, 8, &u, NULL) == LIE_OK);
  other_args args = {p, u};
  pthread_t t;
  assert(!pthread_create(&t, NULL, wrong_owner, &args));
  assert(!pthread_join(t, NULL));
  assert(lie_steering_forward_prepare(p, 6, 8, &u, NULL) == LIE_INVALID && u);
  assert(lie_steering_forward_complete(other, &u, 7, NULL) == LIE_INVALID && u);
  assert(lie_steering_forward_complete(p, &u, 9, NULL) == LIE_INVALID && u);
  unchanged(before, info(p));
  /* EOS before target work and completed work cancelled before client delivery
   * have different retained frontiers; confirmation depends only on that count. */
  assert(lie_steering_forward_complete(p, &u, 6, NULL) == LIE_OK && !u);
  unchanged(before, info(p));
  assert(lie_steering_forward_prepare(p, 6, 8, &u, NULL) == LIE_OK);
  assert(lie_steering_forward_complete(p, &u, 7, NULL) == LIE_OK && !u);
  assert(info(p).completed_positions == 7);
  lie_steering_settings zero = defaults;zero.ffn = 0;
  assert(lie_steering_policy_prepare_change(p, &zero, &u, NULL) == LIE_OK);
  assert(lie_steering_forward_complete(p, &u, 7, NULL) == LIE_INVALID && u);
  assert(lie_steering_update_commit(&u, 7, NULL) == LIE_OK);
  assert(lie_steering_forward_prepare(p, 7, 8, &u, NULL) == LIE_OK);
  before = info(p);
  lie_steering_update *stale = NULL;
  assert(lie_steering_policy_prepare_change(p, &defaults, &stale, NULL) == LIE_OK);
  assert(lie_steering_update_commit(&stale, 7, NULL) == LIE_OK);
  lie_steering_policy_info after = info(p);
  assert(lie_steering_forward_complete(p, &u, 8, NULL) == LIE_INVALID && u);
  unchanged(after, info(p));
  assert(after.revision == before.revision + 1);
  lie_steering_update_discard(&u);
  assert(!info(p).outstanding_updates);
  lie_steering_policy_release(&p);
  lie_steering_policy_release(&other);
  puts("steering model admission and retained-forward transactions: PASS (NOT-INFERENCE)");
  return 0;
}
