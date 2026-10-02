/* SPDX-License-Identifier: MIT */
#ifndef LIE_STATE_CODEC_H
#define LIE_STATE_CODEC_H
#include "lie/store.h"
#include <stdatomic.h>
#include "lie/cache_policy.h"
#define LIE_STATE_DISK_HEADER 160u
#define LIE_STATE_DISK_SECTION 64u
uint64_t lie_state_file_bytes(const lie_state *);
uint64_t lie_state_file_bytes_ex(const lie_state *,const lie_cache_metadata *);
bool lie_state_file_write_ex(int,const lie_state_identity *,const lie_state *,const lie_cache_metadata *,const atomic_bool *);
bool lie_state_file_metadata(int,const lie_state_identity *,uint64_t,lie_cache_metadata *);
bool lie_state_file_touch(int,const lie_state_identity *,uint32_t,uint64_t);
/* Caller opens/owns regular FD. Codec uses pread/pwrite and never changes its
 * offset. Little-endian IEEE payload only; checksum covers header (digest
 * zeroed), section table and entire payload, including alignment padding. */
bool lie_state_file_write(int,const lie_state_identity *,const lie_state *,const atomic_bool *);
lie_state *lie_state_file_read(int,const lie_state_identity *,uint64_t domain,uint64_t budget,
                               const atomic_bool *);
/* Bounded metadata inspection; NOT checksum validation or restore admission. */
bool lie_state_file_probe(int,const lie_state_identity *,uint64_t *file_bytes,unsigned *tokens,unsigned *context);
bool lie_state_prefix_key(const lie_state_identity *,const int32_t *,size_t,char hex[65]);
#endif
