<!-- SPDX-License-Identifier: MIT -->
# HC input and injection coefficient reuse

The next candidate reuses the normalized inputs already loaded by HC mix and
stages its injection coefficients once per workgroup. It is a private compiler
probe, with no production selector or GPU runtime result. Retained Q2 remains
**1585.308983 PP / 25.16079073 TG** against fixed UD
**1685.777092 PP / 24.34174251 TG**. The unchanged exact2048/tg128 comparison
needs 6.337447% more PP, or 76.991736 ms less prefill. No new speedup is claimed.

## Concrete redundant work

The existing mix producer loads four normalized float4 vectors for each hidden
group and token. A separate injection kernel reloads those values. The first
private draft computes four injection dots during those existing reads, writes
compact F32 dots, and keeps the original reduction in a second kernel.

Source inspection of that draft finds repeated coefficient loads: its 128
token rows use the same four-output/four-stream/64-hidden coefficient tile.
The tile is exactly 4096 bytes. After the projection's final K-loop barrier,
its existing 24576-byte LDS allocation holds a 16640-byte gate transpose and
has enough unused tail for those coefficients. The new draft stages them once
with 256 aligned float4 writers, then reads that exact tile for every token.
The first existing gate-publication barrier already precedes every coefficient
read, so no barrier or LDS allocation is added. The coefficients do not overlap
the gate transpose and remain live until all epilogue readers finish.

The source-level coefficient payload at2048 is 320 MiB in the first draft and
2.5 MiB in the staged draft. These counts describe logical requests, **not
physical DRAM traffic**: the 160 KiB whole coefficient matrix may already hit
cache. New LDS reads, address work and register effects must be charged to the
complete mix/injection cycle. The draft still writes and rereads20 MiB of
compact dots, for40 MiB additional scratch traffic at2048.

## Preserved arithmetic and static evidence

Each dot retains the original first rounded F32 multiplication followed by
15 ordered F32 FMAs. The reducer retains the original wave sum, eight-wave
block sum, three hidden chunks and output layout. No atomic sum, regrouped dot
product or alternate normalization is introduced. Runtime equality remains
unqualified.

| Compiler fact | First reuse draft | Coefficient-staged draft |
| --- | ---: | ---: |
| Raw producer instructions |5234|4761|
| Deferred producer instructions |5610|5148|
| Raw static global128 loads |176|49|
| Deferred static global128 loads |208|81|
| Producer VGPR |242|242|
| Raw SGPR |31|32|
| Deferred SGPR |40|32|
| Producer LDS bytes |24576|24576|
| Producer private bytes |0|0|
| Producer WMMA instructions |16|16|
| Producer block barriers |26|26|

Both new producers still contain more instructions than the original separate
mix producers (3473 raw /3807 deferred). Work has moved into the mixer; these
compiler facts are not a prediction of saved time. The reducer's178
instructions, operands and resources are exact to the first draft after
excluding only its renamed defining symbol. All162 production kernel bodies,
operands and resources remain exact to retained1585's saved assembly.

The [static audit](../config/q2-hc-inject-reuse-draft-static-v3.json) verifies
10240 coefficient address vectors across40 hidden tiles, disjoint/aligned LDS
writers, publication order and the complete1027-file parent inventory.
Device-only compilation succeeds; no GPU program or model is run. An initial
audit fails because its reducer comparison includes the deliberately renamed
defining symbol. The additive corrected audit excludes only that header line;
all instructions and all production-body checks remain intact. The original
exit1 and failed analyzer are preserved. No compiler rerun or numerical
tolerance change follows this analysis correction.

## Qualification and priority

First measure the **complete** raw/raw-Q8/deferred mix plus injection cycle,
with full guarded output comparisons, ragged token tails, rotating weights
beyond32 MiB and timing validation. The preceding down component returned70
zero HIP elapsed values; reuse of that timing setup without an independent
check would produce no useful performance evidence. After a device-safe
result, wire one isolated provider from retained1585 and measure only that
candidate with the original2048 tester and saved Q2/UD/best references.

Compact dot storage can fit in the existing `down_e` allocation. This is a
proposed borrow, not implemented lifetime qualification: the previous expert
combine must finish reading it, both HC consumers must run before the next
expert writer, and failures or unsupported consumers must invalidate identities.
The ordinary normalized input and deferred residual/gamma/scales must retain
their original ownership. No extra persistent allocation is proposed.

The saved1571 profile attributes39.548835 ms to96 ordinary/deferred injection
calls and85.284003 ms to the two affected fused raw/deferred mix bodies. It is
historical attribution, not a fresh1585 profile. Even eliminating all separate
injection time cannot alone close the76.991736 ms gap. HC reuse is first because
it removes a specific duplicate pass with a prepared source and bounded scratch;
it must earn a model gain before composition.

The next larger expert candidate is whole640-value producer/packing ownership.
Saved packing takes17.096259 ms and IQ2 gate/up239.499759 ms. Ten independent
64-column producers currently feed a whole-row scale reduction. A new ownership
layout might remove the50 MiB F32 intermediate write and50 MiB packing read per
layer, but must preserve that scale and producer reuse. Replicating F32
conversion in all20 down consumers increases logical payload instead and is
not the proposed optimization. No such producer implementation or gain exists.

SSM compact-LDS, IQ2 tail16/register staging, down register palette and the
compressed expert cache already have negative model evidence. They are retained
for inspection and are not queued for repeated qualification. Reactive launch
gaps total only5.090460 ms in the saved profile. They cannot supply the77 ms
numerical saving required at C1. Long-context attention work remains separate
from the fixed-point target and full-curve qualification stays deferred.

[Source recipe](../tools/prepare-q2-hc-inject-reuse-draft-v3.py),
[private include](../experiments/q2-hc-inject-reuse-draft-v3.inc),
[draft manifest](../config/q2-hc-inject-reuse-draft-v3.json),
[corrected static auditor](../tools/analyze-q2-hc-inject-reuse-draft-v4.py).
