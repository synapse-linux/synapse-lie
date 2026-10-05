<!-- SPDX-License-Identifier: MIT -->
# Expert-ordered scaled Q2 activations

This candidate starts from retained1574.505432 PP /25.17589001 TG. It gathers
slot-major F32 SwiGLU rows once during the existing scaled-half packing pass,
then stores them in the existing padded expert-row order. Q2 down reads this
contiguous layout instead of gathering slot-major activation rows independently
for every output-row block. Inverse scales and down outputs retain slot order;
the weighted expert consumer, original weights and arithmetic remain intact.

At2048/top10/512 experts, the conservative padded capacity is28160 rows. Half
rows plus slot scales consume36,126,720 bytes within the existing52,428,800-byte
F32 up allocation. No allocation, stream, model conversion or public contract
changes. Only the eligible compact-down path uses this layout, after an explicit
capacity check; other shapes retain their existing representation. Zero-filled
padding prevents stale values from entering WMMA. Routing maps remain alive
through packing and down on the original stream.

This changes memory traversal, not the logical matrix operation. Packing now
gathers its input and writes padding, so its extra work can erase a consumer
benefit. Contiguous addresses do not prove fewer hardware transactions. The
component measures both complete packing and packing-plus-down, with50MiB
activation input and315MiB weights independently larger than MALL. Allocation,
upload and checking remain outside timing; all packing/reordering is inside.

The new guarded fixture covers36 packing layouts and35 full down comparisons,
including randomized within-expert permutations, empty experts, padded holes,
ragged rows/outputs and16/48/64-token tiles. Every scale/half is independently
checked with scalar double-ldexp/integer half conversion. The extreme-input
case retains the strict signed-zero oracle, including any inherited failure.
Safe numerical or timing failure does not suppress the original2048/tg128
model performance arm. A device fault, nonfinite/unwritten output or guard
violation stops further device work. Qualified model controls are reused.

The local production assembly preserves all162 existing kernel instruction,
operand and resource bodies and adds four kernels without private scratch.
This is preparation evidence only; GPU/component/model evidence is pending.
The first fixture compilation fails on a pointer field accidentally called as
a function; the source and both host/device exit1 logs are preserved before
the one-line correction. No numerical result is inferred from compilation.

The associated MMQ source review confirms that directly selecting existing
`qfn_mmq_q2_K_moe_raw` would rebuild expert maps, quantize the640 logical values
with768 stored-width padding, and write F32 outputs. A fair producer-Q8/down
adaptation still needs a direct consumer and explicit numerical qualification;
it is not implemented by this layout experiment. Official source provenance
remains Gufo f783fedb9bea2ec7de941f6da4e02f4a4596b29e, independently fetched.

Original fixed references remain Q2 PP1443.672867 and UD1685.777092. No Q4,
full context curve, reference rebuild/rerun, cleanup or tuning is scheduled.
Independent inherited F16 quality and full PP/TG parity remain open.

[Source](../config/q2-scaled-expert-order-source.json),
[static evidence](../config/q2-scaled-expert-order-static.json),
[plan](../config/q2-scaled-expert-order-plan.json).
