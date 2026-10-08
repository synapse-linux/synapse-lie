// SPDX-License-Identifier: MIT
// Synthetic CPU lifetime/ordering fixture. No model forward or GPU evidence.
#define _POSIX_C_SOURCE 200809L
#include "ple_flow.h"

#include <assert.h>
#include <pthread.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

#define CHECK(x)                                                               \
  do {                                                                         \
    if (!(x)) {                                                                \
      fprintf(stderr, "FAIL at line %d: %s\n", __LINE__, #x);                  \
      return 1;                                                                \
    }                                                                          \
  } while (0)

enum mode {
  SERIAL,
  OVERLAP,
  CANCEL_CONSUMER,
  CANCEL_PRODUCER,
  FAIL_PREPARE,
  FAIL_CONSUME
};
typedef struct {
  size_t chunk;
  unsigned char bytes[257];
} payload;
typedef struct {
  uint64_t before;
  payload value;
  uint64_t after;
} guarded;
typedef struct {
  pthread_mutex_t mutex;
  pthread_cond_t changed;
  lie_ple_flow *flow;
  enum mode mode;
  size_t prepared, consumed;
  bool consuming_first, preparing_second, release_second, overlap;
  int errors;
} fixture;

// Deadlines only detect deadlock; no timing thresholds or speed claims.
static bool wait_for(fixture *f, const bool *flag) {
  struct timespec deadline;
  if (clock_gettime(CLOCK_REALTIME, &deadline))
    return false;
  deadline.tv_sec += 5;
  while (!*flag) {
    if (pthread_cond_timedwait(&f->changed, &f->mutex, &deadline))
      return false;
  }
  return true;
}

static int prepare(void *opaque, size_t chunk, void *buffer) {
  fixture *f = opaque;
  payload *slot = buffer;
  pthread_mutex_lock(&f->mutex);
  if (f->prepared != chunk)
    ++f->errors;
  if (f->mode != SERIAL && chunk == 1) {
    if (!wait_for(f, &f->consuming_first))
      ++f->errors;
    f->preparing_second = true;
    pthread_cond_broadcast(&f->changed);
    if (f->mode == CANCEL_PRODUCER)
      lie_ple_flow_cancel(f->flow);
    if (f->mode == CANCEL_CONSUMER || f->mode == FAIL_CONSUME)
      if (!wait_for(f, &f->release_second))
        ++f->errors;
  }
  // Reuse may only happen after the corresponding consumer returned.
  if (chunk >= 2 && f->consumed < chunk - 1)
    ++f->errors;
  slot->chunk = chunk;
  memset(slot->bytes, (int)(chunk % 251), sizeof(slot->bytes));
  ++f->prepared;
  const bool fail = f->mode == FAIL_PREPARE && chunk == 1;
  pthread_mutex_unlock(&f->mutex);
  return fail ? 1 : 0;
}

static int consume(void *opaque, size_t chunk, const void *buffer) {
  fixture *f = opaque;
  const payload *slot = buffer;
  pthread_mutex_lock(&f->mutex);
  if (f->consumed != chunk || slot->chunk != chunk)
    ++f->errors;
  if (chunk == 0) {
    lie_ple_flow_stats ignored;
    if (lie_ple_flow_destroy(f->flow) != LIE_PLE_BUSY ||
        lie_ple_flow_run(f->flow, &ignored) != LIE_PLE_BUSY)
      ++f->errors;
  }
  if (f->mode != SERIAL && chunk == 0) {
    f->consuming_first = true;
    pthread_cond_broadcast(&f->changed);
    if (!wait_for(f, &f->preparing_second))
      ++f->errors;
    f->overlap = true;
    if (f->mode == CANCEL_CONSUMER)
      lie_ple_flow_cancel(f->flow);
    // The third chunk cannot overwrite slot zero while it is consumed.
    if (f->prepared > 2)
      ++f->errors;
    f->release_second = true;
    pthread_cond_broadcast(&f->changed);
  }
  for (size_t i = 0; i < sizeof(slot->bytes); ++i)
    if (slot->bytes[i] != chunk % 251)
      ++f->errors;
  ++f->consumed;
  const bool fail = f->mode == FAIL_CONSUME && chunk == 0;
  pthread_mutex_unlock(&f->mutex);
  return fail ? 1 : 0;
}

static int scenario(enum mode mode) {
  guarded slots[2] = {{.before = 0xfeed, .after = 0xbeef},
                      {.before = 0xfeed, .after = 0xbeef}};
  fixture f = {.mode = mode};
  CHECK(!pthread_mutex_init(&f.mutex, NULL));
  CHECK(!pthread_cond_init(&f.changed, NULL));
  const lie_ple_flow_options options = {
      .chunks = 9,
      .slot_bytes = sizeof(payload),
      .memory_budget = lie_ple_flow_bytes(sizeof(payload)),
      .slots = {&slots[0].value, &slots[1].value},
      .context = &f,
      .lookahead = mode != SERIAL,
      .prepare = prepare,
      .consume = consume};
  f.flow = lie_ple_flow_create(&options);
  CHECK(f.flow);
  lie_ple_flow_stats stats;
  const lie_ple_status status = lie_ple_flow_run(f.flow, &stats);
  CHECK(!f.errors);
  CHECK(stats.reserved_bytes == options.memory_budget);
  CHECK(stats.peak_owned_slots == (mode == SERIAL ? 1u : 2u));
  CHECK((mode == SERIAL) != f.overlap);
  if (mode == SERIAL || mode == OVERLAP) {
    CHECK(status == LIE_PLE_OK);
    CHECK(stats.prepared == 9 && stats.consumed == 9);
  } else {
    CHECK(stats.consumed == (mode == FAIL_CONSUME ? 0u : 1u));
    CHECK(stats.prepared == (mode == FAIL_PREPARE ? 1u : 2u));
    CHECK(status == (mode == FAIL_PREPARE   ? LIE_PLE_PREPARE_FAILED
                     : mode == FAIL_CONSUME ? LIE_PLE_CONSUME_FAILED
                                            : LIE_PLE_CANCELLED));
  }
  CHECK(lie_ple_flow_run(f.flow, &stats) == LIE_PLE_BUSY);
  CHECK(lie_ple_flow_destroy(f.flow) == LIE_PLE_OK);
  for (size_t i = 0; i < 2; ++i)
    CHECK(slots[i].before == 0xfeed && slots[i].after == 0xbeef);
  CHECK(!pthread_cond_destroy(&f.changed));
  CHECK(!pthread_mutex_destroy(&f.mutex));
  return 0;
}

static int unexpected(void *context, size_t chunk, void *slot) {
  (void)context;
  (void)chunk;
  (void)slot;
  return 1;
}
static int unexpected_consume(void *context, size_t chunk, const void *slot) {
  return unexpected(context, chunk, (void *)slot);
}

static int admission(void) {
  payload slots[2];
  lie_ple_flow_options o = {.chunks = 0,
                            .slot_bytes = sizeof(payload),
                            .memory_budget =
                                lie_ple_flow_bytes(sizeof(payload)),
                            .slots = {slots, slots + 1},
                            .lookahead = true,
                            .prepare = unexpected,
                            .consume = unexpected_consume};
  CHECK(!lie_ple_flow_create(NULL));
  CHECK(!lie_ple_flow_bytes(0) && !lie_ple_flow_bytes(SIZE_MAX));
  --o.memory_budget;
  CHECK(!lie_ple_flow_create(&o));
  ++o.memory_budget;
  o.slots[1] = o.slots[0];
  CHECK(!lie_ple_flow_create(&o));
  o.slots[1] = (unsigned char *)o.slots[0] + 1;
  CHECK(!lie_ple_flow_create(&o));
  o.slots[1] = slots + 1;
  lie_ple_flow *f = lie_ple_flow_create(&o);
  CHECK(f);
  lie_ple_flow_stats stats;
  CHECK(lie_ple_flow_run(f, &stats) == LIE_PLE_OK);
  CHECK(!stats.prepared && !stats.consumed && !stats.peak_owned_slots);
  CHECK(lie_ple_flow_destroy(f) == LIE_PLE_OK);
  o.chunks = 3;
  f = lie_ple_flow_create(&o);
  CHECK(f);
  lie_ple_flow_cancel(f);
  CHECK(lie_ple_flow_run(f, &stats) == LIE_PLE_CANCELLED);
  CHECK(!stats.prepared && !stats.consumed && !stats.peak_owned_slots);
  CHECK(lie_ple_flow_destroy(f) == LIE_PLE_OK);
  return 0;
}

int main(void) {
  CHECK(!admission());
  for (enum mode mode = SERIAL; mode <= FAIL_CONSUME; ++mode)
    CHECK(!scenario(mode));
  puts("PASS: bounded PLE flow ordering, overlap, cancellation and drain (CPU "
       "fixture)");
  return 0;
}
