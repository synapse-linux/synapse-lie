/* SPDX-License-Identifier: MIT */
/* Copyright (c) 2026 gufo contributors. */
/* Attributed expression/derivative/DFA compiler port from official Gufo
 * f783fedb. */
#include "lie/grammar_regex_compile.h"
#include <stdlib.h>
#include <string.h>
#define NONE UINT32_MAX
#define EXPR_MAX 32768u
#define DERIV_MAX 1048576u
#define STATE_MAX 4096u
#define TABLE_MAX 262144u
#define PART_MAX 1048576u
typedef enum {
  EMPTY,
  EPSILON,
  CHARS,
  START,
  BOUNDARY,
  OR,
  AND,
  NOT,
  CONCAT,
  REPEAT
} kind;
typedef struct {
  uint32_t *data;
  size_t count, capacity;
} ids;
typedef struct {
  kind kind;
  uint32_t low, high;
  uint32_t *children;
  size_t count;
  uint64_t hash, minimum;
  uint8_t nullable;
} expression;
typedef struct {
  lie_unicode_range *ranges;
  size_t count;
} character_class;
typedef struct {
  uint32_t expression, cp, result;
  uint8_t flags;
} derivative;
struct lie_regex_compiler {
  lie_regex_compiler_description d;
  lie_regex_bases bases;
  expression *nodes;
  size_t count, capacity;
  uint32_t *node_buckets;
  size_t node_bucket_count;
  character_class *classes;
  size_t class_count, class_capacity, range_count;
  derivative *derivatives;
  size_t derivative_count, derivative_capacity;
  uint32_t *derivative_buckets;
  size_t derivative_bucket_count;
  size_t work;
  bool boundaries;
};
typedef lie_regex_compile_status status;
static void *ordinary_allocate(void *ctx, size_t n) {
  (void)ctx;
  return malloc(n);
}
static void ordinary_release(void *ctx, void *p) {
  (void)ctx;
  free(p);
}
static void drop(lie_regex_compiler *c, void *p) {
  if (p)
    c->d.allocator.release(c->d.allocator.context, p);
}
static void *alloc(lie_regex_compiler *c, size_t n) {
  return c->d.allocator.allocate(c->d.allocator.context, n);
}
static status charge(lie_regex_compiler *c, size_t n) {
  if (n > c->d.max_work - c->work)
    return LIE_REGEX_COMPILE_WORK_LIMIT;
  c->work += n;
  return LIE_REGEX_COMPILE_OK;
}
static status grow(lie_regex_compiler *c, void **data, size_t *capacity,
                   size_t used, size_t need, size_t width, size_t limit) {
  if (need > limit || limit > SIZE_MAX / width)
    return LIE_REGEX_COMPILE_RESOURCE;
  if (need <= *capacity)
    return LIE_REGEX_COMPILE_OK;
  size_t n = *capacity ? *capacity : (limit < 8 ? limit : 8);
  while (n < need)
    n = n > limit / 2 ? limit : n * 2;
  void *p = alloc(c, n * width);
  if (!p)
    return LIE_REGEX_COMPILE_RESOURCE;
  if (used)
    memcpy(p, *data, used * width);
  drop(c, *data);
  *data = p;
  *capacity = n;
  return LIE_REGEX_COMPILE_OK;
}
static void vec_release(lie_regex_compiler *c, ids *v) {
  drop(c, v->data);
  *v = (ids){0};
}
static status append(lie_regex_compiler *c, ids *v, const uint32_t *p,
                     size_t n) {
  if (n > PART_MAX - v->count)
    return LIE_REGEX_COMPILE_RESOURCE;
  status rc = charge(c, n);
  if (rc != LIE_REGEX_COMPILE_OK)
    return rc;
  rc = grow(c, (void **)&v->data, &v->capacity, v->count, v->count + n,
            sizeof(uint32_t), PART_MAX);
  if (rc != LIE_REGEX_COMPILE_OK)
    return rc;
  if (n)
    memcpy(v->data + v->count, p, n * sizeof(uint32_t));
  v->count += n;
  return LIE_REGEX_COMPILE_OK;
}
static uint64_t word_hash(uint64_t h, uint64_t v) {
  for (unsigned i = 0; i < 8; ++i) {
    h = (h ^ (uint8_t)v) * UINT64_C(1099511628211);
    v >>= 8;
  }
  return h;
}
static uint64_t node_hash(kind k, const uint32_t *children, size_t n,
                          uint32_t low, uint32_t high) {
  uint64_t h = word_hash(UINT64_C(14695981039346656037), k);
  h = word_hash(h, low);
  h = word_hash(h, high);
  h = word_hash(h, n);
  for (size_t i = 0; i < n; ++i)
    h = word_hash(h, children[i]);
  return h;
}
static bool node_equal(const expression *a, kind k, const uint32_t *p, size_t n,
                       uint32_t low, uint32_t high) {
  return a->kind == k && a->low == low && a->high == high && a->count == n &&
         (!n || !memcmp(a->children, p, n * sizeof(uint32_t)));
}
static size_t node_slot(const lie_regex_compiler *c, uint64_t h, kind k,
                        const uint32_t *p, size_t n, uint32_t low,
                        uint32_t high) {
  size_t at = (size_t)h & (c->node_bucket_count - 1);
  while (c->node_buckets[at] != NONE) {
    const expression *a = c->nodes + c->node_buckets[at];
    if (a->hash == h && node_equal(a, k, p, n, low, high))
      break;
    at = (at + 1) & (c->node_bucket_count - 1);
  }
  return at;
}
static status node_buckets(lie_regex_compiler *c, size_t need) {
  size_t n = c->node_bucket_count ? c->node_bucket_count : 8;
  while (n < need * 2)
    n *= 2;
  if (n == c->node_bucket_count)
    return LIE_REGEX_COMPILE_OK;
  uint32_t *p = alloc(c, n * sizeof(uint32_t));
  if (!p)
    return LIE_REGEX_COMPILE_RESOURCE;
  for (size_t i = 0; i < n; ++i)
    p[i] = NONE;
  for (size_t i = 0; i < c->count; ++i) {
    size_t at = (size_t)c->nodes[i].hash & (n - 1);
    while (p[at] != NONE)
      at = (at + 1) & (n - 1);
    p[at] = (uint32_t)i;
  }
  drop(c, c->node_buckets);
  c->node_buckets = p;
  c->node_bucket_count = n;
  return LIE_REGEX_COMPILE_OK;
}
static status add_node(lie_regex_compiler *c, kind k, const uint32_t *p,
                       size_t n, uint32_t low, uint32_t high, uint32_t *out) {
  status rc = charge(c, n + 1);
  if (rc != LIE_REGEX_COMPILE_OK)
    return rc;
  uint64_t h = node_hash(k, p, n, low, high);
  if (c->node_bucket_count) {
    size_t at = node_slot(c, h, k, p, n, low, high);
    if (c->node_buckets[at] != NONE) {
      *out = c->node_buckets[at];
      return LIE_REGEX_COMPILE_OK;
    }
  }
  if (c->count >= c->d.max_expressions)
    return LIE_REGEX_COMPILE_EXPRESSION_LIMIT;
  uint64_t minimum = k == EMPTY ? NONE : k == CHARS ? 1 : 0;
  uint8_t nullable = k == EPSILON    ? UINT8_MAX
                     : k == START    ? 0xf0
                     : k == BOUNDARY ? (low ? 0x66 : 0x99)
                                     : 0;
  if (k == OR) {
    minimum = NONE;
    for (size_t i = 0; i < n; ++i) {
      const expression *a = c->nodes + p[i];
      if (a->minimum < minimum)
        minimum = a->minimum;
      nullable |= a->nullable;
    }
  } else if (k == CONCAT || k == AND) {
    nullable = UINT8_MAX;
    for (size_t i = 0; i < n; ++i) {
      const expression *a = c->nodes + p[i];
      nullable &= a->nullable;
      if (k == AND) {
        if (a->minimum > minimum)
          minimum = a->minimum;
      } else {
        minimum += a->minimum;
        if (minimum > NONE)
          minimum = NONE;
      }
    }
  } else if (k == NOT)
    nullable = (uint8_t)~c->nodes[p[0]].nullable;
  else if (k == REPEAT) {
    minimum = c->nodes[p[0]].minimum * low;
    if (minimum > NONE)
      minimum = NONE;
    nullable = low ? 0 : UINT8_MAX;
  }
  if (c->count && minimum > c->d.maximum_length) {
    *out = c->bases.empty;
    return LIE_REGEX_COMPILE_OK;
  }
  rc = node_buckets(c, c->count + 1);
  if (rc != LIE_REGEX_COMPILE_OK)
    return rc;
  rc = grow(c, (void **)&c->nodes, &c->capacity, c->count, c->count + 1,
            sizeof(expression), c->d.max_expressions);
  if (rc != LIE_REGEX_COMPILE_OK)
    return rc;
  uint32_t *children = n ? alloc(c, n * sizeof(uint32_t)) : NULL;
  if (n && !children)
    return LIE_REGEX_COMPILE_RESOURCE;
  if (n)
    memcpy(children, p, n * sizeof(uint32_t));
  size_t at = node_slot(c, h, k, p, n, low, high);
  uint32_t id = (uint32_t)c->count++;
  c->nodes[id] = (expression){k, low, high, children, n, h, minimum, nullable};
  c->node_buckets[at] = id;
  *out = id;
  return LIE_REGEX_COMPILE_OK;
}
static bool valid_ids(const lie_regex_compiler *c, const uint32_t *p,
                      size_t n) {
  if (n > PART_MAX || (n && !p))
    return false;
  for (size_t i = 0; i < n; ++i)
    if (p[i] >= c->count)
      return false;
  return true;
}
static void sift(uint32_t *p, size_t n, size_t root) {
  while (root < n / 2) {
    size_t child = root * 2 + 1;
    if (child + 1 < n && p[child] < p[child + 1])
      ++child;
    if (p[root] >= p[child])
      break;
    uint32_t v = p[root];
    p[root] = p[child];
    p[child] = v;
    root = child;
  }
}
static void sort_ids(uint32_t *p, size_t n) {
  for (size_t root = n / 2; root;)
    sift(p, n, --root);
  for (size_t end = n; end > 1;) {
    uint32_t v = p[0];
    p[0] = p[--end];
    p[end] = v;
    sift(p, end, 0);
  }
}
static bool contains_id(const ids *v, uint32_t id) {
  size_t low = 0, high = v->count;
  while (low < high) {
    size_t mid = low + (high - low) / 2;
    if (v->data[mid] < id)
      low = mid + 1;
    else
      high = mid;
  }
  return low < v->count && v->data[low] == id;
}
lie_regex_compile_status lie_regex_combine(lie_regex_compiler *c,
                                           lie_regex_operation operation,
                                           const uint32_t *parts, size_t count,
                                           uint32_t *out) {
  if (!c || !out || operation < LIE_REGEX_UNION ||
      operation > LIE_REGEX_CONCATENATION || !valid_ids(c, parts, count))
    return LIE_REGEX_COMPILE_INVALID;
  kind k = operation == LIE_REGEX_UNION          ? OR
           : operation == LIE_REGEX_INTERSECTION ? AND
                                                 : CONCAT;
  ids flat = {0};
  status rc = LIE_REGEX_COMPILE_OK;
  uint32_t result = NONE;
  for (size_t i = 0; i < count; ++i) {
    uint32_t part = parts[i];
    if (k == CONCAT) {
      if (part == c->bases.empty) {
        result = part;
        goto done;
      }
      if (part == c->bases.epsilon)
        continue;
    } else {
      if (part == (k == OR ? c->bases.all : c->bases.empty)) {
        result = part;
        goto done;
      }
      if (part == (k == OR ? c->bases.empty : c->bases.all))
        continue;
    }
    const expression *a = c->nodes + part;
    if (a->kind == k)
      rc = append(c, &flat, a->children, a->count);
    else if (k != CONCAT || part != c->bases.all || !flat.count ||
             flat.data[flat.count - 1] != c->bases.all)
      rc = append(c, &flat, &part, 1);
    if (rc != LIE_REGEX_COMPILE_OK)
      goto done;
  }
  if (k != CONCAT) {
    sort_ids(flat.data, flat.count);
    size_t used = 0;
    for (size_t i = 0; i < flat.count; ++i)
      if (!used || flat.data[used - 1] != flat.data[i])
        flat.data[used++] = flat.data[i];
    flat.count = used;
    for (size_t i = 0; i < flat.count; ++i) {
      const expression *a = c->nodes + flat.data[i];
      if (a->kind == NOT && contains_id(&flat, a->children[0])) {
        result = k == OR ? c->bases.all : c->bases.empty;
        goto done;
      }
    }
  }
  if (!flat.count)
    result = k == OR    ? c->bases.empty
             : k == AND ? c->bases.all
                        : c->bases.epsilon;
  else if (flat.count == 1)
    result = flat.data[0];
  else
    rc = add_node(c, k, flat.data, flat.count, 0, 0, &result);
done:
  vec_release(c, &flat);
  if (rc == LIE_REGEX_COMPILE_OK)
    *out = result;
  return rc;
}
lie_regex_compile_status lie_regex_not(lie_regex_compiler *c, uint32_t child,
                                       uint32_t *out) {
  if (!c || !out || child >= c->count)
    return LIE_REGEX_COMPILE_INVALID;
  if (child == c->bases.empty)
    *out = c->bases.all;
  else if (child == c->bases.all)
    *out = c->bases.empty;
  else if (c->nodes[child].kind == NOT)
    *out = c->nodes[child].children[0];
  else
    return add_node(c, NOT, &child, 1, 0, 0, out);
  return LIE_REGEX_COMPILE_OK;
}
lie_regex_compile_status lie_regex_nullable(const lie_regex_compiler *c,
                                            uint32_t id, bool start,
                                            bool previous, bool next,
                                            bool *out) {
  if (!c || !out || id >= c->count)
    return LIE_REGEX_COMPILE_INVALID;
  unsigned bit = (start ? 4u : 0u) | (previous ? 2u : 0u) | (next ? 1u : 0u);
  *out = (c->nodes[id].nullable & (1u << bit)) != 0;
  return LIE_REGEX_COMPILE_OK;
}
lie_regex_compile_status lie_regex_repeat(lie_regex_compiler *c, uint32_t child,
                                          uint32_t low, uint32_t high,
                                          uint32_t *out) {
  if (!c || !out || child >= c->count)
    return LIE_REGEX_COMPILE_INVALID;
  if (high < low)
    return LIE_REGEX_COMPILE_REPETITION;
  if (!high || child == c->bases.epsilon) {
    *out = c->bases.epsilon;
    return LIE_REGEX_COMPILE_OK;
  }
  if (child == c->bases.empty) {
    *out = low ? c->bases.empty : c->bases.epsilon;
    return LIE_REGEX_COMPILE_OK;
  }
  if (low == 1 && high == 1) {
    *out = child;
    return LIE_REGEX_COMPILE_OK;
  }
  if (c->nodes[child].nullable & 1u) {
    uint32_t not_epsilon;
    status rc = lie_regex_not(c, c->bases.epsilon, &not_epsilon);
    if (rc != LIE_REGEX_COMPILE_OK)
      return rc;
    uint32_t parts[] = {child, not_epsilon};
    rc = lie_regex_combine(c, LIE_REGEX_INTERSECTION, parts, 2, &child);
    if (rc != LIE_REGEX_COMPILE_OK)
      return rc;
    low = 0;
  }
  uint64_t width = c->nodes[child].minimum;
  if (width && high != NONE) {
    uint64_t cap = c->d.maximum_length / width;
    if (cap < high)
      high = (uint32_t)cap;
  }
  if (high < low) {
    *out = c->bases.empty;
    return LIE_REGEX_COMPILE_OK;
  }
  return add_node(c, REPEAT, &child, 1, low, high, out);
}
lie_regex_compile_status lie_regex_class_add(lie_regex_compiler *c,
                                             const lie_unicode_range *ranges,
                                             size_t count, uint32_t *out) {
  if (!c || !out || (count && !ranges))
    return LIE_REGEX_COMPILE_INVALID;
  if (count > c->d.max_ranges - c->range_count || c->class_count >= TABLE_MAX)
    return LIE_REGEX_COMPILE_CLASS_LIMIT;
  for (size_t i = 0; i < count; ++i)
    if (ranges[i].first > ranges[i].last || ranges[i].last > 0x10ffff ||
        (ranges[i].first <= 0xdfff && ranges[i].last >= 0xd800) ||
        (i && ranges[i].first <= ranges[i - 1].last))
      return LIE_REGEX_COMPILE_INVALID;
  status rc = charge(c, count + 1);
  if (rc != LIE_REGEX_COMPILE_OK)
    return rc;
  rc = grow(c, (void **)&c->classes, &c->class_capacity, c->class_count,
            c->class_count + 1, sizeof(character_class), TABLE_MAX);
  if (rc != LIE_REGEX_COMPILE_OK)
    return rc;
  lie_unicode_range *p = count ? alloc(c, count * sizeof(*p)) : NULL;
  if (count && !p)
    return LIE_REGEX_COMPILE_RESOURCE;
  if (count)
    memcpy(p, ranges, count * sizeof(*p));
  uint32_t id = (uint32_t)c->class_count++;
  c->classes[id] = (character_class){p, count};
  c->range_count += count;
  *out = id;
  return LIE_REGEX_COMPILE_OK;
}
lie_regex_compile_status lie_regex_chars(lie_regex_compiler *c, uint32_t id,
                                         uint32_t *out) {
  if (!c || !out || id >= c->class_count)
    return LIE_REGEX_COMPILE_INVALID;
  return add_node(c, CHARS, NULL, 0, id, 0, out);
}
lie_regex_compile_status lie_regex_boundary(lie_regex_compiler *c,
                                            bool positive, uint32_t *out) {
  if (!c || !out)
    return LIE_REGEX_COMPILE_INVALID;
  uint32_t id;
  status rc = add_node(c, BOUNDARY, NULL, 0, positive ? 1u : 0u, 0, &id);
  if (rc == LIE_REGEX_COMPILE_OK) {
    c->boundaries = true;
    *out = id;
  }
  return rc;
}
void lie_regex_compiler_description_init(lie_regex_compiler_description *d) {
  if (d)
    *d = (lie_regex_compiler_description){.abi_version = LIE_REGEX_COMPILER_ABI,
                                          .struct_bytes = sizeof(*d),
                                          .max_expressions = EXPR_MAX,
                                          .max_derivatives = DERIV_MAX,
                                          .max_states = STATE_MAX,
                                          .max_transitions = TABLE_MAX,
                                          .max_ranges = TABLE_MAX,
                                          .max_work = 256000000,
                                          .maximum_length = NONE};
}
void lie_regex_compiler_release(lie_regex_compiler *c) {
  if (!c)
    return;
  for (size_t i = 0; i < c->count; ++i)
    drop(c, c->nodes[i].children);
  for (size_t i = 0; i < c->class_count; ++i)
    drop(c, c->classes[i].ranges);
  drop(c, c->nodes);
  drop(c, c->node_buckets);
  drop(c, c->classes);
  drop(c, c->derivatives);
  drop(c, c->derivative_buckets);
  lie_grammar_allocator a = c->d.allocator;
  a.release(a.context, c);
}
lie_regex_compile_status
lie_regex_compiler_create(const lie_regex_compiler_description *d,
                          lie_regex_compiler **out) {
  if (!d || !out || d->abi_version != LIE_REGEX_COMPILER_ABI ||
      d->struct_bytes != sizeof(*d) || !d->max_expressions ||
      d->max_expressions > EXPR_MAX || !d->max_derivatives ||
      d->max_derivatives > DERIV_MAX || !d->max_states ||
      d->max_states > STATE_MAX || !d->max_transitions ||
      d->max_transitions > TABLE_MAX || d->max_ranges < 2 ||
      d->max_ranges > TABLE_MAX || !d->max_work || d->max_work == SIZE_MAX ||
      (!!d->allocator.allocate != !!d->allocator.release))
    return LIE_REGEX_COMPILE_INVALID;
  lie_grammar_allocator a = d->allocator;
  if (!a.allocate)
    a = (lie_grammar_allocator){NULL, ordinary_allocate, ordinary_release};
  lie_regex_compiler *c = a.allocate(a.context, sizeof(*c));
  if (!c)
    return LIE_REGEX_COMPILE_RESOURCE;
  *c = (lie_regex_compiler){.d = *d, .bases = {NONE, NONE, NONE, NONE, NONE}};
  c->d.allocator = a;
  status rc = add_node(c, EMPTY, NULL, 0, 0, 0, &c->bases.empty);
  if (rc == LIE_REGEX_COMPILE_OK)
    rc = add_node(c, EPSILON, NULL, 0, 0, 0, &c->bases.epsilon);
  if (rc == LIE_REGEX_COMPILE_OK)
    rc = add_node(c, START, NULL, 0, 0, 0, &c->bases.start);
  const lie_unicode_range scalars[] = {{0, 0xd7ff}, {0xe000, 0x10ffff}};
  uint32_t cls;
  if (rc == LIE_REGEX_COMPILE_OK)
    rc = lie_regex_class_add(c, scalars, 2, &cls);
  if (rc == LIE_REGEX_COMPILE_OK)
    rc = lie_regex_chars(c, cls, &c->bases.any);
  if (rc == LIE_REGEX_COMPILE_OK)
    rc = lie_regex_repeat(c, c->bases.any, 0, NONE, &c->bases.all);
  if (rc != LIE_REGEX_COMPILE_OK) {
    lie_regex_compiler_release(c);
    return rc;
  }
  *out = c;
  return LIE_REGEX_COMPILE_OK;
}
lie_regex_compile_status lie_regex_compiler_bases(const lie_regex_compiler *c,
                                                  lie_regex_bases *out) {
  if (!c || !out)
    return LIE_REGEX_COMPILE_INVALID;
  *out = c->bases;
  return LIE_REGEX_COMPILE_OK;
}
static bool word(uint32_t cp) {
  return (cp >= 'a' && cp <= 'z') || (cp >= 'A' && cp <= 'Z') ||
         (cp >= '0' && cp <= '9') || cp == '_';
}
static bool class_contains(const character_class *a, uint32_t cp) {
  size_t low = 0, high = a->count;
  while (low < high) {
    size_t mid = low + (high - low) / 2;
    if (a->ranges[mid].last < cp)
      low = mid + 1;
    else
      high = mid;
  }
  return low < a->count && a->ranges[low].first <= cp;
}
static uint64_t derivative_hash(uint32_t id, uint32_t cp, uint8_t flags) {
  return word_hash(word_hash(word_hash(UINT64_C(14695981039346656037), id), cp),
                   flags);
}
static size_t derivative_slot(const lie_regex_compiler *c, uint32_t id,
                              uint32_t cp, uint8_t flags) {
  size_t at =
      (size_t)derivative_hash(id, cp, flags) & (c->derivative_bucket_count - 1);
  while (c->derivative_buckets[at] != NONE) {
    const derivative *d = c->derivatives + c->derivative_buckets[at];
    if (d->expression == id && d->cp == cp && d->flags == flags)
      break;
    at = (at + 1) & (c->derivative_bucket_count - 1);
  }
  return at;
}
static bool derivative_find(const lie_regex_compiler *c, uint32_t id,
                            uint32_t cp, uint8_t flags, uint32_t *out) {
  if (!c->derivative_bucket_count)
    return false;
  size_t at = derivative_slot(c, id, cp, flags);
  if (c->derivative_buckets[at] == NONE)
    return false;
  *out = c->derivatives[c->derivative_buckets[at]].result;
  return true;
}
static status derivative_store(lie_regex_compiler *c, uint32_t id, uint32_t cp,
                               uint8_t flags, uint32_t result) {
  if (c->derivative_count >= c->d.max_derivatives)
    return LIE_REGEX_COMPILE_DERIVATIVE_LIMIT;
  size_t n = c->derivative_bucket_count ? c->derivative_bucket_count : 8;
  while (n < (c->derivative_count + 1) * 2)
    n *= 2;
  if (n != c->derivative_bucket_count) {
    uint32_t *p = alloc(c, n * sizeof(uint32_t));
    if (!p)
      return LIE_REGEX_COMPILE_RESOURCE;
    for (size_t i = 0; i < n; ++i)
      p[i] = NONE;
    for (size_t i = 0; i < c->derivative_count; ++i) {
      const derivative *d = c->derivatives + i;
      size_t at =
          (size_t)derivative_hash(d->expression, d->cp, d->flags) & (n - 1);
      while (p[at] != NONE)
        at = (at + 1) & (n - 1);
      p[at] = (uint32_t)i;
    }
    drop(c, c->derivative_buckets);
    c->derivative_buckets = p;
    c->derivative_bucket_count = n;
  }
  status rc = grow(c, (void **)&c->derivatives, &c->derivative_capacity,
                   c->derivative_count, c->derivative_count + 1,
                   sizeof(derivative), c->d.max_derivatives);
  if (rc != LIE_REGEX_COMPILE_OK)
    return rc;
  size_t at = derivative_slot(c, id, cp, flags);
  uint32_t index = (uint32_t)c->derivative_count++;
  c->derivatives[index] = (derivative){id, cp, result, flags};
  c->derivative_buckets[at] = index;
  return LIE_REGEX_COMPILE_OK;
}
typedef struct {
  uint32_t id;
  expression node;
  size_t index;
  ids parts;
} derive_frame;
lie_regex_compile_status lie_regex_derive(lie_regex_compiler *c, uint32_t id,
                                          uint32_t cp, bool at_start,
                                          bool previous, uint32_t *out) {
  if (!c || !out || id >= c->count || cp > 0x10ffff ||
      (cp >= 0xd800 && cp <= 0xdfff))
    return LIE_REGEX_COMPILE_INVALID;
  uint8_t flags = (uint8_t)((at_start ? 2u : 0u) | (previous ? 1u : 0u));
  uint32_t result;
  if (derivative_find(c, id, cp, flags, &result)) {
    *out = result;
    return LIE_REGEX_COMPILE_OK;
  }
  derive_frame *frames = NULL;
  size_t depth = 0, capacity = 0;
  status rc = grow(c, (void **)&frames, &capacity, 0, 1, sizeof(derive_frame),
                   c->d.max_expressions);
  if (rc != LIE_REGEX_COMPILE_OK)
    return rc;
  frames[depth++] = (derive_frame){.id = id, .node = c->nodes[id]};
  while (depth && rc == LIE_REGEX_COMPILE_OK) {
    rc = charge(c, 1);
    if (rc != LIE_REGEX_COMPILE_OK)
      break;
    derive_frame *f = frames + depth - 1;
    kind k = f->node.kind;
    if (f->index < f->node.count) {
      uint32_t child = f->node.children[f->index], derived;
      if (!derivative_find(c, child, cp, flags, &derived)) {
        rc = grow(c, (void **)&frames, &capacity, depth, depth + 1,
                  sizeof(derive_frame), c->d.max_expressions);
        if (rc != LIE_REGEX_COMPILE_OK)
          break;
        frames[depth++] = (derive_frame){.id = child, .node = c->nodes[child]};
        continue;
      }
      if (k == CONCAT) {
        ids suffix = {0};
        rc = append(c, &suffix, &derived, 1);
        if (rc == LIE_REGEX_COMPILE_OK)
          rc = append(c, &suffix, f->node.children + f->index + 1,
                      f->node.count - f->index - 1);
        if (rc == LIE_REGEX_COMPILE_OK)
          rc = lie_regex_combine(c, LIE_REGEX_CONCATENATION, suffix.data,
                                 suffix.count, &derived);
        vec_release(c, &suffix);
        if (rc != LIE_REGEX_COMPILE_OK)
          break;
        rc = append(c, &f->parts, &derived, 1);
        ++f->index;
        unsigned bit =
            (at_start ? 4u : 0u) | (previous ? 2u : 0u) | (word(cp) ? 1u : 0u);
        if (!(c->nodes[child].nullable & (1u << bit)))
          f->index = f->node.count;
      } else {
        rc = append(c, &f->parts, &derived, 1);
        ++f->index;
      }
      continue;
    }
    result = c->bases.empty;
    if (k == CHARS)
      result = class_contains(c->classes + f->node.low, cp) ? c->bases.epsilon
                                                            : c->bases.empty;
    else if (k == NOT)
      rc = lie_regex_not(c, f->parts.data[0], &result);
    else if (k == OR || k == AND || k == CONCAT)
      rc = lie_regex_combine(
          c, k == AND ? LIE_REGEX_INTERSECTION : LIE_REGEX_UNION, f->parts.data,
          f->parts.count, &result);
    else if (k == REPEAT) {
      uint32_t repeated;
      rc = lie_regex_repeat(
          c, f->node.children[0], f->node.low ? f->node.low - 1 : 0,
          f->node.high == NONE ? NONE : f->node.high - 1, &repeated);
      if (rc == LIE_REGEX_COMPILE_OK) {
        uint32_t parts[] = {f->parts.data[0], repeated};
        rc = lie_regex_combine(c, LIE_REGEX_CONCATENATION, parts, 2, &result);
      }
    }
    if (rc == LIE_REGEX_COMPILE_OK)
      rc = derivative_store(c, f->id, cp, flags, result);
    if (rc == LIE_REGEX_COMPILE_OK) {
      vec_release(c, &f->parts);
      --depth;
    }
  }
  for (size_t i = 0; i < depth; ++i)
    vec_release(c, &frames[i].parts);
  drop(c, frames);
  if (rc == LIE_REGEX_COMPILE_OK)
    *out = result;
  return rc;
}

