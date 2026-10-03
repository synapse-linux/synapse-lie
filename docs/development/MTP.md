<!-- SPDX-License-Identifier: MIT -->
# MTP development branch

`feature/mtp` adds verified multi-token generation to the shared C17 core,
HTTP server and core benchmark client. The contract is model-neutral; the first
real binding delegates predictor execution, target verification, sampling and
rollback to the pinned Gufo Qwen3.8 Flash Next provider.

**Status:** CPU contract tests and HIP compilation/linking only. Original-weight
MTP correctness, memory fit and speed have not been qualified. GPU benchmarks
are postponed at the owner's request. Vision is developed on `feature/vision`;
these two feature branches are not yet combined.

## Use

Build as described in the [build guide](../guides/BUILD.md). `LIE_MTP=ON` is the
default build option; `-DLIE_MTP=OFF` removes runtime admission. Explicit predictor
selection enables MTP. Omitting it preserves AR execution.

```sh
build/release/synapse-lie-server \
  --model /models/target-00001-of-00004.gguf \
  --model-mtp /models/predictor.gguf --mtp-draft-tokens 0 \
  --model-id local-model --port 8000 --context 4096 --max-active 2 \
  --kv-cache-ram-mb 0
```

Use ordinary Chat Completions or Responses requests; no MTP-specific HTTP request
fields are needed. `--mtp-draft-tokens 0` selects the admitted provider's default.
The current Qwen binding admits 1–7 proposals. Other providers report their own
limits; seven is not a core constant. The core bounds completed bursts at 32
output tokens to keep reservations finite.

The same engine path is available without HTTP:

```sh
build/release/synapse-lie-bench --suite core \
  --model /models/target-00001-of-00004.gguf \
  --model-mtp /models/predictor.gguf --mtp-draft-tokens 0 \
  --prompt-file prompt.txt --context 4096 --chunk 2048 \
  --users 2 --tg 128 --repetitions 3 --kv-cache-ram-mb 0 \
  --output mtp.jsonl --graphs mtp-graphs
```

These are usage recipes, not a GPU run authorization on shared machines; follow
[coordination](../COORDINATION.md). Predictor and target must be compatible.

## Core and reactive behavior

`include/lie/mtp.h` defines opaque-model entry points and versioned capabilities.
`lie_core_options.mtp_model_path` and `mtp_draft_tokens` configure admission.
The core owns scheduling, output reservations, validated token publication,
resource bounds, cancellation and metrics. No Qwen types or predictor topology
are exposed to clients.

Each ready row reserves at most its demand, remaining generation/context budget
and admitted burst bound. Proposals are private to the provider; only target-
verified tokens consume consumer credit. Short output returns unused credit.
All rows are validated before any output from a completed call is published.
Cancellation suppresses late results; a corrupt peer outcome fails the shared
call. Sequences have independent samplers.

There is still one device owner and completed synchronous provider calls. MTP
adds no worker per request, GPU preemption or internal asynchronous forward.
Any throughput benefit must come from less target work per confirmed token and
must be measured separately from scheduling responsiveness.

`lie_timings` exposes `decode_mode`, `max_decode_output_tokens`,
`mtp_drafted_tokens` and `mtp_accepted_tokens`. `decode_calls` counts completed
row calls, not tokens. The native HTTP client validates the declared burst bound.
Core benchmark identity records mode, predictor path and requested draft bound;
job records include admitted bound and draft/acceptance counts. The actuator
executor snapshot includes aggregate completed, non-cancelled draft/acceptance
counts. Proposals and rejected tokens are never counted as generated output.

## Cache and remaining gates

The C state codec now describes DS4 predictor K/V, raw index and pooled keys,
plus typed residual/kept hidden rows and a validated adaptive controller.
The extra Gufo continuation components use the common authenticated auxiliary
trailer; DS4 payload offsets and ordinary AR files remain unchanged. CPU fixtures
exercise predictor frontiers at 0, 1, 3, 4 and 8 tokens, budget refusal, corruption,
capture/restore and SSD index reconstruction in a new live domain.

The live provider still requires binding these components and pinning predictor
weights/configuration into the stable identity. Its existing MTP path also pools
keys only when sparse attention starts; complete pooled capture must be implemented
without presenting uninitialized history as state. MTP therefore still requires
**explicit `--kv-cache-ram-mb 0` and no `--kv-disk-dir`**;
incompatible configurations are refused before loading a model. AR retains its
normal RAM-cache default. No incomplete state is presented as a cache hit.

Before integration: connect the model-specific predictor state and identity to
the common RAM/SSD lifecycle; qualify greedy AR parity, sampled target behavior,
rejection/rollback, cancellation and mixed concurrency on original weights;
then compare PP/TG, complete-window throughput and memory with AR. Same sampling
seed alone does not imply equal AR/speculative token streams. Additional real
model families require their own bindings and qualification.

The numerical source remains official Gufo
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, with the existing LIE state-access
variant. No numerical kernels or DS4 project files were changed. Two synthetic
provider geometries (8- and 13-token bursts) exercise the generic contract;
these fixtures are **NOT-INFERENCE**. See the
[validation receipt](validation/mtp-2026-10-03.json).
The subsequent state-codec checks are recorded separately in the
[state validation receipt](validation/mtp-state-2026-10-03.json).
