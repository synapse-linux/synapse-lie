<!-- SPDX-License-Identifier: MIT -->
# HC down operand lifetimes

This experiment tests shorter-lived operand fragments in the existing original
F16 HC down projection, M320/K10240 at n>=96. It derives from the retained
HC-up-chains source. The goal remains complete Q2/UD parity; this component
cannot by itself qualify model performance, quality or deep-context serving.

The scaled-input diagnostic attributes 134.125 ms of pp2048 kernel time to
96 calls of this HC specialization. Earlier geometry changes, extra wave
chains and a single accumulator did not give a retained model improvement.
This candidate keeps geometry, weight representation and both accumulators.

For each original K32 block, the reference loads both K16 operand halves,
then interleaves low/high WMMA updates. The candidate loads and consumes the
low half before loading and consuming the high half. A compiler scheduling
barrier separates phases. Each output's low sum, high sum and final F32
addition retain their original order; independent dots may be scheduled
differently. No device barrier, buffer, model conversion or thread is added.

| Compiler resource | Retained | Phased |
| --- | ---: | ---: |
| VGPR | 251 | 155 |
| SGPR | 22 | 22 |
| LDS bytes | 24576 | 24576 |
| Private scratch bytes | 0 | 0 |

The [generator](../tools/prepare-q2-hc-down-phased.py),
[source identity](../config/q2-hc-down-phased-source.json),
[patch](../experiments/q2-hc-down-phased.patch) and
[static checks](../config/q2-hc-down-phased-static.json) preserve official Gufo
pin f783fedb9bea2ec7de941f6da4e02f4a4596b29e and the measured base. The patch
reconstructs all 1019 files exactly. Local device-only compilation changes just
the intended instruction body; the other 145 of 146 remain identical after
label/comment/whitespace normalization. These checks execute no GPU workload.

The existing HC fixture retains all 22 sampled FP64 operators, including
ordinary/tiny/alternating inputs, 32/95/96/97/127/128/129/2048-token boundaries,
ragged rows/K and complete finite/output-guard checks. All full output hashes
and sampled coordinate/value files are compared between freshly built arms.
Independent relative-RMS and error/peak limits remain 2e-5. Known failures
retain exit1 while exploratory timing completes; they are never waived.

The timing scope is one GEMM, five samples of sixteen launches, n2048 and
sixteen rotating weight matrices totaling 100 MiB. The plain HC up projection
is the unchanged control. Weights use hipMalloc, matching the actual HC upload
allocation API. Narrowing is outside this timer and unchanged; a component
gain must survive a separately admitted full-model comparison.

The new source is restricted to `hc-pp-operators` and `hc-pp-bench` in the
launcher. `.157` host checks pass16/16 Debug and16/16 ASan/UBSan, including
refusal of model/profile/Terminal-Bench dispatch. The admitted GPU window uses
fresh original four leases for each arm, the owner's fan82 curve, CPU98 C
inclusive and exposed GPU thresholds. No full-model run is queued.

## Measured scheduling and geometry results

All four arms run on `.157` under the same fan82 policy, with configuration,
build and fixture exits0/0/1. Each completes all timing samples and preserves
the same four independent operator failures (small down batches32/95 and
ragged M319/K10208); all22 full output hashes and44 saved coordinate/value
files agree exactly. These are exploratory timings, not numerical acceptance.

| Arm | Down median us | Change in down time | Unchanged up median us |
| --- | ---: | ---: | ---: |
| Retained HC64x128 | 1175.600 | reference | 951.939 |
| Phased / compiler boundaries | 1871.025 | +59.15% | 946.162 |
| Phased / free schedule | 1170.006 | -0.48% | 961.666 |
| HC160x128 / 640 threads | 1187.047 | +0.97% | 946.218 |

The phase barriers sharply regress despite reducing VGPR251 to155. Removing
them restores251VGPR and overlapping timing; neither variant is promoted.
This is consistent with a loss of useful instruction overlap, but no hardware
counter measurement establishes the exact limiting resource.

The160-row tile keeps each wave's32x32 output and two original K16 sums.
Logical input staging at n2048 falls200 to80MiB; weight staging stays100MiB.
This logical reduction does not measure physical DRAM traffic or imply speed.
The tile uses20waves/640threads and46080bytes LDS instead of8waves/256threads
and24576bytes; the original implementation gives no measured gain.
At the owner's request,160 rows remain an experimental geometry for algorithmic
instruction reduction; their first weak timing does not terminate that analysis.

Every sample is retained in the following reports and standalone charts:

- [Phase barriers JSON](../config/q2-hc-down-phased-results.json),
  [CSV](figures/q2-hc-down-phased.csv), [SVG](figures/q2-hc-down-phased.svg).
- [Free schedule JSON](../config/q2-hc-down-phased-free-results.json),
  [CSV](figures/q2-hc-down-phased-free.csv), [SVG](figures/q2-hc-down-phased-free.svg).
- [HC160 JSON](../config/q2-hc-row160-wide-results.json),
  [CSV](figures/q2-hc-row160-wide.csv), [SVG](figures/q2-hc-row160-wide.svg).

The separate K32-boundary experiment compiles locally (exit0), but receives no
GPU admission or performance verdict: the owner clarifies the current priority
as fewer algorithmic instructions while retaining the160-row tile.
