<!-- SPDX-License-Identifier: MIT -->
# HC160 algorithmic instruction reduction

The owner requests retaining the160-row tile while reducing redundant work.
The original HC160x128 experiment stages fewer logical input bytes, but its
first GPU median1187.047us does not improve on HC64x128 at1175.600us.
This follow-up keeps160x128/BK2/WM5/WN4,640threads and the same F16 data.
No output accumulator, WMMA order, final F32 addition, LDS layout or allocation
changes. Source derives from the independently pinned official Gufo tree;
[the geometry report](Q2-HC-DOWN-PHASED.md) records the preceding variants.

The dispatch already restricts this specialization to M320/K10240. First,
exposing those fixed dimensions to the compiler removes generic indexing and
bounds work. This alone changes the main loop only136 to135 static instructions.
Second, inactive load lanes are initialized once before the K loop. Their
validity is invariant across all160 stages, so repeatedly zeroing the same
fragments is unnecessary. Active lanes still replace all four uint4 chunks;
invalid token lanes retain zero and use the existing masked output path.
The prefetch guard prevents access past the last K stage. Other shapes retain
the original kernel specialization and their row/K tail handling.

| Static compiler result | Original HC160 | Fixed M/K only | Invariant fetch |
| --- | ---: | ---: | ---: |
| Whole kernel instructions | 1061 | 939 | 921 |
| Instructions in main-loop blocks | 136 | 135 | 116 |
| Main-loop WMMA instructions | 16 | 16 | 16 |
| Main-loop global vector loads | 8 | 8 | 8 |
| Main-loop LDS vector reads | 32 | 32 | 32 |
| VGPR | 251 | 249 | 249 |
| SGPR | 20 | 13 | 16 |
| LDS bytes | 46080 | 46080 | 46080 |
| Private scratch bytes | 0 | 0 | 0 |

These are emitted static instructions, including branch paths and delay/wait
instructions; they are not measured dynamic execution counts. Loop blocks are
identified by clang's `in Loop:` annotations. The invariant version eliminates
repeated zero moves, but its loop also has17 wait instructions versus15.
Instruction counts alone do not measure critical-path latency, memory stalls
or useful hardware occupancy. The unchanged640-thread block and46,080-byte
LDS footprint remain possible constraints, not diagnosed bottlenecks.

Both variants compile device-only with the measured flags. All145 unrelated
kernel bodies remain identical after label/comment/whitespace normalization,
and patches reconstruct all1019 source files exactly. The fixed-dimensions-only
variant has no GPU timing; only the complete invariant-fetch candidate is run.

- [Generator](../tools/prepare-q2-hc-row160-fixed.py) (`--hoist-zero`).
- [Source identity](../config/q2-hc-row160-loads-source.json) and
  [patch](../experiments/q2-hc-row160-loads.patch).
- [Fixed-shape static report](../config/q2-hc-row160-fixed-static.json) and
  [invariant-fetch static report](../config/q2-hc-row160-loads-static.json).
- [First GPU report](../config/q2-hc-row160-loads-results.json),
  [CSV](figures/q2-hc-row160-loads.csv),
  [SVG](figures/q2-hc-row160-loads.svg),
  [PNG](figures/q2-hc-row160-loads.png).

The unchanged fixture times five samples of16 launches per shape, n2048,
16 rotating hipMalloc weight matrices totaling100MiB; input narrowing is
outside the timer. The plain HC-up projection remains an unchanged control.
All22 independent FP64 checks, complete-output hashes and44 sampled coordinate/
value files are retained. Historical four independent numerical failures keep
actual exit1; agreement between variants does not turn them into passes.
The launcher restricts this candidate to HC components. Updated host guards
pass16/16 Debug and16/16 ASan/UBSan on `.157`. CPU98 C inclusive, exposed GPU
thresholds and the persistent fan82 curve apply to every fresh four-lease arm.

## GPU outcome

| Cohort | Original HC160 us | Invariant fetch us | Change in time |
| --- | ---: | ---: | ---: |
| First comparison | 1187.047 | 1232.229 | +3.806% |
| Repeat | 1216.704 | 1223.279 | +0.540% |

Both cohorts preserve every full output hash and all44 saved coordinate/value
files. All four arms retain the same independent failures and exits0/0/1.
The second comparison has strongly overlapping ranges and the unchanged up
control moves+0.80%; this does not establish a speed benefit or a stable small
regression. The algorithmic reduction is real in the compiler output, but it
does not justify model integration. No full-model arm is launched or promoted.
Fewer instructions are not sufficient evidence that the limiting execution
path has become shorter. Whether memory dependencies, LDS access or the larger
block's scheduling limits throughput needs a separate measured hypothesis.

[Repeated GPU report](../config/q2-hc-row160-loads-repeat-results.json),
[CSV](figures/q2-hc-row160-loads-repeat.csv),
[SVG](figures/q2-hc-row160-loads-repeat.svg) and
[PNG](figures/q2-hc-row160-loads-repeat.png) retain every sample.

The complete HC scheduling window collects seven GPU arms and four host cohorts,
336 GPU artifacts plus28 host artifacts. Final closure at14:17:19 UTC verifies
56 recorded processes and their owned groups absent, KFD empty and all original
four lease identities acquired EX|NB then released. No restart is queued.
The durable remote/shared registry and main-repository run receipt preserve the
handover. Runtime observations remain limited to readable processes/devices.
