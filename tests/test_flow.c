/* SPDX-License-Identifier: MIT */
/* Synthetic byte-frame tests of the real flow primitive. No model or executor. */
#include "lie/flow.h"
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(x) do { if (!(x)) { fprintf(stderr, "CHECK failed %s:%d: %s\n", __FILE__, __LINE__, #x); abort(); } } while (0)
static lie_flow *create(size_t slots) {
    lie_flow *f = NULL;
    lie_flow_options o = {slots, 64, 1024 * 1024};
    CHECK(lie_flow_create(&o, &f) == LIE_FLOW_OK);
    CHECK(fcntl(lie_flow_fd(f, LIE_FLOW_WORK_READY), F_GETFL) & O_NONBLOCK);
    CHECK(fcntl(lie_flow_fd(f, LIE_FLOW_OUTPUT_READY), F_GETFD) & FD_CLOEXEC);
    return f;
}
static lie_flow_state state(lie_flow *f) {
    lie_flow_state s; CHECK(lie_flow_snapshot(f, &s) == LIE_FLOW_OK); return s;
}
static lie_flow_reservation reserve(lie_flow *f, uint64_t n) {
    lie_flow_reservation r; CHECK(lie_flow_reserve(f, n, &r) == LIE_FLOW_OK); return r;
}
static void publish(lie_flow *f, lie_flow_reservation r, const char *text, uint64_t n, int finish) {
    CHECK(strlen(text) <= r.capacity);
    memcpy(r.data, text, strlen(text));
    CHECK(lie_flow_begin(f, r.ticket) == LIE_FLOW_OK);
    CHECK(lie_flow_commit(f, r.ticket, strlen(text), n, finish) == LIE_FLOW_OK);
}
static void terminal(lie_flow *f, lie_flow_end expected, int error) {
    lie_flow_event e;
    CHECK(lie_flow_next(f, &e) == LIE_FLOW_OK);
    CHECK(e.end == expected && e.error_code == error && !e.data && !e.bytes && !e.tokens);
    CHECK(lie_flow_next(f, &e) == LIE_FLOW_CLOSED);
}
static void finish_destroy(lie_flow **f) {
    CHECK(lie_flow_finish(*f) == LIE_FLOW_OK);
    terminal(*f, LIE_FLOW_COMPLETE, 0);
    CHECK(lie_flow_destroy(f) == LIE_FLOW_OK && !*f);
}
static void wait_signal(lie_flow *f, lie_flow_signal signal) {
    struct pollfd p = {lie_flow_fd(f, signal), POLLIN, 0};
    CHECK(poll(&p, 1, 2000) == 1 && (p.revents & POLLIN));
    CHECK(lie_flow_drain(f, signal) == LIE_FLOW_OK);
}
static void limits_and_credits(void) {
    lie_flow *f = NULL; size_t required;
    lie_flow_options o = {0, 64, 10000};
    CHECK(lie_flow_create(&o, &f) == LIE_FLOW_INVALID && !f);
    o.slots = SIZE_MAX; CHECK(lie_flow_storage(&o, &required) == LIE_FLOW_INVALID);
    o.slots = 2; o.chunk_bytes = SIZE_MAX; CHECK(lie_flow_storage(&o, &required) == LIE_FLOW_INVALID);
    o.chunk_bytes = 64; CHECK(lie_flow_storage(&o, &required) == LIE_FLOW_OK);
    o.memory_budget_bytes = required - 1; CHECK(lie_flow_create(&o, &f) == LIE_FLOW_INVALID && !f);
    o.memory_budget_bytes = required; CHECK(lie_flow_create(&o, &f) == LIE_FLOW_OK);
    CHECK(state(f).storage_bytes == required);
    lie_flow_reservation r;
    CHECK(lie_flow_reserve(f, 1, &r) == LIE_FLOW_WOULD_BLOCK);
    CHECK(lie_flow_destroy(&f) == LIE_FLOW_BUSY);
    CHECK(lie_flow_request(f, 3) == LIE_FLOW_OK); wait_signal(f, LIE_FLOW_WORK_READY);
    r = reserve(f, 8); CHECK(r.tokens == 3 && state(f).demand == 0 && state(f).in_flight == 1);
    CHECK(lie_flow_finish(f) == LIE_FLOW_BUSY);
    CHECK(lie_flow_reserve(f, 1, &(lie_flow_reservation){0}) == LIE_FLOW_BUSY);
    /* A reservation is not dispatch and cannot publish a result yet. */
    CHECK(lie_flow_commit(f, r.ticket, 1, 1, 0) == LIE_FLOW_INVALID);
    publish(f, r, "ab", 2, 0);
    CHECK(state(f).demand == 1); /* Refund the unused grant, never unverified drafts. */
    CHECK(lie_flow_commit(f, r.ticket, 2, 2, 0) == LIE_FLOW_INVALID);
    lie_flow_event e; CHECK(lie_flow_next(f, &e) == LIE_FLOW_OK);
    CHECK(e.tokens == 2 && e.token_offset == 0 && e.bytes == 2 && !memcmp(e.data, "ab", 2));
    CHECK(lie_flow_next(f, &(lie_flow_event){0}) == LIE_FLOW_BUSY);
    CHECK(lie_flow_release(f, e.ticket) == LIE_FLOW_OK);
    CHECK(lie_flow_release(f, e.ticket) == LIE_FLOW_INVALID);
    CHECK(lie_flow_request(f, UINT64_MAX - 1) == LIE_FLOW_OK);
    CHECK(lie_flow_request(f, 10) == LIE_FLOW_OK && state(f).demand == UINT64_MAX);
    r = reserve(f, 4); publish(f, r, "c", 1, 0);
    CHECK(state(f).demand == UINT64_MAX);
    CHECK(lie_flow_next(f, &e) == LIE_FLOW_OK && e.token_offset == 2);
    CHECK(lie_flow_release(f, e.ticket) == LIE_FLOW_OK);
    finish_destroy(&f);
    f = create(1); /* Completion is independent of data demand, including zero output. */
    finish_destroy(&f);
    f = create(1);
    CHECK(lie_flow_request(f, 0) == LIE_FLOW_INVALID);
    terminal(f, LIE_FLOW_ERROR, LIE_FLOW_INVALID_DEMAND);
    CHECK(lie_flow_request(f, 1) == LIE_FLOW_CLOSED && lie_flow_destroy(&f) == LIE_FLOW_OK);
}
static void capacity_order_and_isolation(void) {
    lie_flow *slow = create(1), *fast = create(2);
    CHECK(lie_flow_request(slow, 9) == LIE_FLOW_OK && lie_flow_request(fast, 9) == LIE_FLOW_OK);
    lie_flow_reservation a = reserve(slow, 1), b = reserve(fast, 1);
    CHECK(lie_flow_begin(fast, a.ticket) == LIE_FLOW_INVALID); /* No cross-stream ticket. */
    publish(slow, a, "slow", 1, 0); publish(fast, b, "first", 1, 0);
    CHECK(lie_flow_reserve(slow, 1, &a) == LIE_FLOW_WOULD_BLOCK);
    b = reserve(fast, 1); publish(fast, b, "second", 1, 1);
    lie_flow_event e; CHECK(lie_flow_next(fast, &e) == LIE_FLOW_OK);
    CHECK(e.end == LIE_FLOW_ACTIVE && e.token_offset == 0 && !memcmp(e.data, "first", 5));
    CHECK(lie_flow_release(fast, e.ticket) == LIE_FLOW_OK);
    CHECK(lie_flow_next(fast, &e) == LIE_FLOW_OK && e.token_offset == 1 && !memcmp(e.data, "second", 6));
    CHECK(lie_flow_destroy(&fast) == LIE_FLOW_BUSY);
    CHECK(lie_flow_release(fast, e.ticket) == LIE_FLOW_OK);
    terminal(fast, LIE_FLOW_COMPLETE, 0); CHECK(lie_flow_destroy(&fast) == LIE_FLOW_OK);
    CHECK(lie_flow_next(slow, &e) == LIE_FLOW_OK);
    lie_flow_ticket stale = e.ticket;
    CHECK(lie_flow_reserve(slow, 1, &a) == LIE_FLOW_WOULD_BLOCK); /* Borrow still uses capacity. */
    CHECK(lie_flow_release(slow, e.ticket) == LIE_FLOW_OK);
    wait_signal(slow, LIE_FLOW_WORK_READY);
    a = reserve(slow, 1); publish(slow, a, "resume", 1, 0);
    CHECK(lie_flow_next(slow, &e) == LIE_FLOW_OK && e.token_offset == 1);
    CHECK(lie_flow_release(slow, stale) == LIE_FLOW_INVALID); /* Reused slot, new generation. */
    CHECK(lie_flow_release(slow, e.ticket) == LIE_FLOW_OK);
    finish_destroy(&slow);
}
static void cancellation_and_error(void) {
    lie_flow *f = create(3);
    CHECK(lie_flow_request(f, 10) == LIE_FLOW_OK);
    lie_flow_reservation a = reserve(f, 1); publish(f, a, "held", 1, 0);
    lie_flow_event held; CHECK(lie_flow_next(f, &held) == LIE_FLOW_OK);
    a = reserve(f, 2); publish(f, a, "queued", 2, 0);
    a = reserve(f, 3); CHECK(lie_flow_begin(f, a.ticket) == LIE_FLOW_OK);
    CHECK(state(f).queued + state(f).in_flight + state(f).borrowed == 3);
    CHECK(lie_flow_drain(f, LIE_FLOW_OUTPUT_READY) == LIE_FLOW_OK);
    CHECK(lie_flow_cancel(f) == LIE_FLOW_OK); wait_signal(f, LIE_FLOW_OUTPUT_READY);
    CHECK(state(f).queued == 0 && state(f).in_flight == 1 && state(f).borrowed == 1);
    CHECK(lie_flow_reserve(f, 1, &(lie_flow_reservation){0}) == LIE_FLOW_CLOSED);
    CHECK(lie_flow_destroy(&f) == LIE_FLOW_BUSY);
    memcpy(a.data, "late", 4); /* Still valid while the cancelled work is in flight. */
    CHECK(lie_flow_commit(f, a.ticket, 4, 3, 0) == LIE_FLOW_CLOSED);
    CHECK(!memcmp(held.data, "held", 4)); /* Cannot reclaim already borrowed I/O. */
    CHECK(lie_flow_next(f, &(lie_flow_event){0}) == LIE_FLOW_BUSY);
    CHECK(lie_flow_release(f, held.ticket) == LIE_FLOW_OK);
    terminal(f, LIE_FLOW_CANCELLED, 0); CHECK(lie_flow_destroy(&f) == LIE_FLOW_OK);

    f = create(1); CHECK(lie_flow_request(f, 1) == LIE_FLOW_OK); a = reserve(f, 1);
    CHECK(lie_flow_cancel(f) == LIE_FLOW_OK);
    CHECK(lie_flow_begin(f, a.ticket) == LIE_FLOW_CLOSED); /* Cancel wins before dispatch. */
    CHECK(lie_flow_destroy(&f) == LIE_FLOW_BUSY);
    CHECK(lie_flow_abort(f, a.ticket, 42) == LIE_FLOW_OK);
    terminal(f, LIE_FLOW_CANCELLED, 0); CHECK(lie_flow_destroy(&f) == LIE_FLOW_OK);

    f = create(1); CHECK(lie_flow_request(f, 2) == LIE_FLOW_OK); a = reserve(f, 2);
    CHECK(lie_flow_begin(f, a.ticket) == LIE_FLOW_OK);
    CHECK(lie_flow_commit(f, a.ticket, a.capacity + 1, 1, 0) == LIE_FLOW_INVALID);
    CHECK(lie_flow_commit(f, a.ticket, 1, a.tokens + 1, 0) == LIE_FLOW_INVALID);
    CHECK(lie_flow_commit(f, a.ticket, 0, 0, 0) == LIE_FLOW_INVALID);
    CHECK(state(f).in_flight == 1); /* Validation did not mutate or abandon the loan. */
    CHECK(lie_flow_fail(f, 42) == LIE_FLOW_OK && lie_flow_cancel(f) == LIE_FLOW_OK);
    CHECK(lie_flow_abort(f, a.ticket, 99) == LIE_FLOW_OK);
    terminal(f, LIE_FLOW_ERROR, 42); CHECK(lie_flow_destroy(&f) == LIE_FLOW_OK);

    f = create(1); CHECK(lie_flow_request(f, 1) == LIE_FLOW_OK);
    a = reserve(f, 1); publish(f, a, "unread", 1, 1);
    CHECK(lie_flow_cancel(f) == LIE_FLOW_OK); /* Cancel may abandon pending completion/data. */
    terminal(f, LIE_FLOW_CANCELLED, 0); CHECK(lie_flow_destroy(&f) == LIE_FLOW_OK);

    f = create(1); CHECK(lie_flow_request(f, 1) == LIE_FLOW_OK); a = reserve(f, 1);
    publish(f, a, "", 0, 1); terminal(f, LIE_FLOW_COMPLETE, 0);
    CHECK(lie_flow_destroy(&f) == LIE_FLOW_OK);
}
static void arithmetic_and_fd_lifetime(void) {
    lie_flow *f = create(1); CHECK(lie_flow_request(f, UINT64_MAX) == LIE_FLOW_OK);
    lie_flow_reservation r = reserve(f, UINT64_MAX); publish(f, r, "", UINT64_MAX, 0);
    lie_flow_event e; CHECK(lie_flow_next(f, &e) == LIE_FLOW_OK);
    CHECK(e.tokens == UINT64_MAX && lie_flow_release(f, e.ticket) == LIE_FLOW_OK);
    r = reserve(f, 1); CHECK(lie_flow_begin(f, r.ticket) == LIE_FLOW_OK);
    CHECK(lie_flow_commit(f, r.ticket, 0, 1, 0) == LIE_FLOW_INVALID); /* No ordinal wrap. */
    CHECK(lie_flow_abort(f, r.ticket, 77) == LIE_FLOW_OK);
    terminal(f, LIE_FLOW_ERROR, 77); CHECK(lie_flow_destroy(&f) == LIE_FLOW_OK);
    for (int i = 0; i < 32; ++i) {
        f = create(2); int work = lie_flow_fd(f, LIE_FLOW_WORK_READY), output = lie_flow_fd(f, LIE_FLOW_OUTPUT_READY);
        CHECK(lie_flow_cancel(f) == LIE_FLOW_OK); terminal(f, LIE_FLOW_CANCELLED, 0);
        CHECK(lie_flow_destroy(&f) == LIE_FLOW_OK);
        CHECK(fcntl(work, F_GETFD) == -1 && errno == EBADF);
        CHECK(fcntl(output, F_GETFD) == -1 && errno == EBADF);
    }
}
#define FRAMES 4000
typedef struct { lie_flow *f; pthread_barrier_t barrier; } threaded;
static void *produce(void *arg) {
    lie_flow *f = arg;
    for (uint64_t i = 0; i < FRAMES; ++i) {
        lie_flow_reservation r;
        for (;;) {
            lie_flow_status rc = lie_flow_reserve(f, 3, &r);
            if (rc == LIE_FLOW_OK) break;
            CHECK(rc == LIE_FLOW_WOULD_BLOCK); wait_signal(f, LIE_FLOW_WORK_READY);
        }
        CHECK(lie_flow_begin(f, r.ticket) == LIE_FLOW_OK);
        memcpy(r.data, &i, sizeof(i));
        CHECK(lie_flow_commit(f, r.ticket, sizeof(i), 1, i + 1 == FRAMES) == LIE_FLOW_OK);
    }
    return NULL;
}
static void *cancelled_producer(void *arg) {
    threaded *t = arg; lie_flow_reservation r = reserve(t->f, 1);
    CHECK(lie_flow_begin(t->f, r.ticket) == LIE_FLOW_OK);
    (void)pthread_barrier_wait(&t->barrier); (void)pthread_barrier_wait(&t->barrier);
    memcpy(r.data, "still-owned", 11);
    CHECK(lie_flow_commit(t->f, r.ticket, 11, 1, 0) == LIE_FLOW_CLOSED);
    return NULL;
}
static void cross_thread_events(void) {
    lie_flow *f = create(3); CHECK(lie_flow_request(f, 7) == LIE_FLOW_OK);
    pthread_t worker; CHECK(!pthread_create(&worker, NULL, produce, f));
    uint64_t consumed = 0; bool complete = false;
    while (!complete) {
        wait_signal(f, LIE_FLOW_OUTPUT_READY);
        lie_flow_event e; lie_flow_status rc;
        while ((rc = lie_flow_next(f, &e)) == LIE_FLOW_OK) {
            if (e.end != LIE_FLOW_ACTIVE) { CHECK(e.end == LIE_FLOW_COMPLETE && consumed == FRAMES); complete = true; break; }
            uint64_t value; CHECK(e.bytes == sizeof(value)); memcpy(&value, e.data, sizeof(value));
            CHECK(value == consumed && e.tokens == 1 && e.token_offset == consumed); ++consumed;
            CHECK(lie_flow_release(f, e.ticket) == LIE_FLOW_OK);
            rc = lie_flow_request(f, 1); CHECK(rc == LIE_FLOW_OK || rc == LIE_FLOW_CLOSED);
            lie_flow_state s = state(f); CHECK(s.queued + s.in_flight + s.borrowed <= 3);
        }
        CHECK(complete || rc == LIE_FLOW_WOULD_BLOCK);
    }
    CHECK(!pthread_join(worker, NULL)); CHECK(state(f).published_tokens == FRAMES);
    CHECK(lie_flow_destroy(&f) == LIE_FLOW_OK);
    threaded t = {.f = create(1)}; CHECK(!pthread_barrier_init(&t.barrier, NULL, 2));
    CHECK(lie_flow_request(t.f, 1) == LIE_FLOW_OK);
    CHECK(!pthread_create(&worker, NULL, cancelled_producer, &t));
    (void)pthread_barrier_wait(&t.barrier);
    CHECK(lie_flow_cancel(t.f) == LIE_FLOW_OK);
    CHECK(lie_flow_destroy(&t.f) == LIE_FLOW_BUSY);
    (void)pthread_barrier_wait(&t.barrier); CHECK(!pthread_join(worker, NULL));
    CHECK(state(t.f).published_tokens == 0); terminal(t.f, LIE_FLOW_CANCELLED, 0);
    CHECK(lie_flow_destroy(&t.f) == LIE_FLOW_OK); CHECK(!pthread_barrier_destroy(&t.barrier));
}
int main(void) {
    limits_and_credits(); capacity_order_and_isolation(); cancellation_and_error();
    arithmetic_and_fd_lifetime(); cross_thread_events();
    puts("reactive flow: demand, bounds, dispatch/cancel, loans, FIFO, terminals, peer isolation, eventfd threads PASS (CPU frames; no inference)");
}
