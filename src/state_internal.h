/* SPDX-License-Identifier: MIT */
#ifndef LIE_STATE_INTERNAL_H
#define LIE_STATE_INTERNAL_H
#include "lie/state.h"
#include <stdatomic.h>
struct lie_state {
    lie_state_layout layout;
    uint64_t payload_bytes;
    atomic_uint refs;
    unsigned char payload[];
};
/* Import allocation is private to the validating codec; never exposed until
 * the complete checksum and structural checks have succeeded. */
lie_state *lie_state_allocate(const lie_state_layout *,uint64_t budget);
#endif
