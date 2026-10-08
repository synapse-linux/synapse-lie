// SPDX-License-Identifier: MIT
#ifndef LIE_IQ2_STAGE_LAYOUT_H
#define LIE_IQ2_STAGE_LAYOUT_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// Experimental lossless transpose of 640x2560 IQ2_XXS expert weights.
// Each original row has ten 66-byte superblocks: a two-byte scale followed
// by eight eight-byte groups. The destination keeps the same byte count:
// 40 stage pairs x 640 rows x 16 group bytes, then 10 scale planes x 640 rows
// x 2 bytes. Two neighboring lanes can read a row's stage pair contiguously.
// Source and destination must be disjoint and at least bytes(experts) long.
size_t lie_iq2_stage_layout_bytes(size_t experts);
int lie_iq2_stage_layout_pack(const uint8_t *source, size_t source_bytes,
                              uint8_t *destination, size_t destination_bytes,
                              size_t experts);

#ifdef __cplusplus
}
#endif

#endif
