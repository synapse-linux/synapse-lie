/* SPDX-License-Identifier: MIT */
/* First-party bounded C ownership for the separately owned sampling algorithms. */
#include "lie/sampling_storage.h"
#include <stdlib.h>
#include <string.h>
static void *allocate(void *p, size_t n) { (void)p; return malloc(n); }
static void release(void *p, void *v) { (void)p; free(v); }
void lie_sampling_storage_description_init(lie_sampling_storage_description *d) {
  if (d) *d = (lie_sampling_storage_description){LIE_SAMPLING_STORAGE_ABI, sizeof(*d), 64u * 1024u * 1024u, {0}};
}
static bool description(lie_sampling_storage_description *d, const lie_sampling_storage_description *input) {
  if (input) *d = *input; else lie_sampling_storage_description_init(d);
  if (d->abi_version != LIE_SAMPLING_STORAGE_ABI || d->struct_bytes != sizeof(*d) ||
      !d->max_owned_bytes || (!!d->allocator.allocate != !!d->allocator.release)) return false;
  if (!d->allocator.allocate) d->allocator = (lie_grammar_allocator){NULL, allocate, release};
  return true;
}
static bool overlap(const void *a, size_t an, const void *b, size_t bn) {
  if (!an || !bn) return false;
  const uintptr_t x = (uintptr_t)a, y = (uintptr_t)b;
  return x > UINTPTR_MAX - an || y > UINTPTR_MAX - bn || (x < y + bn && y < x + an);
}
static int grow(const lie_sampling_storage_description *d, lie_sampling_storage_info *info,
    void **pointer, size_t *capacity, size_t count, size_t width) {
  if (count <= *capacity) return 0;
  if (!width || count > SIZE_MAX / width || info->live_owned_bytes > d->max_owned_bytes) return 1;
  const size_t available = (d->max_owned_bytes - info->live_owned_bytes) / width;
  if (count > available) return 1;
  size_t next = *capacity ? *capacity : 16;
  while (next < count) {
    if (next > available / 2) { next = count; break; }
    next *= 2;
  }
  if (next > available) next = count;
  const size_t bytes = next * width, old = *capacity * width;
  void *buffer = d->allocator.allocate(d->allocator.context, bytes);
  if (!buffer) return 1;
  if (old) memcpy(buffer, *pointer, old);
  memset((char *)buffer + old, 0, bytes - old);
  const size_t peak = info->live_owned_bytes + bytes;
  if (peak > info->peak_owned_bytes) info->peak_owned_bytes = peak;
  if (info->allocations != SIZE_MAX) ++info->allocations;
  if (*pointer) d->allocator.release(d->allocator.context, *pointer);
  info->live_owned_bytes = peak - old; *pointer = buffer; *capacity = next; return 0;
}
static int grow_tokens(void *p, size_t count, uint32_t **out, size_t *capacity) {
  lie_sampling_history_storage *s = p; void *buffer = s->state.tokens;
  size_t cap = s->state.token_capacity;
  if (grow(&s->description, &s->info, &buffer, &cap, count, sizeof(uint32_t))) return 1;
  s->state.tokens = buffer; s->state.token_capacity = cap; *out = buffer; *capacity = cap; return 0;
}
static int grow_penalties(void *p, size_t count, lie_sampling_penalty **out, size_t *capacity) {
  lie_sampling_history_storage *s = p; void *buffer = s->state.penalties;
  size_t cap = s->state.penalty_capacity;
  if (grow(&s->description, &s->info, &buffer, &cap, count, sizeof(lie_sampling_penalty))) return 1;
  s->state.penalties = buffer; s->state.penalty_capacity = cap; *out = buffer; *capacity = cap; return 0;
}
lie_sampling_history_status lie_sampling_history_storage_init(lie_sampling_history_storage *s,
    const lie_sampling_storage_description *input) {
  lie_sampling_storage_description d;
  if (!s || !description(&d, input)) return LIE_HISTORY_INVALID;
  *s = (lie_sampling_history_storage){.description = d};
  lie_sampling_history_options_init(&s->options);
  s->state.grow_tokens = grow_tokens; s->state.grow_penalties = grow_penalties; s->state.context = s;
  return LIE_HISTORY_OK;
}
void lie_sampling_history_storage_release(lie_sampling_history_storage *s) {
  if (!s) return;
  const lie_sampling_storage_description d = s->description;
  if (s->state.tokens) d.allocator.release(d.allocator.context, s->state.tokens);
  if (s->state.penalties) d.allocator.release(d.allocator.context, s->state.penalties);
  (void)lie_sampling_history_storage_init(s, &d);
}
lie_sampling_history_status lie_sampling_history_storage_reset(lie_sampling_history_storage *s,
    const lie_sampling_history_options *o, const uint32_t *tokens, size_t count) {
  if (!s) return LIE_HISTORY_INVALID;
  const lie_sampling_history_status rc = lie_sampling_history_reset(o, &s->state, tokens, count);
  if (!rc) s->options = *o;
  return rc;
}
lie_sampling_history_status lie_sampling_history_storage_accept(lie_sampling_history_storage *s,
    const uint32_t *tokens, size_t count) {
  return s ? lie_sampling_history_accept(&s->options, &s->state, tokens, count) : LIE_HISTORY_INVALID;
}
void lie_sampling_history_storage_move(lie_sampling_history_storage *out, lie_sampling_history_storage *s) {
  if (!out || !s || out == s) return;
  lie_sampling_history_storage_release(out);
  *out = *s; out->state.context = out;
  const lie_sampling_storage_description d = s->description;
  (void)lie_sampling_history_storage_init(s, &d);
}
lie_sampling_history_status lie_sampling_history_storage_clone(lie_sampling_history_storage *out,
    const lie_sampling_history_storage *s) {
  if (!out || !s) return LIE_HISTORY_INVALID;
  if (out == s) return LIE_HISTORY_OK;
  if (overlap(out, sizeof(*out), s, sizeof(*s))) return LIE_HISTORY_INVALID;
  lie_sampling_history_storage copy;
  lie_sampling_history_status rc = lie_sampling_history_storage_init(&copy, &out->description);
  if (rc) return rc;
  rc = lie_sampling_history_copy(&s->options, &copy.state, &s->state);
  if (!rc) { copy.options = s->options; lie_sampling_history_storage_move(out, &copy); }
  lie_sampling_history_storage_release(&copy); return rc;
}
lie_sampling_status lie_sampling_probability_storage_init(lie_sampling_probability_storage *s,
    const lie_sampling_storage_description *input) {
  lie_sampling_storage_description d;
  if (!s || !description(&d, input)) return LIE_SAMPLING_INVALID;
  *s = (lie_sampling_probability_storage){.description = d}; return LIE_SAMPLING_OK;
}
void lie_sampling_probability_storage_release(lie_sampling_probability_storage *s) {
  if (!s) return;
  const lie_sampling_storage_description d = s->description;
  if (s->entries) d.allocator.release(d.allocator.context, s->entries);
  (void)lie_sampling_probability_storage_init(s, &d);
}
lie_sampling_status lie_sampling_probability_storage_reserve(lie_sampling_probability_storage *s, size_t count) {
  if (!s) return LIE_SAMPLING_INVALID;
  void *buffer = s->entries; size_t cap = s->capacity;
  if (grow(&s->description, &s->info, &buffer, &cap, count, sizeof(lie_sampling_probability)))
    return LIE_SAMPLING_RESOURCE;
  s->entries = buffer; s->capacity = cap; return LIE_SAMPLING_OK;
}
lie_sampling_status lie_sampling_probability_storage_publish(lie_sampling_probability_storage *s, size_t count) {
  if (!s || count > s->capacity) return LIE_SAMPLING_INVALID;
  s->count = count; return LIE_SAMPLING_OK;
}
lie_sampling_status lie_sampling_probability_storage_assign(lie_sampling_probability_storage *s,
    const lie_sampling_probability *input, size_t count) {
  if (!s || (count && !input) || count > SIZE_MAX / sizeof(*input) ||
      overlap(input, count * sizeof(*input), s->entries, s->capacity * sizeof(*input)))
    return LIE_SAMPLING_INVALID;
  lie_sampling_status rc = lie_sampling_probability_storage_reserve(s, count);
  if (rc) return rc;
  if (count) memcpy(s->entries, input, count * sizeof(*input));
  s->count = count; return LIE_SAMPLING_OK;
}
void lie_sampling_probability_storage_move(lie_sampling_probability_storage *out, lie_sampling_probability_storage *s) {
  if (!out || !s || out == s) return;
  lie_sampling_probability_storage_release(out); *out = *s;
  const lie_sampling_storage_description d = s->description;
  (void)lie_sampling_probability_storage_init(s, &d);
}
lie_sampling_status lie_sampling_probability_storage_clone(lie_sampling_probability_storage *out,
    const lie_sampling_probability_storage *s) {
  if (!out || !s) return LIE_SAMPLING_INVALID;
  if (out == s) return LIE_SAMPLING_OK;
  if (overlap(out, sizeof(*out), s, sizeof(*s))) return LIE_SAMPLING_INVALID;
  lie_sampling_probability_storage copy;
  lie_sampling_status rc = lie_sampling_probability_storage_init(&copy, &out->description);
  if (rc) return rc;
  rc = lie_sampling_probability_storage_assign(&copy, s->entries, s->count);
  if (!rc) lie_sampling_probability_storage_move(out, &copy);
  lie_sampling_probability_storage_release(&copy); return rc;
}
static int grow_probabilities(void *p, size_t count, lie_sampling_probability **out, size_t *capacity) {
  lie_sampling_probability_storage *s = p;
  if (lie_sampling_probability_storage_reserve(s, count)) return 1;
  *out = s->entries; *capacity = s->capacity; return 0;
}
lie_sampling_workspace lie_sampling_probability_storage_workspace(lie_sampling_probability_storage *s) {
  return s ? (lie_sampling_workspace){s->entries, s->capacity, grow_probabilities, s}
           : (lie_sampling_workspace){0};
}
