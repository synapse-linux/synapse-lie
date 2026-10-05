/* SPDX-License-Identifier: MIT */
/* Synthetic host state/transactions only. No model forward or GPU evidence. */
#include "lie/steering.h"
#include "lie/kvc.h"
#include "../src/state_codec.h"
#include "../src/state_internal.h"
#include <assert.h>
#include <fcntl.h>
#include <openssl/evp.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static lie_steering_bank *bank(unsigned layers, unsigned width, float first) {
  char path[] = "steering-state-bank-XXXXXX";
  int fd = mkstemp(path);
  assert(fd >= 0 && layers * width == 4);
  float values[] = {first, 2, 3, 4};
  unsigned char bytes[16];
  for (unsigned j = 0; j < 4; ++j) {
    uint32_t bits;
    memcpy(&bits, &values[j], 4);
    for (unsigned i = 0; i < 4; ++i)
      bytes[4 * j + i] = (unsigned char)(bits >> (8 * i));
  }
  assert(write(fd, bytes, sizeof(bytes)) == (ssize_t)sizeof(bytes));
  assert(!close(fd));
  lie_steering_geometry g = {LIE_STEERING_ABI, sizeof(g), layers, width, 16};
  lie_steering_bank *b = NULL;
  assert(lie_steering_bank_load(path, &g, &b, NULL) == LIE_OK);
  assert(!unlink(path));
  return b;
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
static void equivalent(lie_steering_policy_info a, lie_steering_policy_info b) {
  assert(a.completed_positions == b.completed_positions &&
         a.history_epochs == b.history_epochs && a.bank_present == b.bank_present &&
         a.has_completed_work == b.has_completed_work &&
         a.has_steered_history == b.has_steered_history);
  assert(a.settings.ffn == b.settings.ffn && a.settings.attention == b.settings.attention);
  if (a.has_completed_work)
    assert(a.last_completed_settings.ffn == b.last_completed_settings.ffn &&
           a.last_completed_settings.attention == b.last_completed_settings.attention);
  assert(!memcmp(a.history_sha256, b.history_sha256, 32) &&
         !memcmp(a.cache_scope_sha256, b.cache_scope_sha256, 32));
}
static void unchanged(lie_steering_policy_info a, lie_steering_policy_info b) {
  equivalent(a, b);
  assert(a.revision == b.revision && a.max_positions == b.max_positions);
}
static void change(lie_steering_policy *p, float ffn, float attn) {
  lie_steering_settings s = settings(ffn, attn);
  lie_steering_update *u = NULL;
  assert(lie_steering_policy_prepare_change(p, &s, &u, NULL) == LIE_OK);
  assert(lie_steering_update_commit(&u, info(p).completed_positions, NULL) == LIE_OK && !u);
}
static void advance(lie_steering_policy *p, uint64_t completed) {
  lie_steering_update *u = NULL;
  assert(lie_steering_policy_prepare_advance(p, completed, &u, NULL) == LIE_OK);
  assert(lie_steering_update_commit(&u, completed, NULL) == LIE_OK && !u);
}
static void hex_is(const unsigned char *value, size_t bytes, const char *expected) {
  assert(strlen(expected) == bytes * 2);
  for (size_t i = 0; i < bytes; ++i) {
    char text[3];
    snprintf(text, sizeof(text), "%02x", value[i]);
    assert(!memcmp(text, expected + 2 * i, 2));
  }
}
static void resign(unsigned char frame[LIE_STEERING_STATE_BYTES]) {
  /* Independent segmented checksum, used to exercise structural admission
   * beyond checksum failures. This is not authentication of historical work. */
  const char domain[] = "synapse-lie.steering-state.v1";
  EVP_MD_CTX *h = EVP_MD_CTX_new();
  unsigned n = 0;
  assert(h && EVP_DigestInit_ex(h, EVP_sha256(), NULL) == 1 &&
         EVP_DigestUpdate(h, domain, sizeof(domain)) == 1 &&
         EVP_DigestUpdate(h, frame, 160) == 1 &&
         EVP_DigestFinal_ex(h, frame + 160, &n) == 1 && n == 32);
  EVP_MD_CTX_free(h);
}
static void encode(lie_steering_policy *p, unsigned char out[LIE_STEERING_STATE_BYTES]) {
  assert(lie_steering_policy_encode(p, out, LIE_STEERING_STATE_BYTES, NULL) == LIE_OK);
}
static void roundtrip(lie_steering_policy *p, lie_steering_bank *b) {
  unsigned char frame[LIE_STEERING_STATE_BYTES], again[LIE_STEERING_STATE_BYTES];
  encode(p, frame);
  lie_steering_policy *clone = policy(b, 0, 0, 256);
  uint64_t completed = info(p).completed_positions;
  lie_steering_update *u = NULL;
  assert(lie_steering_policy_prepare_restore(clone, frame, sizeof(frame), completed, &u, NULL) == LIE_OK);
  unsigned char semantic[32] = {3, 1}, want[32], staged[32];
  assert(lie_steering_policy_cache_scope(p, semantic, want, NULL) == LIE_OK);
  assert(lie_steering_update_cache_scope(u, semantic, staged, NULL) == LIE_OK && !memcmp(want, staged, 32));
  memset(frame, 0, sizeof(frame)); /* The plan owns all decoded metadata. */
  assert(lie_steering_update_commit(&u, completed, NULL) == LIE_OK && !u);
  equivalent(info(p), info(clone));
  assert(info(clone).revision == 1 && info(clone).max_positions == 256);
  encode(p, frame);
  encode(clone, again);
  assert(!memcmp(frame, again, sizeof(frame)));
  /* A subsequent completed epoch must extend the restored head at its actual
   * position; the destination's own revision/capacity do not enter the ID. */
  change(p, -2, .5f);
  change(clone, -2, .5f);
  advance(p, completed + 1);
  advance(clone, completed + 1);
  equivalent(info(p), info(clone));
  lie_steering_policy_release(&clone);
}
static void wire_and_histories(void) {
  lie_steering_bank *b = bank(2, 2, 1);
  lie_steering_policy *p = policy(b, 1, 0, 128);
  unsigned char frame[LIE_STEERING_STATE_BYTES];
  encode(p, frame);
  /* Independently reconstructed SHA/LE wire oracles, not C struct layouts. */
  hex_is(frame, sizeof(frame),
    "4c4945535450310001000000c000000001000000000000000000000000000000"
    "00000000000000000000803f000000000000803f00000000f1e2b722c6313848"
    "754d8135cfd8fb4838933bd97162cf2df1e883a282c7e8830000000000000000"
    "0000000000000000000000000000000000000000000000004d875938e3e43656"
    "b4f57d8b9079ea06719076381fca692257b2fcb28952a5070000000000000000"
    "9e22e32308db69a3013610209724f9984859696ffb45f9f825e01d59def4f0c6");
  advance(p, 7);
  encode(p, frame);
  hex_is(frame, sizeof(frame),
    "4c4945535450310001000000c000000007000000000000000700000000000000"
    "01000000000000000000803f000000000000803f00000000f1e2b722c6313848"
    "754d8135cfd8fb4838933bd97162cf2df1e883a282c7e8836554a977790bbfaf"
    "287479d291214cba22cfd11d83cce9d34de7bf346631d01f4d875938e3e43656"
    "b4f57d8b9079ea06719076381fca692257b2fcb28952a5070000000000000000"
    "bf18202e2d1091c8f37767cf05c71162d26b920d08f91288cd25d03ca0d47b71");
  roundtrip(p, b);
  change(p, 0, 0);
  advance(p, 11);
  assert(info(p).has_steered_history && info(p).history_epochs == 3);
  roundtrip(p, b);
  change(p, 3, 1); /* Pending future scales also survive capture. */
  roundtrip(p, b);
  lie_steering_policy_release(&p);
  p = policy(b, 1, 0, 128);
  change(p, 0, 0); /* Unused changes have no numerical history. */
  lie_steering_policy *zero = policy(b, 0, 0, 64);
  unsigned char other[LIE_STEERING_STATE_BYTES];
  encode(p, frame);
  encode(zero, other);
  assert(!memcmp(frame, other, sizeof(frame)));
  roundtrip(p, b);
  lie_steering_policy_release(&p);
  advance(zero, 5);
  change(zero, 1, 0); /* Active future scales following unsteered work. */
  assert(!info(zero).has_steered_history);
  roundtrip(zero, b);
  lie_steering_policy_release(&zero);
  lie_steering_bank_release(&b);
}
static void refused(lie_steering_policy *p, const unsigned char *frame,
                    size_t bytes, uint64_t completed) {
  lie_steering_policy_info before = info(p);
  lie_steering_update *u = NULL;
  assert(lie_steering_policy_prepare_restore(p, frame, bytes, completed, &u, NULL) == LIE_INVALID && !u);
  unchanged(before, info(p));
  assert(!info(p).outstanding_updates);
}
typedef struct {
  lie_steering_policy *p;
  lie_steering_update *u;
  const unsigned char *frame;
} other_args;
static void *other_owner(void *opaque) {
  other_args *a = opaque;
  lie_steering_update *u = NULL;
  unsigned char out[LIE_STEERING_STATE_BYTES], before[sizeof(out)], zero[32] = {0};
  memset(out, 0xa5, sizeof(out));
  memcpy(before, out, sizeof(out));
  assert(lie_steering_policy_encode(a->p, out, sizeof(out), NULL) == LIE_WRONG_OWNER && !memcmp(out, before, sizeof(out)));
  assert(lie_steering_policy_prepare_restore(a->p, a->frame, sizeof(out), 7, &u, NULL) == LIE_WRONG_OWNER && !u);
  assert(lie_steering_update_cache_scope(a->u, zero, out, NULL) == LIE_WRONG_OWNER && !memcmp(out, before, sizeof(out)));
  u = a->u;
  assert(lie_steering_update_commit(&u, 7, NULL) == LIE_WRONG_OWNER && u == a->u);
  return NULL;
}
static void parser_and_transactions(void) {
  lie_steering_bank *b = bank(2, 2, 1);
  lie_steering_policy *source = policy(b, 1, 0, 32), *p = policy(b, 0, 0, 32);
  advance(source, 7);
  unsigned char frame[LIE_STEERING_STATE_BYTES], bad[sizeof(frame)];
  encode(source, frame);
  for (size_t i = 0; i < sizeof(frame); ++i) {
    memcpy(bad, frame, sizeof(bad));
    bad[i] ^= 1;
    refused(p, bad, sizeof(bad), 7);
  }
  refused(p, NULL, sizeof(frame), 7);
  refused(p, frame, 0, 7);
  refused(p, frame, sizeof(frame) - 1, 7);
  refused(p, frame, sizeof(frame) + 1, 7);
  refused(p, frame, sizeof(frame), 6);
  refused(p, frame, sizeof(frame), 33);
  /* All these altered frames have a valid checksum and must still refuse. */
  const struct {size_t at; unsigned char value;} mutations[] = {
    {0, 'X'}, {8, 2}, {12, 191}, {16, 8}, {20, 1}, {152, 1},
    {16, 6}, {16, 5}, {16, 3}, {24, 6}, {32, 0}, {32, 8},
    {56, 0}, {88, 0}, {120, 0}, {42, 200}, {43, 127}, {47, 128},
    {51, 127}
  };
  for (unsigned i = 0; i < sizeof(mutations) / sizeof(*mutations); ++i) {
    memcpy(bad, frame, sizeof(bad));
    bad[mutations[i].at] = mutations[i].value;
    resign(bad);
    refused(p, bad, sizeof(bad), 7);
  }
  memcpy(bad, frame, sizeof(bad));
  memset(bad + 88, 0, 32);
  resign(bad);
  refused(p, bad, sizeof(bad), 7);
  memcpy(bad, frame, sizeof(bad));
  memset(bad + 48, 0, 8); /* Epoch one cannot have an inactive last epoch. */
  resign(bad);
  refused(p, bad, sizeof(bad), 7);
  for (unsigned variant = 0; variant < 3; ++variant) {
    lie_steering_bank *different = variant == 0 ? NULL :
      bank(variant == 1 ? 1 : 2, variant == 1 ? 4 : 2, variant == 2 ? 9 : 1);
    lie_steering_policy *wrong = policy(different, 0, 0, 32);
    refused(wrong, frame, sizeof(frame), 7);
    lie_steering_policy_release(&wrong);
    lie_steering_bank_release(&different);
  }
  lie_steering_policy *small = policy(b, 0, 0, 6);
  refused(small, frame, sizeof(frame), 7);
  lie_steering_policy_release(&small);
  unsigned char out[sizeof(frame)], before[sizeof(frame)];
  memset(out, 0xa5, sizeof(out));
  memcpy(before, out, sizeof(out));
  assert(lie_steering_policy_encode(NULL, out, sizeof(out), NULL) == LIE_INVALID);
  assert(lie_steering_policy_encode(p, NULL, sizeof(out), NULL) == LIE_INVALID);
  assert(lie_steering_policy_encode(p, out, sizeof(out) - 1, NULL) == LIE_BUFFER_SMALL && !memcmp(out, before, sizeof(out)));
  lie_steering_update *u = NULL, *other = NULL;
  assert(lie_steering_policy_prepare_restore(p, frame, sizeof(frame), 7, &u, NULL) == LIE_OK);
  assert(lie_steering_policy_encode(p, out, sizeof(out), NULL) == LIE_RESOURCE_LIMIT && !memcmp(out, before, sizeof(out)));
  assert(lie_steering_policy_prepare_restore(p, frame, sizeof(frame), 7, &other, NULL) == LIE_INVALID && !other);
  assert(lie_steering_policy_prepare_restore(p, frame, sizeof(frame), 7, &u, NULL) == LIE_INVALID && u);
  assert(lie_steering_policy_prepare_restore(p, frame, sizeof(frame), 7, NULL, NULL) == LIE_INVALID);
  other_args args = {p, u, frame};
  pthread_t t;
  assert(!pthread_create(&t, NULL, other_owner, &args));
  assert(!pthread_join(t, NULL));
  unsigned char zero[32] = {0};
  assert(lie_steering_update_cache_scope(NULL, zero, out, NULL) == LIE_INVALID);
  assert(lie_steering_update_cache_scope(u, NULL, out, NULL) == LIE_INVALID && !memcmp(out, before, sizeof(out)));
  assert(lie_steering_update_cache_scope(u, zero, NULL, NULL) == LIE_INVALID);
  assert(lie_steering_update_commit(&u, 6, NULL) == LIE_INVALID && u);
  assert(lie_steering_update_commit(&u, 8, NULL) == LIE_INVALID && u);
  assert(info(p).completed_positions == 0);
  lie_steering_update_discard(&u);
  assert(!u && !info(p).outstanding_updates && info(p).completed_positions == 0);
  assert(lie_steering_policy_prepare_restore(p, frame, sizeof(frame), 7, &u, NULL) == LIE_OK);
  change(p, 2, 0);
  lie_steering_policy_info saved = info(p);
  assert(lie_steering_update_commit(&u, 7, NULL) == LIE_INVALID && u);
  unchanged(saved, info(p));
  lie_steering_update_discard(&u);
  change(p, 0, 0);
  assert(lie_steering_policy_prepare_restore(p, frame, sizeof(frame), 7, &u, NULL) == LIE_OK);
  assert(lie_steering_update_commit(&u, 7, NULL) == LIE_OK && !u);
  equivalent(info(source), info(p));
  refused(p, frame, sizeof(frame), 7);
  lie_steering_policy_release(&p);
  p = policy(b, 0, 0, 32);
  assert(lie_steering_policy_prepare_restore(p, frame, sizeof(frame), 7, &u, NULL) == LIE_OK);
  lie_steering_policy_release(&p);
  lie_steering_bank_release(&b);
  lie_steering_policy_release(&source);
  assert(lie_steering_update_commit(&u, 7, NULL) == LIE_OK && !u);
}
static void legacy_state(void) {
  lie_steering_policy *p = policy(NULL, 0, 0, 64);
  lie_steering_update *u = NULL;
  assert(lie_steering_policy_prepare_restore(p, NULL, 0, 5, &u, NULL) == LIE_OK);
  assert(lie_steering_update_commit(&u, 5, NULL) == LIE_OK);
  unsigned char frame[LIE_STEERING_STATE_BYTES];
  encode(p, frame);
  hex_is(frame, sizeof(frame),
    "4c4945535450310001000000c000000002000000000000000500000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "03675474fdc06f6489f07f4a9468f257eab9c60a654e0d23ab8c8a553f40f294");
  lie_steering_policy *clone = policy(NULL, 0, 0, 128);
  assert(lie_steering_policy_prepare_restore(clone, frame, sizeof(frame), 5, &u, NULL) == LIE_OK);
  assert(lie_steering_update_commit(&u, 5, NULL) == LIE_OK);
  equivalent(info(p), info(clone));
  unsigned char semantic[32] = {7}, out[32];
  assert(lie_steering_policy_cache_scope(clone, semantic, out, NULL) == LIE_OK && !memcmp(semantic, out, 32));
  lie_steering_policy_release(&clone);
  lie_steering_policy_release(&p);
  lie_steering_bank *b = bank(2, 2, 1);
  p = policy(b, 1, 0, 128);
  refused(p, NULL, 0, 5);
  change(p, 0, 0);
  assert(lie_steering_policy_prepare_restore(p, NULL, 0, 5, &u, NULL) == LIE_OK);
  assert(lie_steering_update_cache_scope(u, semantic, out, NULL) == LIE_OK && !memcmp(semantic, out, 32));
  assert(lie_steering_update_commit(&u, 5, NULL) == LIE_OK);
  assert(!info(p).has_steered_history);
  change(p, 1, 0);
  advance(p, 8);
  assert(info(p).history_epochs == 1 && info(p).completed_positions == 8);
  lie_steering_policy_release(&p);
  lie_steering_bank_release(&b);
}

enum { BASE = 108, AUX = 8, POLICY_AT = BASE + AUX,
       SCOPE_AT = POLICY_AT + LIE_STEERING_STATE_BYTES, TOTAL = SCOPE_AT + 32 };
struct lie_sequence {
  lie_state_layout layout;
  unsigned char payload[TOTAL];
  lie_steering_policy *policy;
  unsigned writes;
  bool empty;
};
lie_status lie_sequence_state_describe(lie_sequence *s, const lie_state_layout *in,
                                      lie_state_layout *out, lie_error *e) {
  (void)e;
  if (in && (!s->empty || !lie_state_layout_equal(in, &s->layout)))
    return LIE_INVALID;
  *out = s->layout;
  return LIE_OK;
}
lie_status lie_sequence_state_read(lie_sequence *s, const lie_state_layout *l,
                                 void *out, size_t n, lie_error *e) {
  if (s->empty || n != TOTAL || !lie_state_layout_equal(l, &s->layout))
    return LIE_INVALID;
  lie_status rc = lie_steering_policy_encode(s->policy, s->payload + POLICY_AT,
                                           LIE_STEERING_STATE_BYTES, e);
  if (rc == LIE_OK)
    rc = lie_steering_policy_cache_scope(s->policy, (unsigned char[32]){0},
                                       s->payload + SCOPE_AT, e);
  if (rc == LIE_OK) memcpy(out, s->payload, n);
  return rc;
}
lie_status lie_sequence_state_write(lie_sequence *s, const lie_state_layout *l,
                                  const void *raw, size_t n, lie_error *e) {
  if (!s->empty || n != TOTAL || !lie_state_layout_equal(l, &s->layout))
    return LIE_INVALID;
  const unsigned char *p = raw;
  if (memcmp(p, s->payload, BASE + AUX)) return LIE_INVALID;
  lie_steering_update *u = NULL;
  lie_status rc = lie_steering_policy_prepare_restore(s->policy, p + POLICY_AT,
                         LIE_STEERING_STATE_BYTES, l->token_count, &u, e);
  unsigned char scope[32];
  if (rc == LIE_OK)
    rc = lie_steering_update_cache_scope(u, (unsigned char[32]){0}, scope, e);
  if (rc == LIE_OK && memcmp(scope, p + SCOPE_AT, 32)) rc = LIE_INVALID;
  if (rc != LIE_OK) { lie_steering_update_discard(&u); return rc; }
  /* Simulated device mutation begins only after policy/scope/model admission.
   * This fixture owns synthetic bytes, not original-weight model tensors. */
  memcpy(s->payload, p, n);
  ++s->writes;
  rc = lie_steering_update_commit(&u, l->token_count, e);
  assert(rc == LIE_OK && !u);
  s->empty = false;
  return rc;
}
static struct lie_sequence sequence(lie_steering_policy *p, bool empty) {
  struct lie_sequence s = {.policy = p, .empty = empty,
    .layout = {.abi_version = LIE_STATE_ABI, .representation_version = 1,
      .token_count = 7, .context_tokens = 32, .prefill_chunk = 4, .domain = 77,
      .format = LIE_STATE_KVC_AUX, .model_id = 5, .quant_bits = 4}};
  uint64_t d = 64;
  assert(lie_state_add(&s.layout, LIE_STATE_HEADER, 0, LIE_STATE_U8, 1, &d));
  d = 7; assert(lie_state_add(&s.layout, LIE_STATE_TOKENS, 0, LIE_STATE_I32, 1, &d));
  d = 4; assert(lie_state_add(&s.layout, LIE_STATE_LOGITS, 0, LIE_STATE_F32, 1, &d));
  d = AUX; assert(lie_state_add(&s.layout, LIE_STATE_AUXILIARY, 0, LIE_STATE_U8, 1, &d));
  d = LIE_STEERING_STATE_BYTES;
  assert(lie_state_add(&s.layout, LIE_STATE_STEERING_POLICY, 0, LIE_STATE_U8, 1, &d));
  d = 32; assert(lie_state_add(&s.layout, LIE_STATE_CACHE_SCOPE, 0, LIE_STATE_U8, 1, &d));
  uint64_t n;
  assert(lie_state_validate(&s.layout, &n) && n == TOTAL);
  memset(s.payload, 3, 64);
  int32_t ids[] = {1, 2, 3, 4, 5, 6, 7};
  float logits[] = {0, 1, 2, 3};
  memcpy(s.payload + 64, ids, sizeof(ids));
  memcpy(s.payload + 92, logits, sizeof(logits));
  memcpy(s.payload + BASE, "AUXTEST1", AUX);
  return s;
}
static void state_envelope(void) {
  lie_steering_bank *b = bank(2, 2, 1);
  lie_steering_policy *p = policy(b, 1, 0, 32), *dest = policy(b, 0, 0, 128);
  advance(p, 7);
  struct lie_sequence producer = sequence(p, false), clone = sequence(dest, true);
  lie_state_layout plan;
  uint64_t budget, base, aux;
  lie_error e = {0};
  assert(lie_state_plan(&producer, &plan, &budget, &e) == LIE_OK);
  assert(lie_state_kvc_parts(&plan, &base, &aux) && base == BASE && base + aux == TOTAL);
  lie_state_layout invalid = plan;
  invalid.sections[4].layer = 1;
  assert(!lie_state_validate(&invalid, &base));
  invalid = plan; invalid.sections[4].dtype = LIE_STATE_F32;
  assert(!lie_state_validate(&invalid, &base));
  invalid = plan; invalid.section_count--;
  assert(!lie_state_validate(&invalid, &base));
  lie_state *state = NULL;
  assert(lie_state_capture(&producer, &plan, budget - 1, &state, &e) == LIE_RESOURCE_LIMIT && !state);
  assert(lie_state_capture(&producer, &plan, budget, &state, &e) == LIE_OK && state);
  /* Syntactically valid model bytes with incompatible policy/scope are refused
   * by the fixture provider before any transfer or live policy mutation. */
  unsigned char saved = state->payload[POLICY_AT + 24];
  state->payload[POLICY_AT + 24] = 6;
  resign(state->payload + POLICY_AT);
  lie_steering_policy_info before = info(dest);
  assert(lie_state_restore(&clone, state, &e) == LIE_INVALID && !clone.writes && clone.empty);
  unchanged(before, info(dest));
  state->payload[POLICY_AT + 24] = saved;
  resign(state->payload + POLICY_AT);
  state->payload[SCOPE_AT] ^= 1;
  assert(lie_state_restore(&clone, state, &e) == LIE_INVALID && !clone.writes && clone.empty);
  unchanged(before, info(dest));
  state->payload[SCOPE_AT] ^= 1;
  assert(lie_state_restore(&clone, state, &e) == LIE_OK && clone.writes == 1 && !clone.empty);
  equivalent(info(p), info(dest));
  assert(lie_state_restore(&clone, state, &e) == LIE_INVALID && clone.writes == 1);
  lie_steering_policy_release(&dest);
  char path[] = "steering-state-ssd-XXXXXX";
  int fd = mkstemp(path);
  assert(fd >= 0);
  lie_state_identity id = {{1}}, wrong = {{2}};
  lie_cache_metadata meta = {.text = "fixture", .text_bytes = 7,
    .trailer = "client", .trailer_bytes = 6, .reason = LIE_CACHE_COLD};
  atomic_bool cancel = false;
  assert(lie_state_file_write_ex(fd, &id, state, &meta, &cancel));
  lie_kvc_limits limits = lie_kvc_default_limits(1u << 20);
  lie_kvc *wire = NULL;
  assert(lie_kvc_read_fd(fd, &limits, &wire, &e) == LIE_OK);
  const lie_kvc_view *view = lie_kvc_get_view(wire);
  assert(view->payload.bytes == BASE && !memcmp(view->payload.data, producer.payload, BASE));
  assert(view->trailer.bytes >= 6 && !memcmp(view->trailer.data, "client", 6));
  lie_kvc_destroy(&wire);
  assert(!lie_state_file_read(fd, &wrong, plan.domain, budget, &cancel));
  assert(!lie_state_file_read(fd, &id, plan.domain, budget - 1, &cancel));
  atomic_store(&cancel, true);
  assert(!lie_state_file_read(fd, &id, plan.domain, budget, &cancel));
  atomic_store(&cancel, false);
  lie_state *loaded = lie_state_file_read(fd, &id, plan.domain, budget, &cancel);
  assert(loaded);
  unsigned char scope[32];
  assert(lie_state_cache_scope(loaded, scope) && !memcmp(scope, producer.payload + SCOPE_AT, 32));
  dest = policy(b, 0, 0, 128);
  clone = sequence(dest, true);
  assert(lie_state_restore(&clone, loaded, &e) == LIE_OK && clone.writes == 1);
  equivalent(info(p), info(dest));
  lie_state_destroy(&loaded);
  /* Auxiliary policy is also covered by the containing SSD payload checksum. */
  off_t at = 52 + 7 + BASE + 6 + AUX + 48;
  unsigned char original, corrupt;
  assert(pread(fd, &original, 1, at) == 1);
  corrupt = original ^ 1;
  assert(pwrite(fd, &corrupt, 1, at) == 1 && !lie_state_file_read(fd, &id, plan.domain, budget, NULL));
  assert(pwrite(fd, &original, 1, at) == 1);
  loaded = lie_state_file_read(fd, &id, plan.domain, budget, NULL);
  assert(loaded);
  lie_state_destroy(&loaded);
  assert(!close(fd) && !unlink(path));
  lie_state_destroy(&state);
  lie_steering_policy_release(&dest);
  lie_steering_policy_release(&p);
  lie_steering_bank_release(&b);
}
int main(void) {
  wire_and_histories();
  parser_and_transactions();
  legacy_state();
  state_envelope();
  puts("steering metadata, transactions and RAM/SSD envelope: PASS (NOT-INFERENCE)");
  return 0;
}
