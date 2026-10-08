/* SPDX-License-Identifier: MIT */
/* Native ownership/FIFO/probability/failure controls. HOST, NOT-INFERENCE. */
#include "lie/sampling_storage.h"
#include "lie/sampling_distribution.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { size_t calls, fail, live, bytes; } memory;
typedef union { max_align_t align; size_t bytes; } header;
static void *allocate(void *context, size_t bytes) {
  memory *m = context;
  if (++m->calls == m->fail || bytes > SIZE_MAX - sizeof(header)) return NULL;
  header *h = malloc(sizeof(*h) + bytes);
  if (!h) return NULL;
  h->bytes = bytes; ++m->live; m->bytes += bytes; return h + 1;
}
static void release(void *context, void *p) {
  memory *m = context; header *h = (header *)p - 1;
  assert(m->live && m->bytes >= h->bytes);
  --m->live; m->bytes -= h->bytes;
  memset(p, 0xdd, h->bytes); free(h);
}
static lie_sampling_storage_description description(memory *m) {
  lie_sampling_storage_description d; lie_sampling_storage_description_init(&d);
  d.allocator = (lie_grammar_allocator){m, allocate, release}; return d;
}
typedef struct { uint32_t fifo[32], generated[64]; size_t count; } oracle;
static void input(oracle *r, const lie_sampling_history_options *o,
                  const uint32_t *tokens, size_t n, bool reset) {
  if (reset) memset(r, 0, sizeof(*r));
  for (size_t i = 0; i < n; ++i) {
    assert(tokens[i] < 64);
    if (!reset && o->generated) ++r->generated[tokens[i]];
    if (!o->repeat_last_n) continue;
    if (r->count == o->repeat_last_n)
      memmove(r->fifo, r->fifo + 1, (--r->count) * sizeof(*r->fifo));
    r->fifo[r->count++] = tokens[i];
  }
}
static void check(const lie_sampling_history_storage *s, const oracle *r,
                  const lie_sampling_history_options *o) {
  assert(s->state.context == s && s->state.token_count == r->count);
  if (r->count) assert(!memcmp(s->state.tokens, r->fifo, r->count * sizeof(uint32_t)));
  size_t at = 0;
  for (uint32_t token = 0; token < 64; ++token) {
    bool repeated = false;
    if (o->repetition)
      for (size_t i = 0; i < r->count; ++i) repeated |= r->fifo[i] == token;
    if (!repeated && !r->generated[token]) continue;
    assert(at < s->state.penalty_count);
    const lie_sampling_penalty p = s->state.penalties[at++];
    assert(p.token == token && p.repeated == (uint32_t)repeated &&
           p.generated_count == r->generated[token]);
  }
  assert(at == s->state.penalty_count &&
         s->info.live_owned_bytes == s->state.token_capacity * sizeof(uint32_t) +
           s->state.penalty_capacity * sizeof(lie_sampling_penalty));
  assert(s->info.peak_owned_bytes >= s->info.live_owned_bytes &&
         s->info.peak_owned_bytes <= s->description.max_owned_bytes);
}
static void history_oracles(void) {
  const size_t windows[] = {0, 1, 8, 32};
  for (unsigned flags = 0; flags < 4; ++flags)
    for (size_t w = 0; w < sizeof(windows) / sizeof(*windows); ++w) {
      memory m = {0}; const lie_sampling_storage_description d = description(&m);
      lie_sampling_history_storage s, copy, moved;
      assert(lie_sampling_history_storage_init(&s, &d) == LIE_HISTORY_OK);
      assert(lie_sampling_history_storage_init(&copy, &d) == LIE_HISTORY_OK);
      assert(lie_sampling_history_storage_init(&moved, &d) == LIE_HISTORY_OK);
      assert(!m.calls && !m.live);
      lie_sampling_history_options o; lie_sampling_history_options_init(&o);
      o.repeat_last_n = windows[w]; o.generated = flags & 1; o.repetition = flags & 2;
      uint32_t tokens[37]; oracle r = {0};
      for (unsigned step = 0; step < 96; ++step) {
        const size_t n = step % 37;
        for (size_t i = 0; i < n; ++i) tokens[i] = (step * 17 + i * 13) % 64;
        const bool reset = step % 19 == 0;
        assert((reset ? lie_sampling_history_storage_reset(&s, &o, tokens, n)
                      : lie_sampling_history_storage_accept(&s, tokens, n)) == LIE_HISTORY_OK);
        input(&r, &o, tokens, n, reset); check(&s, &r, &o);
        if (step % 7) continue;
        assert(lie_sampling_history_storage_clone(&copy, &s) == LIE_HISTORY_OK);
        check(&copy, &r, &o); check(&s, &r, &o);
        if (r.count) assert(copy.state.tokens != s.state.tokens);
        const size_t calls = m.calls;
        const void *p = copy.state.tokens, *q = copy.state.penalties;
        lie_sampling_history_storage_move(&moved, &copy);
        assert(m.calls == calls && moved.state.tokens == p && moved.state.penalties == q);
        assert(!copy.state.tokens && !copy.state.penalties && copy.state.context == &copy);
        check(&moved, &r, &o);
        oracle next = r; const uint32_t token = 63;
        assert(lie_sampling_history_storage_accept(&moved, &token, 1) == LIE_HISTORY_OK);
        input(&next, &o, &token, 1, false); check(&moved, &next, &o); check(&s, &r, &o);
        assert(lie_sampling_history_storage_clone(&s, &s) == LIE_HISTORY_OK);
        lie_sampling_history_storage_move(&s, &s); check(&s, &r, &o);
      }
      lie_sampling_history_storage_release(&s); lie_sampling_history_storage_release(&copy);
      lie_sampling_history_storage_release(&moved); assert(!m.live && !m.bytes);
    }
}
static void history_refusals(void) {
  memory m = {0}; lie_sampling_storage_description d = description(&m);
  lie_sampling_history_options o; lie_sampling_history_options_init(&o);
  o.generated = true; o.repetition = true; o.repeat_last_n = 32;
  const uint32_t initial[] = {2, 3, 2}, generated[] = {7, 2, 7};
  lie_sampling_history_storage s, out;
  assert(lie_sampling_history_storage_init(&s, &d) == LIE_HISTORY_OK);
  assert(lie_sampling_history_storage_init(&out, &d) == LIE_HISTORY_OK);
  assert(lie_sampling_history_storage_reset(&s, &o, initial, 3) == LIE_HISTORY_OK);
  assert(lie_sampling_history_storage_accept(&s, generated, 3) == LIE_HISTORY_OK);
  oracle r = {0}; input(&r, &o, initial, 3, true); input(&r, &o, generated, 3, false);
  assert(lie_sampling_history_storage_reset(&out, &o, initial, 3) == LIE_HISTORY_OK);
  oracle before = {0}; input(&before, &o, initial, 3, true);
  for (size_t failure = 1; failure <= 2; ++failure) {
    const size_t live = m.live, bytes = m.bytes;
    m.fail = m.calls + failure;
    assert(lie_sampling_history_storage_clone(&out, &s) == LIE_HISTORY_RESOURCE);
    check(&out, &before, &o); check(&s, &r, &o);
    assert(m.live == live && m.bytes == bytes);
  }
  m.fail = 0;
  assert(lie_sampling_history_storage_accept(&s, s.state.tokens, 1) == LIE_HISTORY_INVALID);
  assert(lie_sampling_history_storage_reset(&s, &o, s.state.tokens, 1) == LIE_HISTORY_INVALID);
  check(&s, &r, &o);
  uint32_t batch[32]; for (size_t i = 0; i < 32; ++i) batch[i] = (uint32_t)i;
  m.fail = m.calls + 1;
  assert(lie_sampling_history_storage_accept(&s, batch, 32) == LIE_HISTORY_RESOURCE);
  check(&s, &r, &o); m.fail = 0;
  lie_sampling_history_options limited = o; limited.max_penalties = 1;
  assert(lie_sampling_history_storage_reset(&s, &limited, initial, 3) == LIE_HISTORY_RESOURCE);
  check(&s, &r, &o); assert(s.options.max_penalties == o.max_penalties);
  lie_sampling_history_storage_release(&s); lie_sampling_history_storage_release(&out);
  assert(!m.live && !m.bytes);
  d.max_owned_bytes = sizeof(uint32_t);
  assert(lie_sampling_history_storage_init(&s, &d) == LIE_HISTORY_OK);
  o.generated = false; o.repetition = false;
  assert(lie_sampling_history_storage_reset(&s, &o, initial, 1) == LIE_HISTORY_OK);
  assert(lie_sampling_history_storage_accept(&s, initial, 1) == LIE_HISTORY_RESOURCE);
  assert(s.state.token_count == 1 && s.state.tokens[0] == 2);
  lie_sampling_history_storage_release(&s); assert(!m.live && !m.bytes);
}
static void probability_ownership(void) {
  memory m = {0}; const lie_sampling_storage_description d = description(&m);
  lie_sampling_probability_storage s, out;
  assert(lie_sampling_probability_storage_init(&s, &d) == LIE_SAMPLING_OK);
  assert(lie_sampling_probability_storage_init(&out, &d) == LIE_SAMPLING_OK);
  assert(!m.calls);
  lie_sampling_workspace w = lie_sampling_probability_storage_workspace(&s);
  assert(!w.grow(w.context, 1, &w.entries, &w.capacity));
  /* Unpublished C algorithm scratch above count must survive native growth. */
  const size_t capacity = w.capacity;
  for (size_t i = 0; i < capacity; ++i)
    w.entries[i] = (lie_sampling_probability){(uint32_t)i, (double)i / 64};
  assert(!s.count && !w.grow(w.context, capacity + 1, &w.entries, &w.capacity));
  for (size_t i = 0; i < capacity; ++i)
    assert(w.entries[i].token == i && w.entries[i].value == (double)i / 64);
  assert(lie_sampling_probability_storage_publish(&s, capacity) == LIE_SAMPLING_OK);
  assert(lie_sampling_probability_storage_publish(&s, s.capacity + 1) == LIE_SAMPLING_INVALID);
  assert(lie_sampling_probability_storage_assign(&s, s.entries, s.count) == LIE_SAMPLING_INVALID);
  const lie_sampling_probability prior[] = {{63, 1.0}};
  assert(lie_sampling_probability_storage_assign(&out, prior, 1) == LIE_SAMPLING_OK);
  const void *previous = out.entries;
  const size_t live = m.live, bytes = m.bytes;
  m.fail = m.calls + 1;
  assert(lie_sampling_probability_storage_clone(&out, &s) == LIE_SAMPLING_RESOURCE);
  assert(out.count == 1 && out.entries == previous &&
         !memcmp(out.entries, prior, sizeof(prior)) && m.live == live && m.bytes == bytes);
  m.fail = 0;
  assert(lie_sampling_probability_storage_clone(&out, &s) == LIE_SAMPLING_OK);
  assert(out.count == s.count && out.entries != s.entries &&
         !memcmp(out.entries, s.entries, s.count * sizeof(*s.entries)));
  const void *identity = s.entries; const size_t calls = m.calls;
  lie_sampling_probability_storage_move(&out, &s);
  assert(out.entries == identity && !s.entries && !s.count && m.calls == calls);
  lie_sampling_probability_storage_move(&out, &out);
  assert(lie_sampling_probability_storage_clone(&out, &out) == LIE_SAMPLING_OK);
  assert(out.entries == identity);
  const lie_sampling_probability input[] = {{5, .25}, {8, .75}};
  assert(lie_sampling_probability_storage_assign(&s, input, 2) == LIE_SAMPLING_OK);
  assert(out.entries == identity && out.count == capacity);
  const lie_sampling_probability *before = s.entries;
  assert(lie_sampling_probability_storage_reserve(&s, SIZE_MAX) == LIE_SAMPLING_RESOURCE);
  assert(s.entries == before && s.count == 2 && !memcmp(s.entries, input, sizeof(input)));
  lie_sampling_probability_storage_release(&s); lie_sampling_probability_storage_release(&out);
  assert(!m.live && !m.bytes);
}
static void probability_budget(void) {
  memory m = {0}; lie_sampling_storage_description d = description(&m);
  const size_t width = sizeof(lie_sampling_probability); d.max_owned_bytes = 3 * width;
  lie_sampling_probability_storage s;
  assert(lie_sampling_probability_storage_init(&s, &d) == LIE_SAMPLING_OK);
  const lie_sampling_probability a[] = {{1, .25}, {2, .75}}, b[] = {{4, .1}, {5, .2}, {6, .7}};
  assert(lie_sampling_probability_storage_assign(&s, a, 2) == LIE_SAMPLING_OK);
  assert(s.capacity == 2 && s.info.live_owned_bytes == 2 * width);
  const size_t calls = m.calls;
  assert(lie_sampling_probability_storage_assign(&s, b, 3) == LIE_SAMPLING_RESOURCE);
  assert(m.calls == calls && s.count == 2 && !memcmp(s.entries, a, sizeof(a)));
  lie_sampling_probability_storage_release(&s); assert(!m.live && !m.bytes);
  assert(lie_sampling_probability_storage_assign(&s, b, 3) == LIE_SAMPLING_OK);
  assert(s.capacity == 3 && s.info.peak_owned_bytes == 3 * width);
  lie_sampling_probability_storage_release(&s); assert(!m.live && !m.bytes);
}
static void invalid_description(void) {
  lie_sampling_storage_description d; lie_sampling_storage_description_init(&d);
  lie_sampling_probability_storage s; unsigned char unchanged[sizeof(s)];
  memset(&s, 0xa5, sizeof(s)); memcpy(unchanged, &s, sizeof(s));
  d.abi_version = 0;
  assert(lie_sampling_probability_storage_init(&s, &d) == LIE_SAMPLING_INVALID);
  assert(!memcmp(&s, unchanged, sizeof(s)));
  lie_sampling_storage_description_init(&d); d.allocator.allocate = allocate;
  assert(lie_sampling_probability_storage_init(&s, &d) == LIE_SAMPLING_INVALID);
  assert(!memcmp(&s, unchanged, sizeof(s)));
}
int main(void) {
  invalid_description(); history_oracles(); history_refusals();
  probability_ownership(); probability_budget();
  puts("C17 sampler storage: ownership/oracles/refusals; HOST-NOT-INFERENCE");
}
