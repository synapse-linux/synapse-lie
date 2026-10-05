/* SPDX-License-Identifier: MIT */
/* Independent probability/retained-draw contracts; synthetic, NOT-INFERENCE. */
#include "lie/sampling_distribution.h"
#include <assert.h>
#include <float.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct {
  lie_sampling_workspace w;
  unsigned fail, calls;
} storage;
static int grow(void *ctx, size_t n, lie_sampling_probability **p,
                size_t *cap) {
  storage *s = ctx;
  ++s->calls;
  if (s->fail) {
    --s->fail;
    return 1;
  }
  void *next = realloc(*p, n * sizeof(**p));
  if (!next)
    return 1;
  *p = next;
  *cap = n;
  return 0;
}
static void init(storage *s) {
  memset(s, 0, sizeof(*s));
  s->w.grow = grow;
  s->w.context = s;
}
static void done(storage *s) { free(s->w.entries); }
static double uniform(uint64_t *s) {
  uint64_t v = *s ? *s : UINT64_C(0x9e3779b97f4a7c15);
  v ^= v >> 12;
  v ^= v << 25;
  v ^= v >> 27;
  *s = v;
  return (double)((v * UINT64_C(0x2545f4914f6cdd1d)) >> 11) * 0x1.0p-53;
}
static uint32_t draw(const lie_sampling_probability *p, size_t n, uint64_t *s) {
  assert(n);
  if (n == 1)
    return p[0].token;
  double u = uniform(s);
  for (size_t i = 0; i < n; ++i) {
    u -= p[i].value;
    if (u < 0)
      return p[i].token;
  }
  return p[n - 1].token;
}
static void normalization(void) {
  storage scratch;
  init(&scratch);
  size_t n = 4;
  lie_sampling_probability p[] = {{9, 1}, {3, 2}, {7, 2}, {1, 0}}, before[4];
  memcpy(before, p, sizeof(p));
  scratch.fail = 1;
  assert(lie_sampling_distribution_checked(p, &n, &scratch.w) ==
         LIE_SAMPLING_RESOURCE);
  assert(n == 4 && !memcmp(before, p, sizeof(p)));
  assert(lie_sampling_distribution_checked(p, &n, &scratch.w) ==
         LIE_SAMPLING_OK);
  assert(n == 3 && p[0].token == 3 && p[1].token == 7 && p[2].token == 9);
  assert(p[0].value == .4 && p[1].value == .4 && p[2].value == .2);
  uint32_t token = 99;
  assert(lie_sampling_distribution_best(p, n, &token) == LIE_SAMPLING_OK &&
         token == 3);
  assert(lie_sampling_distribution_probability(p, n, 7) == .4);
  assert(lie_sampling_distribution_probability(p, n, 99) == 0);
  lie_sampling_probability stable[] = {{9, 1}, {7, 2}, {3, 2}, {1, 0}};
  n = 4;
  assert(lie_sampling_distribution_stable(stable, &n, 5) == LIE_SAMPLING_OK &&
         n == 3);
  assert(stable[0].token == 9 && stable[0].value == .2 && stable[1].token == 7);
  lie_sampling_probability duplicate[] = {{1, 0}, {1, 1}};
  n = 2;
  assert(lie_sampling_distribution_checked(duplicate, &n, &scratch.w) ==
         LIE_SAMPLING_INVALID);
  assert(n == 2 && duplicate[1].value == 1);
  lie_sampling_probability zeros[] = {{1, 0}, {2, 0}};
  assert(lie_sampling_distribution_checked(zeros, &n, &scratch.w) ==
             LIE_SAMPLING_NO_FINITE &&
         n == 2);
  lie_sampling_probability invalid[] = {{1, INFINITY}, {2, -1}};
  assert(lie_sampling_distribution_checked(invalid, &n, &scratch.w) ==
             LIE_SAMPLING_INVALID &&
         n == 2);
  invalid[0].value = DBL_MAX;
  invalid[1].value = DBL_MAX;
  assert(lie_sampling_distribution_checked(invalid, &n, &scratch.w) ==
         LIE_SAMPLING_NO_FINITE);
  n = 3;
  memcpy(before, p, 3 * sizeof(*p));
  assert(lie_sampling_distribution_stable(p, &n, 0) == LIE_SAMPLING_NONFINITE);
  assert(n == 3 && !memcmp(p, before, 3 * sizeof(*p)));
  lie_sampling_workspace alias = {p, 3, NULL, NULL};
  assert(lie_sampling_distribution_checked(p, &n, &alias) ==
         LIE_SAMPLING_INVALID);
  done(&scratch);
}
static unsigned residuals(void) {
  storage draft, residual;
  init(&draft);
  init(&residual);
  unsigned transitions = 0;
  for (unsigned profile = 0; profile < 512; ++profile) {
    lie_sampling_probability target[17], expected[17];
    uint32_t ids[65];
    float probabilities[65];
    double sum = 0;
    for (unsigned i = 0; i < 17; ++i) {
      target[i] = (lie_sampling_probability){
          16 - i, (double)((profile + i * 7) % 29 + 1)};
      sum += target[i].value;
    }
    for (unsigned i = 0; i < 17; ++i)
      target[i].value /= sum;
    size_t count = profile % 66;
    for (size_t i = 0; i < count; ++i) {
      ids[i] = (uint32_t)((profile + i * 3) % 23);
      probabilities[i] = (float)((i * 7 + profile) % 13) / 64;
    }
    lie_sampling_sparse_row q = {ids, count, probabilities, count};
    size_t used = 0;
    sum = 0;
    /* Independent direct scan, original q occurrence order for every key. */
    for (unsigned i = 0; i < 17; ++i) {
      double mass = 0;
      for (size_t j = 0; j < count; ++j)
        if (ids[j] == target[i].token)
          mass += probabilities[j];
      double v = target[i].value - mass;
      if (v > 0) {
        expected[used++] = (lie_sampling_probability){target[i].token, v};
        sum += v;
      }
    }
    if (used)
      for (size_t i = 0; i < used; ++i)
        expected[i].value /= sum;
    size_t actual = 99;
    lie_sampling_status rc = lie_sampling_distribution_residual(
        target, 17, &q, &draft.w, &residual.w, &actual);
    assert(rc == (used ? LIE_SAMPLING_OK : LIE_SAMPLING_NO_FINITE) &&
           actual == used);
    for (size_t i = 0; i < used; ++i)
      assert(expected[i].token == residual.w.entries[i].token &&
             expected[i].value == residual.w.entries[i].value);
    for (unsigned seed = 0; seed < 4; ++seed) {
      uint64_t a = seed, b = seed;
      uint32_t token = 999;
      uint32_t expected_token =
          draw(used ? expected : target, used ? used : 17, &b);
      assert(lie_sampling_distribution_residual_draw(target, 17, &q, &draft.w,
                                                     &residual.w, &a, &token) ==
             LIE_SAMPLING_OK);
      assert(a == b && token == expected_token);
      ++transitions;
    }
  }
  done(&draft);
  done(&residual);
  return transitions;
}
static unsigned proposals(void) {
  const lie_sampling_probability p[] = {{2, .3}, {0, .4}, {1, .3}};
  const uint32_t mapping[] = {10, 11, 12};
  uint32_t ids[3];
  float probabilities[3];
  lie_sampling_proposal q;
  lie_sampling_proposal_init(&q);
  q.ids = ids;
  q.probabilities = probabilities;
  q.capacity = 3;
  unsigned transitions = 0;
  for (unsigned seed = 0; seed < 256; ++seed) {
    uint64_t a = seed, b = seed;
    uint32_t mass[] = {(uint32_t)floor(.3 * LIE_PROPOSAL_UNITS),
                       (uint32_t)floor(.4 * LIE_PROPOSAL_UNITS),
                       (uint32_t)floor(.3 * LIE_PROPOSAL_UNITS)};
    mass[0] += LIE_PROPOSAL_UNITS - mass[0] - mass[1] - mass[2];
    uint32_t value = (uint32_t)(uniform(&b) * LIE_PROPOSAL_UNITS), sum = 0,
             chosen = 0;
    for (unsigned i = 0; i < 3; ++i) {
      sum += mass[i];
      if (value < sum) {
        chosen = i;
        break;
      }
    }
    assert(lie_sampling_proposal_quantize(p, 3, mapping, 3, &a, &q) ==
           LIE_SAMPLING_OK);
    assert(a == b && q.count == 3 && q.token == mapping[p[chosen].token] &&
           q.probability == (float)mass[chosen] / LIE_PROPOSAL_UNITS);
    double total = 0;
    for (unsigned i = 0; i < 3; ++i) {
      assert(ids[i] == mapping[p[i].token] &&
             probabilities[i] == (float)mass[i] / LIE_PROPOSAL_UNITS);
      total += probabilities[i];
    }
    assert(total == 1);
    ++transitions;
  }
  const lie_sampling_probability one = {1, 1};
  uint64_t a = 0, b = 0;
  (void)uniform(&b);
  assert(lie_sampling_proposal_quantize(&one, 1, NULL, 0, &a, &q) ==
             LIE_SAMPLING_OK &&
         a == b && a != 0);
  assert(q.count == 1 && q.token == 1 && q.probability == 1);
  storage draft, residual;
  init(&draft);
  init(&residual);
  const uint32_t draft_ids[] = {0, 1, 2};
  const float draft_probabilities[] = {.125f, .125f, .75f};
  lie_sampling_proposal_view view;
  lie_sampling_proposal_view_init(&view);
  view.ids = draft_ids;
  view.probabilities = draft_probabilities;
  view.count = 3;
  view.token = 2;
  view.probability = .75f;
  unsigned accepts = 0, rejects = 0;
  for (unsigned seed = 0; seed < 512; ++seed) {
    a = seed;
    b = seed;
    bool expected_accept = uniform(&b) * .75 < .3;
    uint32_t expected = 2;
    if (!expected_accept) {
      lie_sampling_probability correction[] = {{0, .4 - .125}, {1, .3 - .125}};
      double total = correction[0].value + correction[1].value;
      correction[0].value /= total;
      correction[1].value /= total;
      expected = draw(correction, 2, &b);
      ++rejects;
    } else
      ++accepts;
    bool accepted = false;
    uint32_t token = 999;
    assert(lie_sampling_proposal_verify(p, 3, 3, &view, &draft.w, &residual.w,
                                        &a, &token,
                                        &accepted) == LIE_SAMPLING_OK);
    assert(accepted == expected_accept && token == expected && a == b);
    ++transitions;
  }
  assert(accepts && rejects);
  /* A refused rejection publishes neither acceptance draw nor correction. */
  storage refused_draft, refused_residual;
  init(&refused_draft);
  init(&refused_residual);
  unsigned seed = 0;
  for (;; ++seed) {
    b = seed;
    if (uniform(&b) * .75 >= .3)
      break;
  }
  a = seed;
  uint32_t token = 999;
  bool accepted = true;
  refused_draft.fail = 1;
  assert(lie_sampling_proposal_verify(p, 3, 3, &view, &refused_draft.w,
                                      &refused_residual.w, &a, &token,
                                      &accepted) == LIE_SAMPLING_RESOURCE);
  assert(a == seed && token == 999 && accepted);
  view.probability = .5f;
  assert(lie_sampling_proposal_verify(p, 3, 3, &view, &draft.w, &residual.w, &a,
                                      &token,
                                      &accepted) == LIE_SAMPLING_INVALID);
  assert(a == seed && token == 999 && accepted);
  lie_sampling_proposal saved = q;
  uint32_t old_ids[3];
  float old_probabilities[3];
  memcpy(old_ids, ids, sizeof(ids));
  memcpy(old_probabilities, probabilities, sizeof(probabilities));
  const lie_sampling_probability invalid[] = {{0, .75}, {1, .75}};
  assert(lie_sampling_proposal_quantize(invalid, 2, NULL, 0, &a, &q) ==
         LIE_SAMPLING_INVALID);
  assert(!memcmp(&q, &saved, sizeof(q)) && !memcmp(old_ids, ids, sizeof(ids)) &&
         !memcmp(old_probabilities, probabilities, sizeof(probabilities)) &&
         a == seed);
  done(&refused_draft);
  done(&refused_residual);
  done(&draft);
  done(&residual);
  return transitions;
}
static void ranked(void) {
  storage entries, scratch;
  init(&entries);
  init(&scratch);
  lie_sampling_ranked_row row;
  lie_sampling_ranked_row_init(&row);
  const float logits[] = {1, -1, 0, 1};
  const uint32_t ids[] = {11, 9, 11, 8};
  const lie_sampling_penalty penalties[] = {{9, 2, 0}, {11, 1, 1}};
  row.logits = logits;
  row.count = 4;
  row.token_ids = ids;
  row.token_id_count = 4;
  row.penalties = penalties;
  row.penalty_count = 2;
  lie_sampling_options o;
  lie_sampling_options_init(&o);
  o.temperature = 1;
  o.repeat_penalty = 2;
  o.frequency_penalty = .25f;
  o.presence_penalty = .5f;
  size_t n = 999;
  entries.fail = 1;
  assert(lie_sampling_distribution_ranked(&row, &o, &entries.w, &scratch.w,
                                          &n) == LIE_SAMPLING_RESOURCE &&
         n == 0);
  assert(lie_sampling_distribution_ranked(&row, &o, &entries.w, &scratch.w,
                                          &n) == LIE_SAMPLING_OK &&
         n == 4);
  /* Hand-adjusted logits: -.25,-2,-.75,1; rank IDs3,0,2,1. */
  const uint32_t expected_ids[] = {3, 0, 2, 1};
  const double adjusted[] = {1, -.25, -.75, -2};
  double expected[4], total = 0;
  for (unsigned i = 0; i < 4; ++i) {
    expected[i] = exp(adjusted[i] - 1);
    total += expected[i];
  }
  double second = 0;
  for (unsigned i = 0; i < 4; ++i) {
    expected[i] /= total;
    second += expected[i];
  }
  for (unsigned i = 0; i < 4; ++i)
    assert(entries.w.entries[i].token == expected_ids[i] &&
           entries.w.entries[i].value == expected[i] / second);
  o.top_p = .5f;
  scratch.fail = 1;
  assert(lie_sampling_distribution_ranked(&row, &o, &entries.w, &scratch.w,
                                          &n) == LIE_SAMPLING_RESOURCE &&
         n == 0);
  assert(lie_sampling_distribution_ranked(&row, &o, &entries.w, &scratch.w,
                                          &n) == LIE_SAMPLING_OK &&
         n == 1 && entries.w.entries[0].token == 3);
  o.temperature = 0;
  o.top_k = 1;
  o.min_keep = 4;
  assert(lie_sampling_distribution_ranked(&row, &o, &entries.w, &scratch.w,
                                          &n) == LIE_SAMPLING_OK &&
         n == 1 && entries.w.entries[0].token == 3);
  row.token_id_count = 3;
  assert(lie_sampling_distribution_ranked(&row, &o, &entries.w, &scratch.w,
                                          &n) == LIE_SAMPLING_INVALID &&
         n == 0);
  row.token_id_count = 4;
  ++row.abi_version;
  assert(lie_sampling_distribution_ranked(&row, &o, &entries.w, &scratch.w,
                                          &n) == LIE_SAMPLING_INVALID &&
         n == 0);
  done(&entries);
  done(&scratch);
}
static void refusals(void) {
  const lie_sampling_probability target[] = {{0, .75}, {1, .25}};
  const uint32_t ids[] = {0, 1};
  float probabilities[] = {.5f, .5f};
  lie_sampling_sparse_row q = {ids, 2, probabilities, 2};
  storage draft, residual;
  init(&draft);
  init(&residual);
  uint64_t rng = 17;
  uint32_t token = 999;
  /* Reject sparse geometry and values without consuming a draw. */
  q.probability_count = 1;
  assert(lie_sampling_distribution_residual_draw(target, 2, &q, &draft.w,
                                                &residual.w, &rng, &token) ==
         LIE_SAMPLING_INVALID);
  q.probability_count = 2;
  for (unsigned i = 0; i < 3; ++i) {
    probabilities[0] = i == 0 ? -1 : i == 1 ? NAN : INFINITY;
    assert(lie_sampling_distribution_residual_draw(target, 2, &q, &draft.w,
                                                  &residual.w, &rng, &token) ==
           LIE_SAMPLING_INVALID);
  }
  probabilities[0] = .5f;
  /* The second allocation may refuse after draft scratch has been populated. */
  residual.fail = 1;
  assert(lie_sampling_distribution_residual_draw(target, 2, &q, &draft.w,
                                                &residual.w, &rng, &token) ==
         LIE_SAMPLING_RESOURCE);
  assert(rng == 17 && token == 999 && draft.w.entries);
  size_t count = 99;
  assert(lie_sampling_distribution_residual(target, 2, &q, &draft.w, &draft.w,
                                           &count) == LIE_SAMPLING_INVALID &&
         count == 0);
  lie_sampling_probability live[] = {{0, .75}, {1, .25}}, saved[2];
  memcpy(saved, live, sizeof(live));
  lie_sampling_workspace alias = {live, 2, NULL, NULL};
  assert(lie_sampling_distribution_residual_draw(live, 2, &q, &draft.w, &alias,
                                                &rng, &token) ==
         LIE_SAMPLING_INVALID);
  assert(rng == 17 && token == 999 && !memcmp(live, saved, sizeof(live)));
  uint32_t out_ids[2] = {99, 98};
  float out_probabilities[2] = {-1, -2};
  lie_sampling_proposal out;
  lie_sampling_proposal_init(&out);
  out.ids = out_ids;
  out.probabilities = out_probabilities;
  out.capacity = 2;
  /* A too-short token map cannot publish a partial proposal. */
  assert(lie_sampling_proposal_quantize(target, 2, ids, 1, &rng, &out) ==
         LIE_SAMPLING_INVALID);
  assert(rng == 17 && !out.count && out_ids[0] == 99 &&
         out_probabilities[0] == -1);
  /* The remapping source must not overlap the mutable proposal output. */
  assert(lie_sampling_proposal_quantize(target, 2, out_ids, 2, &rng, &out) ==
         LIE_SAMPLING_INVALID);
  assert(rng == 17 && !out.count && out_ids[0] == 99 &&
         out_probabilities[0] == -1);
  lie_sampling_proposal_view view;
  lie_sampling_proposal_view_init(&view);
  view.ids = ids;
  view.probabilities = probabilities;
  view.count = 2;
  view.token = 0;
  view.probability = .5f;
  assert(lie_sampling_proposal_validate(&view, 2) == LIE_SAMPLING_OK);
  assert(lie_sampling_proposal_validate(&view, 1) == LIE_SAMPLING_INVALID);
  ++view.abi_version;
  bool accepted = true;
  assert(lie_sampling_proposal_verify(target, 2, 2, &view, &draft.w, &residual.w,
                                      &rng, &token, &accepted) ==
         LIE_SAMPLING_INVALID);
  assert(rng == 17 && token == 999 && accepted);
  done(&draft);
  done(&residual);
}
int main(void) {
  normalization();
  ranked();
  refusals();
  unsigned r = residuals(), p = proposals();
  printf("Distribution/residual/proposal contracts PASS: %u residual draws, %u "
         "proposal/verification draws; NOT-INFERENCE\n",
         r, p);
}
