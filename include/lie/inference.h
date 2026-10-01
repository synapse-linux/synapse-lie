/* SPDX-License-Identifier: MIT */
#ifndef LIE_INFERENCE_H
#define LIE_INFERENCE_H
#include "lie/executor.h"
#include "lie/flow.h"
#include <stdbool.h>
/* Device-owner C inference dispatcher, independent of HTTP. The caller retains
 * sequences/flows and supplies only prefilled, nonterminal candidates. No wait
 * for peers: reserve ready credit now, single decode for one row, native batch
 * for multiple rows. Caller must commit/abort each reserved output afterwards,
 * publishing its own terminal metadata before making a flow terminal visible. */
typedef struct {
    lie_sequence *sequence;
    lie_flow *flow;
    uint32_t position, context, vocab;
    bool reserved, selected, blocked;
    lie_flow_reservation reservation;
    lie_decode_outcome outcome;
} lie_inference_row;
typedef struct {
    lie_inference_row *rows;
    size_t count, selected;
} lie_inference_batch;
lie_status lie_inference_prepare(lie_inference_row *, size_t, unsigned,
                                 lie_inference_batch *, lie_error *);
lie_status lie_inference_run(lie_inference_batch *, lie_error *);
#endif
