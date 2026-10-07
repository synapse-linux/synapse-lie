<!-- SPDX-License-Identifier: MIT -->
# DS4 sampling profile qualification

This is a development protocol for the newly exposed shared-core candidate
filters. It adds no Python dependency to the server, native benchmark, graphs
or default tests. The optional Point supervisor only coordinates an admitted
`.161` run and validates its native output.

## Frozen controls

Declare all seven controls in an optional `generation` object in the Point
campaign manifest. Missing campaign settings preserve historical greedy behavior;
an explicitly supplied object must be complete and typed. The requested DS4
server profile is:

```json
{
  "generation": {
    "temperature": 1,
    "top_p": 1,
    "top_k": 0,
    "min_p": 0.05,
    "frequency_penalty": 0,
    "presence_penalty": 0,
    "seed": 123
  }
}
```

The native CLI equivalent is `--temperature 1 --top-p 1 --top-k 0 --min-p 0.05
--frequency-penalty 0 --presence-penalty 0 --seed 123`. This selects an explicit
profile; LIE's defaults remain greedy with both candidate filters disabled.
The supervisor refuses invalid profiles before model verification/load and
compares the complete reported generation identity to the declared controls.
Historical five-control result identities mean `top_k=0`, `min_p=0`.

## Complete-row capture and offline probability replay

`lie-sampling-capture` is a C17 development client of the existing executor ABI.
It saves completed raw float32 logits immediately before the ordinary AR draw,
then records the actual committed token and frontier. It does not change logits,
sample a second token, call the reporting-logit API or alter the sampler RNG.
Six fresh sessions cover greedy, DS4 temperature-1/min-p, top-k, combined nucleus/
min-p, positive generated-token penalties and temperature-2/negative penalties.
Each uses the same physical prompt and seed 123; the default is 16 rows per
profile, with an explicit 1–128-row limit. EOS remains an ordinary sampled token
under the explicit fixed-budget policy. No cache or HTTP worker participates.

The executable is built alongside `lie-executor-bench` in an opt-in HIP runtime
build. Its GPU command belongs to the deferred final qualification phase and
requires fresh ownership/lease admission; preparing the client schedules no run.

```sh
build/gpu/lie-sampling-capture \
  --model /path/to/original/first-shard.gguf \
  --output-dir evidence/sampling-original-rows --tokens 16
```

The output is a new private directory: `capture.jsonl` binds generation settings,
physical prompt IDs, each binary row's SHA-256 and byte count, actual outputs and
completion. Rows use IEEE754 float32 little-endian, without JSON rounding.
Existing destinations refuse; partial rows and failure records remain evidence.
Storage is `profiles × rows × vocabulary × 4` bytes plus metadata: about 91 MiB
for six 16-row profiles and a 248,320-token vocabulary. Capture is deliberately
outside performance measurement; it adds full-row host copies and I/O.

The optional host-only `tests/sampling` project builds
`reference-sampling-replay`, `candidate-sampling-replay` and
`fallback-sampling-replay`. All three consume the same saved data offline:

```sh
build/sampling/reference-sampling-replay --capture evidence/sampling-original-rows > reference.txt
build/sampling/candidate-sampling-replay --capture evidence/sampling-original-rows > candidate.txt
build/sampling/fallback-sampling-replay --capture evidence/sampling-original-rows > fallback.txt
cmp reference.txt candidate.txt
cmp reference.txt fallback.txt
```

They emit every retained probability, draw and RNG state, verify the captured
live token and committed history, and compare mass against an independent full
ranking/long-double oracle. Probability tolerance is absolute `5e-14` plus
relative `5e-12`; candidate support must match exactly. Separate residual draws
exercise target mass outside a unit proposal's support. These are numerical
correction checks, not an actual MTP predictor/controller rejection. The replay
rejects checksum/length/path drift, malformed generation identity, incomplete
profiles and missing terminal records. Synthetic captures require explicit
`--allow-synthetic` and print `NOT-INFERENCE`.

Source and local fixtures do not establish original-weight probabilities.
Qualification additionally requires an admitted GPU capture, pinned original
weights/runtime provenance, actual command exits and process/lease closure.
This tooling changes no core/executor ABI, reactive scheduling, production
sampler or product Python dependency. The required-function mode below prepares
tool probability evidence; actual MTP acceptance/correction, broader tool
transitions, faults, quality and cost retain their separate gates.

### Required-function rows

The additive owner-only `lie_sequence_decode_mtp_observed` contract now prepares
actual MTP draw/proposal/verification witnesses, including RNG and grammar masks.
Its ON/OFF HOST checks establish observation lifetimes and unchanged draws.
The explicit MTP writer/replay below now passes HOST controls; a new coherent
HIP build and original-weight numerical/controller gates remain required.
The AR CLI and v1/v2 formats below remain unchanged. No MTP GPU run is admitted
by this preparation.

