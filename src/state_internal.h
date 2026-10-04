/* SPDX-License-Identifier: MIT */
#ifndef LIE_STATE_INTERNAL_H
#define LIE_STATE_INTERNAL_H
#include "lie/state.h"
#include <stdatomic.h>
struct lie_state {
    lie_state_layout layout;
    uint64_t payload_bytes;
    uint64_t storage_bytes;
    uint32_t codec; /* 0 raw; 2 byte-plane4/Zstandard blocks. */
    atomic_uint refs;
    unsigned char payload[];
};
/* Import allocation is private to the validating codec; never exposed until
 * the complete checksum and structural checks have succeeded. */
lie_state *lie_state_allocate(const lie_state_layout *,uint64_t budget);
#define LIE_STATE_BLOCK_BYTES 1048576u
/* Helpers never call a provider. Decode validates every length before writing. */
bool lie_state_unpack_payload(const lie_state *,void *,size_t);
uint64_t lie_state_decode_workspace(uint32_t codec);
bool lie_state_decode_block(uint32_t codec,const void *,size_t,void *,size_t);
bool lie_state_compress_cancel(lie_state **,uint64_t,const atomic_bool *);
#endif
