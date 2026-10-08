/* SPDX-License-Identifier: MIT */
/* Independent FIFO/count oracle and allocation refusals; NOT-INFERENCE. */
#include "lie/sampling_history.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
enum { VOCAB = 67, WINDOW = 129 };
typedef struct {
  lie_sampling_history state;
  unsigned fail_tokens, fail_penalties, calls;
} storage;
static int tokens_grow(void *ctx, size_t n, uint32_t **p, size_t *cap) {
  storage *b = ctx;
  ++b->calls;
  if (b->fail_tokens) {
    --b->fail_tokens;
    return 1;
  }
  void *next = realloc(*p, n * sizeof(**p));
  if (!next)
    return 1;
  *p = next;
  *cap = n;
  return 0;
}
static int penalties_grow(void *ctx, size_t n, lie_sampling_penalty **p,
                          size_t *cap) {
  storage *b = ctx;
  ++b->calls;
  if (b->fail_penalties) {
    --b->fail_penalties;
    return 1;
  }
  void *next = realloc(*p, n * sizeof(**p));
  if (!next)
    return 1;
  *p = next;
  *cap = n;
  return 0;
}
static void init(storage *b) {
  memset(b, 0, sizeof(*b));
  b->state.grow_tokens = tokens_grow;
  b->state.grow_penalties = penalties_grow;
  b->state.context = b;
}
static void destroy(storage *b) {
  free(b->state.tokens);
  free(b->state.penalties);
}
typedef struct {
  uint32_t fifo[WINDOW], counts[VOCAB];
  size_t size;
} oracle;
static void oracle_input(oracle *r, const lie_sampling_history_options *o,
                         const uint32_t *input, size_t n, bool reset) {
  if (reset)
    memset(r, 0, sizeof(*r));
  for (size_t i = 0; i < n; ++i) {
    if (!reset && o->generated)
      ++r->counts[input[i]];
    if (!o->repeat_last_n)
      continue;
    if (r->size == o->repeat_last_n) {
      memmove(r->fifo, r->fifo + 1, (--r->size) * sizeof(*r->fifo));
    }
    r->fifo[r->size++] = input[i];
  }
}
static void check(const storage *b, const oracle *r,
                  const lie_sampling_history_options *o) {
  assert(b->state.token_count == r->size);
  if (r->size)
    assert(!memcmp(b->state.tokens, r->fifo, r->size * sizeof(*r->fifo)));
  size_t index = 0;
  for (uint32_t token = 0; token < VOCAB; ++token) {
    bool repeated = false;
    if (o->repetition)
      for (size_t j = 0; j < r->size; ++j)
        repeated |= r->fifo[j] == token;
    if (!r->counts[token] && !repeated)
      continue;
    assert(index < b->state.penalty_count);
    const lie_sampling_penalty *p = b->state.penalties + index++;
    assert(p->token == token && p->generated_count == r->counts[token]);
    assert(p->repeated == (uint32_t)repeated);
  }
  assert(index == b->state.penalty_count);
}
static unsigned random_step(unsigned *x) {
  *x = *x * 1664525u + 1013904223u;
  return *x;
}
static unsigned oracle_cases(void) {
  const size_t windows[] = {0, 1, 2, 8, 64, WINDOW};
  unsigned steps = 0, rng = 773;
  for (unsigned flags = 0; flags < 4; ++flags)
    for (size_t w = 0; w < sizeof(windows) / sizeof(*windows); ++w) {
      storage b, cloned;
      init(&b);
      init(&cloned);
      oracle r = {0};
      lie_sampling_history_options o;
      lie_sampling_history_options_init(&o);
      o.generated = flags & 1;
      o.repetition = flags & 2;
      o.repeat_last_n = windows[w];
      for (unsigned step = 0; step < 600; ++step) {
        uint32_t input[257];
        size_t n = step % 6 == 0   ? 257
                   : step % 6 == 1 ? 33
                   : step % 6 == 2 ? 8
                   : step % 6 == 3 ? 1
                   : step % 6 == 4 ? 0
                                   : 32;
        for (size_t i = 0; i < n; ++i)
          input[i] = random_step(&rng) % VOCAB;
        bool reset = step % 17 == 0;
        assert((reset ? lie_sampling_history_reset(&o, &b.state, input, n)
                      : lie_sampling_history_accept(&o, &b.state, input, n)) ==
               LIE_HISTORY_OK);
        oracle_input(&r, &o, input, n, reset);
        check(&b, &r, &o);
        ++steps;
        if (step % 19 == 0) {
          assert(lie_sampling_history_copy(&o, &cloned.state, &b.state) ==
                 LIE_HISTORY_OK);
          check(&cloned, &r, &o);
          assert(lie_sampling_history_copy(&o, &cloned.state, &cloned.state) ==
                 LIE_HISTORY_OK);
          const uint32_t token = 9;
          assert(lie_sampling_history_accept(&o, &cloned.state, &token, 1) ==
                 LIE_HISTORY_OK);
          check(&b, &r, &o); /* Original stays independent. */
        }
      }
      destroy(&cloned);
      destroy(&b);
    }
  return steps;
}
typedef struct {
  uint32_t tokens[16];
  lie_sampling_penalty penalties[16];
  size_t token_count, penalty_count;
} snapshot;
static snapshot save(const storage *b) {
  snapshot s = {.token_count = b->state.token_count,
                .penalty_count = b->state.penalty_count};
  assert(s.token_count <= 16 && s.penalty_count <= 16);
  if (s.token_count)
    memcpy(s.tokens, b->state.tokens, s.token_count * sizeof(*s.tokens));
  if (s.penalty_count)
    memcpy(s.penalties, b->state.penalties,
           s.penalty_count * sizeof(*s.penalties));
  return s;
}
static void unchanged(const storage *b, const snapshot *s) {
  assert(b->state.token_count == s->token_count &&
         b->state.penalty_count == s->penalty_count);
  if (s->token_count)
    assert(!memcmp(b->state.tokens, s->tokens,
                   s->token_count * sizeof(*s->tokens)));
  if (s->penalty_count)
    assert(!memcmp(b->state.penalties, s->penalties,
                   s->penalty_count * sizeof(*s->penalties)));
}
static void failures(void) {
  storage b, dst;
  init(&b);
  init(&dst);
  lie_sampling_history_options o;
  lie_sampling_history_options_init(&o);
  o.generated = true;
  o.repetition = true;
  o.repeat_last_n = 8;
  const uint32_t prompt[] = {2, 4}, incoming[] = {4, 5, 6, 4};
  assert(lie_sampling_history_reset(&o, &b.state, prompt, 2) == LIE_HISTORY_OK);
  snapshot s = save(&b);
  const uint32_t reset_input[] = {9, 10, 11, 12, 13, 14, 15, 16};
  b.fail_penalties = 1;
  assert(lie_sampling_history_reset(&o, &b.state, reset_input, 8) ==
         LIE_HISTORY_RESOURCE);
  unchanged(&b, &s);
  b.fail_tokens = 1;
  assert(lie_sampling_history_reset(&o, &b.state, reset_input, 8) ==
         LIE_HISTORY_RESOURCE);
  unchanged(&b, &s);
  b.fail_penalties = 1;
  /* Force growth despite scratch capacity retained by the refused reset. */
  uint32_t large[33];
  for (size_t i = 0; i < 33; ++i)
    large[i] = (uint32_t)i;
  assert(lie_sampling_history_accept(&o, &b.state, large, 33) ==
         LIE_HISTORY_RESOURCE);
  unchanged(&b, &s);
  assert(!b.fail_penalties);
  const uint32_t new_token = 19;
  o.max_penalties = 2;
  assert(lie_sampling_history_accept(&o, &b.state, &new_token, 1) ==
         LIE_HISTORY_RESOURCE);
  unchanged(&b, &s);
  assert(lie_sampling_history_reset(&o, &b.state, reset_input, 8) ==
         LIE_HISTORY_RESOURCE);
  unchanged(&b, &s);
  o.max_penalties = UINT32_MAX;
  b.fail_tokens = 1;
  assert(lie_sampling_history_accept(&o, &b.state, incoming, 4) ==
         LIE_HISTORY_RESOURCE);
  unchanged(&b, &s);
  o.max_penalties = 2;
  assert(lie_sampling_history_accept(&o, &b.state, incoming, 4) ==
         LIE_HISTORY_RESOURCE);
  unchanged(&b, &s);
  o.max_penalties = UINT32_MAX;
  o.max_batch_tokens = 1;
  assert(lie_sampling_history_accept(&o, &b.state, incoming, 4) ==
         LIE_HISTORY_RESOURCE);
  unchanged(&b, &s);
  o.max_batch_tokens = UINT32_MAX;
  assert(lie_sampling_history_accept(&o, &b.state, b.state.tokens, 1) ==
         LIE_HISTORY_INVALID);
  assert(lie_sampling_history_reset(&o, &b.state, NULL, 1) ==
         LIE_HISTORY_INVALID);
  lie_sampling_history_options bad = o;
  ++bad.abi_version;
  assert(lie_sampling_history_accept(&bad, &b.state, incoming, 1) ==
         LIE_HISTORY_INVALID);
  unchanged(&b, &s);
  /* Reset may adopt a smaller window/budget without rejecting the old state. */
  o.repeat_last_n = 1;
  o.max_penalties = 1;
  assert(lie_sampling_history_reset(&o, &b.state, prompt, 2) == LIE_HISTORY_OK);
  assert(b.state.token_count == 1 && b.state.tokens[0] == 4);
  assert(b.state.penalty_count == 1 && !b.state.penalties[0].generated_count);
  o.repeat_last_n = 8;
  o.max_penalties = UINT32_MAX;
  b.state.penalties[0].generated_count = UINT32_MAX;
  s = save(&b);
  assert(lie_sampling_history_accept(&o, &b.state, incoming, 1) ==
         LIE_HISTORY_OVERFLOW);
  assert(lie_sampling_history_accept(&o, &b.state, incoming, 4) ==
         LIE_HISTORY_OVERFLOW);
  unchanged(&b, &s);
  snapshot empty = save(&dst);
  dst.fail_tokens = 1;
  assert(lie_sampling_history_copy(&o, &dst.state, &b.state) ==
         LIE_HISTORY_RESOURCE);
  unchanged(&dst, &empty);
  dst.fail_penalties = 1;
  assert(lie_sampling_history_copy(&o, &dst.state, &b.state) ==
         LIE_HISTORY_RESOURCE);
  unchanged(&dst, &empty);
  assert(lie_sampling_history_copy(&o, &dst.state, &b.state) == LIE_HISTORY_OK);
  unchanged(&dst, &s);
  lie_sampling_history alias = b.state;
  assert(lie_sampling_history_copy(&o, &alias, &b.state) ==
         LIE_HISTORY_INVALID);
  alias.penalties = (lie_sampling_penalty *)alias.tokens;
  assert(lie_sampling_history_accept(&o, &alias, incoming, 1) ==
         LIE_HISTORY_INVALID);
  b.state.penalties[0].generated_count = 3;
  assert(lie_sampling_history_reset(&o, &b.state, prompt, 2) == LIE_HISTORY_OK);
  assert(!b.state.penalties[0].generated_count);
  /* Single-token path evicts a prompt-only entry before enforcing the cap. */
  o.generated = false;
  o.repeat_last_n = 1;
  o.max_penalties = 1;
  assert(lie_sampling_history_reset(&o, &b.state, prompt, 2) == LIE_HISTORY_OK);
  const uint32_t high = UINT32_MAX;
  unsigned calls = b.calls;
  assert(lie_sampling_history_accept(&o, &b.state, &high, 1) == LIE_HISTORY_OK);
  assert(b.state.penalties[0].token == high && b.calls == calls);
  assert(lie_sampling_history_accept(&o, &b.state, &high, 1) == LIE_HISTORY_OK);
  assert(b.state.penalties[0].repeated == 1 &&
         !b.state.penalties[0].generated_count);
  destroy(&dst);
  destroy(&b);
  storage zero;
  init(&zero);
  lie_sampling_history_options_init(&o);
  o.repeat_last_n = 0;
  o.repetition = true;
  o.max_penalties = 0;
  zero.state.grow_tokens = NULL;
  zero.state.grow_penalties = NULL;
  assert(lie_sampling_history_accept(&o, &zero.state, incoming, 4) ==
         LIE_HISTORY_OK);
  assert(!zero.state.token_count && !zero.state.penalty_count && !zero.calls);
  o.repeat_last_n = 1;
  assert(lie_sampling_history_accept(&o, &zero.state, incoming, 1) ==
         LIE_HISTORY_RESOURCE);
  assert(!zero.state.token_count && !zero.state.penalty_count && !zero.calls);
}
int main(void) {
  unsigned steps = oracle_cases();
  failures();
  printf("Sampling history: %u FIFO/count oracle transitions and "
         "refusal/clone/overflow checks PASS; NOT-INFERENCE\n",
         steps);
}
