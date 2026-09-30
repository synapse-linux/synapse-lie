/* SPDX-License-Identifier: MIT */
#include "lie/flow.h"
#include <errno.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdlib.h>
#include <sys/eventfd.h>
#include <unistd.h>

#define NO_SLOT SIZE_MAX
typedef enum { SLOT_FREE, SLOT_RESERVED, SLOT_RUNNING, SLOT_QUEUED, SLOT_BORROWED } slot_state;
typedef struct {
    slot_state state;
    uint64_t generation, grant, tokens, offset;
    size_t bytes;
} slot;
struct lie_flow {
    pthread_mutex_t mutex;
    lie_flow_options options;
    slot *slots;
    size_t *queue;
    unsigned char *payload;
    size_t storage, cursor, head, queued, in_flight, borrowed;
    uint64_t demand, generation, published;
    lie_flow_end end;
    int error, terminal_observed;
    int wake[2];
};

lie_flow_status lie_flow_storage(const lie_flow_options *o, size_t *required) {
    if (!o || !required || !o->slots || !o->chunk_bytes) return LIE_FLOW_INVALID;
    size_t metadata = sizeof(slot) + sizeof(size_t);
    if (o->chunk_bytes > SIZE_MAX - metadata) return LIE_FLOW_INVALID;
    size_t per_slot = metadata + o->chunk_bytes;
    if (o->slots > (SIZE_MAX - sizeof(lie_flow)) / per_slot) return LIE_FLOW_INVALID;
    *required = sizeof(lie_flow) + o->slots * per_slot;
    return LIE_FLOW_OK;
}
lie_flow_status lie_flow_create(const lie_flow_options *o, lie_flow **out) {
    size_t storage;
    if (!out || *out || lie_flow_storage(o, &storage) != LIE_FLOW_OK ||
        storage > o->memory_budget_bytes) return LIE_FLOW_INVALID;
    lie_flow *f = calloc(1, sizeof(*f));
    if (!f) return LIE_FLOW_NOMEM;
    f->wake[0] = f->wake[1] = -1;
    f->slots = calloc(o->slots, sizeof(*f->slots));
    f->queue = calloc(o->slots, sizeof(*f->queue));
    f->payload = malloc(o->slots * o->chunk_bytes);
    if (!f->slots || !f->queue || !f->payload) goto fail;
    f->wake[0] = eventfd(0, EFD_CLOEXEC | EFD_NONBLOCK);
    f->wake[1] = eventfd(0, EFD_CLOEXEC | EFD_NONBLOCK);
    if (f->wake[0] < 0 || f->wake[1] < 0 || pthread_mutex_init(&f->mutex, NULL)) goto fail;
    f->options = *o; f->storage = storage;
    f->in_flight = f->borrowed = NO_SLOT;
    *out = f;
    return LIE_FLOW_OK;
fail:
    if (f->wake[0] >= 0) close(f->wake[0]);
    if (f->wake[1] >= 0) close(f->wake[1]);
    free(f->payload); free(f->queue); free(f->slots); free(f);
    return LIE_FLOW_NOMEM;
}
/* Called with mutex held: nonblocking eventfd write. EAGAIN means a wake is
 * already pending. A closed/invalid borrowed FD is a caller lifetime bug. */
