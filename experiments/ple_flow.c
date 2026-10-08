// SPDX-License-Identifier: MIT
#define _POSIX_C_SOURCE 200809L
#include "ple_flow.h"

#include <pthread.h>
#include <stdlib.h>
#include <time.h>

enum slot_state { FREE, FILLING, READY, CONSUMING };
struct lie_ple_flow {
  lie_ple_flow_options options;
  lie_ple_flow_stats stats;
  pthread_mutex_t mutex;
  pthread_cond_t changed;
  enum slot_state state[2];
  bool started, running, stop, worker_done;
};

static uint64_t now_ns(void) {
  struct timespec t;
  if (clock_gettime(CLOCK_MONOTONIC, &t))
    return 0;
  return (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec;
}

static uint64_t elapsed_ns(uint64_t start) {
  const uint64_t end = now_ns();
  return start && end >= start ? end - start : 0;
}

static void add_ns(uint64_t *total, uint64_t elapsed) {
  *total = elapsed > UINT64_MAX - *total ? UINT64_MAX : *total + elapsed;
}

size_t lie_ple_flow_bytes(size_t bytes) {
  if (!bytes || bytes > (SIZE_MAX - sizeof(lie_ple_flow)) / 2)
    return 0;
  return sizeof(lie_ple_flow) + 2 * bytes;
}

lie_ple_flow *lie_ple_flow_create(const lie_ple_flow_options *o) {
  if (!o || !o->prepare || !o->consume || !o->slots[0] || !o->slots[1])
    return NULL;
  const size_t required = lie_ple_flow_bytes(o->slot_bytes);
  if (!required || required > o->memory_budget)
    return NULL;
  const uintptr_t a = (uintptr_t)o->slots[0], b = (uintptr_t)o->slots[1];
  if (a > UINTPTR_MAX - o->slot_bytes || b > UINTPTR_MAX - o->slot_bytes ||
      (a < b + o->slot_bytes && b < a + o->slot_bytes))
    return NULL;
  lie_ple_flow *f = calloc(1, sizeof(*f));
  if (!f)
    return NULL;
  f->options = *o;
  f->stats.reserved_bytes = required;
  if (pthread_mutex_init(&f->mutex, NULL)) {
    free(f);
    return NULL;
  }
  if (pthread_cond_init(&f->changed, NULL)) {
    pthread_mutex_destroy(&f->mutex);
    free(f);
    return NULL;
  }
  return f;
}

static void stop_locked(lie_ple_flow *f, lie_ple_status status) {
  if (!f->stop) {
    f->stop = true;
    f->stats.status = status;
  }
  pthread_cond_broadcast(&f->changed);
}

void lie_ple_flow_cancel(lie_ple_flow *f) {
  if (!f)
    return;
  pthread_mutex_lock(&f->mutex);
  stop_locked(f, LIE_PLE_CANCELLED);
  pthread_mutex_unlock(&f->mutex);
}

static bool prepare(lie_ple_flow *f, size_t chunk) {
  const size_t slot = chunk % 2;
  pthread_mutex_lock(&f->mutex);
  while (!f->stop && f->state[slot] != FREE)
    pthread_cond_wait(&f->changed, &f->mutex);
  if (f->stop) {
    pthread_mutex_unlock(&f->mutex);
    return false;
  }
  f->state[slot] = FILLING;
  const size_t owned = (f->state[0] != FREE) + (f->state[1] != FREE);
  if (owned > f->stats.peak_owned_slots)
    f->stats.peak_owned_slots = owned;
  pthread_mutex_unlock(&f->mutex);

  const uint64_t start = now_ns();
  const int rc =
      f->options.prepare(f->options.context, chunk, f->options.slots[slot]);
  const uint64_t elapsed = elapsed_ns(start);

  pthread_mutex_lock(&f->mutex);
  add_ns(&f->stats.prepare_ns, elapsed);
  if (!rc)
    ++f->stats.prepared;
  else
    stop_locked(f, LIE_PLE_PREPARE_FAILED);
  f->state[slot] = f->stop ? FREE : READY;
  pthread_cond_broadcast(&f->changed);
  const bool good = !f->stop;
  pthread_mutex_unlock(&f->mutex);
  return good;
}

static void *produce(void *argument) {
  lie_ple_flow *f = argument;
  for (size_t i = 0; i < f->options.chunks; ++i)
    if (!prepare(f, i))
      break;
  pthread_mutex_lock(&f->mutex);
  f->worker_done = true;
  pthread_cond_broadcast(&f->changed);
  pthread_mutex_unlock(&f->mutex);
  return NULL;
}

lie_ple_status lie_ple_flow_run(lie_ple_flow *f, lie_ple_flow_stats *stats) {
  if (!f || !stats)
    return LIE_PLE_INVALID;
  pthread_mutex_lock(&f->mutex);
  if (f->started) {
    pthread_mutex_unlock(&f->mutex);
    return LIE_PLE_BUSY;
  }
  f->started = f->running = true;
  pthread_mutex_unlock(&f->mutex);

  pthread_t worker;
  bool worker_started = false;
  if (f->options.lookahead && f->options.chunks) {
    if (!pthread_create(&worker, NULL, produce, f))
      worker_started = true;
    else {
      pthread_mutex_lock(&f->mutex);
      stop_locked(f, LIE_PLE_THREAD_FAILED);
      pthread_mutex_unlock(&f->mutex);
    }
  }
  for (size_t i = 0; i < f->options.chunks; ++i) {
    if (!f->options.lookahead && !prepare(f, i))
      break;
    const size_t slot = i % 2;
    const uint64_t waiting = now_ns();
    pthread_mutex_lock(&f->mutex);
    while (!f->stop && f->state[slot] != READY)
      pthread_cond_wait(&f->changed, &f->mutex);
    add_ns(&f->stats.consumer_wait_ns, elapsed_ns(waiting));
    if (f->stop) {
      pthread_mutex_unlock(&f->mutex);
      break;
    }
    f->state[slot] = CONSUMING;
    pthread_mutex_unlock(&f->mutex);

    const uint64_t start = now_ns();
    const int rc =
        f->options.consume(f->options.context, i, f->options.slots[slot]);
    const uint64_t elapsed = elapsed_ns(start);

    pthread_mutex_lock(&f->mutex);
    add_ns(&f->stats.consume_ns, elapsed);
    if (!rc)
      ++f->stats.consumed;
    else
      stop_locked(f, LIE_PLE_CONSUME_FAILED);
    f->state[slot] = FREE;
    pthread_cond_broadcast(&f->changed);
    const bool stop = f->stop;
    pthread_mutex_unlock(&f->mutex);
    if (stop)
      break;
  }
  if (worker_started) {
    // Even an unexpected join error must not return a borrowed buffer
    // while the producer can still access it.
    pthread_mutex_lock(&f->mutex);
    while (!f->worker_done)
      pthread_cond_wait(&f->changed, &f->mutex);
    pthread_mutex_unlock(&f->mutex);
    if (pthread_join(worker, NULL)) {
      pthread_mutex_lock(&f->mutex);
      stop_locked(f, LIE_PLE_THREAD_FAILED);
      pthread_mutex_unlock(&f->mutex);
    }
  }
  pthread_mutex_lock(&f->mutex);
  f->state[0] = f->state[1] = FREE;
  f->running = false;
  *stats = f->stats;
  pthread_mutex_unlock(&f->mutex);
  return stats->status;
}

lie_ple_status lie_ple_flow_destroy(lie_ple_flow *f) {
  if (!f)
    return LIE_PLE_INVALID;
  pthread_mutex_lock(&f->mutex);
  const bool busy = f->running;
  pthread_mutex_unlock(&f->mutex);
  if (busy)
    return LIE_PLE_BUSY;
  pthread_cond_destroy(&f->changed);
  pthread_mutex_destroy(&f->mutex);
  free(f);
  return LIE_PLE_OK;
}
