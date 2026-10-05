<!-- SPDX-License-Identifier: MIT -->
# SSM projection with 128 output rows per block

This candidate starts from the retained compact IQ2 composition, measured at
1498.799455 PP / 25.16866636 TG on the original exact2048/tg128 tester. It does
not include the rejected Q8 lookup or selectively add the earlier routed tiles.
The fixed comparison stays Q2 1443.672867 and UD 1685.777092 PP. Only the new
component and model are planned; qualified controls and old cohorts are saved
references. Performance and numerical results remain pending fresh admission.

## Mechanism and cost

The fused Q8 SSM projection changes from BM256/BN128/BK2/WM8/WN1 to
BM128/BN128/BK2/WM4/WN2. Each thread owns 64 rather than 128 F32 accumulator
values. The smaller stage needs 32 KiB, while the unchanged eight 32-token
convolution transpose planes require 36 KiB; the allocation explicitly takes
that maximum. The old block needs 48 KiB. The grid has twice as many row blocks,
with repeated activation reads and block overhead. Lower register/LDS pressure
does not prove a runtime gain.

Signed Q8 half construction, rounded scale/FMA and sequential K16 WMMA remain
unchanged. Each wave retains the same two row tiles and contiguous float4 stores;
its token groups still align to the existing 32-token fused/boundary convolution.
The dispatch dimensions, minimum1024 tokens, live raw-output mask, convolution
arithmetic and history remain unchanged. Generic dense, attention, F16-weight,
routed IQ2/Q2, W8A8 and decode dispatches are untouched. No persistent state,
public ABI/metrics contract, extra allocation, stream or table is introduced.

Local matched gfx1151 assembly preserves all 156 other kernel bodies. The new
SSM body has 2102 instructions per block versus 4027 in the saved parent,
next-free-VGPR directives 217 versus 241, LDS36864 versus49152 and zero private
scratch. These are compiler/static quantities; the row-block grid doubles and
they are not dynamic instruction counts, allocated VGPR counts or throughput.
The parent assembly is reused without recompiling its qualified source/binary.

## Required output coverage and measurements

The new fixture contains the literal retained parent dense kernel as its
numerical control. Four SSM shapes,1024/1025/1057/2048 tokens, cover the dispatch
threshold and partial token tiles. Three immutable weight rotations per shape
produce24 full raw-projection/convolution buffer comparisons. Each device
allocation has64-byte guards on both sides, and initialization, uploads,
launches and readback use one owned nonblocking stream.

Outputs begin with0xFFFFFFFF poison. Full buffers must remain byte-exact.
All required raw values and every convolution value must be written and finite;
intentionally unused raw values must stay poisoned. The raw live mask is the
existing production contract: all channels10240..16383 plus first/last three
tokens of each32-token tile and the final three prompt tokens. This implements
the saved-array diagnosis from the previous experiment without modifying its
fixture, exit1 or historical report. Missing required stores cannot pass through
matching poison values.

Only the2048-token case is timed: two warmup and five measured pairs alternate
order, each rotating three weight buffers totaling133693440 bytes above32MiB
MALL. All14 timing samples are retained. Uploads, allocations, hashing and
validation are outside GPU event timers. Numeric rejection saves full arrays
and continues timing; guard/runtime faults prevent further GPU work.

The one new original-weight model follows any safe component verdict, retaining
the original input SHA, capacity9216, chunk2048, one warmup plus three measured
sessions,128 output tokens/127 timed decode calls and15-second waits outside
timers. The saved Q2/compact-parent/UD model controls are not rebuilt or rerun.
The full context curve still waits for fixed-point parity; independent task
quality is not inferred from differential output equality.

## Preparation and provenance

Production device assembly, fixture device compilation and host syntax pass.
All85 launch-scope guards and explicit-style new-file formatting pass. The shared
provider formatter preserves exit1 for nine byte-identical inherited files.
A local wrapper initially uses a relative path from the provider directory and
exits2 before formatting; its correction and actual exits are retained.
The new `.157` CPU capsule passes25/25 Debug and25/25 ASan/UBSan CTest, all six
commands exit0,34 frozen fixtures and seven artifacts verify. Those CPU fixtures
access no model/GPU and establish no inference performance.

The initial admission helper mistakenly points PREVIOUS to this new window's
release. It exits1 before acquiring leases, writing a receipt/registry event or
starting GPU work. The corrected helper changes only that path to the saved
Q8-pair release. A separate corrected plan preserves all four manifests and34
fixture hashes; it rebinds the same qualified host capsule without a CPU rerun.
The original plan/helper/host result and failed command remain retained.

The independent provider has1025 files, with only the kernel file changed from
the retained compact source. It derives from this workstream's independently
fetched official Gufo pin `f783fedb9bea2ec7de941f6da4e02f4a4596b29e`.
Original upstream notices remain; first-party changes and fixtures are MIT.
Source/runs remain in persistent project directories. No sibling DS4 source,
model, build, cache, profile or qualified artifact is imported or mutated;
there is no cleanup, dependency installation, tuning, deployment or publication.

[Source identity](../config/q2-ssm-row128-source.json),
[static evidence](../config/q2-ssm-row128-static.json),
[corrected frozen plan](../config/q2-ssm-row128-plan-fixed.json),
[new HIP fixture](../tests/q2_ssm_row128.hip),
[provenance](../third_party/gufo/LIE-Q2-SSM-ROW128.md).
