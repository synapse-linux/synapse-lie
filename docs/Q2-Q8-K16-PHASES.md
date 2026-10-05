<!-- SPDX-License-Identifier: MIT -->
# Ordered K16 phases in wide Q8 dense prefill

One new candidate starts from the measured IQ2 raw-prefetch composition at
1505.152258 PP / 25.15493858 TG. It targets the wide Q8 dense plain, SSM and
attention specializations with BM256/BN128/BK2/WM8/WN1. For each K32 block,
all independent outputs consume the low K16 product, followed by their high
K16 product. Every individual accumulator preserves the original low/high
and K32 sequence, operands and F32 WMMA arithmetic.

The initial hypothesis was shorter simultaneous half-fragment lifetimes and
more independent WMMA operations between dependent updates. Compiled peak
VGPR does not fall, so only scheduling effects remain to measure. The saved
profile attributes 293.725 milliseconds (21.183% of GPU kernel time) to Q8
weight/F16 activation dense projections; it is target evidence, not candidate
performance. No cache, table, allocation, new stream or dispatch geometry is
introduced. F16 weight paths and all routed/decode paths remain unchanged.
Public ABI, state and metrics contracts are unchanged.

Matched production assembly reuses the saved parent without a rebuild. It
verifies three changed bodies and 154 other bodies exact, including the retained
IQ2 improvement. All three retain LDS49152, zero private bytes, next-free
VGPR241 and64 WMMA instructions. Static instructions change as follows:

| Projection | Parent instructions | New instructions |
| --- | ---: | ---: |
| Plain |3198 |3201 |
| SSM |4027 |4030 |
| Attention |14400 |14403 |

There is no static instruction/register saving, occupancy claim or inferred
speedup. Changes in dependency distance and LDS read scheduling require GPU
measurements. Source arithmetic and each output's accumulation order stay fixed.

The new fixture compares66 guarded complete output pairs across three distinct
weight rotations. Five plain ragged token counts1/15/17/129/1025 use m257/k96,
exercising token/row edges and an odd K32 count inside BK2. SSM tests1024/1025/
1057/2048 rows with m16384/k2560 and original boundary convolution. Attention
tests1025/2048 rows with m13312/k2560, complete F32 query/gate outputs, F16
key/value outputs, nontrivial gamma and the original norm/RoPE epilogue.

SSM raw projection intentionally leaves interior convolved cells unpublished.
Their expected poison bytes are verified separately from required raw cells
and complete convolved output. Missing/nonfinite required output, unexpected
unused-cell writes and any byte difference preserve arrays and timings. Guard
or runtime faults stop device work. All inputs, gamma, position, original Q8
weights, convolution parameters and history are checked immutable at completion.
Initialization, poison, launches and readback share one nonblocking stream.

Three rotated weights occupy133693440 /50135040 /108625920 bytes for SSM/plain/
attention, above32MiB MALL. Forty-two alternating observations include two
warmups and five measurements per arm/shape. Device event timing excludes
allocations/uploads and includes only the projection plus its production
epilogue, not an entire model or MoE cycle.

The original model is always measured after any safe component verdict, using
exact2048/tg128,127 timed decode calls, capacity9216/chunk2048,MTP off,one warmup
and three measured sessions with15-second waits outside timers. The saved
fixed Q2 PP1443.672867 /TG25.09595499, fixed UD PP1685.777092 /TG24.34174251,
and best IQ2 parent PP1505.152258 /TG25.15493858 are reused without rebuilding or
rerunning old controls or component cohorts. No curve, cleanup, dependency
installation, tuning or deployment is admitted.

Local generation, production/fixture device compilation, fixture host
compilation,91 guards and new-file formatting pass. Three exploratory tooling
failures are preserved: a display reader used the wrong field name; a shared
formatter was invoked from the wrong directory; a static selector incorrectly
matched the first template parameter. Corrected reader/working directory/
selector checks pass. No failed GPU, model or remote build is inferred from
those preparation failures. The shared formatter still records exit1 on nine
unchanged inherited files. No qualified source or previous report is rewritten.

The plan freezes40 fixtures,four manifests and all1025 provider files. Local
staging verifies the complete component capsule and stops before SSH. New .157 host
qualification passes25/25 Debug and25/25 ASan/UBSan: six commands zero,seven
artifacts and40 frozen files verify, with neither model nor GPU access. Fresh
coordinated admission remains required before remote GPU build/run. At initial
preparation no new component or original model has run; compile/host checks are
not numerical acceptance, independent task quality or performance evidence.

[Frozen plan](../config/q2-q8-k16-phases-plan.json),
[source inventory](../config/q2-q8-k16-phases-source.json),
[static evidence](../config/q2-q8-k16-phases-static.json),
[staging evidence](../config/q2-q8-k16-phases-staging-results.json),
[patch](../experiments/q2-q8-k16-phases.patch),
[literal parent](../experiments/q2-q8-k16-phases-control.inc),
[new fixture](../tests/q2_q8_k16_phases.hip).
