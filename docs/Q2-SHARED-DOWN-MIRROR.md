<!-- SPDX-License-Identifier: MIT -->
# Shared-down cache and fixed-shape component preparation

This is a new component experiment for M2560/N2048/K640 shared down, excluded
from the already measured [large Q8 mirror trial](Q2-Q8-MIRROR.md). That earlier
trial lost2.164926% whole-model PP; it is not repeated or relabeled here.
The new providers derive from saved1580.226725 PP /25.10411864 TG. Neither
changes model upload, executor dispatch, resource ownership or measured speed.

Four arms separate weight caching from indexing changes:

| Arm | Weight representation | Addressing/epilogue |
| --- | --- | --- |
| Original Q8 | Original encoded Q8 | Existing generic dense kernel |
| Generic F16 | Persistent GPU-derived F16 copy | Same generic geometry and single K16 accumulation |
| Fixed Q8 | Original encoded Q8 | M2560/K640 constants, proven full-row stores |
| Fixed F16 | Persistent GPU-derived F16 copy | Same fixed-shape addressing as fixed Q8 |

All arms use BM256/BN128/BK1/WM4/WN2. Half-weight arms explicitly retain the
original Q8 single K16 accumulation chain; the ordinary unquantized-F16
two-chain route is not substituted. The fixed arms keep every token-tail
check and twenty K32 blocks. Integer enumeration verifies2560 weight-row
owners and20480 float4 row-coordinate cases over the ten complete row tiles.

The model currently keeps compressed expert weights resident already. This
proposal would additionally keep shared-down weights dequantized. A later
model integration would need48 mirrors totaling150MiB payload plus192KiB
allocation tails, retaining original Q8 for decode. The current component
provider allocates no such model memory and is not selectable by the executor.
Resource admission, publication/failure handling and model qualification remain
future work if a component candidate is useful.

## Local compilation evidence

| Static property | Original Q8 | Generic F16 | Fixed Q8 | Fixed F16 |
| --- | ---: | ---: | ---: | ---: |
| Instructions | 3056 | 3067 | 812 | 690 |
| VGPRs | 224 | 256 | 256 | 256 |
| Scratch bytes/thread | 0 | 64 | 68 | 68 |
| LDS bytes | 24576 | 24576 | 24576 | 24576 |
| Static occupancy field | 6 | 5 | 5 | 5 |
| Static WMMA opcodes | 32 | 32 | 64 | 64 |

The fixed arms eliminate generic scalar-store fallbacks and expose constants,
but register spilling remains. Their compiler output has32 matrix instructions
in the loop and32 in the peeled final stage/epilogue. Static instruction totals
are not executed-instruction counts or throughput; no speedup is established.
The initial analyzer wrongly required32 static WMMA opcodes for every arm. Its
exit1 and source are preserved; the corrected report records the actual counts
without modifying either candidate. This was not a numerical test failure.

All162 retained production kernels are instruction/operand/resource-exact to
saved assembly. The initial generic mirror and converter remain exact in the
fixed provider. Converter assembly also matches the previously qualified large
mirror converter. Both separate1028-file providers and complete patches remain.
Host and gfx1151 device syntax checks pass for the final four-arm fixture;
this is not GPU execution, sanitizer coverage or numerical qualification.

## Prepared GPU scope

The fixture covers96/97/127/129/1025/2048/2049 tokens. It prepares126 complete
candidate/reference output comparisons,168 independent sampled FP64 checks
with24 outputs each, and42 complete integer-formula mirror checks totaling
68,812,800 values. The FP64 RMS/scaled-maximum limits remain0.002. Output
guards, required stores, original inputs and mirror immutability are checked;
failed outputs are retained and timed outputs are checked against numerical
replay. These counts describe the prepared scope; zero GPU checks have run.

Only2048 is timed. Twenty-four distinct weight sets rotate39.84375MiB Q8 or
75MiB F16 weights, each exceeding the32MiB MALL. Four arms rotate their order
over two warmups and five measured repetitions:28 event records,20 measured.
Events include all24 projection launches and exclude conversion, allocation,
input generation and readback. This measures a projection with amortized
conversion, not the complete shared-expert cycle or canonical model throughput.
Safe numerical rejection returns1 after retaining timings; memory/write/runtime
failures return2 and stop dependent work.

The already frozen SSM row-group campaign stays first. Its88 fixtures, five
manifests and window helper remain unchanged. This new component is not yet
wired to CMake or the remote launcher and grants no .157 admission. At
20:48:42UTC on5 October2026, the original Core-19 supervisor and runner remain
alive on .157. No Q2 host/build/client/lease/reservation is started there.
GPU execution requires actual CPU closure and fresh coordinated handover.

[Initial source](../config/q2-shared-down-mirror-source.json),
[four-arm source](../config/q2-shared-down-fixed-source.json),
[assembly, fixture contract and actual command exits](../config/q2-shared-down-static.json),
[fixture](../tests/q2_shared_down_mirror.hip).
The original fixed Q2/UD/1580 model results remain unchanged, and no full
context curve or Q4 run is admitted by this preparation.
