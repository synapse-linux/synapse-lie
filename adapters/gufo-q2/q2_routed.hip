// SPDX-License-Identifier: MIT
// LIE-owned launch/workspace integration over pinned Gufo/llama.cpp MMQ
// helpers. Numerical helpers retain their upstream licenses, notices and
// arithmetic.
#include "mmq/qfn_mmq_prelude.h"
#include "q2_routed.h"
namespace qfn_mmq {
#include "mmq/common.hpp"
#include "mmq/mmid.hpp"
#include "mmq/mmq.hpp"
#include "mmq/mmvq.hpp"
#include "mmq/quantize.hpp"

ggml_backend_hip_context* get_ctx_for_device(int device);
// New reserved-scratch and zero-safe quantizer entries in the private variant.
int lie_q2_ids(const int32_t*, int32_t*, int32_t*, int32_t*, int32_t*, size_t,
               int, int, int, hipStream_t);
int lie_q2_quantize_mmq(const float*, const int32_t*, void*, ggml_type, int,
                        int, int, hipStream_t);

static_assert(sizeof(block_q8_1) == 36 && sizeof(block_q8_1_mmq) == 144);
static_assert(MATRIX_ROW_PADDING == 512 && MMVQ_MAX_BATCH_SIZE == 8);

template<typename T>
static T* region(lie_q2_workspace& ws, int index) {
  return reinterpret_cast<T*>(static_cast<char*>(ws.storage) +
                              ws.plan.offset[index]);
}

template<ggml_type type>
static int tiled_project(lie_q2_workspace& ws, const lie_q2_layout& layout,
                         const void* w, const void* wb, const float* x,
                         const int32_t* ids, float* out, float* out_b, int m,
                         int rows, int used, int max_rows, int tile_cols,
                         hipStream_t stream) {
  const int slots = rows * used;
  auto* src = region<int32_t>(ws, LIE_Q2_IDS_SRC);
  auto* dst = region<int32_t>(ws, LIE_Q2_IDS_DST);
  auto* bounds = region<int32_t>(ws, LIE_Q2_BOUNDS);
  auto* quant = region<char>(ws, LIE_Q2_QUANT);
  // Negative slots are not written by MMQ; never publish stale intermediates.
  if (hipMemsetAsync(out, 0, size_t(slots) * m * sizeof(float), stream) !=
          hipSuccess ||
      (out_b && hipMemsetAsync(out_b, 0, size_t(slots) * m * sizeof(float),
                               stream) != hipSuccess) ||
      hipMemsetAsync(src, 0, size_t(slots) * sizeof(int32_t), stream) !=
          hipSuccess)
    return -2;
  if (lie_q2_ids(ids, src, dst, bounds, region<int32_t>(ws, LIE_Q2_RANK),
                 ws.plan.bytes[LIE_Q2_RANK] / sizeof(int32_t), ws.plan.experts,
                 rows, used, stream) != 0)
    return -2;
  const size_t quant_bytes =
      size_t(slots) * layout.quant_cols * sizeof(block_q8_1_mmq) / 128;
  // Scratch may previously have served a larger batch: clear the CURRENT tail.
  if (hipMemsetAsync(quant + quant_bytes, 0,
                     LIE_Q2_TILE_GUARD * sizeof(block_q8_1_mmq),
                     stream) != hipSuccess)
    return -2;
  if (lie_q2_quantize_mmq(x, src, quant, type, layout.read_cols,
                          layout.quant_cols, slots, stream) != 0)
    return -2;
  mmq_args args{};
  args.x = static_cast<const char*>(w);
  args.type_x = type;
  args.y = reinterpret_cast<const int*>(quant);
  args.ids_dst = dst;
  args.expert_bounds = bounds;
  args.dst = out;
  args.ncols_x = layout.weight_cols;
  args.nrows_x = m;
  args.ncols_dst = slots;
  args.stride_row_x = layout.row_blocks;
  args.ncols_y = slots;
  args.nrows_dst = m;
  args.nchannels_x = args.nchannels_y = ws.plan.experts;
  args.stride_channel_x = int64_t(m) * layout.row_blocks;
  args.stride_channel_y =
      int64_t(layout.quant_cols) * sizeof(block_q8_1_mmq) / (128 * sizeof(int));
  args.nsamples_x = args.nsamples_y = 1;
  args.stride_sample_y = rows * args.stride_channel_y;
  args.ncols_max = slots;
  args.ncols_grid_max = max_rows;
  args.mmq_x_request = tile_cols;
  auto& ctx = *static_cast<ggml_backend_hip_context*>(ws.context);
  mul_mat_q_case<type>(ctx, args, stream);
  if (hipGetLastError() != hipSuccess)
    return -3;
  if (wb) {
    args.x = static_cast<const char*>(wb);
    args.dst = out_b;
    mul_mat_q_case<type>(ctx, args, stream);
    if (hipGetLastError() != hipSuccess)
      return -3;
  }
  return 0;
}

template void mul_mat_q_case<GGML_TYPE_Q2_K>(ggml_backend_hip_context&,
                                             const mmq_args&, hipStream_t);
template void mul_mat_q_case<GGML_TYPE_IQ2_XXS>(ggml_backend_hip_context&,
                                                const mmq_args&, hipStream_t);
}  // namespace qfn_mmq

