/* SPDX-License-Identifier: MIT */
#ifndef LIE_STATE_KVC_H
#define LIE_STATE_KVC_H
#include "state_codec.h"
bool lie_state_kvc_detect(int);
uint64_t lie_state_kvc_bytes(const lie_state *,const lie_cache_metadata *);
bool lie_state_kvc_write(int,const lie_state_identity *,const lie_state *,const lie_cache_metadata *,const atomic_bool *);
lie_state *lie_state_kvc_read(int,const lie_state_identity *,uint64_t,uint64_t,const atomic_bool *);
bool lie_state_kvc_probe(int,const lie_state_identity *,uint64_t *,unsigned *,unsigned *);
bool lie_state_kvc_metadata(int,const lie_state_identity *,uint64_t,lie_cache_metadata *);
bool lie_state_kvc_touch(int,const lie_state_identity *,uint32_t,uint64_t);
bool lie_state_kvc_token_key(int,const lie_state_identity *,char hex[65]);
bool lie_state_kvc_scope(int,const lie_state_identity *,unsigned char scope[32]);
#endif
