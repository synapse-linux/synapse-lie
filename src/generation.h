/* SPDX-License-Identifier: MIT */
#ifndef LIE_GENERATION_PRIVATE_H
#define LIE_GENERATION_PRIVATE_H
#include "lie/core.h"
typedef struct {
  char pending[LIE_STOP_BYTES];
  size_t bytes;
  bool matched;
} lie_stop_state;
/* In-place completed-token text filter; capacity includes pending suffix.
 * Retain only a suffix which can still become a stop sequence. */
bool lie_stop_feed(lie_stop_state *, const lie_core_request *, char *, size_t *,
                   size_t, bool);
bool lie_logprob_row(const float *, size_t, unsigned, lie_token_logprobs *);
#endif
