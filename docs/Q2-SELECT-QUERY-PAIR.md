<!-- SPDX-License-Identifier: MIT -->

The single-query LDS trial below completes on .157 at18:28:44 UTC,
2026-10-07. All48 complete score/mask comparisons and48 independent FP64/
CPU top-k checks pass; actual exit0. Completed score-plus-mark wall means
over the five alternating pairs are:

| Same internal selector slice | Original, us | Query LDS, us | Latency change |
|---|---:|---:|---:|
| Last full32K slice | 1047.9396 | 1700.8782 | +62.3069% |
| Last full128K slice | 2868.9106 | 5489.4646 | +91.3432% |
| Last128K tail slice | 2260.2874 | 4217.1506 | +86.5759% |

All individual samples and valid HIP-event durations remain in
[`q2-select-query-lds-results.json`](../config/q2-select-query-lds-results.json).
The candidate is slower and is not composed into a model. Collection verifies
35 artifacts before18:32:55.912809 release6b0d4d02; independent closure verifies
the epoch registry, empty KFD, five free leases and unchanged model stats.

The next isolated candidate changes only key layout to8-key by8-feature tiles.
An exact uint4 packing pass is included in the complete score-plus-mark timer.
Original FP32 queries, F16 key bits and score/reduction/top-k order remain.
The synthetic fixture checks every packed half and unused sentinel, along with
the same full outputs and independent checks. Its scratch is8560640 bytes;
no persistent executor buffer or model dispatch is changed. Static compilation
keeps115VGPR/84SGPR and zero LDS/scratch for scoring, matching the original
resource counts. Invoked original score/mark functions are byte-exact to the
retained model. Source/static manifests are
`config/q2-select-key-tile-{source,static}.json`. Compilation and the .157 CPU
runner fixture have passed; GPU execution still requires fresh admission.

A separate single-query LDS component is prepared on2026-10-07. It retains
one original score per thread and cooperatively stages the same4x128 FP32
query values into2048bytes of workgroup storage. Every four-FMA partial,
descending reduction, head sum and original top-k remain. Uniform empty-block
returns precede the barrier; partial key blocks wait before inactive lanes exit.
This is distinct from the rejected two/four-query key-reuse experiments below.
The fixture uses the same original32K/128K internal selector slices and complete
score-plus-mark checks. No model input/chunk, attention precision, persistent
buffer or production dispatch changes. No model performance claim follows.

Local compilation reports142VGPR/16SGPR/2048LDS/zero scratch versus the native
control115VGPR/84SGPR/zero LDS/scratch. Both invoked control kernels, score
and mark, are byte-exact to the saved native server. The broader fixture has
153/165 common functions byte-exact;12 unused functions differ, with identical
sizes/resources. Do not claim all device code identical. Source and static
bindings are `config/q2-select-query-lds-{source,static}.json`; GPU execution
requires fresh coordinated admission. More registers may offset saved reads.

# Exact selector key reuse across two queries

This private component follows the owner's new decode/full-prefill-through-128K
priority. Fixed-point UD parity remains paused. It does not modify a production
provider, prompt, prefill chunk, attention precision, ranking rule or context
capacity. It is distinct from upstream's rejected paired-lane score calculation:
one thread here still computes a complete original score, for two query rows.

The draft loads one F16 key and reuses it for two independent FP32 queries.
Every query retains the original four-FMA partials, descending32-partial tree,
head order, ReLU and final sum. Each row's causal bound still controls its store;
an odd last query and the budget boundary remain separate cases. The original
SelectMarkKernel consumes scores unchanged, with lower-index tie ordering.

The compiler preserves all164 original device bodies. The selected draft uses
184 descriptor VGPRs, versus115 in the control, and zero scratch/LDS bytes.
This register cost is a tradeoff to measure, not a gain. Five other compiler
probes are retained: implicit packed keys do not reduce allocation, a rolled
query loop still uses185 VGPRs, explicit bitpack/compiler barriers introduce
3604 scratch bytes, and head-interleaved versions use173 VGPRs plus32 scratch
bytes. These are static observations, not measured rejections. The GPU trial
uses only the zero-scratch original query-pair draft.
[Static audit](../config/q2-select-query-pair-static.json).

The fixture times the complete score plus mark operation, with two warmups
and five measured repetitions, alternating control/candidate order. Every timed
score and mask is checked before overwrite: full-byte comparison, finite valid
scores, unchanged inactive score sentinels, mask cardinality and causal tails,
device guards and immutable inputs. Sampled FP64 dots retain the2e-5 thresholds;
CPU rank/tie checks consume sampled complete score rows. Finite disagreements
retain timings and their actual exit. Invalid outputs or device faults stop.

| Component case | Query rows | Chunk start | First query in chunk |
|---|---:|---:|---:|
| Last complete chunk of saved32K prefix | 512 | 28672 | 1536 |
| Last complete chunk of saved128K prefix | 512 | 126976 | 1536 |
| Last selector slice of saved128K final tail | 365 | 129024 | 1536 |

These are actual selector subdivisions of the original2048-token prefill
chunks. The final128K input is still130925 tokens:63 complete chunks and1901
final tokens. The365 rows above are the final slice of those1901, not a new
model input or an intermediate shortened prefill. Capacity133760, padded score
pitch33440,1045 mask words, ratio4 and512 selected blocks match the executor.
Additional cases cover one/three query rows, small inputs and zero-score ties
across the non-sparse boundary. Synthetic query/key values check the component;
they provide no original-weight model throughput or quality result.

No saved Q2/UD control, Q4, full curve or model run is scheduled by this plan.
Collect and release the .157 window before analysis. A component win must still
survive a separate model trial on the original saved requests.

## Completed component — 2026-10-06 UTC

All48 score/mask pairs are byte-exact and all48 independent score/top-k reports
pass. The measured operation is slower; no model trial or adoption follows.

| Shape | Original µs | Query pair µs | Time change |
|---|---:|---:|---:|
| Last full32K selector slice | 968.4734 | 1294.9370 | +33.709% |
| Last full128K selector slice | 2359.0504 | 4242.8964 | +79.856% |
| Original128K final tail slice | 2172.4586 | 3387.0920 | +55.911% |

These are arithmetic means of the five saved wall samples, not model token
rates. The32K observations are noisy; both128K candidate ranges are entirely
slower than their control ranges. All42 zero HIP event durations remain invalid.
[Full samples and validation](../config/q2-select-query-pair-results.json).

HOST39+39 passes; component exits0,0,0. Four artifacts collect before release
21:47:04.780034 UTC /f40710f4. All1755 identities and1402 groups retire, KFD is
empty, original leases/models are unchanged, mirrors match and Core receives
closure before analysis. The register pressure tradeoff did not pay here.
