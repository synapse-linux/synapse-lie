/* SPDX-License-Identifier: MIT */
/* Exact-decimal algorithm port from independently pinned MIT Gufo
 * f783fedb9bea2ec7de941f6da4e02f4a4596b29e, json_schema_lexeme.cpp.
 * LIE owns bounded storage, immutable policies and transactional refusals. */
#include "lie/grammar_number.h"
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#define CAP 8192u
#define DEFAULT_WORK 32000000u
typedef struct { char d[CAP]; size_t n; int scale; bool negative; } decimal;
typedef struct { decimal value; bool exclusive, present; } bound;
struct lie_number_policy {
  lie_grammar_allocator allocator;
  size_t max_work;
  bool integer, has_multiple;
  bound lower, upper;
  decimal multiple;
};
typedef struct {
  decimal value, low, high, quotient, remainder, denominator, candidate, x, y, z;
  unsigned product[CAP];
  size_t work;
} workspace;
static void *alloc_default(void *context, size_t n) { (void)context; return malloc(n); }
static void free_default(void *context, void *p) { (void)context; free(p); }
static bool allocator_get(const lie_grammar_allocator *a, lie_grammar_allocator *out) {
  *out = a ? *a : (lie_grammar_allocator){0};
  if (!!out->allocate != !!out->release) return false;
  if (!out->allocate) { out->allocate = alloc_default; out->release = free_default; }
  return true;
}
static lie_number_status spend(workspace *w, size_t n) {
  if (n > w->work) return LIE_NUMBER_WORK_LIMIT;
  w->work -= n; return LIE_NUMBER_OK;
}
#define TRY(expr) do { lie_number_status rc_ = (expr); if (rc_ != LIE_NUMBER_OK) return rc_; } while (0)
/* Copy only live digits, not the unused fixed-capacity tail. */
static void copy(decimal *to, const decimal *from) {
  to->n = from->n; to->scale = from->scale; to->negative = from->negative;
  memcpy(to->d, from->d, from->n);
}
static bool zero(const decimal *v) { return v->n == 1 && v->d[0] == '0'; }
static void trim(decimal *v) {
  size_t first = 0;
  while (first + 1 < v->n && v->d[first] == '0') ++first;
  v->n -= first; memmove(v->d, v->d + first, v->n);
}
static void normalize(decimal *v) {
  trim(v);
  if (zero(v)) { v->scale = 0; v->negative = false; return; }
  while (v->n > 1 && v->d[v->n - 1] == '0') { --v->n; --v->scale; }
}
static lie_number_status parse(lie_number_text t, decimal *v, bool trailing_dot) {
  if (!t.data || !t.bytes) return LIE_NUMBER_INVALID;
  if (t.bytes > 4096) return LIE_NUMBER_RESOURCE;
  size_t i = 0; v->n = 0; v->scale = 0; v->negative = t.data[0] == '-';
  if (v->negative) ++i;
  size_t start = i;
  while (i < t.bytes && t.data[i] >= '0' && t.data[i] <= '9') v->d[v->n++] = t.data[i++];
  if (i == start || (i - start > 1 && t.data[start] == '0')) return LIE_NUMBER_INVALID;
  if (i < t.bytes && t.data[i] == '.') {
    start = ++i;
    while (i < t.bytes && t.data[i] >= '0' && t.data[i] <= '9') {
      v->d[v->n++] = t.data[i++]; ++v->scale;
    }
    if (i == start && (!trailing_dot || i != t.bytes)) return LIE_NUMBER_INVALID;
  }
  if (i < t.bytes && (t.data[i] == 'e' || t.data[i] == 'E')) {
    ++i; bool neg = false;
    if (i < t.bytes && (t.data[i] == '+' || t.data[i] == '-')) neg = t.data[i++] == '-';
    start = i; unsigned e = 0;
    while (i < t.bytes && t.data[i] >= '0' && t.data[i] <= '9') {
      if (e > 4096 / 10) return LIE_NUMBER_RESOURCE;
      e = e * 10 + (unsigned)(t.data[i++] - '0');
      if (e > 4096) return LIE_NUMBER_RESOURCE;
    }
    if (i == start) return LIE_NUMBER_INVALID;
    v->scale += neg ? (int)e : -(int)e;
  }
  if (i != t.bytes) return LIE_NUMBER_INVALID;
  normalize(v); return LIE_NUMBER_OK;
}
static int magnitude(const decimal *a, const decimal *b) {
  if (zero(a) || zero(b)) return (!zero(a)) - (!zero(b));
  int ae = (int)a->n - a->scale, be = (int)b->n - b->scale;
  if (ae != be) return ae < be ? -1 : 1;
  size_t n = a->n > b->n ? a->n : b->n;
  for (size_t i = 0; i < n; ++i) {
    char x = i < a->n ? a->d[i] : '0', y = i < b->n ? b->d[i] : '0';
    if (x != y) return x < y ? -1 : 1;
  }
  return 0;
}
static int compare(const decimal *a, const decimal *b) {
  if (a->negative != b->negative) return a->negative ? -1 : 1;
  return (a->negative ? -1 : 1) * magnitude(a, b);
}
static int natural_compare(const decimal *a, const decimal *b) {
  if (a->n != b->n) return a->n < b->n ? -1 : 1;
  return memcmp(a->d, b->d, a->n);
}
static lie_number_status append_zeros(decimal *v, size_t count) {
  if (count > CAP - v->n) return LIE_NUMBER_RESOURCE;
  memset(v->d + v->n, '0', count); v->n += count; return LIE_NUMBER_OK;
}
static void subtract(decimal *a, const decimal *b) {
  int borrow = 0;
  for (size_t i = 0; i < a->n; ++i) {
    int d = a->d[a->n - 1 - i] - '0' - borrow;
    if (i < b->n) d -= b->d[b->n - 1 - i] - '0';
    borrow = d < 0; a->d[a->n - 1 - i] = (char)('0' + d + 10 * borrow);
  }
  trim(a);
}
/* All arguments are distinct from q/r/denominator. Numerator padding is
 * streamed; only the denominator and the current remainder are materialized. */
