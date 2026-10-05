/* SPDX-License-Identifier: MIT */
/* Copyright (c) 2026 gufo contributors. */
/* Probability port from independently fetched official Gufo f783fedb, MIT.
 * See third_party/gufo-NOTICE and docs/development/C17-SAMPLING.md. */
#include "lie/sampling_distribution.h"
#include <math.h>
#include <string.h>

static bool span(const void *p, size_t n, size_t width) {
  return n <= SIZE_MAX / width && (!n || p);
}
static bool overlap(const void *a, size_t an, const void *b, size_t bn) {
  if (!an || !bn)
    return false;
  uintptr_t x = (uintptr_t)a, y = (uintptr_t)b;
  return x > UINTPTR_MAX - an || y > UINTPTR_MAX - bn ||
         (x < y + bn && y < x + an);
}
static bool workspace(const lie_sampling_workspace *w) {
  return w && span(w->entries, w->capacity, sizeof(*w->entries));
}
static bool aliases(const lie_sampling_workspace *w, const void *p,
                    size_t bytes) {
  return overlap(w->entries, w->capacity * sizeof(*w->entries), p, bytes);
}
static bool separated(const lie_sampling_workspace *a,
                      const lie_sampling_workspace *b) {
  return a != b && !aliases(a, b->entries, b->capacity * sizeof(*b->entries));
}
static lie_sampling_status reserve(lie_sampling_workspace *w, size_t n) {
  if (n > SIZE_MAX / sizeof(*w->entries))
    return LIE_SAMPLING_RESOURCE;
  if (n <= w->capacity)
    return LIE_SAMPLING_OK;
  lie_sampling_probability *p = w->entries;
  size_t cap = w->capacity;
  if (!w->grow || w->grow(w->context, n, &p, &cap) ||
      !span(p, cap, sizeof(*p)) || cap < n)
    return LIE_SAMPLING_RESOURCE;
  w->entries = p;
  w->capacity = cap;
  return LIE_SAMPLING_OK;
}
static bool better(lie_sampling_probability a, lie_sampling_probability b,
                   bool keys) {
  if (keys)
    return a.token == b.token ? a.value < b.value : a.token < b.token;
  return a.value == b.value ? a.token < b.token : a.value > b.value;
}
static void exchange(lie_sampling_probability *a, lie_sampling_probability *b) {
  lie_sampling_probability p = *a;
  *a = *b;
  *b = p;
}
static void sift(lie_sampling_probability *p, size_t n, size_t root,
                 bool keys) {
  while (root < n / 2) {
    size_t child = root * 2 + 1;
    if (child + 1 < n && better(p[child], p[child + 1], keys))
      ++child;
    if (!better(p[root], p[child], keys))
      return;
    exchange(p + root, p + child);
    root = child;
  }
}
static void sort(lie_sampling_probability *p, size_t n, bool keys) {
  if (n <= 24) {
    for (size_t i = 1; i < n; ++i) {
      lie_sampling_probability v = p[i];
      size_t j = i;
      while (j && better(v, p[j - 1], keys)) {
        p[j] = p[j - 1];
        --j;
      }
      p[j] = v;
    }
    return;
  }
  for (size_t root = n / 2; root;)
    sift(p, n, --root, keys);
  for (size_t end = n; end > 1;) {
    exchange(p, p + --end);
    sift(p, end, 0, keys);
  }
}
void lie_sampling_ranked_row_init(lie_sampling_ranked_row *r) {
  if (r)
    *r = (lie_sampling_ranked_row){.abi_version = LIE_DISTRIBUTION_ABI,
                                   .struct_bytes = sizeof(*r)};
}
void lie_sampling_proposal_init(lie_sampling_proposal *p) {
  if (p)
    *p = (lie_sampling_proposal){.abi_version = LIE_DISTRIBUTION_ABI,
                                 .struct_bytes = sizeof(*p)};
}
void lie_sampling_proposal_view_init(lie_sampling_proposal_view *p) {
  if (p)
    *p = (lie_sampling_proposal_view){.abi_version = LIE_DISTRIBUTION_ABI,
                                      .struct_bytes = sizeof(*p)};
}
static bool values(const lie_sampling_probability *p, size_t n, double *sum) {
  if (!span(p, n, sizeof(*p)) || n > UINT32_MAX)
    return false;
  *sum = 0;
  for (size_t i = 0; i < n; ++i) {
    if (!isfinite(p[i].value) || p[i].value < 0)
      return false;
    *sum += p[i].value;
  }
  return true;
}
static void normalize(lie_sampling_probability *p, size_t *n, double total) {
  for (size_t i = 0; i < *n; ++i)
    p[i].value /= total;
  size_t used = 0;
  for (size_t i = 0; i < *n; ++i)
    if (p[i].value != 0)
      p[used++] = p[i];
  *n = used;
}
lie_sampling_status
lie_sampling_distribution_stable(lie_sampling_probability *p, size_t *n,
                                 double total) {
  double sum;
  if (!n || !values(p, *n, &sum))
    return LIE_SAMPLING_INVALID;
  if (!(total > 0) || !isfinite(total))
    return LIE_SAMPLING_NONFINITE;
  for (size_t i = 0; i < *n; ++i)
    if (!isfinite(p[i].value / total))
      return LIE_SAMPLING_NONFINITE;
  normalize(p, n, total);
  return LIE_SAMPLING_OK;
}
lie_sampling_status
lie_sampling_distribution_checked(lie_sampling_probability *p, size_t *n,
                                  lie_sampling_workspace *s) {
  double total;
  if (!n || !*n || !values(p, *n, &total) || !workspace(s) ||
      aliases(s, p, *n * sizeof(*p)))
    return LIE_SAMPLING_INVALID;
  if (*n > 1) {
    lie_sampling_status rc = reserve(s, *n);
    if (rc != LIE_SAMPLING_OK)
      return rc;
    for (size_t i = 0; i < *n; ++i)
      s->entries[i] = (lie_sampling_probability){p[i].token, (double)i};
    sort(s->entries, *n, true);
    for (size_t i = 1; i < *n; ++i)
      if (s->entries[i - 1].token == s->entries[i].token)
        return LIE_SAMPLING_INVALID;
  }
  if (!(total > 0) || !isfinite(total))
    return LIE_SAMPLING_NO_FINITE;
  normalize(p, n, total);
  sort(p, *n, false);
  return LIE_SAMPLING_OK;
}
lie_sampling_status
lie_sampling_distribution_best(const lie_sampling_probability *p, size_t n,
                               uint32_t *out) {
  double total;
  if (!out || !n || !values(p, n, &total))
    return LIE_SAMPLING_INVALID;
  size_t best = 0;
  for (size_t i = 1; i < n; ++i)
    if (better(p[i], p[best], false))
      best = i;
  *out = p[best].token;
  return LIE_SAMPLING_OK;
}
double lie_sampling_distribution_probability(const lie_sampling_probability *p,
                                             size_t n, uint32_t token) {
  if (!span(p, n, sizeof(*p)))
    return 0;
  for (size_t i = 0; i < n; ++i)
    if (p[i].token == token)
      return p[i].value;
  return 0;
}
static size_t lower(const lie_sampling_penalty *p, size_t n, uint32_t token) {
  size_t lo = 0;
  while (lo < n) {
    size_t mid = lo + (n - lo) / 2;
    if (p[mid].token < token)
      lo = mid + 1;
    else
      n = mid;
  }
  return lo;
}
static size_t minimum(const lie_sampling_options *o, size_t n) {
  size_t keep = o->min_keep > 1 ? o->min_keep : 1;
  return keep < n ? keep : n;
}
lie_sampling_status lie_sampling_distribution_ranked(
    const lie_sampling_ranked_row *r, const lie_sampling_options *o,
    lie_sampling_workspace *w, lie_sampling_workspace *s, size_t *count) {
  if (!count)
    return LIE_SAMPLING_INVALID;
  *count = 0;
  if (lie_sampling_options_validate(o) != LIE_SAMPLING_OK || !r ||
      r->abi_version != LIE_DISTRIBUTION_ABI || r->struct_bytes != sizeof(*r) ||
      !r->count || r->count > UINT32_MAX ||
      !span(r->logits, r->count, sizeof(*r->logits)) ||
      (r->token_ids ? r->token_id_count != r->count : r->token_id_count != 0) ||
      !span(r->penalties, r->penalty_count, sizeof(*r->penalties)) ||
      !workspace(w) || !workspace(s) || !separated(w, s))
    return LIE_SAMPLING_INVALID;
  for (size_t i = 1; i < r->penalty_count; ++i)
    if (r->penalties[i - 1].token >= r->penalties[i].token)
      return LIE_SAMPLING_INVALID;
  const lie_sampling_workspace *buffers[] = {w, s};
  for (size_t i = 0; i < 2; ++i)
    if (aliases(buffers[i], r->logits, r->count * sizeof(*r->logits)) ||
        aliases(buffers[i], r->token_ids,
                r->token_id_count * sizeof(*r->token_ids)) ||
        aliases(buffers[i], r->penalties,
                r->penalty_count * sizeof(*r->penalties)))
      return LIE_SAMPLING_INVALID;
  lie_sampling_status rc = reserve(w, r->count);
  if (rc != LIE_SAMPLING_OK)
    return rc;
  size_t n = 0;
  for (size_t i = 0; i < r->count; ++i) {
    if (!isfinite(r->logits[i]))
      continue;
    double value = r->logits[i];
    uint32_t token = r->token_ids ? r->token_ids[i] : (uint32_t)i;
    size_t at = lower(r->penalties, r->penalty_count, token);
    if (at < r->penalty_count && r->penalties[at].token == token) {
      const lie_sampling_penalty *p = r->penalties + at;
      value = lie_sampling_penalize(value, o->repeat_penalty,
                                    o->frequency_penalty, o->presence_penalty,
                                    p->repeated, p->generated_count);
    }
    if (!isfinite(value))
      return LIE_SAMPLING_NONFINITE;
    w->entries[n++] = (lie_sampling_probability){(uint32_t)i, value};
  }
  if (!n)
    return LIE_SAMPLING_NO_FINITE;
  sort(w->entries, n, false);
  if (o->top_k > 0) {
    size_t keep = (size_t)o->top_k;
    if (keep < minimum(o, n))
      keep = minimum(o, n);
    if (keep < n)
      n = keep;
  }
  if (o->temperature == 0) {
    w->entries[0].value = 1;
    *count = 1;
    return LIE_SAMPLING_OK;
  }
  double maximum = w->entries[0].value;
  if (o->top_p < 1 && n > 1) {
    rc = reserve(s, n);
    if (rc != LIE_SAMPLING_OK)
      return rc;
    double total = 0;
    for (size_t i = 0; i < n; ++i) {
      s->entries[i].value =
          exp((w->entries[i].value - maximum) / (double)o->temperature);
      total += s->entries[i].value;
    }
    if (!(total > 0) || !isfinite(total))
      return LIE_SAMPLING_NONFINITE;
    for (size_t i = 0; i < n; ++i)
      s->entries[i].value /= total;
    double cumulative = 0;
    size_t keep = 0, floor = minimum(o, n);
    while (keep < n) {
      cumulative += s->entries[keep].value;
      ++keep;
      if (keep >= floor && cumulative >= (double)o->top_p)
        break;
    }
    n = keep;
  }
  if (o->min_p > 0 && n > 1) {
    double threshold = (double)o->temperature * log((double)o->min_p);
    size_t keep = 0, floor = minimum(o, n);
    while (keep < n && w->entries[keep].value - maximum >= threshold)
      ++keep;
    if (keep < floor)
      keep = floor;
    if (keep < n)
      n = keep;
  }
  double total = 0;
  for (size_t i = 0; i < n; ++i) {
    w->entries[i].value =
        exp((w->entries[i].value - maximum) / (double)o->temperature);
    total += w->entries[i].value;
  }
  if (!(total > 0) || !isfinite(total))
    return LIE_SAMPLING_NONFINITE;
  for (size_t i = 0; i < n; ++i)
    w->entries[i].value /= total;
  /* The reference public constructor renormalizes, even after softmax. */
  total = 0;
  for (size_t i = 0; i < n; ++i)
    total += w->entries[i].value;
  normalize(w->entries, &n, total);
  sort(w->entries, n, false);
  *count = n;
  return LIE_SAMPLING_OK;
}
static bool sparse(const lie_sampling_sparse_row *q) {
  if (!q || q->id_count != q->probability_count || q->id_count > UINT32_MAX ||
      !span(q->ids, q->id_count, sizeof(*q->ids)) ||
      !span(q->probabilities, q->probability_count, sizeof(*q->probabilities)))
    return false;
  for (size_t i = 0; i < q->probability_count; ++i)
    if (!isfinite(q->probabilities[i]) || q->probabilities[i] < 0)
      return false;
  return true;
}
lie_sampling_status
lie_sampling_distribution_residual(const lie_sampling_probability *p, size_t n,
                                   const lie_sampling_sparse_row *q,
                                   lie_sampling_workspace *d,
                                   lie_sampling_workspace *w, size_t *count) {
  if (!count)
    return LIE_SAMPLING_INVALID;
  *count = 0;
  double total;
  if (!n || !values(p, n, &total) || !(total > 0) || !isfinite(total) ||
      fabs(total - 1) > 1e-8 || !sparse(q) || !workspace(d) || !workspace(w) ||
      !separated(d, w))
    return LIE_SAMPLING_INVALID;
  const lie_sampling_workspace *buffers[] = {d, w};
  for (size_t i = 0; i < 2; ++i)
    if (aliases(buffers[i], p, n * sizeof(*p)) ||
        aliases(buffers[i], q->ids, q->id_count * sizeof(*q->ids)) ||
        aliases(buffers[i], q->probabilities,
                q->probability_count * sizeof(*q->probabilities)))
      return LIE_SAMPLING_INVALID;
  lie_sampling_status rc = reserve(d, q->id_count);
  if (rc != LIE_SAMPLING_OK)
    return rc;
  for (size_t i = 0; i < q->id_count; ++i)
    d->entries[i] = (lie_sampling_probability){q->ids[i], (double)i};
  sort(d->entries, q->id_count, true);
  size_t used = 0;
  for (size_t i = 0; i < q->id_count; ++i) {
    lie_sampling_probability entry = d->entries[i];
    double v = q->probabilities[(size_t)entry.value];
    if (used && d->entries[used - 1].token == entry.token)
      d->entries[used - 1].value += v;
    else
      d->entries[used++] = (lie_sampling_probability){entry.token, v};
  }
  rc = reserve(w, n);
  if (rc != LIE_SAMPLING_OK)
    return rc;
  size_t kept = 0;
  total = 0;
  for (size_t i = 0; i < n; ++i) {
    size_t lo = 0, hi = used;
    while (lo < hi) {
      size_t mid = lo + (hi - lo) / 2;
      if (d->entries[mid].token < p[i].token)
        lo = mid + 1;
      else
        hi = mid;
    }
    double v = p[i].value - (lo < used && d->entries[lo].token == p[i].token
                                 ? d->entries[lo].value
                                 : 0);
    if (v > 0) {
      w->entries[kept++] = (lie_sampling_probability){p[i].token, v};
      total += v;
    }
  }
  if (!(total > 0) || !isfinite(total))
    return LIE_SAMPLING_NO_FINITE;
  normalize(w->entries, &kept, total);
  *count = kept;
  return LIE_SAMPLING_OK;
}
lie_sampling_status lie_sampling_distribution_residual_draw(
    const lie_sampling_probability *p, size_t n,
    const lie_sampling_sparse_row *q, lie_sampling_workspace *d,
    lie_sampling_workspace *w, uint64_t *rng, uint32_t *out) {
  if (!out)
    return LIE_SAMPLING_INVALID;
  size_t count = 0;
  lie_sampling_status rc =
      lie_sampling_distribution_residual(p, n, q, d, w, &count);
  if (rc == LIE_SAMPLING_NO_FINITE)
    return lie_sampling_draw(p, n, rng, out);
  if (rc != LIE_SAMPLING_OK)
    return rc;
  return lie_sampling_draw(w->entries, count, rng, out);
}
static bool proposal(const lie_sampling_proposal *q) {
  return q && q->abi_version == LIE_DISTRIBUTION_ABI &&
         q->struct_bytes == sizeof(*q) && q->count <= q->capacity &&
         span(q->ids, q->capacity, sizeof(*q->ids)) &&
         span(q->probabilities, q->capacity, sizeof(*q->probabilities)) &&
         !overlap(q->ids, q->capacity * sizeof(*q->ids), q->probabilities,
                  q->capacity * sizeof(*q->probabilities));
}
lie_sampling_status
lie_sampling_proposal_quantize(const lie_sampling_probability *p, size_t n,
                               const uint32_t *ids, size_t id_count,
                               uint64_t *rng, lie_sampling_proposal *q) {
  double total;
  if (!rng || !n || n > LIE_PROPOSAL_UNITS || !values(p, n, &total) ||
      fabs(total - 1) > 1e-8 || !proposal(q) || n > q->capacity ||
      (ids ? !span(ids, id_count, sizeof(*ids)) : id_count != 0) ||
      overlap(p, n * sizeof(*p), q->ids, q->capacity * sizeof(*q->ids)) ||
      overlap(p, n * sizeof(*p), q->probabilities,
              q->capacity * sizeof(*q->probabilities)) ||
      overlap(ids, id_count * sizeof(*ids), q->ids,
              q->capacity * sizeof(*q->ids)) ||
      overlap(ids, id_count * sizeof(*ids), q->probabilities,
              q->capacity * sizeof(*q->probabilities)))
    return LIE_SAMPLING_INVALID;
  uint64_t mass_total = 0;
  for (size_t i = 0; i < n; ++i) {
    if (ids && p[i].token >= id_count)
      return LIE_SAMPLING_INVALID;
    double m = floor(p[i].value * LIE_PROPOSAL_UNITS);
    if (!isfinite(m) || m < 0 || m > LIE_PROPOSAL_UNITS)
      return LIE_SAMPLING_INVALID;
    mass_total += (uint32_t)m;
  }
  if (mass_total > LIE_PROPOSAL_UNITS)
    return LIE_SAMPLING_INVALID;
  const uint32_t draw =
      (uint32_t)(lie_sampling_uniform(rng) * LIE_PROPOSAL_UNITS);
  uint32_t cumulative = 0;
  bool selected = false;
  for (size_t i = 0; i < n; ++i) {
    uint32_t mass = (uint32_t)floor(p[i].value * LIE_PROPOSAL_UNITS);
    if (!i)
      mass += LIE_PROPOSAL_UNITS - (uint32_t)mass_total;
    q->ids[i] = ids ? ids[p[i].token] : p[i].token;
    q->probabilities[i] = (float)mass / LIE_PROPOSAL_UNITS;
    cumulative += mass;
    if (!selected && draw < cumulative) {
      q->token = q->ids[i];
      q->probability = q->probabilities[i];
      selected = true;
    }
  }
  q->count = n;
  return LIE_SAMPLING_OK;
}
lie_sampling_status
lie_sampling_proposal_validate(const lie_sampling_proposal_view *q,
                               size_t vocabulary) {
  if (!vocabulary || vocabulary > UINT32_MAX || !q ||
      q->abi_version != LIE_DISTRIBUTION_ABI || q->struct_bytes != sizeof(*q) ||
      !q->count || q->count > UINT32_MAX ||
      !span(q->ids, q->count, sizeof(*q->ids)) ||
      !span(q->probabilities, q->count, sizeof(*q->probabilities)) ||
      q->token >= vocabulary || !isfinite(q->probability) ||
      q->probability <= 0 || q->probability > 1)
    return LIE_SAMPLING_INVALID;
  double total;
  total = 0;
  double selected = 0;
  for (size_t i = 0; i < q->count; ++i) {
    if (q->ids[i] >= vocabulary || !isfinite(q->probabilities[i]) ||
        q->probabilities[i] < 0)
      return LIE_SAMPLING_INVALID;
    total += q->probabilities[i];
    if (q->ids[i] == q->token)
      selected += q->probabilities[i];
  }
  if (total != 1 || selected != q->probability)
    return LIE_SAMPLING_INVALID;
  return LIE_SAMPLING_OK;
}
lie_sampling_status lie_sampling_proposal_verify(
    const lie_sampling_probability *p, size_t n, size_t vocabulary,
    const lie_sampling_proposal_view *q, lie_sampling_workspace *d,
    lie_sampling_workspace *w, uint64_t *rng, uint32_t *out, bool *accepted) {
  double total;
  if (!rng || !out || !accepted || !n || !values(p, n, &total) ||
      !(total > 0) || !isfinite(total) || fabs(total - 1) > 1e-8 ||
      lie_sampling_proposal_validate(q, vocabulary) != LIE_SAMPLING_OK)
    return LIE_SAMPLING_INVALID;
  for (size_t i = 0; i < n; ++i)
    if (p[i].token >= vocabulary)
      return LIE_SAMPLING_INVALID;
  uint64_t next = *rng;
  uint32_t token = q->token;
  bool ok = lie_sampling_uniform(&next) * q->probability <
            lie_sampling_distribution_probability(p, n, q->token);
  if (!ok) {
    lie_sampling_sparse_row sparse_row = {q->ids, q->count, q->probabilities,
                                          q->count};
    lie_sampling_status rc = lie_sampling_distribution_residual_draw(
        p, n, &sparse_row, d, w, &next, &token);
    if (rc != LIE_SAMPLING_OK)
      return rc;
  }
  *rng = next;
  *out = token;
  *accepted = ok;
  return LIE_SAMPLING_OK;
}
