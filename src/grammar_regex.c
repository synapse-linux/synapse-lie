/* SPDX-License-Identifier: MIT */
/* Unicode DFA runtime port from official MIT Gufo f783fedb9bea2ec7de941f6da4e02f4a4596b29e,
 * src/core/json_schema_regex.cpp; compiler remains independently transitional. */
#include "lie/grammar_regex.h"
#include <stdlib.h>
#include <string.h>
struct lie_regex_program {
  lie_grammar_allocator allocator;
  size_t states, classes, ranges, max_work;
  uint32_t maximum_suffix;
  uint32_t *storage, *next, *accepting, *distance, *offsets, *successors;
  lie_grammar_range *class_ranges;
  lie_unicode_range *unicode;
};
typedef struct { uint32_t *allocation, *active, *anchor, *reachable; } scratch;
static void *default_alloc(void *ctx, size_t bytes) { (void)ctx; return malloc(bytes); }
static void default_free(void *ctx, void *ptr) { (void)ctx; free(ptr); }
static lie_regex_status spend(size_t *work, size_t n) {
  if (n > *work) return LIE_REGEX_WORK_LIMIT;
  *work -= n; return LIE_REGEX_OK;
}
#define TRY(x) do { lie_regex_status rc_ = (x); if (rc_ != LIE_REGEX_OK) return rc_; } while (0)
void lie_regex_description_init(lie_regex_description *d) {
  if (!d) return;
  memset(d, 0, sizeof(*d)); d->abi_version = LIE_REGEX_ABI; d->struct_bytes = sizeof(*d);
  d->limits = (lie_regex_limits){LIE_REGEX_ABI,sizeof(lie_regex_limits),4096,262144,262144,256000000};
}
static lie_regex_status validate(const lie_regex_description *d) {
  if (!d || d->abi_version != LIE_REGEX_ABI || d->struct_bytes != sizeof(*d) ||
      d->limits.abi_version != LIE_REGEX_ABI || d->limits.struct_bytes != sizeof(d->limits) ||
      !d->state_count || d->state_count >= LIE_REGEX_DEAD || !d->class_count ||
      !d->classes || !d->accepting || !d->transitions || !d->ranges || !d->limits.max_work ||
      !!d->allocator.allocate != !!d->allocator.release) return LIE_REGEX_INVALID;
  if (d->state_count > d->limits.max_states || d->range_count > d->limits.max_ranges ||
      d->class_count > d->limits.max_transitions / d->state_count ||
      d->class_count > UINT32_MAX || d->range_count > UINT32_MAX) return LIE_REGEX_RESOURCE;
  /* All table-size arithmetic below is also checked, independently of caller budgets. */
  if (d->state_count > (SIZE_MAX / 4 - 1) / 4 ||
      d->class_count > SIZE_MAX / d->state_count / 8 ||
      d->range_count > SIZE_MAX / 16 || d->class_count > SIZE_MAX / 16) return LIE_REGEX_RESOURCE;
  for (size_t c = 0; c < d->class_count; ++c) {
    lie_grammar_range r = d->classes[c];
    if (!r.count || r.offset > d->range_count || r.count > d->range_count - r.offset) return LIE_REGEX_INVALID;
    for (size_t i = 0; i < r.count; ++i) {
      lie_unicode_range u = d->ranges[r.offset + i];
      if (u.first > u.last || u.last > 0x10ffff || (u.first <= 0xdfff && u.last >= 0xd800) ||
          (i && d->ranges[r.offset + i - 1].last >= u.first)) return LIE_REGEX_INVALID;
    }
  }
  for (size_t s = 0; s < d->state_count; ++s) {
    if (d->accepting[s] > 1) return LIE_REGEX_INVALID;
    for (size_t c = 0; c < d->class_count; ++c) {
      uint32_t next = d->transitions[s * d->class_count + c];
      if (next != LIE_REGEX_DEAD && next >= d->state_count) return LIE_REGEX_INVALID;
    }
  }
  return LIE_REGEX_OK;
}
static lie_regex_status build(lie_regex_program *p, uint32_t *temp, size_t *work) {
  uint32_t *seen = temp, *counts = seen + p->states, *cursor = counts + p->states + 1;
  uint32_t *queue = cursor + p->states, *predecessors = queue + p->states;
  size_t edges = 0;
  memset(counts, 0, (p->states + 1) * sizeof(*counts));
  for (size_t s = 0; s < p->states; ++s) {
    TRY(spend(work, p->states * 2 + p->classes));
    memset(seen, 0, p->states * sizeof(*seen));
    for (size_t c = 0; c < p->classes; ++c) {
      uint32_t next = p->next[s * p->classes + c];
      if (next != LIE_REGEX_DEAD) seen[next] = 1;
    }
    p->offsets[s] = (uint32_t)edges;
    for (size_t next = 0; next < p->states; ++next)
      if (seen[next]) { p->successors[edges++] = (uint32_t)next; ++counts[next + 1]; }
  }
  p->offsets[p->states] = (uint32_t)edges;
  for (size_t s = 0; s < p->states; ++s) { counts[s + 1] += counts[s]; cursor[s] = counts[s]; }
  for (size_t s = 0; s < p->states; ++s)
    for (uint32_t i = p->offsets[s]; i < p->offsets[s + 1]; ++i)
      predecessors[cursor[p->successors[i]]++] = (uint32_t)s;
  size_t head = 0, tail = 0;
  for (size_t s = 0; s < p->states; ++s) {
    p->distance[s] = p->accepting[s] ? 0 : LIE_REGEX_DEAD;
    if (p->accepting[s]) queue[tail++] = (uint32_t)s;
  }
  while (head < tail) {
    uint32_t s = queue[head++]; TRY(spend(work, counts[s + 1] - counts[s] + 1));
    for (uint32_t i = counts[s]; i < counts[s + 1]; ++i) {
      uint32_t previous = predecessors[i];
      if (p->distance[previous] == LIE_REGEX_DEAD) {
        p->distance[previous] = p->distance[s] + 1; queue[tail++] = previous;
      }
    }
  }
  TRY(spend(work, p->states * p->classes + p->states));
  for (size_t i = 0; i < p->states * p->classes; ++i)
    if (p->next[i] != LIE_REGEX_DEAD && p->distance[p->next[i]] == LIE_REGEX_DEAD) p->next[i] = LIE_REGEX_DEAD;
  for (size_t s = 0; s < p->states; ++s)
    if (p->distance[s] != LIE_REGEX_DEAD && p->distance[s] > p->maximum_suffix) p->maximum_suffix = p->distance[s];
  return LIE_REGEX_OK;
}
lie_regex_status lie_regex_create(const lie_regex_description *d, lie_regex_program **out) {
  if (!out) return LIE_REGEX_INVALID;
  lie_regex_status rc = validate(d); if (rc != LIE_REGEX_OK) return rc;
  lie_grammar_allocator a = d->allocator;
  if (!a.allocate) { a.allocate = default_alloc; a.release = default_free; }
  size_t n = d->state_count, c = d->class_count, r = d->range_count, t = n * c;
  /* Geometry is bounded above before allocating the contiguous word tables. */
  if (t > UINT32_MAX || t > (SIZE_MAX / sizeof(uint32_t) - 1) / 2) return LIE_REGEX_RESOURCE;
  size_t words = 2 * t;
  if (3 * n + 1 > SIZE_MAX / 4 - words || 4 * n + 1 > SIZE_MAX / 4 - t) return LIE_REGEX_RESOURCE;
  words += 3 * n + 1;
  if (2 * c > SIZE_MAX / 4 - words || 2 * r > SIZE_MAX / 4 - words - 2 * c) return LIE_REGEX_RESOURCE;
  words += 2 * c + 2 * r;
  lie_regex_program *p = a.allocate(a.context, sizeof(*p)); if (!p) return LIE_REGEX_RESOURCE;
  memset(p, 0, sizeof(*p)); p->allocator = a; p->states = n; p->classes = c; p->ranges = r; p->max_work = d->limits.max_work;
  p->storage = a.allocate(a.context, words * sizeof(uint32_t));
  if (!p->storage) { a.release(a.context,p); return LIE_REGEX_RESOURCE; }
  p->next = p->storage; p->successors = p->next + t;
  p->accepting = p->successors + t; p->distance = p->accepting + n; p->offsets = p->distance + n;
  p->class_ranges = (lie_grammar_range *)(p->offsets + n + 1);
  p->unicode = (lie_unicode_range *)(p->class_ranges + c);
  memcpy(p->next, d->transitions, t * sizeof(*p->next));
  memcpy(p->class_ranges, d->classes, c * sizeof(*p->class_ranges));
  memcpy(p->unicode, d->ranges, r * sizeof(*p->unicode));
  for (size_t s = 0; s < n; ++s) p->accepting[s] = d->accepting[s];
  uint32_t *temp = a.allocate(a.context, (4 * n + 1 + t) * sizeof(*temp));
  if (!temp) { lie_regex_release(p); return LIE_REGEX_RESOURCE; }
  size_t work = p->max_work; rc = build(p, temp, &work); a.release(a.context,temp);
  if (rc != LIE_REGEX_OK) lie_regex_release(p); else *out = p;
  return rc;
}
void lie_regex_release(lie_regex_program *p) {
  if (p) { p->allocator.release(p->allocator.context,p->storage); p->allocator.release(p->allocator.context,p); }
}
size_t lie_regex_state_count(const lie_regex_program *p) { return p ? p->states : 0; }
uint32_t lie_regex_maximum_suffix(const lie_regex_program *p) { return p ? p->maximum_suffix : 0; }
static bool state_valid(const lie_regex_program *p, uint32_t s) { return p && (s == LIE_REGEX_DEAD || s < p->states); }
lie_regex_status lie_regex_accepting(const lie_regex_program *p, uint32_t s, bool *out) {
  if (!out || !state_valid(p,s)) return LIE_REGEX_INVALID;
  *out = s != LIE_REGEX_DEAD && p->accepting[s]; return LIE_REGEX_OK;
}
static bool contains(const lie_regex_program *p, size_t c, uint32_t first, uint32_t last) {
  lie_grammar_range r = p->class_ranges[c]; size_t low = 0, high = r.count;
  while (low < high) {
    size_t middle = low + (high - low) / 2;
    if (p->unicode[r.offset + middle].last < first) low = middle + 1; else high = middle;
  }
  return low < r.count && p->unicode[r.offset + low].first <= last;
}
lie_regex_status lie_regex_advance(const lie_regex_program *p, uint32_t s, uint32_t cp, uint32_t *out) {
  if (!out || !state_valid(p,s)) return LIE_REGEX_INVALID;
  uint32_t next = LIE_REGEX_DEAD;
  if (s != LIE_REGEX_DEAD && cp <= 0x10ffff)
    for (size_t c = 0; c < p->classes; ++c)
      if (contains(p,c,cp,cp)) { next = p->next[s * p->classes + c]; break; }
  *out = next; return LIE_REGEX_OK;
}
static lie_regex_status finish(const lie_regex_program *p, uint32_t s, uint32_t min, uint32_t max,
  scratch *temp, size_t *work, bool *out) {
  *out = false;
  if (s == LIE_REGEX_DEAD || min > max) return LIE_REGEX_OK;
  uint32_t distance = p->distance[s];
  if (distance == LIE_REGEX_DEAD || distance > max) return LIE_REGEX_OK;
  if (distance >= min) { *out = true; return LIE_REGEX_OK; }
  if (!temp->allocation) {
    temp->allocation = p->allocator.allocate(p->allocator.context, 3 * p->states * sizeof(uint32_t));
    if (!temp->allocation) return LIE_REGEX_RESOURCE;
    temp->active = temp->allocation; temp->anchor = temp->active + p->states; temp->reachable = temp->anchor + p->states;
  }
  size_t active_count = 1, anchor_count = 1;
  temp->active[0] = temp->anchor[0] = s;
  uint32_t steps = 0; uint64_t block = 1, period = 0; bool cycle = false;
  while (steps < min) {
    TRY(spend(work,p->states)); memset(temp->reachable,0,p->states * sizeof(uint32_t));
    for (size_t i = 0; i < active_count; ++i) {
      uint32_t current = temp->active[i];
      TRY(spend(work,p->offsets[current + 1] - p->offsets[current]));
      for (uint32_t j = p->offsets[current]; j < p->offsets[current + 1]; ++j) {
        uint32_t next = p->successors[j];
        if (p->distance[next] != LIE_REGEX_DEAD) temp->reachable[next] = 1;
      }
    }
    active_count = 0; TRY(spend(work,p->states));
    for (uint32_t next = 0; next < p->states; ++next) if (temp->reachable[next]) temp->active[active_count++] = next;
    if (!active_count) return LIE_REGEX_OK;
    ++steps;
    if (!cycle) {
      ++period; TRY(spend(work,active_count));
      if (active_count == anchor_count && !memcmp(temp->active,temp->anchor,active_count * sizeof(uint32_t))) {
        steps += (uint32_t)(((min - steps) / period) * period); cycle = true;
      } else if (period == block) {
        anchor_count = active_count; memcpy(temp->anchor,temp->active,active_count * sizeof(uint32_t));
        block *= 2; period = 0;
      }
    }
  }
  for (size_t i = 0; i < active_count; ++i)
    if (p->distance[temp->active[i]] <= max - min) { *out = true; break; }
  return LIE_REGEX_OK;
}
lie_regex_status lie_regex_can_finish(const lie_regex_program *p, uint32_t s, uint32_t min, uint32_t max, bool *out) {
  if (!out || !state_valid(p,s)) return LIE_REGEX_INVALID;
  scratch temp = {0}; size_t work = p->max_work; bool result;
  lie_regex_status rc = finish(p,s,min,max,&temp,&work,&result);
  if (temp.allocation) p->allocator.release(p->allocator.context,temp.allocation);
  if (rc == LIE_REGEX_OK) *out = result;
  return rc;
}
lie_regex_status lie_regex_can_advance(const lie_regex_program *p, uint32_t s, uint32_t first,
  uint32_t last, uint32_t min, uint32_t max, bool *out) {
  if (!out || !state_valid(p,s)) return LIE_REGEX_INVALID;
  scratch temp = {0}; size_t work = p->max_work; bool result = false; lie_regex_status rc = LIE_REGEX_OK;
  if (s != LIE_REGEX_DEAD && first <= last)
    for (size_t c = 0; c < p->classes; ++c) {
      rc = spend(&work,p->class_ranges[c].count + 1); if (rc != LIE_REGEX_OK) break;
      uint32_t next = p->next[s * p->classes + c];
      if (next != LIE_REGEX_DEAD && contains(p,c,first,last)) {
        rc = finish(p,next,min,max,&temp,&work,&result);
        if (rc != LIE_REGEX_OK || result) break;
      }
    }
  if (temp.allocation) p->allocator.release(p->allocator.context,temp.allocation);
  if (rc == LIE_REGEX_OK) *out = result;
  return rc;
}
