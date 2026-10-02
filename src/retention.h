/* SPDX-License-Identifier: MIT */
#ifndef LIE_RETENTION_H
#define LIE_RETENTION_H
#include "lie/cache_policy.h"
/* Advisory utility; callers supply UTC seconds. Backward clock jumps do not
 * increase hits. This state is independent of numerical compatibility. */
typedef struct { uint64_t touched, created; uint32_t hits, reason; } lie_retention;
void lie_retention_init(lie_retention *,uint64_t clock,bool continuation);
void lie_retention_hit(lie_retention *,uint64_t clock);
double lie_retention_score(const lie_retention *,uint64_t clock,uint64_t tokens,uint64_t bytes,bool superseded);
const char *lie_retention_policy(void);
#endif
