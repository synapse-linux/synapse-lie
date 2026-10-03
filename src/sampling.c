/* SPDX-License-Identifier: MIT */
/* Copyright (c) 2026 gufo contributors. */
/* Dense sampling port derived from official Gufo f783fedb, MIT.
 * See third_party/gufo-NOTICE and docs/development/C17-SAMPLING.md. */
#include "lie/sampling.h"
#include <math.h>
#include <stdbool.h>
#include <string.h>

void lie_sampling_options_init(lie_sampling_options *o) {
  if (!o) return;
  memset(o, 0, sizeof(*o));
  o->abi_version = LIE_SAMPLING_ABI;
  o->struct_bytes = sizeof(*o);
  o->top_p = 1;
  o->repeat_penalty = 1;
}
lie_sampling_status lie_sampling_options_validate(const lie_sampling_options *o) {
  if (!o || o->abi_version != LIE_SAMPLING_ABI ||
      o->struct_bytes != sizeof(*o) || !isfinite(o->temperature) ||
      o->temperature < 0 || o->top_k < 0 || !isfinite(o->top_p) ||
      o->top_p <= 0 || o->top_p > 1 || !isfinite(o->min_p) ||
      o->min_p < 0 || o->min_p > 1 || !isfinite(o->repeat_penalty) ||
      o->repeat_penalty <= 0 || !isfinite(o->frequency_penalty) ||
      !isfinite(o->presence_penalty)) return LIE_SAMPLING_INVALID;
  return LIE_SAMPLING_OK;
}
double lie_sampling_penalize(double logit, float repeat, float frequency,
                            float presence, uint32_t repeated,
                            uint32_t generated_count) {
  if (repeated && repeat != 1)
    logit = logit <= 0 ? logit * repeat : logit / repeat;
  logit -= (double)frequency * generated_count;
  if (generated_count) logit -= presence;
  return logit;
}
static lie_sampling_status validate(const lie_sampling_row *r,
                                    const lie_sampling_options *o) {
  if (lie_sampling_options_validate(o) != LIE_SAMPLING_OK || !r ||
      !r->logits || !r->count || r->count > UINT32_MAX ||
      (r->penalty_count && !r->penalties) || (r->bias_count && !r->bias) ||
      r->bias_count > r->count ||
      (r->allowed ? r->allowed_count != r->count : r->allowed_count != 0))
    return LIE_SAMPLING_INVALID;
  for (size_t i = 0; i < r->penalty_count; ++i)
    if (i && r->penalties[i-1].token >= r->penalties[i].token)
      return LIE_SAMPLING_INVALID;
  for (size_t i = 0; i < r->bias_count; ++i)
    if (!isfinite(r->bias[i])) return LIE_SAMPLING_INVALID;
  return LIE_SAMPLING_OK;
}
static double adjusted(const lie_sampling_row *r, const lie_sampling_options *o,
                       size_t token) {
  double value = r->logits[token];
  size_t lo = 0, hi = r->penalty_count;
  while (lo < hi) {
    size_t mid = lo + (hi-lo)/2;
    if (r->penalties[mid].token < token) lo = mid+1;
    else hi = mid;
  }
  if (lo < r->penalty_count && r->penalties[lo].token == token) {
    const lie_sampling_penalty *p = &r->penalties[lo];
    value = lie_sampling_penalize(value, o->repeat_penalty,
                                 o->frequency_penalty, o->presence_penalty,
                                 p->repeated, p->generated_count);
  }
  return value + (token < r->bias_count ? r->bias[token] : 0);
}
static bool eligible(const lie_sampling_row *r, size_t i) {
  return (!r->allowed || r->allowed[i]) && isfinite(r->logits[i]);
}
lie_sampling_status lie_sampling_greedy(const lie_sampling_row *r,
                                       const lie_sampling_options *o,
                                       uint32_t *token) {
  if (!token) return LIE_SAMPLING_INVALID;
  lie_sampling_status rc = validate(r, o);
  if (rc != LIE_SAMPLING_OK) return rc;
  bool found = false;
  double maximum = -INFINITY;
  uint32_t best = 0;
  /* Ordinary greedy needs no scratch allocation or penalty lookup. */
  if (!r->penalty_count && !r->bias_count) {
    float max_float = -INFINITY;
    for (size_t i = 0; i < r->count; ++i)
      if (r->logits[i] > max_float && eligible(r, i)) {
        max_float = r->logits[i]; best = (uint32_t)i; found = true;
      }
  } else for (size_t i = 0; i < r->count; ++i) {
    if (!eligible(r, i)) continue;
    double value = adjusted(r, o, i);
    if (!isfinite(value)) return LIE_SAMPLING_NONFINITE;
    if (!found || value > maximum) {
      maximum = value; best = (uint32_t)i; found = true;
    }
  }
  if (!found) return LIE_SAMPLING_NO_FINITE;
  *token = best;
  return LIE_SAMPLING_OK;
}
static lie_sampling_status reserve(lie_sampling_workspace *w, size_t n) {
  if (n > SIZE_MAX/sizeof(*w->entries)) return LIE_SAMPLING_RESOURCE;
  if (w->capacity >= n && w->entries) return LIE_SAMPLING_OK;
  if (!w->grow || w->grow(w->context, n, &w->entries, &w->capacity) ||
      !w->entries || w->capacity < n) return LIE_SAMPLING_RESOURCE;
  return LIE_SAMPLING_OK;
}
static bool better(lie_sampling_probability a, lie_sampling_probability b) {
  return a.value == b.value ? a.token < b.token : a.value > b.value;
}
static void exchange(lie_sampling_probability *a, lie_sampling_probability *b) {
  lie_sampling_probability tmp = *a; *a = *b; *b = tmp;
}
/* Root is the worst candidate. This preserves the upstream bounded top-k heap. */
static void down(lie_sampling_probability *p, size_t n, size_t root) {
  while (root < n/2) {
    size_t child = root*2+1;
    if (child+1 < n && better(p[child], p[child+1])) ++child;
    if (!better(p[root], p[child])) break;
    exchange(&p[root], &p[child]); root = child;
  }
}
static void up(lie_sampling_probability *p, size_t child) {
  while (child) {
    size_t parent = (child-1)/2;
    if (!better(p[parent], p[child])) break;
    exchange(&p[parent], &p[child]); child = parent;
  }
}
static void heap_sort(lie_sampling_probability *p, size_t n) {
  for (size_t i = n/2; i; --i) down(p, n, i-1);
  for (size_t end = n; end > 1; --end) {
    exchange(p, &p[end-1]); down(p, end-1, 0);
  }
}
static void insertion_sort(lie_sampling_probability *p, size_t n) {
  for (size_t i = 1; i < n; ++i) {
    lie_sampling_probability value = p[i];
    size_t j = i;
    while (j && better(value, p[j-1])) {
      p[j] = p[j-1]; --j;
    }
    p[j] = value;
  }
}
static void intro_sort(lie_sampling_probability *p, size_t n, unsigned depth) {
  while (n > 24) {
    if (!depth) { heap_sort(p, n); return; }
    --depth;
    size_t middle = n/2;
    if (better(p[middle], p[0])) exchange(p, &p[middle]);
    if (better(p[n-1], p[middle])) exchange(&p[middle], &p[n-1]);
    if (better(p[middle], p[0])) exchange(p, &p[middle]);
    const lie_sampling_probability pivot = p[middle];
    size_t left = 0, right = n-1;
    for (;;) {
      while (left < n && better(p[left], pivot)) ++left;
      while (right && better(pivot, p[right])) --right;
      if (left >= right) break;
      exchange(&p[left], &p[right]); ++left; --right;
    }
    /* A degenerate partition cannot cause unbounded recursion or a retry. */
    if (!left || left == n) { heap_sort(p, n); return; }
    if (left < n-left) {
      intro_sort(p, left, depth); p += left; n -= left;
    } else {
      intro_sort(p+left, n-left, depth); n = left;
    }
  }
  insertion_sort(p, n);
}
static void sort(lie_sampling_probability *p, size_t n) {
  /* Total value/token ordering is unchanged. Recurse only on the smaller
   * partition; the depth limit retains heapsort's worst-case bound. No heap
   * allocation or callback is needed, including on adversarial input. */
  unsigned depth = 0;
  for (size_t remaining = n; remaining > 1; remaining >>= 1) depth += 2;
  intro_sort(p, n, depth);
}
static lie_sampling_status select_best(const lie_sampling_row *r,
                                       const lie_sampling_options *o,
                                       lie_sampling_workspace *w, size_t limit,
                                       size_t *count) {
  lie_sampling_status rc = reserve(w, limit);
  if (rc != LIE_SAMPLING_OK) return rc;
  size_t n = 0;
  for (size_t i = 0; i < r->count; ++i) {
    if (!eligible(r, i)) continue;
    double value = adjusted(r, o, i);
    if (!isfinite(value)) return LIE_SAMPLING_NONFINITE;
    lie_sampling_probability p = {(uint32_t)i, value};
    if (n < limit) { w->entries[n] = p; up(w->entries, n++); }
    else if (better(p, w->entries[0])) {
      w->entries[0] = p; down(w->entries, n, 0);
    }
  }
  if (!n) return LIE_SAMPLING_NO_FINITE;
  sort(w->entries, n); *count = n;
  return LIE_SAMPLING_OK;
}
static lie_sampling_status select_all(const lie_sampling_row *r,
                                      const lie_sampling_options *o,
                                      lie_sampling_workspace *w, bool ranked,
                                      size_t *count, double *maximum) {
  lie_sampling_status rc = reserve(w, r->count);
  if (rc != LIE_SAMPLING_OK) return rc;
  size_t n = 0;
  for (size_t i = 0; i < r->count; ++i) {
    if (!eligible(r, i)) continue;
    double value = adjusted(r, o, i);
    if (!isfinite(value)) return LIE_SAMPLING_NONFINITE;
    w->entries[n++] = (lie_sampling_probability){(uint32_t)i, value};
    if (maximum && value > *maximum) *maximum = value;
  }
  if (!n) return LIE_SAMPLING_NO_FINITE;
  if (ranked) sort(w->entries, n);
  *count = n;
  return LIE_SAMPLING_OK;
}
static size_t minimum_kept(const lie_sampling_options *o, size_t count) {
  size_t n = o->min_keep > 1 ? o->min_keep : 1;
  return n < count ? n : count;
}
lie_sampling_status lie_sampling_build(const lie_sampling_row *r,
                                      const lie_sampling_options *o,
                                      lie_sampling_workspace *w, size_t *count) {
  if (!count) return LIE_SAMPLING_INVALID;
  *count = 0;
  if (!w || (w->capacity && !w->entries)) return LIE_SAMPLING_INVALID;
  lie_sampling_status rc = validate(r, o);
  if (rc != LIE_SAMPLING_OK) return rc;
  if (o->temperature == 0) {
    uint32_t best;
    rc = lie_sampling_greedy(r, o, &best);
    if (rc != LIE_SAMPLING_OK) return rc;
    rc = reserve(w, 1);
    if (rc != LIE_SAMPLING_OK) return rc;
    w->entries[0] = (lie_sampling_probability){best, 1}; *count = 1;
    return LIE_SAMPLING_OK;
  }
  bool linear = o->top_k == 0 && o->top_p == 1 &&
                !(o->min_p > 0 && o->min_keep > 1);
  size_t n = 0;
  double full_sum = 0, maximum = -INFINITY;
  bool has_full_sum = false;
  if (linear) {
    rc = select_all(r, o, w, false, &n, &maximum);
    if (rc != LIE_SAMPLING_OK) return rc;
  } else if (o->top_k > 0) {
    size_t limit = (size_t)o->top_k;
    if (limit < minimum_kept(o, r->count)) limit = minimum_kept(o, r->count);
    if (limit > r->count) limit = r->count;
    rc = select_best(r, o, w, limit, &n);
  } else if (o->top_p < 1 && r->count > 1024) {
    bool found = false;
    for (size_t i = 0; i < r->count; ++i) if (eligible(r, i)) {
      double value = adjusted(r, o, i);
      if (!isfinite(value)) return LIE_SAMPLING_NONFINITE;
      if (value > maximum) maximum = value;
      found = true;
    }
    if (!found) return LIE_SAMPLING_NO_FINITE;
    for (size_t i = 0; i < r->count; ++i) if (eligible(r, i))
      full_sum += exp((adjusted(r, o, i)-maximum)/o->temperature);
    if (!(full_sum > 0) || !isfinite(full_sum)) return LIE_SAMPLING_NONFINITE;
    has_full_sum = true;
    size_t limit = minimum_kept(o, r->count);
    if (limit < 256) limit = 256;
    if (limit > r->count) limit = r->count;
    rc = select_best(r, o, w, limit, &n);
    if (rc != LIE_SAMPLING_OK) return rc;
    double partial = 0;
    for (size_t i = 0; i < n; ++i)
      partial += exp((w->entries[i].value-maximum)/o->temperature);
    if (partial < (double)o->top_p*full_sum)
      rc = select_all(r, o, w, true, &n, NULL);
  } else rc = select_all(r, o, w, true, &n, NULL);
  if (rc != LIE_SAMPLING_OK) return rc;
  if (!linear) {
    maximum = w->entries[0].value;
    size_t minimum = minimum_kept(o, n);
    if (o->top_p < 1 && n > 1) {
      double sum = full_sum;
      if (!has_full_sum) {
        sum = 0;
        for (size_t i = 0; i < n; ++i)
          sum += exp((w->entries[i].value-maximum)/o->temperature);
      }
      double target = (double)o->top_p*sum, cumulative = 0;
      size_t keep = 0;
      while (keep < n) {
        cumulative += exp((w->entries[keep].value-maximum)/o->temperature);
        if (++keep >= minimum && cumulative >= target) break;
      }
      n = keep;
    }
    if (o->min_p > 0 && n > 1) {
      double threshold = maximum+(double)o->temperature*log((double)o->min_p);
      size_t keep = 0;
      while (keep < n && w->entries[keep].value >= threshold) ++keep;
      if (keep < minimum) keep = minimum;
      if (keep < n) n = keep;
    }
  }
  double threshold = linear && o->min_p > 0
    ? maximum+(double)o->temperature*log((double)o->min_p) : -INFINITY;
  double total = 0;
  for (size_t i = 0; i < n; ++i) {
    double value = w->entries[i].value;
    w->entries[i].value = value >= threshold
      ? exp((value-maximum)/o->temperature) : 0;
    total += w->entries[i].value;
  }
  if (!(total > 0) || !isfinite(total)) return LIE_SAMPLING_NONFINITE;
  size_t used = 0;
  for (size_t i = 0; i < n; ++i) {
    w->entries[i].value /= total;
    if (w->entries[i].value != 0) w->entries[used++] = w->entries[i];
  }
  *count = used;
  return LIE_SAMPLING_OK;
}
uint64_t lie_sampling_next_random(uint64_t *state) {
  if (!state) return 0;
  uint64_t value = *state ? *state : UINT64_C(0x9e3779b97f4a7c15);
  value ^= value >> 12; value ^= value << 25; value ^= value >> 27;
  *state = value;
  return value*UINT64_C(0x2545f4914f6cdd1d);
}
double lie_sampling_uniform(uint64_t *state) {
  return (double)(lie_sampling_next_random(state) >> 11)*0x1.0p-53;
}
lie_sampling_status lie_sampling_draw(const lie_sampling_probability *p, size_t n,
                                     uint64_t *state, uint32_t *out) {
  if (!p || !n || !out || (n > 1 && !state)) return LIE_SAMPLING_INVALID;
  double sum = 0;
  for (size_t i = 0; i < n; ++i) {
    if (!isfinite(p[i].value) || p[i].value < 0) return LIE_SAMPLING_INVALID;
    sum += p[i].value;
  }
  if (!(sum > 0) || !isfinite(sum) || fabs(sum-1) > 1e-8)
    return LIE_SAMPLING_INVALID;
  if (n == 1) { *out = p[0].token; return LIE_SAMPLING_OK; }
  double draw = lie_sampling_uniform(state);
  for (size_t i = 0; i < n; ++i) {
    draw -= p[i].value;
    if (draw < 0) { *out = p[i].token; return LIE_SAMPLING_OK; }
  }
  *out = p[n-1].token;
  return LIE_SAMPLING_OK;
}
