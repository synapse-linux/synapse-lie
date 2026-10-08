/* SPDX-License-Identifier: MIT */
/* Actual C worker dispatch with synthetic tokens; NOT model inference. */
#include "lie/core.h"
#include "fake_executor.h"
#include <assert.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

static void wait_state(lie_core *core, lie_core_state expected) {
    const struct timespec pause = {0, 1000000};
    for (unsigned i = 0; i < 4000; ++i) {
        lie_core_info info;
        lie_core_snapshot(core, &info);
        if (info.state == expected) return;
        nanosleep(&pause, NULL);
    }
    assert(!"core state deadline");
}

static void check(unsigned chunk, size_t count) {
    lie_core_options options;
    lie_core_options_init(&options);
    options.model_path = ":fixture:";
    options.context = 20000;
    options.chunk = chunk;
    options.max_active = 1;
    options.prefix_cache_bytes = 0;
    fake_calls_reset();
    lie_core *core = lie_core_create(&options);
    assert(core);
    wait_state(core, LIE_READY);
    int32_t *tokens = calloc(count, sizeof(*tokens));
    assert(tokens);
    lie_core_request request;
    lie_core_request_init(&request);
    request.kind = LIE_INPUT_TOKENS;
    request.tokens = tokens;
    request.token_count = count;
    request.max_tokens = 1;
    lie_job *job = NULL;
    assert(lie_core_submit(core, &request, &job) == 0);
    free(tokens);
    unsigned terminal = 0;
    for (unsigned i = 0; i < 4000 && !terminal; ++i) {
        lie_flow_event event;
        lie_flow_status status = lie_flow_next(lie_job_flow(job), &event);
        if (status == LIE_FLOW_WOULD_BLOCK) {
            struct pollfd fd = {lie_flow_fd(lie_job_flow(job), LIE_FLOW_OUTPUT_READY), POLLIN, 0};
            assert(poll(&fd, 1, 1) >= 0);
            assert(lie_flow_drain(lie_job_flow(job), LIE_FLOW_OUTPUT_READY) == LIE_FLOW_OK);
            continue;
        }
        assert(status == LIE_FLOW_OK);
        if (event.end != LIE_FLOW_ACTIVE) {
            assert(event.end == LIE_FLOW_COMPLETE);
            terminal = 1;
        } else {
            assert(lie_flow_release(lie_job_flow(job), event.ticket) == LIE_FLOW_OK);
            (void)lie_flow_request(lie_job_flow(job), event.tokens);
        }
    }
    assert(terminal);
    lie_job_info info;
    lie_job_snapshot(job, &info);
    assert(info.timing_valid && info.prefill_tokens == count);
    assert(info.prefill_calls == (count + chunk - 1) / chunk);
    assert(info.cached_tokens == 0 && info.output_tokens == 1);
    assert(fake_calls_snapshot().prefill == info.prefill_calls);
    lie_job_release(job);
    lie_core_stop(core);
    wait_state(core, LIE_STOPPED);
    lie_core_destroy(core);
}

int main(void) {
    for (unsigned chunk = 2048; chunk <= 8192; chunk *= 2) {
        check(chunk, chunk - 1);
        check(chunk, chunk);
        check(chunk, chunk + 1);
        check(chunk, 2 * chunk + 17);
    }
    lie_core_options invalid;
    lie_core_options_init(&invalid);
    invalid.model_path = ":fixture:";
    invalid.context = 20000;
    invalid.chunk = 8193;
    assert(lie_core_create(&invalid) == NULL);
    puts("PASS C17 full-chunk and natural-tail dispatch (NOT-INFERENCE)");
    return 0;
}
