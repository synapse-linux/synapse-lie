/* SPDX-License-Identifier: MIT */
/* Legacy HTTP request adapter. Direct engine clients include lie/core.h. */
#ifndef LIE_WORKER_H
#define LIE_WORKER_H
#include "lie/core.h"
#include "lie/chat.h"
typedef lie_core lie_worker;
typedef lie_core_state lie_worker_state;
typedef lie_core_options lie_worker_options;
typedef lie_core_info lie_worker_info;
#define LIE_WORKER_JOBS LIE_CORE_JOBS
#define LIE_WORKER_MAX_CONTEXT LIE_CORE_MAX_CONTEXT
#define lie_worker_create lie_core_create
#define lie_worker_stop lie_core_stop
#define lie_worker_destroy lie_core_destroy
#define lie_worker_snapshot lie_core_snapshot
#define lie_worker_fd lie_core_fd
#define lie_worker_drain lie_core_drain
/* Copies normalized data into the core; frees/zeros parsed request on success.
 * Refusal preserves caller ownership. JSON never crosses into the core job. */
int lie_worker_submit(lie_worker *, lie_chat_request *, lie_job **out);
#endif
