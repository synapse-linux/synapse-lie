// SPDX-License-Identifier: MIT
#ifndef LIE_EXPERIMENT_PLE_FLOW_H
#define LIE_EXPERIMENT_PLE_FLOW_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct lie_ple_flow lie_ple_flow;
typedef enum {
  LIE_PLE_OK = 0,
  LIE_PLE_INVALID,
  LIE_PLE_BUSY,
  LIE_PLE_CANCELLED,
  LIE_PLE_PREPARE_FAILED,
  LIE_PLE_CONSUME_FAILED,
  LIE_PLE_THREAD_FAILED
} lie_ple_status;

typedef struct {
  size_t chunks, slot_bytes, memory_budget;
  void *slots[2];
  void *context;
  bool lookahead;
  /* Exactly one producer and one consumer, with separate slot ownership.
   * The producer prepares immutable inputs, never live model/session state.
   * Callbacks return zero on success. Pointers may not escape callbacks.
   * consume must drain every asynchronous buffer reader before returning,
   * including failure/cancellation. Inputs remain alive until run returns. */
  int (*prepare)(void *context, size_t chunk, void *slot);
  int (*consume)(void *context, size_t chunk, const void *slot);
} lie_ple_flow_options;

typedef struct {
  uint64_t prepared, consumed, prepare_ns, consume_ns, consumer_wait_ns;
  size_t reserved_bytes, peak_owned_slots;
  lie_ple_status status;
} lie_ple_flow_stats;

/* Two caller-owned disjoint buffers; reservation includes control metadata,
 * excludes OS thread stacks and allocations inside the adapter callbacks.
 * No worker exists until run. The handle runs once; destroy requires run to
 * have returned and must not race another public operation. */
size_t lie_ple_flow_bytes(size_t slot_bytes);
lie_ple_flow *lie_ple_flow_create(const lie_ple_flow_options *options);
lie_ple_status lie_ple_flow_run(lie_ple_flow *flow, lie_ple_flow_stats *stats);
/* Stops admission and wakes waiters. In-flight callbacks are drained, not
 * forcefully interrupted. Safe from either callback or another thread. */
void lie_ple_flow_cancel(lie_ple_flow *flow);
lie_ple_status lie_ple_flow_destroy(lie_ple_flow *flow);

#ifdef __cplusplus
}
#endif
#endif
