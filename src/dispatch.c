/* SPDX-License-Identifier: MIT */
#include "lie/dispatch.h"
#include <limits.h>
#include <stddef.h>
#include <string.h>

void lie_attention_dispatch_info_init(lie_attention_dispatch_info *info) {
  if (!info)
    return;
  memset(info, 0, sizeof(*info));
  info->abi_version = LIE_ATTENTION_DISPATCH_ABI;
  info->struct_bytes = sizeof(*info);
}
void lie_attention_dispatch_init(lie_attention_dispatch_counter *counter,
                                 bool supported, uint64_t domain) {
  if (!counter)
    return;
  memset(counter, 0, sizeof(*counter));
  lie_attention_dispatch_info_init(&counter->info);
  counter->info.supported = supported;
  counter->info.domain = domain;
}
static bool tagged(const lie_attention_dispatch_info *info) {
  return info && info->abi_version == LIE_ATTENTION_DISPATCH_ABI &&
         info->struct_bytes == sizeof(*info) &&
         (!info->supported || info->domain != 0);
}
static void add(uint64_t *value, uint64_t amount, bool *overflowed) {
  if (amount > UINT64_MAX - *value) {
    *value = UINT64_MAX;
    *overflowed = true;
  } else
    *value += amount;
}
lie_dispatch_status
lie_attention_dispatch_begin(lie_attention_dispatch_counter *counter) {
  if (!counter || !tagged(&counter->info) || counter->info.pending)
    return LIE_DISPATCH_INVALID;
  if (!counter->info.supported)
    return LIE_DISPATCH_UNAVAILABLE;
  memset(&counter->staged, 0, sizeof(counter->staged));
  counter->info.pending = true;
  return LIE_DISPATCH_OK;
}
lie_dispatch_status
lie_attention_dispatch_record(lie_attention_dispatch_counter *counter,
                              lie_attention_path path, uint32_t rows,
                              uint32_t words, lie_attention_refusal refusal) {
  bool sparse = path == LIE_ATTENTION_MATRIX_SPARSE ||
                path == LIE_ATTENTION_SCALAR_SPARSE;
  bool matrix =
      path == LIE_ATTENTION_MATRIX_DENSE || path == LIE_ATTENTION_MATRIX_SPARSE;
  if (!counter || !tagged(&counter->info) || !counter->info.pending || !rows ||
      (unsigned)path > LIE_ATTENTION_SCALAR_SPARSE ||
      (unsigned)refusal > LIE_ATTENTION_REFUSAL_MASK_PITCH ||
      (sparse ? !words : words != 0) ||
      (matrix && refusal != LIE_ATTENTION_REFUSAL_NONE) ||
      (refusal == LIE_ATTENTION_REFUSAL_MASK_PITCH && !sparse))
    return LIE_DISPATCH_INVALID;
  lie_attention_dispatch_totals *staged = &counter->staged;
  uint64_t *paths[] = {&staged->matrix_dense, &staged->matrix_sparse,
                       &staged->scalar_dense, &staged->scalar_sparse};
  add(paths[path], 1, &counter->info.overflowed);
  add(&staged->attention_rows, rows, &counter->info.overflowed);
  if (refusal == LIE_ATTENTION_REFUSAL_GEOMETRY)
    add(&staged->geometry_refusals, 1, &counter->info.overflowed);
  if (refusal == LIE_ATTENTION_REFUSAL_MASK_PITCH)
    add(&staged->mask_pitch_refusals, 1, &counter->info.overflowed);
  if (rows > counter->info.max_observed_rows)
    counter->info.max_observed_rows = rows;
  if (words > counter->info.max_observed_mask_words)
    counter->info.max_observed_mask_words = words;
  return LIE_DISPATCH_OK;
}
static void merge(lie_attention_dispatch_totals *to,
                  const lie_attention_dispatch_totals *from, bool *overflowed) {
#define ADD(field) add(&to->field, from->field, overflowed)
  ADD(matrix_dense);
  ADD(matrix_sparse);
  ADD(scalar_dense);
  ADD(scalar_sparse);
  ADD(geometry_refusals);
  ADD(mask_pitch_refusals);
  ADD(attention_rows);
#undef ADD
}
lie_dispatch_status
lie_attention_dispatch_finish(lie_attention_dispatch_counter *counter,
                              bool confirmed) {
  if (!counter || !tagged(&counter->info) || !counter->info.pending)
    return LIE_DISPATCH_INVALID;
  merge(confirmed ? &counter->info.confirmed : &counter->info.unconfirmed,
        &counter->staged, &counter->info.overflowed);
  add(confirmed ? &counter->info.confirmed_batches
                : &counter->info.unconfirmed_batches,
      1, &counter->info.overflowed);
  memset(&counter->staged, 0, sizeof(counter->staged));
  counter->info.pending = false;
  return LIE_DISPATCH_OK;
}
lie_dispatch_status
lie_attention_dispatch_snapshot(const lie_attention_dispatch_counter *counter,
                                lie_attention_dispatch_info *out) {
  if (!counter || !tagged(&counter->info) || !tagged(out))
    return LIE_DISPATCH_INVALID;
  *out = counter->info;
  return LIE_DISPATCH_OK;
}
static bool subtract(const lie_attention_dispatch_totals *after,
                     const lie_attention_dispatch_totals *before,
                     lie_attention_dispatch_totals *out) {
#define SUB(field)                                                             \
  do {                                                                         \
    if (after->field < before->field)                                          \
      return false;                                                            \
    out->field = after->field - before->field;                                 \
  } while (0)
  SUB(matrix_dense);
  SUB(matrix_sparse);
  SUB(scalar_dense);
  SUB(scalar_sparse);
  SUB(geometry_refusals);
  SUB(mask_pitch_refusals);
  SUB(attention_rows);
#undef SUB
  return true;
}
lie_dispatch_status
lie_attention_dispatch_delta(const lie_attention_dispatch_info *before,
                             const lie_attention_dispatch_info *after,
                             lie_attention_dispatch_info *out) {
  if (!tagged(before) || !tagged(after) || !tagged(out))
    return LIE_DISPATCH_INVALID;
  if (!before->supported || !after->supported)
    return LIE_DISPATCH_UNAVAILABLE;
  if (before->domain != after->domain || before->pending || after->pending ||
      before->overflowed || after->overflowed ||
      after->confirmed_batches < before->confirmed_batches ||
      after->unconfirmed_batches < before->unconfirmed_batches ||
      after->max_observed_rows < before->max_observed_rows ||
      after->max_observed_mask_words < before->max_observed_mask_words)
    return LIE_DISPATCH_INVALID;
  lie_attention_dispatch_info result = *after;
  if (!subtract(&after->confirmed, &before->confirmed, &result.confirmed) ||
      !subtract(&after->unconfirmed, &before->unconfirmed, &result.unconfirmed))
    return LIE_DISPATCH_INVALID;
  result.confirmed_batches -= before->confirmed_batches;
  result.unconfirmed_batches -= before->unconfirmed_batches;
  *out = result;
  return LIE_DISPATCH_OK;
}
