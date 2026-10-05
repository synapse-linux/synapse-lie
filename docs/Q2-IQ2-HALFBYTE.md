<!-- SPDX-License-Identifier: MIT -->
# Compact IQ2 half-bit decoding

The new candidate replaces the signed integer code bytes in the existing IQ2
weight stage with the high byte of their exact F16 representation. Absolute
values 8, 25 and 43 have half bits 0x4800, 0x4e40 and 0x5160. The low byte is
reconstructed from the low two bits of the high byte; its sign remains in bit 7.
Weight storage in LDS stays at one byte per value. No model-weight conversion,
new allocation, stream, stage layout or public ABI is introduced.

The previous [shared F16 stage](Q2-IQ2-HALFSTAGE.md) preserves every parent
output but regresses full-model prefill by 2.108708%. This new mechanism keeps
compact staging and removes the consumer's half addition, preserving its exact
signed magnitude, rounded scale, packed half FMA and ordered K16 WMMA sequence.
The 2 KiB derived codebook is generated from the independently pinned official
Gufo/ggml table. Original upstream notices and table bytes remain unchanged.

## Local preparation

Both compact decoders pass 262,144 scalar bit checks across every codebook/sign
pair and 1,296 packed four-value combinations. These are host format checks,
not original-weight inference or independent model quality.

The permutation decoder uses one packed byte selection to reconstruct the low
bytes. The shift decoder reconstructs the same bytes with masked shifts and
ORs. Matched local gfx1151 assembly changes eight paired IQ2 bodies and preserves
149 other bodies exactly. The saved parent assembly is reused without rebuilding
or rerunning a qualified model/component. All three source snapshots are retained.

| Unpacked token tile | Parent instructions | Permutation instructions | Shift instructions | Parent → permutation VGPR | LDS bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| 16 | 661 | 640 | 672 | 82 → 83 | 11392 |
| 48 | 1161 | 1143 | 1175 | 94 → 94 | 15488 |
| 64 | 1391 | 1366 | 1398 | 102 → 102 | 17536 |
| 128 | 2381 | 2361 | 2395 | 148 → 148 | 25728 |

The selected permutation bodies have zero private scratch. Static packed half
adds change from 32 to zero, half FMAs stay at 32 and byte permutations grow
from 32 to 48. IQ2 loader packed xor/add instructions change from 16 to zero.
LDS load/store counts remain unchanged. These instruction/resource counts do
not establish a runtime gain; the shift variant is retained without a GPU run.

The shared upstream formatting command returns 1 for seven unchanged inherited
provider files. Its initial runs also reject include ordering in the new kernel
because stdin formatting lacked its filename. A separate filename-aware source
corrects that ordering and generates exactly the same kernel bodies. The changed
production file and new fixture pass their focused formatting checks. All actual
exits and original sources remain retained; no unrelated parent source is fixed.

The first local scope test returns 1 because the new component is absent from
parser mode choices. It is corrected before staging or SSH, and all 83 final
launch guards pass. Fixture device compilation and host syntax checks pass.

## Frozen new-only scope

One new component compares 81 whole outputs at widths 16/48/64/128, ragged row
and output edges, and ordinary/packed outputs. Three rotations of gate/up weights
span 162201600 / 324403200 / 1297612800 bytes for 64/128/512 active experts,
each exceeding 32 MiB MALL. Its 42 alternating timing samples measure fused
IQ2 gate/up and SwiGLU with existing maps and F16 input. They exclude map
construction and down projection and are not complete MoE/model throughput.

The new GPU format replay has 917,504 entries and 3,670,016 packed word pairs:
all 256 codebook indices × 128 signs × 16 scale boundaries, followed by all
65,536 F16 scale patterns for six signed magnitudes. NaNs/infinities are checked
by raw bits, and each entry has a distinct write stamp. Initialization, output
poison, launch and readback use the same nonblocking stream. Numerical failures
retain arrays and do not suppress performance; corrupted guards stop device work.

Only this candidate's original counting model follows, including if the new
component regresses or its numerical check rejects. The original exact2048
input, capacity 9216/chunk 2048, one warmup plus three measurements, tg128 with
127 timed decode calls and 15-second pauses outside timers stay fixed. Saved
Q2 1443.672867 PP, parent 1496.830907, marginal selective 1497.606050 and fixed
UD 1685.777092 remain references. No qualified control or old component reruns,
full curve, dependency installation, tuning, cleanup or deployment is admitted.

The new `.157` CPU capsule passes 25/25 Debug and 25/25 ASan/UBSan CTest.
All six commands exit 0; seven artifacts, 32 frozen fixtures and 1020 pinned
host-source files verify. These are CPU fixtures and open no model or GPU.

GPU performance and full-model replay remain pending fresh coordinated
admission. Static preparation establishes neither point parity nor completion
of the Q2/UD context, resource and independent quality requirements.

[Initial permutation source](../config/q2-iq2-halfbyte-perm-source.json),
[shift source](../config/q2-iq2-halfbyte-shift-source.json),
[formatted selected source](../config/q2-iq2-halfbyte-perm-formatted-source.json),
[static evidence](../config/q2-iq2-halfbyte-static.json),
[new fixture](../tests/q2_iq2_halfbyte.hip),
[frozen plan](../config/q2-iq2-halfbyte-plan.json),
[host receipt](../config/q2-iq2-halfbyte-host-results.json),
[provenance](../third_party/gufo/LIE-Q2-IQ2-HALFBYTE.md).