extern "C" int lie_q2_workspace_prepare(lie_q2_workspace* ws) {
  lie_q2_plan expected;
  if (!ws || !ws->storage || ws->context ||
      !lie_q2_plan_make(ws->plan.max_tokens, ws->plan.experts, ws->plan.used,
                        &expected) ||
      expected.total_bytes != ws->plan.total_bytes ||
      expected.slots != ws->plan.slots)
    return -1;
  for (int i = 0; i < LIE_Q2_REGIONS; ++i)
    if (expected.offset[i] != ws->plan.offset[i] ||
        expected.bytes[i] != ws->plan.bytes[i])
      return -1;
  const int dev = qfn_mmq::ggml_hip_get_device();
  const auto& info = qfn_mmq::ggml_hip_info();
  if (dev < 0 || dev >= info.device_count)
    return -2;
  const int cc = info.devices[dev].cc;
  if (cc != GGML_HIP_CC_OFFSET_AMD + 0x1151 ||
      qfn_mmq::get_mmq_x_max_host(cc) > LIE_Q2_TILE_GUARD)
    return -1;
  ws->context = qfn_mmq::get_ctx_for_device(dev);
  return ws->context ? 0 : -2;
}

extern "C" int lie_q2_project(lie_q2_workspace* ws, int type, int tiled,
                              int gated, const void* w, const void* wb,
                              const float* x, const int32_t* ids, float* out,
                              float* out_b, int m, int logical_k,
                              int physical_k, int rows, int used,
                              int max_expert_rows, int tile_cols,
                              hipStream_t stream) {
  lie_q2_layout layout;
  if (!ws || !ws->storage || !ws->context || !w || !x || !ids || !out ||
      m <= 0 || m > 2560 || rows <= 0 || used <= 0 ||
      used > int(ws->plan.used) || (tiled != 0 && tiled != 1) ||
      (gated != 0 && gated != 1) ||
      !lie_q2_layout_make(type, logical_k, physical_k, &layout) ||
      size_t(rows) * used > ws->plan.slots ||
      (type == LIE_IQ2_XXS && rows > int(ws->plan.max_tokens)) ||
      (type == LIE_Q2_K && (used != 1 || wb || out_b || gated)) ||
      (gated ? (type != LIE_IQ2_XXS || tiled || rows > 8 || !wb || out_b)
             : bool(wb) != bool(out_b)) ||
      max_expert_rows < 0 || max_expert_rows > rows * used || tile_cols < 0 ||
      tile_cols > 80 || tile_cols % 16 != 0)
    return -1;
  using namespace qfn_mmq;
  if (tiled) {
    if (type == LIE_IQ2_XXS)
      return tiled_project<GGML_TYPE_IQ2_XXS>(
          *ws, layout, w, wb, x, ids, out, out_b, m, rows, used,
          max_expert_rows, tile_cols, stream);
    return tiled_project<GGML_TYPE_Q2_K>(*ws, layout, w, nullptr, x, ids, out,
                                         nullptr, m, rows, used,
                                         max_expert_rows, tile_cols, stream);
  }
  auto* quant = region<block_q8_1>(*ws, LIE_Q2_QUANT);
  const auto kind = static_cast<ggml_type>(type);
  // Logical source width/stride; physical quantized width. No FP32 padded copy.
  quantize_row_q8_1_hip(x, nullptr, quant, kind, layout.read_cols,
                        layout.read_cols, layout.read_cols,
                        int64_t(layout.read_cols) * rows, layout.quant_cols, 1,
                        rows, 1, stream);
  if (hipGetLastError() != hipSuccess)
    return -2;
  const int stride = layout.quant_cols / QK8_1;
  if (gated) {
    mul_mat_vec_moe_gated(w, wb, kind, quant, ids,
                          region<int32_t>(*ws, LIE_Q2_GROUPS), out, physical_k,
                          m, rows, used, stride, stream);
    return hipGetLastError() == hipSuccess ? 0 : -3;
  }
  mul_mat_vec_moe_dispatch(w, kind, quant, ids, out, physical_k, m, rows, used,
                           stride, stream);
  if (hipGetLastError() != hipSuccess)
    return -3;
  if (wb) {
    mul_mat_vec_moe_dispatch(wb, kind, quant, ids, out_b, physical_k, m, rows,
                             used, stride, stream);
    if (hipGetLastError() != hipSuccess)
      return -3;
  }
  return 0;
}