static lie_number_status divide(workspace *w, const decimal *a, const decimal *b) {
  if (zero(b)) return LIE_NUMBER_INVALID;
  int scale = a->scale > b->scale ? a->scale : b->scale;
  size_t pad = (size_t)(scale - a->scale);
  if (pad > CAP - a->n) return LIE_NUMBER_RESOURCE;
  decimal *den = &w->denominator, *q = &w->quotient, *r = &w->remainder;
  copy(den, b); TRY(append_zeros(den, (size_t)(scale - b->scale)));
  q->n = 0; q->scale = 0; q->negative = false;
  r->n = 1; r->d[0] = '0'; r->scale = 0; r->negative = false;
  for (size_t i = 0; i < a->n + pad; ++i) {
    if (zero(r)) r->n = 0;
    if (r->n == CAP) return LIE_NUMBER_RESOURCE;
    r->d[r->n++] = i < a->n ? a->d[i] : '0';
    unsigned count = 0;
    for (;;) {
      TRY(spend(w, r->n + den->n));
      if (natural_compare(r, den) < 0) break;
      TRY(spend(w, r->n)); subtract(r, den); ++count;
    }
    if (count || q->n) q->d[q->n++] = (char)('0' + count);
  }
  if (!q->n) { q->n = 1; q->d[0] = '0'; }
  return LIE_NUMBER_OK;
}
static lie_number_status increment(decimal *v) {
  for (size_t i = v->n; i; --i) {
    if (v->d[i - 1] != '9') { ++v->d[i - 1]; return LIE_NUMBER_OK; }
    v->d[i - 1] = '0';
  }
  if (v->n == CAP) return LIE_NUMBER_RESOURCE;
  memmove(v->d + 1, v->d, v->n); ++v->n;
  v->d[0] = '1'; return LIE_NUMBER_OK;
}
static lie_number_status product(workspace *w, const decimal *a, const decimal *b, decimal *out) {
  if (b->n > CAP - a->n) return LIE_NUMBER_RESOURCE;
  size_t n = a->n + b->n;
  TRY(spend(w, a->n * b->n + n));
  memset(w->product, 0, n * sizeof(*w->product));
  for (size_t i = 0; i < a->n; ++i)
    for (size_t j = 0; j < b->n; ++j)
      w->product[i + j + 1] += (unsigned)(a->d[i] - '0') * (unsigned)(b->d[j] - '0');
  for (size_t i = n - 1; i; --i) {
    w->product[i - 1] += w->product[i] / 10; w->product[i] %= 10;
  }
  out->n = n; out->scale = a->scale; out->negative = false;
  for (size_t i = 0; i < n; ++i) out->d[i] = (char)('0' + w->product[i]);
  normalize(out); return LIE_NUMBER_OK;
}
static lie_number_status valid(const lie_number_policy *p, workspace *w, const decimal *v, bool *ok) {
  *ok = false;
  if ((p->integer && v->scale > 0) ||
      (p->lower.present && compare(v, &p->lower.value) < (int)p->lower.exclusive) ||
      (p->upper.present && compare(v, &p->upper.value) > -(int)p->upper.exclusive)) return LIE_NUMBER_OK;
  if (p->has_multiple && !zero(v)) {
    TRY(divide(w, v, &p->multiple));
    if (!zero(&w->remainder)) return LIE_NUMBER_OK;
  }
  *ok = true; return LIE_NUMBER_OK;
}
static lie_number_status grid(const lie_number_policy *p, workspace *w,
  const decimal *lower, bool lex, const decimal *upper, bool uex, bool *ok) {
  *ok = false;
  if (lower->negative && !upper->negative && !zero(upper)) { *ok = true; return LIE_NUMBER_OK; }
  /* Copy only into dedicated x/y scratch, preserving policy and prefix bounds. */
  if (lower->negative) { copy(&w->x, upper); copy(&w->y, lower); bool t = lex; lex = uex; uex = t; }
  else { copy(&w->x, lower); copy(&w->y, upper); }
  w->x.negative = w->y.negative = false;
  TRY(divide(w, &w->x, &p->multiple));
  if (!zero(&w->remainder) || lex) TRY(increment(&w->quotient));
  TRY(product(w, &p->multiple, &w->quotient, &w->candidate));
  int c = compare(&w->candidate, &w->y);
  *ok = c < 0 || (c == 0 && !uex); return LIE_NUMBER_OK;
}
void lie_number_description_init(lie_number_description *d) {
  if (!d) return;
  memset(d, 0, sizeof(*d)); d->abi_version = LIE_GRAMMAR_NUMBER_ABI;
  d->struct_bytes = sizeof(*d); d->max_work = DEFAULT_WORK;
}
static lie_number_status compile(lie_number_policy *p, workspace *w, const lie_number_description *d) {
  lie_number_text texts[] = {d->minimum, d->maximum, d->exclusive_minimum, d->exclusive_maximum, d->multiple};
  for (size_t i = 0; i < 5; ++i) {
    if (!texts[i].data) { if (texts[i].bytes) return LIE_NUMBER_INVALID; continue; }
    TRY(parse(texts[i], &w->value, false));
    if (i == 4) {
      if (zero(&w->value) || w->value.negative) return LIE_NUMBER_INVALID;
      copy(&p->multiple, &w->value); p->has_multiple = true; continue;
    }
    bool lower = i == 0 || i == 2, exclusive = i >= 2;
    bound *b = lower ? &p->lower : &p->upper;
    int c = b->present ? compare(&w->value, &b->value) : 0;
    if (!b->present || (lower ? c > 0 : c < 0) || (!c && exclusive)) {
      copy(&b->value, &w->value); b->exclusive = exclusive; b->present = true;
    }
  }
  if (p->lower.present && p->upper.present) {
    int c = compare(&p->lower.value, &p->upper.value); bool ok = true;
    if (!c && !p->lower.exclusive && !p->upper.exclusive) TRY(valid(p, w, &p->lower.value, &ok));
    if (c > 0 || (!c && (p->lower.exclusive || p->upper.exclusive || !ok))) return LIE_NUMBER_EMPTY_INTERVAL;
  }
  if (p->integer) {
    if (!p->has_multiple) {
      p->multiple.n = 1; p->multiple.d[0] = '1'; p->multiple.scale = 0;
      p->has_multiple = true;
    }
    if (p->multiple.scale > 0) {
      int scale = p->multiple.scale; p->multiple.scale = 0;
      const char factors[] = {'2', '5'};
      for (size_t f = 0; f < 2; ++f) {
        w->z.n = 1; w->z.d[0] = factors[f]; w->z.scale = 0; w->z.negative = false;
        for (int count = 0; count < scale; ++count) {
          TRY(divide(w, &p->multiple, &w->z));
          if (!zero(&w->remainder)) break;
          copy(&p->multiple, &w->quotient);
        }
      }
      normalize(&p->multiple);
    }
  }
  if (p->lower.present && p->upper.present && p->has_multiple) {
    bool ok; TRY(grid(p, w, &p->lower.value, p->lower.exclusive, &p->upper.value, p->upper.exclusive, &ok));
    if (!ok) return LIE_NUMBER_EMPTY_GRID;
  }
  return LIE_NUMBER_OK;
}
lie_number_status lie_number_create(const lie_number_description *d, lie_number_policy **out) {
  lie_grammar_allocator a;
  if (!d || !out || d->abi_version != LIE_GRAMMAR_NUMBER_ABI ||
      d->struct_bytes != sizeof(*d) || !d->max_work || !allocator_get(&d->allocator, &a)) return LIE_NUMBER_INVALID;
  lie_number_policy *p = a.allocate(a.context, sizeof(*p));
  if (!p) return LIE_NUMBER_RESOURCE;
  memset(p, 0, sizeof(*p)); p->allocator = a; p->max_work = d->max_work; p->integer = d->integer;
  workspace *w = a.allocate(a.context, sizeof(*w));
  if (!w) { a.release(a.context, p); return LIE_NUMBER_RESOURCE; }
  w->work = d->max_work;
  lie_number_status rc = compile(p, w, d); a.release(a.context, w);
  if (rc != LIE_NUMBER_OK) a.release(a.context, p); else *out = p;
  return rc;
}
void lie_number_release(lie_number_policy *p) { if (p) p->allocator.release(p->allocator.context, p); }
static lie_number_status check(const lie_number_policy *p, workspace *w, lie_number_text bytes, lie_number_match *out) {
  *out = (lie_number_match){false, false};
  if (!bytes.bytes) { out->prefix = true; return LIE_NUMBER_OK; }
  if (bytes.bytes > 4096) return LIE_NUMBER_OK;
  bool negative = bytes.data[0] == '-';
  const char *text = bytes.data + negative; size_t n = bytes.bytes - negative;
  if (!n) {
    out->prefix = !p->lower.present || p->lower.value.negative || (zero(&p->lower.value) && !p->lower.exclusive);
    return LIE_NUMBER_OK;
  }
  size_t dot = n;
  for (size_t i = 0; i < n; ++i) {
    if (text[i] == '.' && dot == n) dot = i;
    else if (text[i] < '0' || text[i] > '9') return LIE_NUMBER_OK;
  }
  if (!dot || (p->integer && dot != n) || (n > 1 && text[0] == '0' && text[1] != '.')) return LIE_NUMBER_OK;
  TRY(parse(bytes, &w->value, true));
  bool complete = false;
  if (text[n - 1] != '.') TRY(valid(p, w, &w->value, &complete));
  out->complete = complete;
  if (bytes.bytes == 4096) { out->prefix = complete; return LIE_NUMBER_OK; }
  copy(&w->low, &w->value); w->low.negative = false; copy(&w->high, &w->low);
  int places = dot == n ? 0 : (int)(n - dot - 1);
  if (zero(&w->high)) { w->high.d[0] = '1'; w->high.scale = places; }
  else {
    TRY(append_zeros(&w->high, (size_t)(places - w->high.scale)));
    w->high.scale = places; TRY(increment(&w->high)); normalize(&w->high);
  }
  for (unsigned shift = 0; shift <= 1024; ++shift) {
    decimal *first = negative ? &w->high : &w->low, *last = negative ? &w->low : &w->high;
    first->negative = negative && !zero(first); last->negative = negative && !zero(last);
    int lc = p->lower.present ? compare(last, &p->lower.value) : 1;
    int uc = p->upper.present ? compare(first, &p->upper.value) : -1;
    bool il = !p->lower.present || lc > 0 || (negative && !p->lower.exclusive && !lc);
    bool iu = !p->upper.present || uc < 0 || (!negative && !p->upper.exclusive && !uc);
    TRY(spend(w, first->n + last->n + 1));
    if (il && iu) {
      const decimal *lo = first, *hi = last; bool lex = negative, uex = !negative;
      if (p->lower.present) { int c = compare(&p->lower.value, lo); if (c > 0 || (!c && p->lower.exclusive)) { lo = &p->lower.value; lex = p->lower.exclusive; } }
      if (p->upper.present) { int c = compare(&p->upper.value, hi); if (c < 0 || (!c && p->upper.exclusive)) { hi = &p->upper.value; uex = p->upper.exclusive; } }
      bool ok = true;
      if (p->has_multiple) TRY(grid(p, w, lo, lex, hi, uex, &ok));
      if (ok) { out->prefix = true; return LIE_NUMBER_OK; }
    }
    if (dot != n || text[0] == '0' || (negative && !il) || (!negative && !iu)) break;
    --w->low.scale; --w->high.scale;
  }
  out->prefix = complete; return LIE_NUMBER_OK;
}
lie_number_status lie_number_check(const lie_number_policy *p, lie_number_text t, lie_number_match *out) {
  if (!p || !out || (t.bytes && !t.data)) return LIE_NUMBER_INVALID;
  workspace *w = p->allocator.allocate(p->allocator.context, sizeof(*w));
  if (!w) return LIE_NUMBER_RESOURCE;
  w->work = p->max_work; lie_number_match result;
  lie_number_status rc = check(p, w, t, &result);
  p->allocator.release(p->allocator.context, w);
  if (rc == LIE_NUMBER_OK) *out = result;
  return rc;
}
lie_number_status lie_number_accept(const lie_number_policy *p, lie_number_text t, bool *out) {
  if (!p || !out) return LIE_NUMBER_INVALID;
  workspace *w = p->allocator.allocate(p->allocator.context, sizeof(*w));
  if (!w) return LIE_NUMBER_RESOURCE;
  w->work = p->max_work; bool result = false;
  lie_number_status rc = parse(t, &w->value, false);
  if (rc == LIE_NUMBER_OK) rc = valid(p, w, &w->value, &result);
  p->allocator.release(p->allocator.context, w);
  if (rc == LIE_NUMBER_OK) *out = result;
  return rc;
}
static lie_number_status intersect(workspace *w, lie_number_text a, lie_number_text b) {
  TRY(parse(a, &w->low, false)); TRY(parse(b, &w->high, false));
  if (zero(&w->low) || zero(&w->high) || w->low.negative || w->high.negative) return LIE_NUMBER_INVALID;
  int scale = w->low.scale > w->high.scale ? w->low.scale : w->high.scale;
  TRY(append_zeros(&w->low, (size_t)(scale - w->low.scale)));
  TRY(append_zeros(&w->high, (size_t)(scale - w->high.scale)));
  w->low.scale = w->high.scale = 0; copy(&w->x, &w->low); copy(&w->y, &w->high);
  while (!zero(&w->y)) {
    TRY(divide(w, &w->x, &w->y)); copy(&w->x, &w->y); copy(&w->y, &w->remainder);
  }
  TRY(divide(w, &w->low, &w->x));
  TRY(product(w, &w->quotient, &w->high, &w->candidate));
  w->candidate.scale += scale; normalize(&w->candidate); return LIE_NUMBER_OK;
}
lie_number_status lie_number_intersect(lie_number_text a, lie_number_text b,
  const lie_grammar_allocator *hooks, size_t max_work, char *out, size_t capacity, size_t *length) {
  lie_grammar_allocator allocator;
  if (!out || !length || !allocator_get(hooks, &allocator)) return LIE_NUMBER_INVALID;
  /* Reject overlap without dereferencing the output. */
  uintptr_t o = (uintptr_t)out, aa = (uintptr_t)a.data, bb = (uintptr_t)b.data;
  if (capacity > UINTPTR_MAX - o || a.bytes > UINTPTR_MAX - aa || b.bytes > UINTPTR_MAX - bb ||
      (a.bytes && capacity && o < aa + a.bytes && aa < o + capacity) ||
      (b.bytes && capacity && o < bb + b.bytes && bb < o + capacity)) return LIE_NUMBER_INVALID;
  workspace *w = allocator.allocate(allocator.context, sizeof(*w));
  if (!w) return LIE_NUMBER_RESOURCE;
  w->work = max_work ? max_work : DEFAULT_WORK;
  lie_number_status rc = intersect(w, a, b);
  if (rc == LIE_NUMBER_OK) {
    int exponent = -w->candidate.scale;
    char digits[16]; size_t n = 0; unsigned e = (unsigned)(exponent < 0 ? -exponent : exponent);
    do { digits[n++] = (char)('0' + e % 10); e /= 10; } while (e);
    size_t total = w->candidate.n + 1 + (exponent < 0) + n;
    if (total > capacity) rc = LIE_NUMBER_RESOURCE;
    else {
      memcpy(out, w->candidate.d, w->candidate.n); size_t i = w->candidate.n;
      out[i++] = 'e'; if (exponent < 0) out[i++] = '-';
      while (n) out[i++] = digits[--n];
      *length = i;
    }
  }
  allocator.release(allocator.context, w); return rc;
}
lie_number_status lie_number_equal_with_allocator(lie_number_text a, lie_number_text b,
  const lie_grammar_allocator *hooks, bool *out) {
  lie_grammar_allocator allocator;
  if (!out || !allocator_get(hooks, &allocator)) return LIE_NUMBER_INVALID;
  workspace *w = allocator.allocate(allocator.context, sizeof(*w));
  if (!w) return LIE_NUMBER_RESOURCE;
  lie_number_status rc = parse(a, &w->x, false);
  if (rc == LIE_NUMBER_OK) rc = parse(b, &w->y, false);
  if (rc == LIE_NUMBER_OK) *out = compare(&w->x, &w->y) == 0;
  allocator.release(allocator.context, w); return rc;
}
lie_number_status lie_number_equal(lie_number_text a, lie_number_text b, bool *out) {
  return lie_number_equal_with_allocator(a, b, NULL, out);
}
