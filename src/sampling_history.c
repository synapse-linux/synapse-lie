/* SPDX-License-Identifier: MIT */
#include "lie/sampling_history.h"
#include <limits.h>
#include <string.h>

typedef struct {
  const uint32_t *old, *incoming;
  size_t old_count, incoming_count;
} window;
static size_t minimum(size_t a, size_t b) { return a < b ? a : b; }
static bool overlaps(const void *, size_t, const void *, size_t);
void lie_sampling_history_options_init(lie_sampling_history_options *o) {
  if (o)
    *o = (lie_sampling_history_options){LIE_SAMPLING_HISTORY_ABI,
                                        sizeof(*o),
                                        64,
                                        UINT32_MAX,
                                        UINT32_MAX,
                                        false,
                                        false};
}
static bool valid(const lie_sampling_history_options *o,
                  const lie_sampling_history *s, bool bounded) {
  if (!o || !s || o->abi_version != LIE_SAMPLING_HISTORY_ABI ||
      o->struct_bytes != sizeof(*o) ||
      o->repeat_last_n > SIZE_MAX / sizeof(uint32_t) ||
      o->max_penalties > SIZE_MAX / sizeof(lie_sampling_penalty) ||
      o->max_batch_tokens > UINT32_MAX || s->token_count > s->token_capacity ||
      s->penalty_count > s->penalty_capacity ||
      s->token_capacity > SIZE_MAX / sizeof(uint32_t) ||
      s->penalty_capacity > SIZE_MAX / sizeof(lie_sampling_penalty) ||
      (s->token_capacity && !s->tokens) ||
      (s->penalty_capacity && !s->penalties))
    return false;
  if (bounded && (s->token_count > o->repeat_last_n ||
                  s->penalty_count > o->max_penalties))
    return false;
  if (overlaps(s->tokens, s->token_capacity * sizeof(*s->tokens), s->penalties,
               s->penalty_capacity * sizeof(*s->penalties)))
    return false;
  for (size_t i = 0; i < s->penalty_count; ++i) {
    const lie_sampling_penalty *p = s->penalties + i;
    if (p->repeated > 1 || (!p->generated_count && !p->repeated) ||
        (i && s->penalties[i - 1].token >= p->token))
      return false;
  }
  return true;
}
static bool overlaps(const void *a, size_t an, const void *b, size_t bn) {
  if (!an || !bn)
    return false;
  uintptr_t x = (uintptr_t)a, y = (uintptr_t)b;
  if (x > UINTPTR_MAX - an || y > UINTPTR_MAX - bn)
    return true;
  return x < y + bn && y < x + an;
}
static bool aliases(const lie_sampling_history *s, const uint32_t *p,
                    size_t n) {
  return overlaps(p, n * sizeof(*p), s->tokens,
                  s->token_capacity * sizeof(*s->tokens)) ||
         overlaps(p, n * sizeof(*p), s->penalties,
                  s->penalty_capacity * sizeof(*s->penalties));
}
static lie_sampling_history_status grow_tokens(lie_sampling_history *s,
                                               size_t n) {
  if (n <= s->token_capacity)
    return LIE_HISTORY_OK;
  if (n > SIZE_MAX / sizeof(*s->tokens) || !s->grow_tokens)
    return LIE_HISTORY_RESOURCE;
  uint32_t *p = s->tokens;
  size_t cap = s->token_capacity;
  if (s->grow_tokens(s->context, n, &p, &cap) || !p || cap < n ||
      cap > SIZE_MAX / sizeof(*p))
    return LIE_HISTORY_RESOURCE;
  s->tokens = p;
  s->token_capacity = cap;
  return LIE_HISTORY_OK;
}
static lie_sampling_history_status grow_penalties(lie_sampling_history *s,
                                                  size_t n) {
  if (n <= s->penalty_capacity)
    return LIE_HISTORY_OK;
  if (n > SIZE_MAX / sizeof(*s->penalties) || !s->grow_penalties)
    return LIE_HISTORY_RESOURCE;
  lie_sampling_penalty *p = s->penalties;
  size_t cap = s->penalty_capacity;
  if (s->grow_penalties(s->context, n, &p, &cap) || !p || cap < n ||
      cap > SIZE_MAX / sizeof(*p))
    return LIE_HISTORY_RESOURCE;
  s->penalties = p;
  s->penalty_capacity = cap;
  return LIE_HISTORY_OK;
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
static bool contains(window w, uint32_t token) {
  for (size_t i = 0; i < w.old_count; ++i)
    if (w.old[i] == token)
      return true;
  for (size_t i = 0; i < w.incoming_count; ++i)
    if (w.incoming[i] == token)
      return true;
  return false;
}
static window tail(const lie_sampling_history_options *o,
                   const lie_sampling_history *s, const uint32_t *tokens,
                   size_t n, bool reset) {
  size_t fresh = minimum(n, o->repeat_last_n),
         old = reset ? 0 : minimum(s->token_count, o->repeat_last_n - fresh);
  return (window){old ? s->tokens + s->token_count - old : NULL,
                  fresh ? tokens + n - fresh : NULL, old, fresh};
}
static void publish_window(lie_sampling_history *s, window w) {
  if (w.old_count)
    memmove(s->tokens, w.old, w.old_count * sizeof(*s->tokens));
  if (w.incoming_count)
    memcpy(s->tokens + w.old_count, w.incoming,
           w.incoming_count * sizeof(*s->tokens));
  s->token_count = w.old_count + w.incoming_count;
}
static lie_sampling_history_status stage(lie_sampling_history *s, size_t base,
                                         size_t *count, uint32_t token,
                                         bool generated) {
  size_t at = *count ? lower(s->penalties + base, *count, token) : 0;
  if (at < *count && s->penalties[base + at].token == token) {
    if (generated && s->penalties[base + at].generated_count == UINT32_MAX)
      return LIE_HISTORY_OVERFLOW;
    if (generated)
      ++s->penalties[base + at].generated_count;
    return LIE_HISTORY_OK;
  }
  if (base > SIZE_MAX - 1 - *count)
    return LIE_HISTORY_RESOURCE;
  lie_sampling_history_status rc = grow_penalties(s, base + *count + 1);
  if (rc != LIE_HISTORY_OK)
    return rc;
  if (at < *count)
    memmove(s->penalties + base + at + 1, s->penalties + base + at,
            (*count - at) * sizeof(*s->penalties));
  s->penalties[base + at] =
      (lie_sampling_penalty){token, generated ? 1u : 0u, generated ? 0u : 1u};
  ++*count;
  return LIE_HISTORY_OK;
}
static void swap(lie_sampling_penalty *a, lie_sampling_penalty *b) {
  lie_sampling_penalty saved = *a;
  *a = *b;
  *b = saved;
}
static void sift(lie_sampling_penalty *p, size_t root, size_t n) {
  while (root < n / 2) {
    size_t child = root * 2 + 1;
    if (child + 1 < n && p[child].token < p[child + 1].token)
      ++child;
    if (p[root].token >= p[child].token)
      return;
    swap(p + root, p + child);
    root = child;
  }
}
static void sort(lie_sampling_penalty *p, size_t n) {
  /* In-place heapsort: no libc sort workspace outside the caller's budget. */
  for (size_t root = n / 2; root;)
    sift(p, --root, n);
  for (size_t end = n; end > 1;) {
    swap(p, p + --end);
    sift(p, 0, end);
  }
}
static lie_sampling_history_status stage_batch(lie_sampling_history *s,
                                               size_t base,
                                               const uint32_t *tokens, size_t n,
                                               bool generated, size_t *count) {
  *count = 0;
  if (n <= 32) {
    for (size_t i = 0; i < n; ++i) {
      lie_sampling_history_status rc =
          stage(s, base, count, tokens[i], generated);
      if (rc != LIE_HISTORY_OK)
        return rc;
    }
    return LIE_HISTORY_OK;
  }
  if (n > SIZE_MAX - base)
    return LIE_HISTORY_RESOURCE;
  lie_sampling_history_status rc = grow_penalties(s, base + n);
  if (rc != LIE_HISTORY_OK)
    return rc;
  for (size_t i = 0; i < n; ++i)
    s->penalties[base + i] = (lie_sampling_penalty){
        tokens[i], generated ? 1u : 0u, generated ? 0u : 1u};
  sort(s->penalties + base, n);
  for (size_t i = 0; i < n; ++i) {
    lie_sampling_penalty p = s->penalties[base + i];
    if (*count && s->penalties[base + *count - 1].token == p.token) {
      if (generated)
        ++s->penalties[base + *count - 1].generated_count;
    } else
      s->penalties[base + (*count)++] = p;
  }
  return LIE_HISTORY_OK;
}
lie_sampling_history_status
lie_sampling_history_reset(const lie_sampling_history_options *o,
                           lie_sampling_history *s, const uint32_t *tokens,
                           size_t n) {
  if (!valid(o, s, false) || (!tokens && n) || n > SIZE_MAX / sizeof(*tokens) ||
      aliases(s, tokens, n))
    return LIE_HISTORY_INVALID;
  window w = tail(o, s, tokens, n, true);
  size_t q = 0, base = s->penalty_count;
  lie_sampling_history_status rc = LIE_HISTORY_OK;
  if (o->repetition && w.incoming_count)
    rc = stage_batch(s, base, w.incoming, w.incoming_count, false, &q);
  if (rc != LIE_HISTORY_OK)
    return rc;
  if (q > o->max_penalties)
    return LIE_HISTORY_RESOURCE;
  rc = grow_tokens(s, w.incoming_count);
  if (rc != LIE_HISTORY_OK)
    return rc;
  /* The input is disjoint; growing token storage does not invalidate it. */
  if (q)
    memmove(s->penalties, s->penalties + base, q * sizeof(*s->penalties));
  s->penalty_count = q;
  publish_window(s, w);
  return LIE_HISTORY_OK;
}
static lie_sampling_history_status
accept_one(const lie_sampling_history_options *o, lie_sampling_history *s,
           uint32_t token) {
  window w = tail(o, s, &token, 1, false);
  size_t removed = 0, at = s->penalty_count
                               ? lower(s->penalties, s->penalty_count, token)
                               : 0;
  bool exists = at < s->penalty_count && s->penalties[at].token == token;
  if (o->generated && exists && s->penalties[at].generated_count == UINT32_MAX)
    return LIE_HISTORY_OVERFLOW;
  bool wanted = o->generated || (o->repetition && w.incoming_count);
  for (size_t i = 0; i < s->penalty_count; ++i) {
    const lie_sampling_penalty *p = s->penalties + i;
    bool generated = p->generated_count || (o->generated && p->token == token);
    bool repeated = o->repetition && (p->repeated || p->token == token) &&
                    contains(w, p->token);
    if (!generated && !repeated)
      ++removed;
  }
  size_t needed = s->penalty_count - removed;
  if (wanted && !exists) {
    if (needed == SIZE_MAX)
      return LIE_HISTORY_RESOURCE;
    ++needed;
  }
  if (needed > o->max_penalties)
    return LIE_HISTORY_RESOURCE;
  lie_sampling_history_status rc = grow_penalties(s, needed);
  if (rc != LIE_HISTORY_OK)
    return rc;
  rc = grow_tokens(s, w.old_count + w.incoming_count);
  if (rc != LIE_HISTORY_OK)
    return rc;
  /* The old-window pointer may have moved during token growth. */
  w = tail(o, s, &token, 1, false);
  size_t count = 0;
  for (size_t i = 0; i < s->penalty_count; ++i) {
    lie_sampling_penalty p = s->penalties[i];
    if (o->generated && p.token == token)
      ++p.generated_count;
    p.repeated = o->repetition && (p.repeated || p.token == token) &&
                 contains(w, p.token);
    if (p.generated_count || p.repeated)
      s->penalties[count++] = p;
  }
  if (wanted && !exists) {
    at = count ? lower(s->penalties, count, token) : 0;
    if (at < count)
      memmove(s->penalties + at + 1, s->penalties + at,
              (count - at) * sizeof(*s->penalties));
    s->penalties[at] =
        (lie_sampling_penalty){token, o->generated ? 1u : 0u,
                               o->repetition && w.incoming_count ? 1u : 0u};
    ++count;
  }
  s->penalty_count = count;
  publish_window(s, w);
  return LIE_HISTORY_OK;
}
lie_sampling_history_status
lie_sampling_history_accept(const lie_sampling_history_options *o,
                            lie_sampling_history *s, const uint32_t *tokens,
                            size_t n) {
  if (!valid(o, s, true) || (!tokens && n) || n > SIZE_MAX / sizeof(*tokens) ||
      aliases(s, tokens, n))
    return LIE_HISTORY_INVALID;
  if (n > o->max_batch_tokens)
    return LIE_HISTORY_RESOURCE;
  if (!n)
    return LIE_HISTORY_OK;
  if (n == 1)
    return accept_one(o, s, *tokens);
  window w = tail(o, s, tokens, n, false);
  size_t base = s->penalty_count, q = 0;
  lie_sampling_history_status rc = LIE_HISTORY_OK;
  if (o->generated || (o->repetition && w.incoming_count))
    rc = stage_batch(s, base, o->generated ? tokens : w.incoming,
                     o->generated ? n : w.incoming_count, o->generated, &q);
  if (rc != LIE_HISTORY_OK)
    return rc;
  size_t keep = 0, added = 0;
  for (size_t i = 0; i < base; ++i) {
    lie_sampling_penalty p = s->penalties[i];
    size_t delta = q ? lower(s->penalties + base, q, p.token) : 0;
    bool changed = delta < q && s->penalties[base + delta].token == p.token;
    uint32_t increment = changed && o->generated
                             ? s->penalties[base + delta].generated_count
                             : 0;
    if (increment > UINT32_MAX - p.generated_count)
      return LIE_HISTORY_OVERFLOW;
    if (p.generated_count || increment ||
        (o->repetition && (p.repeated || changed) && contains(w, p.token)))
      ++keep;
  }
  for (size_t i = 0; i < q; ++i) {
    const lie_sampling_penalty *p = s->penalties + base + i;
    size_t at = base ? lower(s->penalties, base, p->token) : 0;
    if ((at == base || s->penalties[at].token != p->token) &&
        (o->generated || (o->repetition && contains(w, p->token))))
      ++added;
  }
  if (keep > o->max_penalties || added > o->max_penalties - keep)
    return LIE_HISTORY_RESOURCE;
  rc = grow_tokens(s, w.old_count + w.incoming_count);
  if (rc != LIE_HISTORY_OK)
    return rc;
  w = tail(o, s, tokens, n, false);
  size_t count = 0;
  for (size_t i = 0; i < base; ++i) {
    lie_sampling_penalty p = s->penalties[i];
    size_t delta = q ? lower(s->penalties + base, q, p.token) : 0;
    bool changed = delta < q && s->penalties[base + delta].token == p.token;
    if (changed && o->generated)
      p.generated_count += s->penalties[base + delta].generated_count;
    p.repeated =
        o->repetition && (p.repeated || changed) && contains(w, p.token);
    if (p.generated_count || p.repeated)
      s->penalties[count++] = p;
  }
  /* The compacted prefix has at most base entries. Each staged key adds at
   * most one, so insertion writes no farther than base+i: unread scratch
   * entries stay intact even when the two ranges meet. */
  for (size_t i = 0; i < q; ++i) {
    lie_sampling_penalty p = s->penalties[base + i];
    p.repeated = o->repetition && contains(w, p.token);
    if (!p.generated_count && !p.repeated)
      continue;
    size_t at = count ? lower(s->penalties, count, p.token) : 0;
    if (at < count && s->penalties[at].token == p.token)
      continue;
    if (at < count)
      memmove(s->penalties + at + 1, s->penalties + at,
              (count - at) * sizeof(*s->penalties));
    s->penalties[at] = p;
    ++count;
  }
  s->penalty_count = count;
  publish_window(s, w);
  return LIE_HISTORY_OK;
}
lie_sampling_history_status
lie_sampling_history_copy(const lie_sampling_history_options *o,
                          lie_sampling_history *dst,
                          const lie_sampling_history *src) {
  if (!valid(o, dst, true) || !valid(o, src, true))
    return LIE_HISTORY_INVALID;
  if (dst == src)
    return LIE_HISTORY_OK;
  if (aliases(dst, src->tokens, src->token_capacity) ||
      overlaps(src->penalties, src->penalty_capacity * sizeof(*src->penalties),
               dst->tokens, dst->token_capacity * sizeof(*dst->tokens)) ||
      overlaps(src->penalties, src->penalty_capacity * sizeof(*src->penalties),
               dst->penalties, dst->penalty_capacity * sizeof(*dst->penalties)))
    return LIE_HISTORY_INVALID;
  lie_sampling_history_status rc = grow_tokens(dst, src->token_count);
  if (rc != LIE_HISTORY_OK)
    return rc;
  rc = grow_penalties(dst, src->penalty_count);
  if (rc != LIE_HISTORY_OK)
    return rc;
  if (src->token_count)
    memcpy(dst->tokens, src->tokens, src->token_count * sizeof(*src->tokens));
  if (src->penalty_count)
    memcpy(dst->penalties, src->penalties,
           src->penalty_count * sizeof(*src->penalties));
  dst->token_count = src->token_count;
  dst->penalty_count = src->penalty_count;
  return LIE_HISTORY_OK;
}
