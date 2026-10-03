<!-- SPDX-License-Identifier: MIT -->
# Shared core output events

HTTP, Responses and `synapse-lie-bench --suite core` consume the same C17 event
contract in [`lie/events.h`](../../include/lie/events.h). Direct clients need no
HTTP service, libuv, llhttp or json-c. Initialize requests with
`lie_core_request_init`; request ABI **4** adds `parallel_tool_calls`, defaulting
to true. Event ABI **1** identifies its version and structure size in each event.

## Events and order

| Event | Payload | Credits |
| --- | --- | --- |
| `LIE_EVENT_TEXT` | A valid UTF-8 fragment; split sequences are held and malformed bytes become U+FFFD. | Confirmed tokens represented by this chunk; a final UTF-8 flush may have zero. |
| `LIE_EVENT_PROGRESS` | No visible text or callable function. Used while a tool-enabled turn is buffered. | Confirmed tokens, allowing the client to replenish demand without publishing an unvalidated call. |
| `LIE_EVENT_TOOL_CALL` | Core-owned ID, function name, validated complete arguments JSON and zero-based index. | Zero: these tokens were already counted in progress events. |
| `LIE_EVENT_TURN_END` | Final job metadata, error and typed reason: stop, length, tool calls, cancelled or error. | Zero; no loan. |

Ordinary output emits text followed by one terminal. A tool-enabled turn emits
progress, then its validated prose and calls, followed by one terminal. Every
call in the turn validates before any prose or executable call is exposed.
Unknown functions, duplicate arguments, missing required parameters, basic type
mismatches, forbidden parallel calls and truncated/malformed tags fail the turn.
A required or named choice cannot silently become ordinary text. Calls are data;
LIE never executes tools.

The current output grammar binding is Qwen's function tags, isolated in
`src/models/qwen_output.c`. Other model families must supply a qualified binding
against these neutral contracts. Validation covers basic JSON types, required
properties and `additionalProperties=false`, including type unions. It is not
full JSON-Schema validation or constrained generation. Incremental executable
argument deltas remain future work.

Call IDs are minted by the core with a random per-core namespace and job/call
indices. They remain unchanged across that job's events and HTTP projections;
they do not depend on an HTTP request ID or collide merely because a core was
restarted.

## Consuming events

Each job has **one output consumer**. Select either semantic events or the
legacy raw `lie_job_flow` interface. Mixing them is refused: the raw accessor
returns NULL after semantic selection; event APIs refuse a raw-selected job.
Raw output remains available for existing diagnostics, but it does not validate
or interpret tool turns.

The core grants eight initial confirmed-token credits. Release each nonterminal
event, then replenish its token count; never request zero tokens. An event with
zero tokens still has a loan. Its text/call pointers remain valid until release.
Tickets identify both the job and loan generation; stale or foreign releases
fail. `next` returns BUSY while an event remains borrowed. `TURN_END` has no loan
and is returned once; subsequent `next` returns CLOSED.

```c
#include "lie/events.h"
#include <poll.h>

/* job has been admitted; this function owns its single output consumer. */
for (;;) {
    lie_event event;
    lie_flow_status status = lie_job_event_next(job, &event);
    if (status == LIE_FLOW_WOULD_BLOCK) {
        struct pollfd ready = {lie_job_event_fd(job), POLLIN, 0};
        if (poll(&ready, 1, -1) < 0) { /* Handle interruption/error. */ break; }
        lie_job_event_drain(job);
        continue;
    }
    if (status != LIE_FLOW_OK) break;
    if (event.kind == LIE_EVENT_TURN_END) {
        /* Inspect event.reason and event.info. */
        break;
    }
    /* Consume TEXT, TOOL_CALL or PROGRESS; copy payload if retaining it. */
    uint64_t tokens = event.tokens;
    if (lie_job_event_release(job, event.ticket) != LIE_FLOW_OK) break;
    if (tokens) lie_job_event_request(job, tokens);
}
/* Release any still-borrowed event before releasing job. */
lie_job_release(job);
```

Use `fd`/`drain`/`next`/`release` on the single consumer thread. Cross-thread job
cancellation remains a lifetime-protected latch. A slow text client holds the
underlying flow loan until delivery completes; its row cannot advance beyond
confirmed demand. Buffered tool clients can acknowledge progress without
publishing calls. Cancellation suppresses queued results and pending calls;
an already borrowed payload remains valid until release. A semantic terminal
waits for numerical and cache work to retire, including cancellation in prefill.
The legacy raw terminal may become observable earlier.

## Ownership, bounds and metrics

Incremental UTF-8 and tool validation run inside the shared core's consumer API.
They add no thread and make no provider call on a client thread. The device
owner retains its existing ready-row, credit-driven dispatch. This extraction
is an ownership/lifecycle change, not a measured inference speedup.

A text scratch buffer covers the admitted MTP burst, up to three UTF-8 bytes per
raw output byte plus decoder slack. Tool buffering grows only up to
`max_tokens * 256 * 3 + 8` bytes. At most 16 calls and 128 arguments per call are
accepted; each arguments JSON buffer is capped at 8 MiB. JSON parsing is bounded
to depth 32 and 32768 value nodes, rejects duplicate keys, decoded NUL and
nonfinite numbers, and uses locale-neutral number parsing. String quoting and
validated call storage are also bounded by the admitted output length. Memory
is allocated as needed; raw/text jobs do not allocate a whole-turn tool buffer.

The immutable request arena (at most 32 MiB), semantic buffers and token
witnesses remain until the final job reference is released. They are not KV
checkpoints. Clients retaining retired jobs retain that memory. RAM/SSD cache
formats, model payloads and default policies are unchanged.

`lie_job_info.semantic_checked`, `output_invalid` and `tool_calls` describe the
semantic check. An invalid turn reports `finish=INVALID` with its specific error.
Physical output tokens and executor timings remain generation witnesses.
`lie_core_info.output_validation_errors`, exposed in `/actuator/llm.scheduler`,
counts checks that fail through any semantic client. Existing completed/failed
executor counters retain their physical scope; the HTTP tool-error meter counts
failures projected to that protocol. Clients that stop before validation do not
produce a validation-error count.

## Validation

The headless event fixture covers UTF-8 splits, AR and two MTP geometries,
complete/invalid/truncated calls, choices and parallel policy, credit starvation,
peer progress, loan tickets, cancellation before pending calls, prefill
retirement and raw/semantic exclusion. Native HTTP fixtures cover Chat and
Responses JSON/SSE, failure projections, ordered terminals and full-size burst
pieces beyond the previous single-token HTTP scratch buffer.

These are **CPU fixtures, NOT-INFERENCE**. Host HIP compilation/linking checks
composition only. Original-weight tool correctness, GPU faults, resources and
performance still require compatible models and a fresh coordinated GPU window.
See the [source-bound receipt](../development/validation/core-events-2026-10-03.json).
