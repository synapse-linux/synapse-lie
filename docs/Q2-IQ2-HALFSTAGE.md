<!-- SPDX-License-Identifier: MIT -->
# IQ2 shared F16 weight stages

The saved fixed-input MoE profile attributes 254.797 ms of prefill GPU work to
IQ2 expert gate/up. The new isolated candidate starts from measured MoE-deferred
1496.830907 PP / 25.17435733 TG. Fixed Q2 1443.672867 / 25.09595499 and UD
1685.777092 / 24.34174251 remain saved references. The original exact2048 input,
capacity9216/chunk2048, one warmup plus three measured samples, tg128 with127
timed decode calls and15-second waits outside timers remain the model contract.
No qualified control or old component is relaunched; full curves wait for parity.

The paired IQ2 kernel currently expands signed weight codes into F16 in both
half-waves of every consuming wave. The candidate performs the same
CodesToHalves packed add/FMA in the producer once per weight and stages those
halves in LDS. The duplicate consumers load the identical half values. Scale
rounding, signed codebook bytes, K16 accumulation order, live-fragment bounds,
SwiGLU and ordinary/packed output contracts remain. No stream, synchronization
point, global scratch, weight conversion or public ABI change is added.

F16 weight staging doubles the code plane from8192 to16384 bytes. Replacing
activation-plane padding with a quarter/token XOR permutation bounds the full
BN128 stage to32768 bytes. XOR operates inside each16-token fragment, so it
cannot leave any supported16/48/64/128-token tile. The separate corrected
weight swizzle uses the low row bits: eight producer lanes address eight bank
groups for a128-bit store. The initial row-shift variant and all its assembly
remain retained; neither variant has measured runtime when this preparation is
recorded. Static bank addressing does not prove hardware occupancy or speed.

Local matched gfx1151 assemblies change eight paired IQ2 bodies and preserve
all149 other bodies exactly. Both variants have zero private scratch. The
initial variant changes unpacked BN64 VGPR102 to121 and BN128 VGPR148 to169;
expanded shared memory and longer producer lifetimes can reduce residency or
overlap. Instruction/resource counts do not establish a performance gain.
The final swizzled resource inventory is retained separately.

The new synthetic fixture embeds the literal saved parent kernel in the same
binary. It compares81 complete outputs over four widths, ragged token/output
edges, float/packed outputs and three weight rotations. Its three large cases
use2048 tokens,640 output rows,2560 inputs, top10 and64/128/512 experts with the
existing mixed128/64 map. Rotated gate/up weights span162201600/324403200/
1297612800 bytes, exceeding32 MiB MALL. Initialization, uploads, poison fills,
launches and readback use one nonblocking stream. Output mismatches retain
whole arrays and do not suppress42 kernel-timing samples. A changed output
guard stops further device work. This fixture measures fused gate/up plus
SwiGLU with prebuilt maps/F16 input, excluding map construction and down
projection; it is not a complete MoE cycle or original-weight model rate.

Launch guards admit this provider only for the new component or its matched
original counting model with full MMQ build. The first local guard run finds
the new provider missing from the final source whitelist: exit1 is retained
and corrected before staging. Final82 scope guards pass. Device assembly and
host fixture syntax pass. The frozen plan schedules one host Debug/ASan capsule,
one new component and one new model, retaining performance independently from
numerical or timing rejection. It requires fresh coordinated admission before
GPU build/run. Dependencies, tuning, cleanup and deployment are excluded.

The new `.157` CPU host capsule passes25/25 Debug and25/25 ASan/UBSan.
Its six commands exit0; seven artifacts,31 frozen fixtures and1020 pinned
host-source files verify. This is host qualification and opens neither GPU
nor original model. Component/model GPU work remains unadmitted at this point.

[Initial retained source](../config/q2-iq2-halfstage-source.json),
[swizzled source](../config/q2-iq2-halfstage-swizzled-source.json),
[literal control](../experiments/q2-iq2-halfstage-control.inc),
[swizzled patch](../experiments/q2-iq2-halfstage-swizzled.patch),
[fixture](../tests/q2_iq2_halfstage.hip),
[static evidence](../config/q2-iq2-halfstage-swizzled-static.json),
[host receipt](../config/q2-iq2-halfstage-host-results.json),
[frozen plan](../config/q2-iq2-halfstage-plan.json).