static void notify(lie_flow *f, lie_flow_signal direction) {
    uint64_t one = 1;
    ssize_t n;
    do { n = write(f->wake[direction], &one, sizeof(one)); } while (n < 0 && errno == EINTR);
    if (n != (ssize_t)sizeof(one) && !(n < 0 && errno == EAGAIN)) abort();
}
static uint64_t add_demand(uint64_t a, uint64_t b) {
    return b > UINT64_MAX - a ? UINT64_MAX : a + b;
}
static void discard_queued(lie_flow *f) {
    while (f->queued) {
        f->slots[f->queue[f->head]].state = SLOT_FREE;
        f->head = (f->head + 1) % f->options.slots;
        --f->queued;
    }
}
static void terminate(lie_flow *f, lie_flow_end end, int error) {
    if (!f->terminal_observed && (f->end == LIE_FLOW_ACTIVE || f->end == LIE_FLOW_COMPLETE)) {
        f->end = end; f->error = error; f->demand = 0;
        discard_queued(f);
    }
    notify(f, LIE_FLOW_WORK_READY); notify(f, LIE_FLOW_OUTPUT_READY);
}
lie_flow_status lie_flow_request(lie_flow *f, uint64_t tokens) {
    if (!f) return LIE_FLOW_INVALID;
    pthread_mutex_lock(&f->mutex);
    lie_flow_status status = LIE_FLOW_OK;
    if (f->end != LIE_FLOW_ACTIVE) status = LIE_FLOW_CLOSED;
    else if (!tokens) {
        terminate(f, LIE_FLOW_ERROR, LIE_FLOW_INVALID_DEMAND);
        status = LIE_FLOW_INVALID;
    } else {
        f->demand = add_demand(f->demand, tokens);
        notify(f, LIE_FLOW_WORK_READY);
    }
    pthread_mutex_unlock(&f->mutex);
    return status;
}
lie_flow_status lie_flow_reserve(lie_flow *f, uint64_t limit, lie_flow_reservation *out) {
    if (!f || !limit || !out) return LIE_FLOW_INVALID;
    pthread_mutex_lock(&f->mutex);
    lie_flow_status status = LIE_FLOW_OK;
    if (f->end != LIE_FLOW_ACTIVE) status = LIE_FLOW_CLOSED;
    else if (f->in_flight != NO_SLOT) status = LIE_FLOW_BUSY;
    else if (!f->demand || f->queued + (f->borrowed != NO_SLOT) == f->options.slots)
        status = LIE_FLOW_WOULD_BLOCK;
    else if (f->generation == UINT64_MAX) status = LIE_FLOW_INVALID;
    else {
        size_t i = f->cursor;
        while (f->slots[i].state != SLOT_FREE) i = (i + 1) % f->options.slots;
        f->cursor = (i + 1) % f->options.slots;
        slot *s = &f->slots[i];
        s->state = SLOT_RESERVED; s->generation = ++f->generation;
        s->grant = limit < f->demand ? limit : f->demand;
        if (f->demand != UINT64_MAX) f->demand -= s->grant;
        f->in_flight = i;
        *out = (lie_flow_reservation){ {f, s->generation}, s->grant,
            f->payload + i * f->options.chunk_bytes, f->options.chunk_bytes };
    }
    pthread_mutex_unlock(&f->mutex);
    return status;
}
static bool matches(lie_flow *f, lie_flow_ticket t, size_t i, slot_state state) {
    return t.owner == f && i != NO_SLOT && f->slots[i].state == state &&
           t.generation == f->slots[i].generation;
}
lie_flow_status lie_flow_begin(lie_flow *f, lie_flow_ticket ticket) {
    if (!f) return LIE_FLOW_INVALID;
    pthread_mutex_lock(&f->mutex);
    lie_flow_status status = LIE_FLOW_INVALID;
    if (matches(f, ticket, f->in_flight, SLOT_RESERVED)) {
        if (f->end != LIE_FLOW_ACTIVE) status = LIE_FLOW_CLOSED;
        else { f->slots[f->in_flight].state = SLOT_RUNNING; status = LIE_FLOW_OK; }
    }
    pthread_mutex_unlock(&f->mutex);
    return status;
}
lie_flow_status lie_flow_commit(lie_flow *f, lie_flow_ticket ticket, size_t bytes,
                                uint64_t tokens, int finish) {
    if (!f) return LIE_FLOW_INVALID;
    pthread_mutex_lock(&f->mutex);
    lie_flow_status status = LIE_FLOW_INVALID;
    if (!matches(f, ticket, f->in_flight, SLOT_RUNNING)) goto done;
    size_t i = f->in_flight; slot *s = &f->slots[i];
    if (bytes > f->options.chunk_bytes || tokens > s->grant ||
        (!tokens && (bytes || !finish)) || tokens > UINT64_MAX - f->published ||
        (finish != 0 && finish != 1)) goto done;
    f->in_flight = NO_SLOT;
    if (f->end != LIE_FLOW_ACTIVE) {
        s->state = SLOT_FREE; status = LIE_FLOW_CLOSED; /* Late completed work: discard. */
    } else {
        if (f->demand != UINT64_MAX) f->demand = add_demand(f->demand, s->grant - tokens);
        if (tokens) {
            s->tokens = tokens; s->bytes = bytes; s->offset = f->published;
            f->published += tokens; s->state = SLOT_QUEUED;
            f->queue[(f->head + f->queued) % f->options.slots] = i; ++f->queued;
        } else s->state = SLOT_FREE;
        if (finish) { f->end = LIE_FLOW_COMPLETE; f->demand = 0; }
        status = LIE_FLOW_OK;
    }
    notify(f, LIE_FLOW_WORK_READY); notify(f, LIE_FLOW_OUTPUT_READY);
done:
    pthread_mutex_unlock(&f->mutex);
    return status;
}
lie_flow_status lie_flow_abort(lie_flow *f, lie_flow_ticket ticket, int error) {
    if (!f || !error) return LIE_FLOW_INVALID;
    pthread_mutex_lock(&f->mutex);
    lie_flow_status status = LIE_FLOW_INVALID;
    if (matches(f, ticket, f->in_flight, SLOT_RESERVED) || matches(f, ticket, f->in_flight, SLOT_RUNNING)) {
        f->slots[f->in_flight].state = SLOT_FREE; f->in_flight = NO_SLOT;
        terminate(f, LIE_FLOW_ERROR, error); status = LIE_FLOW_OK;
    }
    pthread_mutex_unlock(&f->mutex);
    return status;
}
lie_flow_status lie_flow_finish(lie_flow *f) {
    if (!f) return LIE_FLOW_INVALID;
    pthread_mutex_lock(&f->mutex);
    lie_flow_status status = LIE_FLOW_OK;
    if (f->end != LIE_FLOW_ACTIVE) status = LIE_FLOW_CLOSED;
    else if (f->in_flight != NO_SLOT) status = LIE_FLOW_BUSY;
    else {
        f->end = LIE_FLOW_COMPLETE; f->demand = 0;
        notify(f, LIE_FLOW_WORK_READY); notify(f, LIE_FLOW_OUTPUT_READY);
    }
    pthread_mutex_unlock(&f->mutex);
    return status;
}
static lie_flow_status stop(lie_flow *f, lie_flow_end end, int error) {
    if (!f) return LIE_FLOW_INVALID;
    pthread_mutex_lock(&f->mutex);
    lie_flow_status status = f->terminal_observed ? LIE_FLOW_CLOSED : LIE_FLOW_OK;
    if (status == LIE_FLOW_OK) terminate(f, end, error);
    pthread_mutex_unlock(&f->mutex);
    return status;
}
lie_flow_status lie_flow_cancel(lie_flow *f) { return stop(f, LIE_FLOW_CANCELLED, 0); }
lie_flow_status lie_flow_fail(lie_flow *f, int error) {
    return error ? stop(f, LIE_FLOW_ERROR, error) : LIE_FLOW_INVALID;
}
lie_flow_status lie_flow_next(lie_flow *f, lie_flow_event *out) {
    if (!f || !out) return LIE_FLOW_INVALID;
    pthread_mutex_lock(&f->mutex);
    lie_flow_status status = LIE_FLOW_WOULD_BLOCK;
    if (f->borrowed != NO_SLOT) status = LIE_FLOW_BUSY;
    else if (f->queued) {
        size_t i = f->queue[f->head]; f->head = (f->head + 1) % f->options.slots; --f->queued;
        slot *s = &f->slots[i]; s->state = SLOT_BORROWED; f->borrowed = i;
        *out = (lie_flow_event){LIE_FLOW_ACTIVE, 0, {f, s->generation},
            f->payload + i * f->options.chunk_bytes, s->bytes, s->tokens, s->offset};
        status = LIE_FLOW_OK;
    } else if (f->end != LIE_FLOW_ACTIVE && f->in_flight == NO_SLOT) {
        if (f->terminal_observed) status = LIE_FLOW_CLOSED;
        else {
            *out = (lie_flow_event){ .end = f->end, .error_code = f->error };
            f->terminal_observed = 1; status = LIE_FLOW_OK;
        }
    }
    pthread_mutex_unlock(&f->mutex);
    return status;
}
lie_flow_status lie_flow_release(lie_flow *f, lie_flow_ticket ticket) {
    if (!f) return LIE_FLOW_INVALID;
    pthread_mutex_lock(&f->mutex);
    lie_flow_status status = LIE_FLOW_INVALID;
    if (matches(f, ticket, f->borrowed, SLOT_BORROWED)) {
        f->slots[f->borrowed].state = SLOT_FREE; f->borrowed = NO_SLOT;
        notify(f, LIE_FLOW_WORK_READY); notify(f, LIE_FLOW_OUTPUT_READY);
        status = LIE_FLOW_OK;
    }
    pthread_mutex_unlock(&f->mutex);
    return status;
}
lie_flow_status lie_flow_snapshot(lie_flow *f, lie_flow_state *out) {
    if (!f || !out) return LIE_FLOW_INVALID;
    pthread_mutex_lock(&f->mutex);
    *out = (lie_flow_state){ f->demand, f->published, f->queued,
        f->in_flight != NO_SLOT, f->borrowed != NO_SLOT, f->storage,
        f->in_flight != NO_SLOT && f->slots[f->in_flight].state == SLOT_RUNNING,
        f->end, f->terminal_observed };
    pthread_mutex_unlock(&f->mutex);
    return LIE_FLOW_OK;
}
int lie_flow_fd(lie_flow *f, lie_flow_signal direction) {
    return f && (direction == LIE_FLOW_WORK_READY || direction == LIE_FLOW_OUTPUT_READY) ? f->wake[direction] : -1;
}
lie_flow_status lie_flow_drain(lie_flow *f, lie_flow_signal direction) {
    int fd = lie_flow_fd(f, direction); if (fd < 0) return LIE_FLOW_INVALID;
    uint64_t count; ssize_t n;
    do { n = read(fd, &count, sizeof(count)); } while (n < 0 && errno == EINTR);
    return n == (ssize_t)sizeof(count) || (n < 0 && errno == EAGAIN) ? LIE_FLOW_OK : LIE_FLOW_INVALID;
}
lie_flow_status lie_flow_destroy(lie_flow **handle) {
    if (!handle || !*handle) return LIE_FLOW_INVALID;
    lie_flow *f = *handle;
    pthread_mutex_lock(&f->mutex);
    bool busy = f->end == LIE_FLOW_ACTIVE || f->queued || f->in_flight != NO_SLOT || f->borrowed != NO_SLOT;
    pthread_mutex_unlock(&f->mutex);
    if (busy) return LIE_FLOW_BUSY;
    /* External quiescence required; a mutex cannot protect callers after free. */
    pthread_mutex_destroy(&f->mutex); close(f->wake[0]); close(f->wake[1]);
    free(f->payload); free(f->queue); free(f->slots); free(f); *handle = NULL;
    return LIE_FLOW_OK;
}
