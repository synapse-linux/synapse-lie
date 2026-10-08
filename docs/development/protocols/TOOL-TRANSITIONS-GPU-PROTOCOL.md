<!-- SPDX-License-Identifier: MIT -->
# Original-weight function transition qualification

This final-phase development gate extends the selected single-function and
[numerical MTP qualification](DS4-SAMPLING-GPU-PROTOCOL.md). It uses the existing
server on an admitted `.161` window. The optional Python coordinator adds no
dependency to the C17 server, native benchmark, graph generation or default tests.
No numerical kernel, executor/core ABI, reactive queue or worker changes.

## Frozen workload

The gate declares 71 checks, with one server run for AR and a separately admitted
run for MTP. Each uses the original model, seed 123 and these explicit controls:

| Profile | Temperature | Top-p | Top-k | Min-p |
| --- | --- | --- | --- | --- |
| Greedy | 0 | 1 | 0 | 0 |
| DS4 | 1 | 1 | 0 | 0.05 |
| Filtered | 0.8 | 0.9 | 32 | 0.02 |

Frequency/presence penalties remain at their zero server defaults. Output is
bounded at 512 tokens; natural completion is required. Context is 16,384 and
prefill chunk is 2,048; RAM cache is disabled. Each request runs alone on private
ephemeral loopback ports. These are functional observations, not benchmark data.

Each profile covers Chat Completions and Responses, in JSON and SSE, for four
predeclared questions: automatic choice with a text-only answer, prose before
a function call, two independent calls, and one required call with parallel
calls disabled. The strict function schema permits `get_value` with key `alpha`
or `beta`. Valid schema membership and following the requested keys are checked
separately from transport correctness.

Parallel calls return distinct values, alpha 137 and beta 941. The client sends
the result items in reverse call order, retaining each actual call ID. The next
question asks for a JSON mapping without embedding the expected values in the
question or output schema. Chat carries full history; Responses covers both
stateless full history and retained `previous_response_id` continuation.
Responses parallel SSE also requires byte-identical retired-journal replay.

Eight additional cases require HTTP400 for orphan, missing, duplicate and
unknown result IDs in both APIs. Actual idle executor counters before/after
each refusal must remain identical. Fixture call IDs in these malformed
histories are client input, explicitly distinct from original-weight output.

## Independent wire checks

The development client assembles each indexed argument stream itself, checks
unique IDs and fixed names, and parses complete argument objects with duplicate
property/nonfinite-value refusal. Chat requires one finish, one usage record
and one terminal sentinel. Responses requires contiguous typed sequence numbers,
start/delta/argument-done/item-done correlation and a completed terminal matching
the complete function items. Prose must precede function starts. Token usage and
seeded JSON/SSE content/argument equality are checked independently.

Chat observations retain actual decode mode and draft/acceptance counters.
The MTP run requires actual proposals; an enabled server alone does not prove
speculation. These checks do not replace the saved-row probability/RNG oracle.

Protocol failures and predeclared model-quality misses retain the partial wire
and receipt and fail the gate. A valid response that omits requested prose or
confuses the distinct returned values is a `model_quality` failure. Do not
change questions, weaken criteria or relabel a failed capture as passing.

## Preparation and acceptance

The optional `modern-http` campaign manifest selects
`http_tool_transition_gate:true` and binds the SHA-256 of
`tools/strix-point-tool-transition-gate.py` as `http_tool_transitions_sha256`.
Stage that exact helper as `http-tool-transitions.py` in the exclusive job root.
The existing HTTP gate passes `--tool-transitions`; its historical selections
and default check inventory remain unchanged. The runner validates all 71
completed witnesses, selected mode and refusal counters. The collector retains
the helper, partial/final receipt, complete wire, server logs and thermal/control
records, including failed runs.

Offline HOST tests use canned responses without sockets, models or GPU. They
prove the checking code and failure retention only. Original-weight acceptance
requires coherent bound runtime/model provenance, current peer coordination,
fresh global and in-lease admission, actual exits, collected hashes and exact
process/container/lease retirement. No preparation reserves a future window.

The first [original AR run](../validation/tool-transitions-ar-point-r2-2026-10-07.json)
fails `greedy_chat_parallel_json` after four new checks: the fixed two-key
question produces only `alpha`. All subsequent checks are unexecuted, and MTP
is unadmitted. This failure does not change the workload or acceptance criteria.

The [corrected-runtime AR observation](../validation/tool-transitions-ar-point-r3-2026-10-07.json)
passes that unchanged greedy Chat JSON two-call case. Its next fixed reversed-
results continuation instead swaps the two integer values. Five new checks pass,
one fails and 65 are unexecuted. Source diagnosis identifies omitted call IDs in
the model renderer; result-correlation correction and AR/MTP requalification
remain open. Questions, profiles, budgets and acceptance criteria are unchanged.

The [correlation-corrected AR observation](../validation/tool-transitions-ar-point-r4-2026-10-07.json)
passes 14 new checks, including the unchanged reversed-results Chat JSON/SSE
questions and all four malformed Chat histories. The next seeded Responses
request receives HTTP400: `seed` is missing from the Responses parser allowlist
and normalization. One check fails, 56 are unexecuted, and MTP is unadmitted.
This protocol refusal and the earlier model-quality failures retain their
separate source identities. The workload and acceptance remain unchanged.

The [Responses-corrected AR gate](../validation/tool-transitions-ar-point-r5-2026-10-07.json)
passes all 71 unchanged new checks and five baseline controls on the matching
`90a88455`/r68 runtime. Independent collected-wire review covers 48 ordinary
requests, twelve reversed-result continuations, eight refusals before forward
and three exact journal replays. Supplied seed and filters are retained.
All actual exits and verified whole-container retirement pass. This qualifies
the frozen AR workload; the separately admitted equivalent MTP gate and broader
quality/fault/resource/performance acceptance remain required.

The [matching MTP gate](../validation/tool-transitions-mtp-point-r2-2026-10-07.json)
subsequently passes the same 71 new checks and five baseline controls with
original Q4/Q8 weights. Independent wire review also confirms 362 actual
Chat draft tokens and 230 accepted tokens. All 15 artifacts verify and all
process/collector/closure exits are0. The initial local review ordering error
(missing still-pending closure receipt, exit1) is preserved; the unchanged
review passes0 after closure, without repeating GPU work. This qualifies the
frozen MTP workload; broader quality/fault/resources and matched cost remain open.
