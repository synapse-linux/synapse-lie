/* SPDX-License-Identifier: MIT */
#ifndef LIE_CACHE_POLICY_H
#define LIE_CACHE_POLICY_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
/* Numeric reasons/extension bits follow the public DS4 kvstore contract.
 * Protocol clients own extension contents; the C core only retains bytes. */
typedef enum {
    LIE_CACHE_UNKNOWN, LIE_CACHE_COLD, LIE_CACHE_CONTINUED, LIE_CACHE_EVICT,
    LIE_CACHE_SHUTDOWN, LIE_CACHE_AGENT_SYSTEM, LIE_CACHE_AGENT_SESSION
} lie_cache_reason;
enum { LIE_CACHE_TOOL_MAP=1, LIE_CACHE_RESPONSES_VISIBLE=2,
       LIE_CACHE_THINKING_VISIBLE=4, LIE_CACHE_SESSION_TITLE=8 };
#define LIE_CACHE_HALF_LIFE_SECONDS UINT64_C(21600)
#define LIE_CACHE_TEXT_MAX (8u*1024u*1024u)
#define LIE_CACHE_TRAILER_MAX (1024u*1024u)
typedef struct {
    bool enabled, text_prefix, capture_finish;
    uint32_t min_tokens, cold_max_tokens, continued_interval_tokens;
    uint32_t boundary_trim_tokens, boundary_align_tokens;
} lie_cache_policy;
typedef struct {
    uint64_t created_at, last_used;
    uint32_t hits, reason, flags;
    const char *text;
    size_t text_bytes;
    const void *trailer;
    size_t trailer_bytes;
} lie_cache_metadata;
/* 0 unknown option, 1 accepted, -1 invalid value. */
int lie_cache_policy_option(lie_cache_policy *,const char *,const char *);
void lie_cache_policy_init(lie_cache_policy *);
uint64_t lie_cache_now(void);
uint32_t lie_cache_store_len(const lie_cache_policy *,uint32_t);
uint32_t lie_cache_continued_step(const lie_cache_policy *);
bool lie_cache_metadata_valid(const lie_cache_metadata *);
bool lie_cache_metadata_copy(lie_cache_metadata *,const lie_cache_metadata *);
void lie_cache_metadata_clear(lie_cache_metadata *);
#endif
