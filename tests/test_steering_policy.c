/* SPDX-License-Identifier: MIT */
/* Session policy/identity fixture; no model weights, inference or GPU. */
#include "lie/steering.h"
#include <assert.h>
#include <math.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static lie_steering_bank *bank(void) {
  char path[] = "steering-policy-bank-XXXXXX";
  int fd = mkstemp(path);
  assert(fd >= 0);
  float values[] = {1, 0, 0, 0, .6f, .8f};
  unsigned char data[24];
  for (unsigned j = 0; j < 6; ++j) {
    uint32_t v;
    memcpy(&v, &values[j], 4);
    for (unsigned i = 0; i < 4; ++i)
      data[j * 4 + i] = (unsigned char)(v >> (8 * i));
  }
  assert(write(fd, data, sizeof(data)) == (ssize_t)sizeof(data));
  assert(!close(fd));
  lie_steering_geometry g = {LIE_STEERING_ABI, sizeof(g), 2, 3, 24};
  lie_steering_bank *out = NULL;
  assert(lie_steering_bank_load(path, &g, &out, NULL) == LIE_OK);
  assert(!unlink(path));
  return out;
}
static lie_steering_settings settings(float ffn, float attention) {
  return (lie_steering_settings){LIE_STEERING_POLICY_ABI,
                                 sizeof(lie_steering_settings), ffn, attention};
}
static lie_steering_policy *policy(lie_steering_bank *b, float ffn, float attn,
                                   uint64_t limit) {
  lie_steering_policy_options o = {LIE_STEERING_POLICY_ABI, sizeof(o), limit, b,
                                   settings(ffn, attn)};
  lie_steering_policy *p = NULL;
  assert(lie_steering_policy_create(&o, &p, NULL) == LIE_OK);
  return p;
}
static lie_steering_policy_info info(lie_steering_policy *p) {
  lie_steering_policy_info out = {.abi_version = LIE_STEERING_POLICY_ABI,
                                  .struct_bytes = sizeof(out)};
  assert(lie_steering_policy_snapshot(p, &out, NULL) == LIE_OK);
  return out;
}
static void change(lie_steering_policy *p, float ffn, float attn) {
  lie_steering_settings s = settings(ffn, attn);
  lie_steering_update *u = NULL;
  assert(lie_steering_policy_prepare_change(p, &s, &u, NULL) == LIE_OK);
  assert(lie_steering_update_settings(u)->ffn == ffn);
  assert(lie_steering_update_commit(&u, info(p).completed_positions, NULL) ==
             LIE_OK &&
         !u);
}
static void advance(lie_steering_policy *p, uint64_t maximum,
                    uint64_t completed) {
  lie_steering_update *u = NULL;
  assert(lie_steering_policy_prepare_advance(p, maximum, &u, NULL) == LIE_OK);
  assert(lie_steering_update_commit(&u, completed, NULL) == LIE_OK && !u);
}
static void hex_is(const unsigned char value[32], const char *expected) {
  char text[65];
  for (unsigned i = 0; i < 32; ++i)
    snprintf(text + i * 2, 3, "%02x", value[i]);
  assert(!strcmp(text, expected));
}
static void unchanged(lie_steering_policy_info a, lie_steering_policy_info b) {
  assert(a.completed_positions == b.completed_positions &&
         a.revision == b.revision && a.history_epochs == b.history_epochs);
  assert(a.has_completed_work == b.has_completed_work &&
         a.has_steered_history == b.has_steered_history);
  assert(a.settings.ffn == b.settings.ffn &&
         a.settings.attention == b.settings.attention);
  assert(!memcmp(a.history_sha256, b.history_sha256, 32) &&
         !memcmp(a.cache_scope_sha256, b.cache_scope_sha256, 32));
}
static void identity_history(void) {
  lie_steering_bank *b = bank();
  lie_steering_policy *p = policy(b, 1, 0, 128),
                      *partitioned = policy(b, 1, 0, 128);
  lie_steering_bank_release(
      &b); /* Both policies independently pin immutable data. */
  lie_steering_policy_info initial = info(p);
  hex_is(initial.cache_scope_sha256,
         "08f7850c93b5efedb7f078146b8a979121aaf02d843d8ab95567f59054132858");
  assert(!initial.has_completed_work && !initial.history_epochs);
  advance(p, 8, 8);
  advance(partitioned, 3, 2);
  advance(partitioned, 4, 4);
  advance(partitioned, 8, 8);
  lie_steering_policy_info first = info(p), other = info(partitioned);
  assert(!memcmp(first.cache_scope_sha256, initial.cache_scope_sha256, 32));
  assert(!memcmp(first.cache_scope_sha256, other.cache_scope_sha256, 32));
  assert(first.history_epochs == 1 && first.has_steered_history);
  hex_is(first.history_sha256,
         "b6061819d413dc01097bc41249f0ef780200a670fc7107e454743e4130cd237b");
  change(p, 2, 0);
  lie_steering_policy_info pending = info(p);
  assert(!memcmp(pending.history_sha256, first.history_sha256, 32));
  hex_is(pending.cache_scope_sha256,
         "5a0ffd7f29d15ab6dfc6b41ecf41f15d5b80dccd11cfd178ee145477045dc8d0");
  advance(p, 16, 10);
  lie_steering_policy_info mixed = info(p);
  hex_is(mixed.history_sha256,
         "5da3439646245a7120bdac8bd3c79f11a5b8a8c11158807c2b93aa75e3bafc4d");
  hex_is(mixed.cache_scope_sha256,
         "743b866453b9ca1c5ef582fe58abc3aa6a555ce701abfd131cc86b947307c6f2");
  assert(mixed.completed_positions == 10 && mixed.history_epochs == 2);
  change(p, 0, 0);
  advance(p, 16, 16);
  lie_steering_policy_info off = info(p);
  unsigned char zero[32] = {0};
  assert(off.has_steered_history && off.history_epochs == 3 &&
         memcmp(off.cache_scope_sha256, zero, 32));
  assert(memcmp(off.cache_scope_sha256, mixed.cache_scope_sha256, 32));
  lie_steering_policy_release(&p);
  lie_steering_policy_release(&partitioned);
}
static void zero_and_semantic(void) {
  unsigned char zero[32] = {0}, semantic[32] = {1, 2, 3}, out[32];
  lie_steering_bank *b = bank();
  lie_steering_policy *p = policy(b, -0.0f, 0, 64),
                      *plain = policy(NULL, 0, 0, 64);
  lie_steering_policy_info before = info(p);
  assert(!signbit(before.settings.ffn));
  assert(!memcmp(before.cache_scope_sha256, zero, 32));
  change(p, 1, 1);
  change(p, 0, 0);
  advance(p, 8, 8);
  before = info(p);
  assert(!before.has_steered_history &&
         !memcmp(before.cache_scope_sha256, zero, 32));
  assert(lie_steering_policy_cache_scope(p, semantic, out, NULL) == LIE_OK &&
         !memcmp(out, semantic, 32));
  assert(lie_steering_policy_cache_scope(plain, semantic, out, NULL) ==
             LIE_OK &&
         !memcmp(out, semantic, 32));
  change(p, 1, 0);
  advance(p, 16, 16);
  lie_steering_policy_info steered = info(p);
  assert(lie_steering_policy_cache_scope(p, zero, out, NULL) == LIE_OK &&
         !memcmp(out, steered.cache_scope_sha256, 32));
  unsigned char combined[32];
  assert(lie_steering_policy_cache_scope(p, semantic, combined, NULL) ==
         LIE_OK);
  assert(memcmp(combined, semantic, 32) &&
         memcmp(combined, steered.cache_scope_sha256, 32));
  memcpy(out, semantic, 32);
  assert(lie_steering_policy_cache_scope(p, out, out, NULL) == LIE_OK &&
         !memcmp(out, combined, 32));
  assert(lie_steering_policy_cache_scope(p, NULL, out, NULL) == LIE_INVALID &&
         !memcmp(out, combined, 32));
  lie_steering_policy_release(&p);
  lie_steering_policy_release(&plain);
  lie_steering_bank_release(&b);
}
typedef struct {
  lie_steering_policy *p;
  lie_steering_update *u;
} wrong_owner;
static void *other_owner(void *opaque) {
  wrong_owner *x = opaque;
  lie_steering_update *empty = NULL;
  lie_steering_settings s = settings(0, 0);
  assert(lie_steering_policy_prepare_change(x->p, &s, &empty, NULL) ==
             LIE_WRONG_OWNER &&
         !empty);
  assert(lie_steering_policy_prepare_advance(x->p, 2, &empty, NULL) ==
             LIE_WRONG_OWNER &&
         !empty);
  lie_steering_update *saved = x->u;
  assert(lie_steering_update_commit(&x->u, 0, NULL) == LIE_WRONG_OWNER &&
         x->u == saved);
  assert(info(x->p).completed_positions == 0);
  return NULL;
}
static void refusals_transactions(void) {
  lie_steering_bank *b = bank();
  lie_steering_policy *p = policy(b, 0, 0, 32);
  lie_steering_update *u = NULL, *stale = NULL;
  lie_steering_policy_info before = info(p);
  float bad[] = {NAN, INFINITY, -INFINITY, 100.1f, -100.1f};
  for (unsigned i = 0; i < sizeof(bad) / sizeof(*bad); ++i) {
    lie_steering_settings s = settings(bad[i], 0);
    assert(lie_steering_policy_prepare_change(p, &s, &u, NULL) == LIE_INVALID &&
           !u);
    s = settings(0, bad[i]);
    assert(lie_steering_policy_prepare_change(p, &s, &u, NULL) == LIE_INVALID &&
           !u);
  }
  lie_steering_settings s = settings(1, 0);
  s.abi_version = 0;
  assert(lie_steering_policy_prepare_change(p, &s, &u, NULL) == LIE_INVALID &&
         !u);
  s = settings(1, 0);
  s.struct_bytes--;
  assert(lie_steering_policy_prepare_change(p, &s, &u, NULL) == LIE_INVALID &&
         !u);
  assert(lie_steering_policy_prepare_advance(p, 0, &u, NULL) == LIE_INVALID &&
         !u);
  assert(lie_steering_policy_prepare_advance(p, 33, &u, NULL) == LIE_INVALID &&
         !u);
  lie_steering_policy_info after = info(p);
  unchanged(before, after);
  s = settings(1, 0);
  assert(lie_steering_policy_prepare_change(p, &s, &u, NULL) == LIE_OK);
  wrong_owner w = {p, u};
  pthread_t t;
  assert(!pthread_create(&t, NULL, other_owner, &w));
  assert(!pthread_join(t, NULL));
  assert(w.u == u);
  assert(lie_steering_update_commit(&u, 1, NULL) == LIE_INVALID && u);
  assert(lie_steering_policy_prepare_advance(p, 8, &stale, NULL) == LIE_OK);
  lie_steering_update *excess = NULL;
  assert(lie_steering_policy_prepare_advance(p, 8, &excess, NULL) ==
             LIE_RESOURCE_LIMIT &&
         !excess);
  after = info(p);
  assert(after.outstanding_updates == LIE_STEERING_MAX_UPDATES &&
         after.staged_bytes > 0 && after.policy_bytes > 0);
  assert(lie_steering_update_commit(&u, 0, NULL) == LIE_OK && !u);
  assert(lie_steering_update_commit(&stale, 8, NULL) == LIE_INVALID && stale);
  lie_steering_update_discard(&stale);
  assert(!info(p).outstanding_updates && !info(p).staged_bytes);
  before = info(p);
  advance(p, 8, 0);
  after = info(p);
  unchanged(before, after);
  assert(lie_steering_policy_prepare_advance(p, 8, &u, NULL) == LIE_OK);
  assert(lie_steering_update_commit(&u, 9, NULL) == LIE_INVALID && u);
  lie_steering_update_discard(&u);
  after = info(p);
  unchanged(before, after);
  change(p, 100, -100);
  advance(p, 32, 32);
  assert(lie_steering_policy_prepare_advance(p, 32, &u, NULL) == LIE_INVALID &&
         !u);
  lie_steering_policy_release(&p);
  lie_steering_bank_release(&b);
  p = policy(NULL, 0, 0, UINT64_MAX);
  s = settings(1, 0);
  assert(lie_steering_policy_prepare_change(p, &s, &u, NULL) == LIE_INVALID &&
         !u);
  assert(lie_steering_policy_prepare_advance(p, UINT64_MAX, &u, NULL) ==
         LIE_OK);
  lie_steering_policy_release(&p);
  assert(!p);
  assert(lie_steering_update_commit(&u, UINT64_MAX, NULL) == LIE_OK &&
         !u); /* Plan's pin was the last live owner. */
  lie_steering_policy_options o = {LIE_STEERING_POLICY_ABI, sizeof(o), 32, NULL,
                                   settings(1, 0)};
  assert(lie_steering_policy_create(&o, &p, NULL) == LIE_INVALID && !p);
  o.settings = settings(0, 0);
  o.max_positions = 0;
  assert(lie_steering_policy_create(&o, &p, NULL) == LIE_INVALID && !p);
}
static void *reader(void *opaque) {
  lie_steering_policy *p = opaque;
  uint64_t revision = 0;
  for (unsigned i = 0; i < 5000; ++i) {
    lie_steering_policy *pin = p;
    assert(lie_steering_policy_retain(pin) == LIE_OK);
    lie_steering_policy_info s = info(pin);
    assert(s.bank_present && s.bank.layers == 2 && s.bank.width == 3);
    assert(s.completed_positions <= s.max_positions && s.revision >= revision);
    revision = s.revision;
    lie_steering_policy_release(&pin);
    assert(!pin);
  }
  return NULL;
}
static void concurrent_snapshots(void) {
  lie_steering_bank *b = bank();
  lie_steering_policy *p = policy(b, 1, 0, 1024);
  lie_steering_bank_release(&b);
  pthread_t readers[4];
  for (unsigned i = 0; i < 4; ++i)
    assert(!pthread_create(&readers[i], NULL, reader, p));
  for (unsigned i = 0; i < 128; ++i) {
    change(p, (float)(i % 3), 0);
    advance(p, i + 1, i + 1);
  }
  for (unsigned i = 0; i < 4; ++i)
    assert(!pthread_join(readers[i], NULL));
  lie_steering_policy_release(&p);
}
int main(void) {
  lie_steering_settings s;
  lie_steering_settings_init(&s, false);
  assert(s.ffn == 0 && s.attention == 0);
  lie_steering_settings_init(&s, true);
  assert(s.ffn == 1 && s.attention == 0);
  identity_history();
  zero_and_semantic();
  refusals_transactions();
  concurrent_snapshots();
  puts("steering session history, cache identity and transactions: PASS "
       "(NOT-INFERENCE)");
  return 0;
}
