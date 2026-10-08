<!-- SPDX-License-Identifier: MIT -->
# Q2/UD bounded phase profiles

These are diagnostic GPU kernel times, not unprofiled throughput. The installed
rocprofv3 traced the same physical 2048-token input and 16 emitted tokens (15
decode steps), C1, MTP off, on `.157`. A complete warm session preceded the
measured session. Explicit GPU markers exclude loading, semantic checks,
warmup, allocation and markers from both phases. Each arm's two semantic
frontiers, input IDs, 2K prefill frontier and first 16 output IDs match its
retained unprofiled baseline exactly (11 checks per arm).

| Prefill kernel category | Q2 ms | UD ms |
|---|---:|---:|
| Routed down projection | 1382.876 | 179.954 |
| Routed gate/up projection | 531.585 | 241.965 |
| hipBLASLt GEMM | 478.911 | 4.051 |
| Explicit activation packing | 119.826 | 2.496 |
| Other kernels | 850.929 | 817.885 |
| **All kernels** | **3364.126** | **1246.350** |
| Span between first/last kernel | 3370.774 | 1250.886 |
| Uncovered inter-kernel span | 6.649 | 4.536 |

Q2_K down accounts for 41.1% of Q2 prefill kernel time. IQ2_XXS gate/up
accounts for 15.8%. Generic MMQ already uses matrix instructions; the missing
route is the specialized compacted F16 pipeline used by UD, not matrix hardware
in general. The small inter-kernel gaps do not support host scheduling as the
main explanation for this prefill loss. They say nothing about DMA outside
kernel intervals or complete device utilization.

| Decode kernel category, 15 steps | Q2 ms | UD ms |
|---|---:|---:|
| SmallGemm F16 | 232.268 (4170 calls) | 28.445 (1260 calls) |
| Q8 dense GEMV, unfused | 247.900 | 272.333 |
| Routed gate/up | 63.135 | 67.849 |
| Routed down | 34.968 | 40.811 |
| Specialized Q8 HC down | absent | 25.206 |
| **All kernels** | **673.491** | **549.378** |
| Span between first/last kernel | 754.491 | 635.527 |
| Uncovered inter-kernel span | 80.999 | 86.150 |

Decode categories above are selected costs, not an exhaustive sum. The routed
Q2 experts collectively take less kernel time in this trace than the UD experts.
The large relative F16 dense cost requires a separate optimization. The two
additional grid geometries correspond to 320 output rows (1455 calls,
152.960 ms) and 10240 output rows (1455 calls, 50.979 ms). The source's
four-rows-per-block SmallGemm launch and HC matrix shapes identify these as HC
down/up. Their 203.940 ms total accounts for almost the entire F16 delta;
UD's other F16 grid geometries cost essentially the same as Q2's. Q2's F16 HC
projections miss UD's Q8 specialized path; the PP wide mixer also requires Q8
HC down. This is not evidence that all of that time can be eliminated.

## Validation and retained evidence

- `q2-profile-host-r1`: six Debug and six ASan/UBSan CTests pass on `.157`,
  including seven process-supervision and three profile-accounting cases.
- `q2-profile-r1`: diagnostic succeeds; 24 collected artifacts verified.
  Trace SHA-256 `b0c6b94ad9c331a356f83e056fed567b424fba455a35485649cc94690f67b3e9`.
- `q2-ud-profile-r1`: diagnostic succeeds; 24 collected artifacts verified.
  Trace SHA-256 `c3e60bf3c464d9b3b5e8152863b3b7483862775e2410043a7bc6216134f30340`.

`config/q2-profiling.json` retains nanosecond aggregates. Each raw arm includes
`profile-phases.json` with full kernel names/counts and the original SQLite
trace. `tools/analyze-q2-profile.py` recomputes per-phase totals and interval
unions independently from the database. Union and sum are kept separate even
though these measured streams show no overlapping kernel intervals.

The runner supervises the owned process session/group, preserves actual exit
codes, verifies child retirement and acquires four nonblocking leases before
every remote HIP build/GPU run. It cannot claim universal device exclusivity
from readable process observations. No profiler timing replaces the retained
unprofiled comparison in [Q2-RESULTS.md](Q2-RESULTS.md).

## Selected experiment

Extend only the Q2_K PP down projection to compacted WMMA. Keep the original
encoded weights and the 640 logical / 768 stored K geometry. The kernel reads
the existing F32 slot buffer and splits each activation into F16 high plus a
scaled F16 residual inside LDS. Two F32 WMMA accumulations combine at the end.
No persistent dequantized weight cache or new session allocation is introduced.
Weights are reconstructed in F32 and rounded once to F16. This arithmetic still
differs from the original Q8-activation MMQ, so operator checks do not replace
the saved-model-frontier gates in `config/q2-down-wmma-protocol.json`.

| Operator arm | Outcome | Relative RMS, first/max affected case |
|---|---|---:|
| `q2-down-wmma-operators-r1` | FAIL; single F16 input, F16 affine | 0.00587014 |
| `q2-down-wmma-operators-r2` | FAIL; F32 affine before weight rounding | 0.00586853 |
| `q2-down-wmma-operators-r3` | FAIL; diagnostic confirms input rounding | 0.00586853 |
| `q2-down-wmma-operators-r4` | PASS; compensated input | 0.000363416 |

In r3 the independent rounded-operand formula matches GPU output to RMS
0.00000186839, while rounding only the activation yields RMS 0.00585618 against
the original operands. This isolates the rejected route's main error. The
unchanged threshold is RMS and peak-scaled error <= 0.002. R4 covers tiles
16/48/64, experts 0/17/511, logical/storage tails, ordinary and small inputs,
output guards, the existing IQ2/Q2 operators and exhaustive finite F16 widening.
All failures remain in evidence. The following [model and unprofiled
comparison](Q2-DOWN-EXPERIMENT.md) found a 34–64% PP gain but rejected the
variant because its saved-frontier KL exceeded the unchanged limit. The active
runtime has been restored.
