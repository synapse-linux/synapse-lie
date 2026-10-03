<!-- SPDX-License-Identifier: MIT -->
# Q2/UD parity on the requested context curve

The target is Q2 prefill and decode at least equal to UD at **every** short,
medium and long context point. A gain at one point cannot compensate for a
deficit elsewhere. The canonical comparison is the single-user AR graph in
official Gufo's `docs/models/qwen3.8-flash-next/BENCHMARKS.md`, using the
method in `QUALITY.md`, `artifacts/bench.json` and `tools/gufo/model_bench/llm.py`
at pin `f783fedb9bea2ec7de941f6da4e02f4a4596b29e`. The
[plan](../config/q2-curve-parity-plan.json) records these source hashes.
Published UD numbers remain historical references; acceptance requires fresh
paired Q2/UD measurements on `.157` with recorded builds and model identities.

## Why the recent measurements do not establish this target

The historical C17 benchmark was restored to reconcile UD's approximately
26 token/s decode reference with a diagnostic that used a different sampler
and timer. Its approximately 2K case has 2042 physical input tokens. That case
exposed a library-dispatch boundary: HC down used the native consumer except
at exactly 2048 rows. The investigation then followed that boundary into a
ragged-batch optimization instead of establishing the requested whole curve.
Making this diagnostic the primary optimization target was a prioritization
error. It did not result from a user request to replace the Gufo workload.

Both the exact-2048 counting fixture (1411.691→1439.264 prefill token/s) and
the original-C17 2042-token fixture (1359.654→1386.506 in the latest paired
experiment) remain valid evidence for their stated scopes. They use different
inputs and measurement paths from the HTTP conversation sweep. These rates
must not be joined into one trend or used as canonical curve cells.

The distinction is **not exact 2048 versus 2042 tokens**. Gufo itself uses
calibrated approximate lengths. Prompt content, template, cached history,
prefill interval, output accounting and timed scope define the comparison.
A new prompt padded to exactly 2048 tokens is not automatically canonical.

## Required canonical protocol

- Use HTTP on both sides, C1 AR, greedy, thinking off, no MTP. Record server
  commands, build identities, tokenizer/template and actual request histories.
- Use the pinned deterministic synthetic prose generator and its summary/story
  instruction, seeds, calibration and ordered sweep. A counting prompt or the
  existing LIE benchmark's generic project-notes prompt is a different workload.
- Match the ordered cached-prefix targets **0, 4096, 8192, 12288, 16384,
  32768, 65536, 131072**, with configured capacity 133760 on both sides.
  Depth zero starts fresh. At deeper points prepare a conversation prefix and
  its eight-token reply, then measure approximately 2048 **new** tokens and
  128 generated output tokens. Prefix construction is outside the measured
  continuation prefill interval.
- Preserve upstream calibration and tolerance `max(32, floor(target*0.005))`
  for actual reused/new token counts. Record `cache_n`, `prompt_n`,
  `predicted_n`, completion hashes and timings for every accepted sample.
  Reject short outputs, unsupported cache reuse and context overflow.
- Use server-reported prefill and decode timing, with matching accounting.
  Client whole-request time and native executor timing are separate metrics.
  The published method uses one warmed sample per point. Additional repeated
  paired sweeps investigate discrepancies and report mean/standard deviation;
  they must retain the same ordered workload, not silently change the recipe.
- Prefix replies can differ between quantizations. Preserve those actual
  histories and counts rather than claiming byte-identical cache state.
  Fixed-token numerical or profiling controls are separate diagnostics.

The first implementation gate is to establish that the benchmark/server
composition implements this protocol. The current C17 benchmark is useful
infrastructure, but neither its name nor its `--depths` option proves workload
equivalence. Missing HTTP timing or cache-frontier support must be implemented
or explicitly reported, never filled with a native diagnostic rate.

## Additional coverage and current status

Fresh long-prompt ingestion and extension toward the shared nominal 262144
context limit are additional suites, separate from the published graph.
Near-capacity points need room for the actual calibrated prefix, template,
new turn and output; `259968 + 2048 + 128` is only a nominal arithmetic budget,
not an admitted safe calibrated workload. 512K/1M requires a common engine
context extension and quality/resource validation for both models.

The bounded [header/source audit](../config/q2-context-header-audit.json)
finds the same nominal 262144 limit and byte-identical attention dispatch and
session-accounting source slices in the inspected Q2/UD providers. This does
not prove long-context memory fit, numerical quality or performance parity.

The first paired implementation uses the pinned workload on the common C17
HTTP server. Its composition and results are recorded in
[the HTTP curve report](Q2-CANONICAL-HTTP.md). The completed ragged experiment
is retained as a diagnostic; further kernel work should be chosen from deficits
measured on the whole curve. Arithmetic and task quality remain independent
acceptance gates.

## Workload equivalence and timer boundary

`tools/q2-canonical-http.py` imports the pinned Gufo `Tokenizer`,
`synthetic_text`, `turn_prompt` and `_measure_depth` behavior rather than
substituting another text generator. Both providers use the same frozen C17
HTTP/worker/state composition. The analyzer independently reconstructs each
accepted request, including its calibration attempt and actual eight-token
prefix reply, and checks the raw usage, cache frontier and completed outputs.

The current server exposes `synapse-lie.request-timings.v1`, with scope
`synchronous_executor_calls`: the sum of completed prefill/decode executor
calls. Cache capture/restore, tokenization, queueing and HTTP transport are
outside those rates. Raw responses retain cache timings, and the report also
exports client request wall time. At C1 the decode attribution has no shared
batch overlap. This contract is unchanged in the frozen core.

Consequently, the **workload** matches Gufo's canonical graph and the fresh
Q2/UD pair has a common timer; the published Gufo scheduler timer is not claimed
identical. Neither historical Gufo values nor native counting-fixture rates
are used to fill this measured curve. Direct reproduction of the published
server's timing remains a separate check if needed for cross-server claims.
