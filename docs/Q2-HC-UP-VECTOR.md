<!-- SPDX-License-Identifier: MIT -->
# Scalar F16 HC up vector loads

The measured packed Q2 decode profile assigns 50.793 ms across 1,455
`SmallGemmKernel<F16, 1>` HC up calls in fifteen decode steps, or 34.910 µs
per call. Its 10,240×320 original-F16 matrix is served by the generic scalar
kernel. The [profile grid split](../config/q2-hc-up-decode-profile.json)
separates these calls from two other F16 shapes; it is diagnostic kernel time,
not unprofiled model wall time.

This experiment adds one guarded `SmallGemm` dispatch for F16, one token,
`m=10240`, `k=320`. One wave owns each output row and loads four half weights
and four F32 activations with aligned `uint2`/`float4` accesses. The third
128-value group uses lanes 0–15 only. Row reduction, output type, original
weights, allocation and all other shapes retain the prior route. The source
derives only from this worktree's measured [HC up fused](Q2-HC-UP-FUSION.md)
checkpoint at the independently fetched official Gufo pin; it is an isolated
HIP numerical port, not a change to LIE's C17 core or reactive scheduler.

Two variants were measured. The first let fast-math reassociate the vector
products. It passed the independent FP64 oracle, yet 7,350 of 10,240 changed
operator values differed from the generic result by up to 1.1921e-7. Across
127 decode steps, six final-logit buffers differed by up to 1.1721, with
relative L2 up to 0.08536. All generated tokens remained the same and maximum
KL was 4.62e-6. This is a real numerical drift, not a false test flag or
proof of equal quality. The variant is retained as performance evidence only.

The second variant uses explicit round-to-nearest FMA operations in the
generic kernel's observed component order 0, 1, 2, 3, with the same aligned
loads. Static gfx1151 compilation uses 19 VGPR, 8 SGPR, no private memory and
no LDS for this kernel. All eleven complete synthetic F32 buffers are
byte-exact against the measured reference, and each independent FP64 check
passes its unchanged 2e-5 relative-RMS/error-over-peak limit. All twelve
saved model F32 frontiers and all token files match the retained packed Q2
reference byte for byte; nine within-arm replay checks pass. No numerical
threshold was relaxed. Source identities and static compiler resources are
recorded in the [exact source](../config/q2-hc-up-vec-exact-source.json) and
[static receipt](../config/q2-hc-up-vec-exact-static.json). The faster but
drifting variant has its own [source](../config/q2-hc-up-vec-source.json),
[static receipt](../config/q2-hc-up-vec-static.json) and
[micro report](../config/q2-hc-up-vec-micro.json).

| `.157` C1 arm | HC up µs/launch | Prefill tok/s | Decode steps/s |
| --- | ---: | ---: | ---: |
| Q2 HC fused reference | 34.474 | 1287.188 | 22.948 |
| Q2 vector, drift retained | 30.432 | 1289.407 | 23.216 |
| Q2 vector, byte-exact | **29.919** | 1287.119 | **23.214** |
| Fresh UD | — | **1682.768** | **24.301** |

The HC up component speeds up 15.22% with the exact variant. The full model's
decode improves 1.16% over its same-window Q2 reference; prefill is unchanged
within the three-sample spread. The exact Q2 variant still trails fresh UD by
23.51% in prefill and 4.47% in decode. The experiment does not establish
long-context behavior, concurrency, sustained serving or parity with UD. All
model arms used one warmup plus three measured C1 pp2048/tg128 sessions, 15 s
idle outside timing, original model files and a full MMQ rebuild. All command
exits were zero and all collected artifacts hash verified. The peak observed
GPU/CPU temperatures for the exact model arm were 80/91.625 C, below the
unchanged 98 C inclusive Q2 guard. The [full report](../config/q2-hc-up-vector-results.json)
keeps every sample, duration, replay, numerical comparison and model identity;
the [exact micro report](../config/q2-hc-up-vec-exact-micro.json) retains the
five 128-launch samples. [SVG](figures/q2-hc-up-vector.svg),
[PNG](figures/q2-hc-up-vector.png) and [CSV](figures/q2-hc-up-vector.csv)
show the complete performance comparison.

The first benchmark attempt failed in fixture compilation because `matrix_bytes`
was `constexpr` after making `m` runtime-selected. Its exit code and full build
log remain in `evidence/q2-hc-up-vec-reference-r1`; the corrected fixture
passes syntax check and subsequent GPU runs. No failed command is reclassified
as a completed performance result. Both variants are isolated patches against
the HC up fused source, with preparation scripts under `tools/` and original
source trees retained outside `/tmp`.

The final `.157` host capsule passes 10/10 Debug and 10/10 ASan/UBSan tests,
including the remote variant guards; all six commands exit zero and seven
artifacts are hash verified. The [window release receipt](../config/q2-hc-vector-window-release.json)
records retirement of all 15 Q2-owned runners and 55 commands, empty KFD and
four unchanged, free EX|NB leases. It retains the one earlier fixture build
failure as a real exit code.
