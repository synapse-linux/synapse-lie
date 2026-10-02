/* SPDX-License-Identifier: MIT */
#ifndef LIE_RETENTION_H
#define LIE_RETENTION_H
#include <stdbool.h>
#include <stdint.h>
/* Per-store logical access clock: deterministic aging, no wall-clock jumps.
 * Metadata is advisory and resets on process reopen; state identity is separate. */
typedef struct { uint64_t touched; double hits; bool continuation; } lie_retention;
void lie_retention_init(lie_retention *,uint64_t clock,bool continuation);
void lie_retention_hit(lie_retention *,uint64_t clock);
double lie_retention_score(const lie_retention *,uint64_t clock,uint64_t tokens,uint64_t bytes,bool superseded);
const char *lie_retention_policy(void);
#endif
