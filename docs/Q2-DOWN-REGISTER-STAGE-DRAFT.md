<!-- SPDX-License-Identifier: MIT -->
# Q2 down: wave-private stage removal

The [isolated v3 trial](Q2-DOWN-REGISTER-PALETTE.md) completes on `.157` at
1579.532131 PP /25.17055431 TG,nominal-0.364399% PP.123 component pairs/21 parent
model files are exact;70 HIP timings are invalid zeros. Keep1585.308983.
Host34+34/focused CTest1/1 pass and the window releases04:27:46UTC/e64145d6.

The v3 draft now has an [isolated production trial](Q2-TARGET-PRIORITIES.md),
123-pair/70-timing fixture and historical `.157` host33+33 pass. Its GPU trial
did not start because SSH failed before connection. Current phase changes
require fresh34+34 on `.157`; no down speed or numerical result exists yet.
The preparation descriptions below retain their original compiler-only scope.

These source-only drafts start from retained1585.308983 PP /25.16079073 TG,
not the negative IQ2 register-stage candidate. No model speed, device safety
or numerical equivalence is established for these drafts.

The active fixed2048 path calls `RoutedQ2ScaledHalfGemm` with BM128 output
rows, BN48 token rows, BK2, m2560/k640, original Q2_K weights, scaled half
input and per-slot inverse scales. It uses the exact four-value half palette,
ordered WMMA, F32 inverse-scale multiplication and retained F16 output
storage. The old generic unscaled Q2 or IQ2 gate/up template is not this path.
The saved1571 trace attributes161.558060ms to this down region; that is
historical diagnostic attribution, not a fresh1585 timing or predicted gain.

For each128-row block, the current weights and F32 affine values are published
to LDS and then consumed by the same wave32. Enumerating256 row/K32-group
fetches confirms the address set is unchanged after assigning each half-wave
one K32 group of the same16 rows. The drafts keep stage values in registers
and exchange the opposite half-wave's words. Activation staging, eight waves,
WMMA order, maps, grid and the original padded output transpose remain.

The v2 draft exchanges code bytes and F32 affine bits, retaining original
palette formation in the consumer. The v3 draft forms the same rounded half
palette once during stage commit and exchanges those bits instead. This differs
from the old LDS staged-palette experiment: both new drafts remove the entire
code/affine LDS stage. No extra persistent buffers, weight conversion, KV or
expert caching, stream or launch is introduced in the compiler probe.

| Compiler observation on active BN48 | Saved parent | Register affine v2 | Register palette v3 |
| --- | ---: | ---: | ---: |
| LDS bytes |18560|8320|8320|
| Next-free VGPR |96|102|102|
| Next-free SGPR |36|38|38|
| Private scratch bytes |0|0|0|
| Static instructions |2641|2705|2699|
| Static block-barrier sites |8|8|8|
| Static WMMA instructions |12|12|12|
| Other production bodies unchanged |—|162|162|

The removed code/affine planes contain12288 bytes. Actual per-block allocation
falls10240 bytes because the original output transpose still needs8320 bytes,
more than the6272-byte activation stage. The initial8192-byte draft failed the
existing epilogue static assertion and is preserved with compiler exit1. The
correction keeps that assertion and sizes LDS to the real output bound.
A separate static analyzer exit1 is retained: its inherited compiler-comment
parser assumed another function followed the last kernel. A section sentinel
now bounds that comment-only parser; no assembly or resource data is changed.

The v3 change removes six static instructions relative to v2, but both still
increase instructions and registers against the parent. Reduced LDS alone
has not established a speedup; the completed IQ2 register-stage model regressed
0.641809% despite small positive component timings. Both down variants remain
candidates for actual comparison, with v3 first because it avoids duplicate
palette evaluation. No rejected source or previous controls will be rebuilt.

Next construct an isolated provider selector for BN48 and a literal-parent
fixture using captured expert counts, three weight rotations, m/routing tails,
complete guarded F16 outputs and inverse scales. Measure both whole down and
original fixed2048/tg128 on .157 after fresh coordination. Preserve performance
on safe numeric differences; stop device guard/runtime faults. The full curve
and Q4 remain deferred until fixed-point parity. Existing quality limitations
are unchanged; source algebra and static compilation are not independent quality.

[Static results](../config/q2-down-register-stage-draft-static.json),
[initial source binding](../config/q2-down-register-stage-draft.json),
[v2 include](../experiments/q2-down-register-stage-draft-v2.inc),
[v3 include](../experiments/q2-down-register-stage-draft-v3.inc),
[initial generator](../tools/prepare-q2-down-register-stage-draft.py),
[correction and palette generator](../tools/prepare-q2-down-register-stage-draft-v3.py),
[provenance](../third_party/gufo/LIE-Q2-DOWN-REGISTER-STAGE-DRAFT.md).

The draft wrappers compile locally to device ISA only. A separate production
selector/provider and runtime fixture are now wired for v3, with GPU execution
pending as stated above. No GPU reservation exists. Public C17 model/state/
metrics contracts and the retained provider remain unchanged.