typedef struct {
  ids members;
  lie_unicode_range *ranges;
  size_t count, capacity;
  uint64_t hash;
} partition;
typedef struct {
  uint32_t expression, depth;
  uint8_t flags;
} graph_state;
typedef struct {
  partition *alphabet;
  size_t alphabet_count, alphabet_capacity;
  uint32_t *part_buckets;
  size_t part_bucket_count;
  graph_state *states;
  size_t state_count, state_capacity;
  uint32_t *state_buckets;
  size_t state_bucket_count;
  uint8_t *accepting;
  size_t accepting_capacity;
  uint32_t *transitions;
  size_t transition_count, transition_capacity;
} graph;
static void graph_release(lie_regex_compiler *c, graph *g) {
  for (size_t i = 0; i < g->alphabet_count; ++i) {
    vec_release(c, &g->alphabet[i].members);
    drop(c, g->alphabet[i].ranges);
  }
  drop(c, g->alphabet);
  drop(c, g->part_buckets);
  drop(c, g->states);
  drop(c, g->state_buckets);
  drop(c, g->accepting);
  drop(c, g->transitions);
}
static uint64_t members_hash(const ids *m) {
  uint64_t h = word_hash(UINT64_C(14695981039346656037), m->count);
  for (size_t i = 0; i < m->count; ++i)
    h = word_hash(h, m->data[i]);
  return h;
}
static bool members_equal(const ids *a, const ids *b) {
  return a->count == b->count &&
         (!a->count || !memcmp(a->data, b->data, a->count * sizeof(uint32_t)));
}
static size_t partition_slot(const graph *g, const ids *members,
                             uint64_t hash) {
  size_t at = (size_t)hash & (g->part_bucket_count - 1);
  while (g->part_buckets[at] != NONE) {
    const partition *p = g->alphabet + g->part_buckets[at];
    if (p->hash == hash && members_equal(&p->members, members))
      break;
    at = (at + 1) & (g->part_bucket_count - 1);
  }
  return at;
}
static status partition_buckets(lie_regex_compiler *c, graph *g, size_t need) {
  size_t n = g->part_bucket_count ? g->part_bucket_count : 8;
  while (n < need * 2)
    n *= 2;
  if (n == g->part_bucket_count)
    return LIE_REGEX_COMPILE_OK;
  uint32_t *p = alloc(c, n * sizeof(uint32_t));
  if (!p)
    return LIE_REGEX_COMPILE_RESOURCE;
  for (size_t i = 0; i < n; ++i)
    p[i] = NONE;
  for (size_t i = 0; i < g->alphabet_count; ++i) {
    size_t at = (size_t)g->alphabet[i].hash & (n - 1);
    while (p[at] != NONE)
      at = (at + 1) & (n - 1);
    p[at] = (uint32_t)i;
  }
  drop(c, g->part_buckets);
  g->part_buckets = p;
  g->part_bucket_count = n;
  return LIE_REGEX_COMPILE_OK;
}
static status partition_interval(lie_regex_compiler *c, graph *g, ids *members,
                                 uint32_t first, uint32_t last) {
  uint64_t hash = members_hash(members);
  status rc = partition_buckets(c, g, g->alphabet_count + 1);
  if (rc != LIE_REGEX_COMPILE_OK)
    return rc;
  size_t at = partition_slot(g, members, hash);
  uint32_t id = g->part_buckets[at];
  if (id == NONE) {
    if (g->alphabet_count >= c->d.max_transitions)
      return LIE_REGEX_COMPILE_STATE_LIMIT;
    rc =
        grow(c, (void **)&g->alphabet, &g->alphabet_capacity, g->alphabet_count,
             g->alphabet_count + 1, sizeof(partition), c->d.max_transitions);
    if (rc != LIE_REGEX_COMPILE_OK)
      return rc;
    ids copy = {0};
    rc = append(c, &copy, members->data, members->count);
    if (rc != LIE_REGEX_COMPILE_OK) {
      vec_release(c, &copy);
      return rc;
    }
    id = (uint32_t)g->alphabet_count++;
    g->alphabet[id] = (partition){.members = copy, .hash = hash};
    g->part_buckets[at] = id;
  }
  partition *p = g->alphabet + id;
  if (p->count && p->ranges[p->count - 1].last + 1 == first)
    p->ranges[p->count - 1].last = last;
  else {
    rc = grow(c, (void **)&p->ranges, &p->capacity, p->count, p->count + 1,
              sizeof(lie_unicode_range), c->d.max_ranges);
    if (rc != LIE_REGEX_COMPILE_OK)
      return rc;
    p->ranges[p->count++] = (lie_unicode_range){first, last};
  }
  return LIE_REGEX_COMPILE_OK;
}
static status build_partition(lie_regex_compiler *c, graph *g) {
  ids endpoints = {0}, members = {0};
  const uint32_t base[] = {0, 0xd800, 0xe000, 0x110000};
  status rc = append(c, &endpoints, base, 4);
  for (size_t i = 0; i < c->class_count && rc == LIE_REGEX_COMPILE_OK; ++i)
    for (size_t j = 0; j < c->classes[i].count && rc == LIE_REGEX_COMPILE_OK;
         ++j) {
      const lie_unicode_range r = c->classes[i].ranges[j];
      uint32_t pair[] = {r.first, r.last + 1};
      rc = append(c, &endpoints, pair, 2);
    }
  if (rc == LIE_REGEX_COMPILE_OK && c->boundaries) {
    const uint32_t words[] = {'0', '9' + 1, 'A', 'Z' + 1,
                              '_', '_' + 1, 'a', 'z' + 1};
    rc = append(c, &endpoints, words, 8);
  }
  if (rc == LIE_REGEX_COMPILE_OK) {
    sort_ids(endpoints.data, endpoints.count);
    size_t used = 0;
    for (size_t i = 0; i < endpoints.count; ++i)
      if (!used || endpoints.data[used - 1] != endpoints.data[i])
        endpoints.data[used++] = endpoints.data[i];
    endpoints.count = used;
    for (size_t i = 0; i + 1 < endpoints.count && rc == LIE_REGEX_COMPILE_OK;
         ++i) {
      uint32_t first = endpoints.data[i], last = endpoints.data[i + 1] - 1;
      if (first >= 0xd800 && first <= 0xdfff)
        continue;
      members.count = 0;
      rc = charge(c, c->class_count + 1);
      if (rc != LIE_REGEX_COMPILE_OK)
        break;
      for (size_t j = 0; j < c->class_count && rc == LIE_REGEX_COMPILE_OK; ++j)
        if (class_contains(c->classes + j, first)) {
          uint32_t id = (uint32_t)j;
          rc = append(c, &members, &id, 1);
        }
      if (rc == LIE_REGEX_COMPILE_OK && c->boundaries && word(first)) {
        uint32_t id = NONE;
        rc = append(c, &members, &id, 1);
      }
      if (rc == LIE_REGEX_COMPILE_OK)
        rc = partition_interval(c, g, &members, first, last);
    }
  }
  vec_release(c, &members);
  vec_release(c, &endpoints);
  return rc;
}
static uint64_t state_hash(uint32_t expression, uint8_t flags) {
  return word_hash(word_hash(UINT64_C(14695981039346656037), expression),
                   flags);
}
static size_t state_slot(const graph *g, uint32_t expression, uint8_t flags) {
  size_t at =
      (size_t)state_hash(expression, flags) & (g->state_bucket_count - 1);
  while (g->state_buckets[at] != NONE) {
    const graph_state *s = g->states + g->state_buckets[at];
    if (s->expression == expression && s->flags == flags)
      break;
    at = (at + 1) & (g->state_bucket_count - 1);
  }
  return at;
}
static status intern_state(lie_regex_compiler *c, graph *g, uint32_t expression,
                           uint8_t flags, uint32_t depth, uint32_t *out) {
  if (g->state_bucket_count) {
    size_t at = state_slot(g, expression, flags);
    if (g->state_buckets[at] != NONE) {
      *out = g->state_buckets[at];
      return LIE_REGEX_COMPILE_OK;
    }
  }
  if (g->state_count >= c->d.max_states ||
      g->state_count + 1 > c->d.max_transitions / g->alphabet_count)
    return LIE_REGEX_COMPILE_STATE_LIMIT;
  size_t n = g->state_bucket_count ? g->state_bucket_count : 8;
  while (n < (g->state_count + 1) * 2)
    n *= 2;
  if (n != g->state_bucket_count) {
    uint32_t *p = alloc(c, n * sizeof(uint32_t));
    if (!p)
      return LIE_REGEX_COMPILE_RESOURCE;
    for (size_t i = 0; i < n; ++i)
      p[i] = NONE;
    for (size_t i = 0; i < g->state_count; ++i) {
      const graph_state *s = g->states + i;
      size_t at = (size_t)state_hash(s->expression, s->flags) & (n - 1);
      while (p[at] != NONE)
        at = (at + 1) & (n - 1);
      p[at] = (uint32_t)i;
    }
    drop(c, g->state_buckets);
    g->state_buckets = p;
    g->state_bucket_count = n;
  }
  status rc = grow(c, (void **)&g->states, &g->state_capacity, g->state_count,
                   g->state_count + 1, sizeof(graph_state), c->d.max_states);
  if (rc != LIE_REGEX_COMPILE_OK)
    return rc;
  size_t at = state_slot(g, expression, flags);
  uint32_t id = (uint32_t)g->state_count++;
  g->states[id] = (graph_state){expression, depth, flags};
  g->state_buckets[at] = id;
  *out = id;
  return LIE_REGEX_COMPILE_OK;
}
lie_regex_compile_status lie_regex_seal(lie_regex_compiler *c, uint32_t root,
                                        lie_regex_program **out) {
  if (!c || !out || root >= c->count)
    return LIE_REGEX_COMPILE_INVALID;
  graph g = {0};
  status rc = build_partition(c, &g);
  uint32_t id;
  if (rc == LIE_REGEX_COMPILE_OK)
    rc = intern_state(c, &g, root, 2, 0, &id);
  for (size_t i = 0; i < g.state_count && rc == LIE_REGEX_COMPILE_OK; ++i) {
    graph_state s = g.states[i];
    rc = grow(c, (void **)&g.accepting, &g.accepting_capacity, i, i + 1,
              sizeof(uint8_t), c->d.max_states);
    if (rc != LIE_REGEX_COMPILE_OK)
      break;
    bool accepting;
    rc = lie_regex_nullable(c, s.expression, (s.flags & 2) != 0,
                            (s.flags & 1) != 0, false, &accepting);
    if (rc != LIE_REGEX_COMPILE_OK)
      break;
    g.accepting[i] = (uint8_t)accepting;
    for (size_t j = 0; j < g.alphabet_count && rc == LIE_REGEX_COMPILE_OK;
         ++j) {
      uint32_t next = NONE;
      rc = charge(c, 1);
      if (rc != LIE_REGEX_COMPILE_OK)
        break;
      if (s.depth < c->d.maximum_length) {
        uint32_t cp = g.alphabet[j].ranges[0].first, derived;
        rc = lie_regex_derive(c, s.expression, cp, (s.flags & 2) != 0,
                              (s.flags & 1) != 0, &derived);
        if (rc != LIE_REGEX_COMPILE_OK)
          break;
        if (derived != c->bases.empty)
          rc =
              intern_state(c, &g, derived, (uint8_t)(c->boundaries && word(cp)),
                           s.depth + 1, &next);
      }
      if (rc == LIE_REGEX_COMPILE_OK)
        rc = grow(c, (void **)&g.transitions, &g.transition_capacity,
                  g.transition_count, g.transition_count + 1, sizeof(uint32_t),
                  c->d.max_transitions);
      if (rc == LIE_REGEX_COMPILE_OK)
        g.transitions[g.transition_count++] = next;
    }
  }
  lie_grammar_range *classes = NULL;
  lie_unicode_range *ranges = NULL;
  size_t range_count = 0;
  if (rc == LIE_REGEX_COMPILE_OK) {
    for (size_t i = 0; i < g.alphabet_count; ++i) {
      if (g.alphabet[i].count > c->d.max_ranges - range_count) {
        rc = LIE_REGEX_COMPILE_CLASS_LIMIT;
        break;
      }
      range_count += g.alphabet[i].count;
    }
  }
  if (rc == LIE_REGEX_COMPILE_OK) {
    classes = alloc(c, g.alphabet_count * sizeof(*classes));
    ranges = alloc(c, range_count * sizeof(*ranges));
    if (!classes || !ranges)
      rc = LIE_REGEX_COMPILE_RESOURCE;
  }
  if (rc == LIE_REGEX_COMPILE_OK) {
    size_t at = 0;
    for (size_t i = 0; i < g.alphabet_count; ++i) {
      classes[i] =
          (lie_grammar_range){(uint32_t)at, (uint32_t)g.alphabet[i].count};
      memcpy(ranges + at, g.alphabet[i].ranges,
             g.alphabet[i].count * sizeof(*ranges));
      at += g.alphabet[i].count;
    }
    lie_regex_description d;
    lie_regex_description_init(&d);
    d.classes = classes;
    d.class_count = g.alphabet_count;
    d.ranges = ranges;
    d.range_count = range_count;
    d.accepting = g.accepting;
    d.state_count = g.state_count;
    d.transitions = g.transitions;
    d.allocator = c->d.allocator;
    d.limits.max_states = c->d.max_states;
    d.limits.max_transitions = c->d.max_transitions;
    d.limits.max_ranges = c->d.max_ranges;
    d.limits.max_work = c->d.max_work;
    lie_regex_program *program = NULL;
    lie_regex_status runtime = lie_regex_create(&d, &program);
    rc = runtime == LIE_REGEX_OK           ? LIE_REGEX_COMPILE_OK
         : runtime == LIE_REGEX_RESOURCE   ? LIE_REGEX_COMPILE_RESOURCE
         : runtime == LIE_REGEX_WORK_LIMIT ? LIE_REGEX_COMPILE_WORK_LIMIT
                                           : LIE_REGEX_COMPILE_INVALID;
    if (rc == LIE_REGEX_COMPILE_OK)
      *out = program;
  }
  drop(c, classes);
  drop(c, ranges);
  graph_release(c, &g);
  return rc;
}