The same C17 client accepts `--tools` for six fresh seeded sessions with the
same generation profiles. It renders one strict `describe_stack` function,
requires exactly one call and disables parallel calls. Its frozen schema admits
`order` (`LIFO` or `FIFO`) and integer `size` from 0 through 9; the user prompt
requests `LIFO` and 3. A structured-answer constraint makes this workload
call-only, without free prose before or after the call. The ordinary shared-core
output validator checks the entire completed call; no function is executed.

```sh
build/gpu/lie-sampling-capture \
  --model /path/to/original/first-shard.gguf \
  --output-dir evidence/sampling-required-functions --tools
```

Here `--tokens` is a maximum **row** budget, including the final EOS row; the
default is 128. Natural EOS is required after a valid call. A budget exhausted
before EOS fails and preserves partial evidence. EOS advances no physical
position and emits no token. The executor does not expose the sampled EOS ID:
the replay verifies that its draw belongs to the captured stop-token set and
that the live stop occurs at the same completed frontier, rather than claiming
an observed live EOS identity.

The version-2 manifest binds `vocabulary.bin`, raw row hashes, physical prompt
and committed IDs, emitted/stop flags, generation/constraint identity and parsed
call arguments. Vocabulary encoding is the eight-byte `LIEVOC01` magic, a
little-endian u32 count, then per-token u32 byte length, u32 stop flag (0 or 1)
and exact raw bytes. Limits are 1,048,576 tokens, 32,768 bytes per piece and
64 MiB overall; empty pieces, split UTF-8 and embedded NUL remain representable
in the vocabulary. Completed tool output is separately bounded at 32,768 bytes
and rejects embedded NUL. The owner-only, model-neutral
`lie_model_token_is_stop` accessor performs no forward or sampler mutation.

The existing three replay executables automatically recognize this format.
They reconstruct the grammar from the bound constraint and vocabulary, check
**every** token against a separate byte-by-byte membership walk, then compare
the complete mask, filtered probability mass, committed draws and history.
The independent long-double oracle excludes disallowed tokens before ranking.
The replay also assembles the captured pieces and independently validates the
call name, schema and saved arguments. `semantic_match` reports whether the
model chose the requested `LIFO` and 3; schema validity is not a quality score.

This is deferred qualification tooling. Local synthetic fixtures do not prove
original-weight tool probabilities, result correlation, free-prose/parallel
behavior, MTP controller branches, faults or performance. The matching
[final HIP build](../validation/integrated-point-capture-hip-build-2026-10-07.json)
now links and binds this client and its metadata accessor. An actual GPU
capture still requires fresh admission.
Version-1 unconstrained captures and their complete witnesses remain compatible.

The [current required-function AR qualification](../validation/sampling-required-tools-ar-point-2026-10-07.json)
completes six original-weight profiles and 152 rows on `.161`. Original/C17/OFF
Release and unsuppressed sanitizer outputs agree completely, including every
mask bit and retained probability. Independent mass, RNG, history and complete
call checks pass; all six calls choose `LIFO`/3 and finish with natural EOS.
Probability oracles compare support and mass by token, retaining actual entry
order for draws; descending mass order is not a contract requirement. Real
generation controls are admitted as float32 before independent calculations.
The receipt retains the initial supplementary-review assumptions and corrections.
This qualifies the frozen single-function AR workload at chunk 2,048; wider tool
transitions, actual MTP execution, fault/resource/quality and cost remain separate.

### Actual MTP target/proposal/verification capture

After a coherent GPU build and fresh machine admission, select the original
predictor explicitly:

```sh
lie-sampling-capture --model ORIGINAL-FIRST-SHARD --output-dir NEW-DIRECTORY \
  --mtp-model ORIGINAL-PREDICTOR --draft-tokens 7 --tokens 128
```

Add `--tools` for the same strict required-function workload. The six generation
profiles and seed are unchanged. The MTP budget bounds confirmed output tokens;
tool mode requires natural EOS and a fully parsed call before completion.
Greedy reserves one output per call and covers the host head only. GPU greedy
verification may have no host rows; this capture does not qualify that fast path.
Positive-temperature profiles use the admitted MTP burst, including adaptive
shorter draft chains and final partial reservations.

Schema v3 records `cycle_begin`, borrowed `sampling_trace` events and
`cycle_complete` with the exact committed IDs/frontier and drafted/accepted
counters. Every trace stores its raw F32 row and optional full U8 mask in
checksummed exclusive files. Compact proposals include their ID mapping and
exact F32 masses; RNG states use 16 hexadecimal characters. History/penalties
describe the state at that draw. Deferred correction is identified and must
consume no second random draw. The callback configuration is copied; needed
borrowed data is written within the callback. A writer failure is checked after
the numerical call returns, preserves partial evidence and is never retried.

Limits are 1–128 confirmed tokens per profile, 1–7 requested drafts, 1,152
traces per profile, 4 GiB aggregate trace payload and 128 MiB replay metadata.
Vocabulary retains its separate 64 MiB bound. Original/C17/OFF offline programs
reconstruct every target/proposal/verification decision, integer proposal mass,
acceptance/residual RNG, grammar mask and complete output frontier. Independent
long-double mass and grammar byte-walk oracles also apply. Synthetic files
require explicit `--allow-synthetic` and remain NOT-INFERENCE.

