<!-- SPDX-License-Identifier: MIT -->
# Alternating SSM activation buffers

## Runtime campaign prepared after row-group completion

The first row-group campaign is now complete and released. Its model result
1576.943074 PP does not replace saved1580.226725. The follow-up runtime patch
is applied and this candidate has a separate frozen90-fixture/ten-manifest
plan, with six integrated launcher checks,142 existing guards and11 analysis
checks passing. Both actual-runtime source archives verify1027 provider files.
Fresh .157 checks at22:10:24UTC confirm Core closure and continued non-use;
host checks are running. Component and model inference remain unmeasured and
require fresh GPU admission. Earlier preparation sections below are historical.

[Frozen campaign](../config/q2-ssm-pingpong-plan.json),
[applied runtime receipt](../config/q2-ssm-followup-runtime-applied.json),
[archive staging](../config/q2-ssm-pingpong-staging.json).

Host checks finish at22:11:07UTC:27/27 Debug and27/27 ASan/UBSan, six
commands exit0 and seven artifacts verify. All90 fixture and ten manifest
bindings pass. These checks are CPU fixtures; GPU admission remains pending.
[Host report](../config/q2-ssm-pingpong-host-results.json).

This local candidate follows the [compact-LDS SSM experiment](Q2-SSM-COMPACT-LDS.md)
and retains both sources separately. It addresses that candidate's doubled
block barriers without increasing the32768-byte shared allocation. It has no
GPU numerical, memory-safety or throughput result. The measured original
exact2048/tg128 result remains1580.226725 PP /25.10411864 TG.

With BK1/WM8/WN1, each wave produces and consumes exactly its own32 weight
rows. The weight stage therefore needs16384 bytes and a wave-local retirement
barrier. Activations are different: the first four waves populate128 rows,
and all eight waves consume them. Two8192-byte activation slots fit alongside
the weights, using the same32768 bytes already needed by the convolution
transpose.

Each K stage writes its weight rows and the alternating activation slot, then
publishes them through a block barrier. After matrix reads, a wave barrier
protects reuse of that wave's weights. The next activation write uses the
other slot. Reusing slot k for stage k+2 requires passing publication barrier
k+1; every wave must have finished reading k before committing k+1. One final
block barrier remains mandatory before the transpose reuses other waves'
weight/activation bytes. Removing it would permit an early wave to overwrite
data still read by another wave.

| Local property | Original SSM | Compact LDS | Alternating slots |
| --- | ---: | ---: | ---: |
| Shared bytes/block | 49152 | 32768 | 32768 |
| Compiler-reported VGPRs | 222 | 207 | 212 |
| Scratch bytes/thread | 0 | 0 | 0 |
| Compiler occupancy field | 4 | 7 | 7 |
| Static instructions | 4027 | 4120 | 4131 |
| Source block barriers in matrix path | 80 | 160 | 81 |
| Added source wave barriers | 0 | 0 | 80 |

The81 count includes80 stage-publication barriers and the final retirement
barrier. Wave barriers, slot addressing and compiler scheduling still have
costs; these source/static counts do not establish a speedup or measured
active-wave occupancy. Launch count, block grid, arithmetic helpers, K16
order, convolution windows, history boundary kernel and scalar decode remain
unchanged. No model allocation, host scheduling callback or stream is added.

## Ownership checks and remaining qualification

The integer version model runs129 schedules over80 stages/eight waves,
checking82560 complete stage reads and165120 events. Every read observes its
expected A/B version. A deliberately unsafe one-slot control detects an
incorrect activation version at stage0. A separate negative layout case exposes2048 bytes where an
early transpose can overwrite another wave's live weights if the final block
barrier is removed. These checks validate the modeled dependencies; they do
not prove compiler/device memory ordering or GPU correctness.

Local source reconstruction and full1027-file inventories verify. All161
other kernels match saved instructions, operands and resources; the saved
parent is not rebuilt. Host/device syntax passes against the unchanged compact
SSM fixture, preparing30 complete output pairs,60 sampled FP64 checks,14
timing records and two HIP resource-limit records. Only2048 is timed; the
five numerical shapes, independent formula and limits remain unchanged.
Safe numeric rejection retains timing, while guards/write/runtime faults stop.
The fixture's event names identify the compact-LDS family; the source manifest
and private run identity must distinguish this variant from its predecessor.

The initial source manifest accidentally retained its predecessor's stage-byte
and barrier counts. The initial JSON and correction receipt are preserved;
current versus inherited layout proofs are now separate. No provider code
or assembly changed during that metadata correction.

The frozen SSM row-group campaign remains first, with its88 fixtures, five
manifests and helper unchanged. This follow-up has no remote launcher wiring
or GPU admission. Actual Core-19 CPU closure and a fresh .157 handover remain
required. The fixed Q2/UD model comparison, deferred Q4 and full-curve gate
remain unchanged.

[Source and synchronization model](../config/q2-ssm-pingpong-source.json),
[assembly/fixture audit](../config/q2-ssm-pingpong-static.json),
[shared fixture](../tests/q2_ssm_compact_lds.hip).
Actual local commands and the preserved metadata correction are under
`evidence/q2-ssm-pingpong-preparation/`.
