/* SPDX-License-Identifier: MIT */
#ifndef LIE_Q2_ROUTED_H
#define LIE_Q2_ROUTED_H
#include <hip/hip_runtime.h>

#include "q2_plan.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Single owner/stream. Caller owns this allocation until completed work drains.
   This launch API is asynchronous; it is NOT the synchronous LIE executor ABI.
 */
typedef struct {
  lie_q2_plan plan;
  void* storage;
  void* context;
} lie_q2_workspace;
/* Preparation may initialize the existing per-device HIP context, once at load.
   Project calls neither allocate scratch nor grow the global ID-map pool. */
int lie_q2_workspace_prepare(lie_q2_workspace* ws);
/* Internal routing IDs must be in [0, experts), or negative for inactive slots.
   Weights include the existing upload's zeroed 4096-byte MMQ tail margin.
   IQ2: logical/physical 2560/2560; Q2: 640/768 (input remains tightly packed).
   Gate/up pair: wb/out_b together, except gated uses wb and a single output.
   Gated IQ2 is limited to 1..8 input rows; tiled returns separate projections.
 */
int lie_q2_project(lie_q2_workspace* ws, int type, int tiled, int gated,
                   const void* w, const void* wb, const float* x,
                   const int32_t* ids, float* out, float* out_b, int m,
                   int logical_k, int physical_k, int rows, int used,
                   int max_expert_rows, int tile_cols, hipStream_t stream);
#ifdef __cplusplus
}
#endif
#endif