The [HOST receipt](../validation/mtp-capture-host-2026-10-07.json) records
text/tools/128-token fixtures, complete three-program witness agreement,
accepted/rejected/deferred branches and 22 refusal cases. It does not establish
original-weight probability, quality or performance acceptance. Capture I/O is
excluded from throughput comparisons.

The [selected original-weight text receipt](../validation/sampling-mtp-text-point-2026-10-07.json)
now binds six 16-token Q4/Q8 profiles and 192 actual observations. Complete
original/C17/OFF Release and sanitizer mass/RNG/controller witnesses match.
Greedy remains a host-head baseline; required-tool MTP masks, broader quality,
fault/resources and matched cost retain their separate gates.

### Point supervisor and collection

The optional `.161` supervisor routes the native client with these fields in
an otherwise pinned campaign manifest:

```json
{
  "bench_profile": "modern-sampling-capture",
  "decode_mode": "ar",
  "capture_mode": "tools",
  "capture_row_budget": 128
}
```

Use `capture_mode: "text"` for unconstrained rows, with an explicit 1–128 row
budget. The manifest also binds the original model plan, compiled runtime build
identity and capture executable hash, using the existing lease, thermal and
model-stat contracts. AR admits no predictor. For MTP, set `decode_mode: "mtp"`,
bind an explicit verified `predictor_plan` and select `mtp_draft_tokens` in 1–7
(default 7). The retained manifest field `capture_row_budget` then bounds
confirmed output tokens, while trace files have their separate limits above.
The read-only predictor mount and both original weight identities are checked.
The supervisor
records possible model access as soon as the native manifest appears and
preserves model identities even when the child or receipt validation fails.

Successful receipts verify all six frozen generation profiles, raw-file hashes,
ordered rows, committed frontiers, terminal counts and completed required-call
arguments. Schema-valid calls and requested `LIFO`/3 semantics are counted
separately. Probability, full-mask, MTP-controller, quality and performance
acceptance remain the separate gates described above.

After the campaign ends, collect its native data with:

```sh
python3 tools/strix-point-bench-collect.py UNIQUE_LABEL --kind sampling-capture
```

Data lands in `evidence/UNIQUE_LABEL/capture`, ready for the existing three
offline replay executables. Collection also preserves partial manifests, empty
failure artifacts and raw rows written before an unsuccessful draw. Only bounded
regular files with the native names are accepted; symlinks and named pipes
refuse. This optional development orchestration changes no product dependency,
HTTP behavior or reactive scheduling, and schedules no GPU run by itself.

## Required gates

| Gate | Acceptance |
| --- | --- |
| AR controls | Pinned original target weights, complete fixed output, matching seven-control identity and deterministic repeated AR runs with identical seed/input/lifecycle. |
| MTP controls | Same target profile plus explicitly admitted predictor; witnessed drafts and accepted target tokens, rejection/residual correction and complete fixed output. |
| Probability behavior | Independent filter/distribution oracles, including target mass outside the proposal support and forced rejection. Positive-temperature MTP must preserve the filtered target distribution. |
| Tool transitions | Required/allowed strict functions complete with valid arguments and correlated results. No provisional call is executable before successful completion. |
| Cost | Paired frozen LIE/Gufo configurations, physical input, PP/TG/TTFT, repetitions, allocations/resources and filter settings. Record overhead even when throughput declines. |
| Closure | Fresh coordinated lease, actual exit codes and failures, unchanged model stats, artifact verification and all owned processes retired with the named router restored. |

The fixed-output oracle remains unchanged: natural EOS before the declared TG
budget is a failed sample even if the native child exits 0. Live progress does
not replace completion. Equal seeds do not require equal AR and speculative
token streams: speculative acceptance uses additional random draws. Numerical
and quality claims require distribution evidence, not only sampler metadata.

The pinned provider's `qwen38_flash_next/mtp_sampling.hpp` uses the filtered
target mass for acceptance and the positive residual for correction; the
engine retains that correction as the next anchor. This source audit and local
header compilation do not qualify the newly exposed filters on original weights.

CPU protocol checks are recorded in the
[supervisor receipt](../validation/ds4-sampling-point-supervisor-2026-10-04.json);
the [native client receipt](../validation/ds4-sampling-controls-2026-10-04.json)
records parser, ABI, retained options and report compatibility. The integrated
`1bff953` runtime completes two seeded PP1500/TG128 sessions for greedy AR and
the declared profile in AR/MTP on `.161`
([selected GPU evidence](../validation/c17-sampling-point-gpu-2026-10-05.json)).
That proves selected fixed-output/replay and actual MTP draft/acceptance controls.
Independent probability/filter/tool-transition and matched-cost gates above
remain open; the recorded source does not qualify later binaries automatically.
