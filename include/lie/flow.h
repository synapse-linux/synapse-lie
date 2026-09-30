/* SPDX-License-Identifier: MIT */
#ifndef LIE_FLOW_H
#define LIE_FLOW_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

/* One logical producer (device owner), one consumer (output owner). Other
 * threads may request credits/cancel/fail. Calls serialize through a short
 * mutex; none waits for demand, capacity, GPU or network completion.
 * Destruction additionally requires external quiescence of all callers. */
typedef struct lie_flow lie_flow;
typedef enum {
    LIE_FLOW_OK, LIE_FLOW_WOULD_BLOCK, LIE_FLOW_BUSY, LIE_FLOW_CLOSED,
    LIE_FLOW_INVALID, LIE_FLOW_NOMEM
} lie_flow_status;
typedef enum {
    LIE_FLOW_ACTIVE, LIE_FLOW_COMPLETE, LIE_FLOW_ERROR, LIE_FLOW_CANCELLED
} lie_flow_end;
typedef enum { LIE_FLOW_WORK_READY, LIE_FLOW_OUTPUT_READY } lie_flow_signal;
enum { LIE_FLOW_INVALID_DEMAND = 1 };
typedef struct {
    size_t slots;
    size_t chunk_bytes;
    size_t memory_budget_bytes; /* Requested heap storage including metadata. */
} lie_flow_options;
typedef struct { const lie_flow *owner; uint64_t generation; } lie_flow_ticket;
typedef struct {
    lie_flow_ticket ticket;
    uint64_t tokens; /* Granted confirmed-token credits, not proposal count. */
    unsigned char *data; /* Loan, writable until commit/abort, even after cancel. */
    size_t capacity;
} lie_flow_reservation;
typedef struct {
    lie_flow_end end; /* ACTIVE = a confirmed-token chunk; otherwise terminal. */
    int error_code;
    lie_flow_ticket ticket;
    const unsigned char *data; /* Loan until release; terminal events have none. */
    size_t bytes;
    uint64_t tokens, token_offset;
} lie_flow_event;
typedef struct {
    uint64_t demand, published_tokens;
    size_t queued, in_flight, borrowed, storage_bytes;
    size_t dispatch_started; /* in_flight also includes pre-dispatch reservations. */
    lie_flow_end end;
    int terminal_observed;
} lie_flow_state;

lie_flow_status lie_flow_storage(const lie_flow_options *, size_t *required);
lie_flow_status lie_flow_create(const lie_flow_options *, lie_flow **out);
/* Refuses ACTIVE, queued, in-flight or borrowed storage. No forced free. */
lie_flow_status lie_flow_destroy(lie_flow **);
/* request(0) is a protocol error; overflow saturates to UINT64_MAX (unbounded).
 * Data reservations consume credits; short steps refund unused credits. */
lie_flow_status lie_flow_request(lie_flow *, uint64_t tokens);
lie_flow_status lie_flow_reserve(lie_flow *, uint64_t step_limit, lie_flow_reservation *);
/* Dispatch gate, after preparation and immediately before submitting the step.
 * Cancel that wins this gate refuses dispatch; a winning begin is in-flight
 * work, not a promise of instantaneous GPU preemption. On refusal the caller
 * must still abort its reservation (no worker may retain an abandoned loan). */
lie_flow_status lie_flow_begin(lie_flow *, lie_flow_ticket);
/* Producer asserts these tokens are confirmed. Data already lives in the loan.
 * Validation refusal keeps the reservation; abort it after work is finished.
 * Cancel/fail do not unpin a reservation. Matching commit/abort does, and a
 * late completion after cancel/fail is discarded, never delivered as data. */
lie_flow_status lie_flow_commit(lie_flow *, lie_flow_ticket, size_t bytes,
                                uint64_t tokens, int finish);
/* Retire failed work ONLY after it completed or was never dispatched.
 * This does not interrupt/wait for a kernel. Never use it as async GPU abort. */
lie_flow_status lie_flow_abort(lie_flow *, lie_flow_ticket, int error_code);
/* Finishes an empty/idle producer; an in-flight step must commit(finish=1). */
lie_flow_status lie_flow_finish(lie_flow *);
lie_flow_status lie_flow_cancel(lie_flow *);
lie_flow_status lie_flow_fail(lie_flow *, int error_code);
/* FIFO, at most one borrowed output frame. Terminal requires all loans retired,
 * no demand, and is observed once. CANCELLED is an internal retirement event,
 * not an onComplete callback sent to a disconnected Reactive Streams client. */
lie_flow_status lie_flow_next(lie_flow *, lie_flow_event *);
lie_flow_status lie_flow_release(lie_flow *, lie_flow_ticket);
lie_flow_status lie_flow_snapshot(lie_flow *, lie_flow_state *);
/* Linux eventfd, borrowed: never close/write it externally. One drain owner per
 * direction. Drain BEFORE inspecting level state until WOULD_BLOCK/CLOSED.
 * Notifications coalesce and carry no payload. No periodic polling is needed. */
int lie_flow_fd(lie_flow *, lie_flow_signal);
lie_flow_status lie_flow_drain(lie_flow *, lie_flow_signal);
#ifdef __cplusplus
}
#endif
#endif
