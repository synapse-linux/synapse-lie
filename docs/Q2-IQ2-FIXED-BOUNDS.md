<!-- SPDX-License-Identifier: MIT -->

# Fixed IQ2 gate/up bounds

Start from the retained1585.308983 PP/25.16079073 TG SSM-bounds Q2 provider,
not the slower measured1582.080007 sign-arithmetic candidate. Fixed Q2 remains
1443.672867 PP; fixed UD1685.777092 PP. The exact original2048 input/tg128
point,127 timed decode calls,capacity9216/chunk2048,C1 greedy,MTP off and
one warmup/three measured sessions with15-second untimed pauses stay unchanged.
Saved controls are neither rebuilt nor rerun. Whole-curve parity is unmet.

Only unpacked IQ2 paired gate/up m640/k2560 BN64/128 selects a private clone.
It uses constant model row/K dimensions, marks all weight rows live and removes
output-tail scalar fallbacks. Ten grid blocks each own64 logical rows, covering
640 exactly; every float2 pair starts on an even row and remains within its
block. The640 output stride preserves alignment. Routing/token validity checks
stay in place. Other dimensions/packed modes/decode use the original selector.

The original sign table, codebook, four-lane compressed ownership, scale owner,
F16 rounding/FMA,K16 WMMA order and anchored F32 SwiGLU are unchanged. No table,
buffer, lifetime, stream, callback or public ABI/state/metric change occurs.
Original source template and all162 original numerical ISA bodies/resources
remain exact. Two private bodies are added; no original control recompiles.

| Geometry | Static instructions before / candidate | VGPR before / candidate | SGPR before / candidate | LDS bytes | Private bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| BN64 |1351 /1004|104 /104|28 /24|17536|0|
| BN128 |2361 /1685|150 /150|38 /32|25728|0|

Static instruction reductions25.68%/28.63% do not establish runtime savings.
F16 FMA/WMMA/exponential/barrier counts remain unchanged. Output stores use
64-bit float2 instead of the generic runtime alignment/tail scalar branches.
The generated grid/source assumptions need full runtime qualification.

A new fixture compares113 complete float output pairs across36 cases. It
retains ragged generic dimensions and captured real routing, and adds short
actual640x2560 cases n1/17/65/145 to exercise the private bounds directly.
Three weight rotations exceed MALL in five timed production-sized shapes;
70 alternating complete-operator wall/HIP records include two warmups/five
measurements. Post-timing outputs and immutable inputs are checked. Safe finite
numerical/timing rejection still allows the original model; guard/unwritten/
nonfinite/device faults stop further device work. No old sign-format experiment
is rerun because this candidate leaves those bytes unchanged.

Local source/production assembly/static audit/fixture host+device compilation
all exit0. Fresh .157 closure/lease/process/KFD/model-stat checks pass11:27:30UTC
against40974980. Core reports updated .157/.158 non-use11:28UTC. Host-r1
finishes2026-10-06T11:28:28.582584UTC,36/36 Debug plus36/36 ASan/UBSan, all six
commands0/seven artifacts collected. Freeze160 fixtures/six manifests/1028
provider files. GPU admission/component/model results are pending.

The launcher also refuses collection of a receipt without actual finished_at
or any command without an integer exit code. New regression cases cover live
receipts, missing/null command exits and terminal numerical-failure preservation.
This prevents the prior early-collection snapshot mistake without altering
benchmark timing, model behavior or accepted historical evidence.

[Source](../config/q2-iq2-fixed-bounds-source.json),
[static audit](../config/q2-iq2-fixed-bounds-static.json),
[frozen plan](../config/q2-iq2-fixed-bounds-plan.json).
