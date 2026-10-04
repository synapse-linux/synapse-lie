<!-- SPDX-License-Identifier: MIT -->
# Constant integer geometry in the paired HC norm

The fixed performance reference remains **1443.672867 Q2 / 1685.777092 UD**
on the exact-2048 counting input. This experiment starts from that exact
mixed-map Q2 provider. It changes integer indexing inside two paired norm
producers that already run on the fixed input; it does not extend dispatch
to a different prompt size or change the model comparison.

Both public launchers already reject hidden widths other than 2560 and stream
counts other than four. The GPU bodies nevertheless receive a variable hidden
width and repeat divisions, bounds checks and index selection over ten chunks.
The candidate makes that integer width constant inside those two bodies.
The original runtime floating-point normalization divisor remains separate,
preserving its arithmetic expression. Expert FMAs, square sums, reduction tree,
F32 rounding anchors and F16 output conversion remain in source order.

Only `kernels.hip.cpp` changes; 1021 other provider files remain exact. No
buffer, allocator, public signature, executor, library algorithm, expert map,
accepted decode path, PLE policy or C17 contract changes. Official source pin
and licenses remain those of the independently fetched Gufo baseline.
This differs from the rejected HC160 projection specialization and deferred
F32 norm experiments; neither is being repeated or relabeled.

| Static compiler observation | Reference | Candidate |
|---|---:|---:|
| Ordinary paired norm instructions | 1634 | 1028 |
| MoE paired norm instructions | 1716 | 1077 |
| Ordinary VGPR | 84 | 95 |
| MoE VGPR | 84 | 100 |

Both kernels retain zero private scratch and their original LDS sizes.
All 150 unrelated kernel bodies remain exact after local label normalization.
These are device-only compiler observations, not dynamic instruction counts,
GPU performance or numerical evidence. Higher register use may offset fewer
instructions; exact runtime replay remains required.

The [source manifest](../config/q2-norm-fixed-shape-source.json),
[patch](../experiments/q2-norm-fixed-shape.patch),
[generator](../tools/prepare-q2-norm-fixed-shape.py) and
[static receipt](../config/q2-norm-fixed-shape-static.json) retain provenance.

The existing `q2_hc_library_norm` fixture and library algorithm7526 are reused
unchanged. Three sequential arms compare the original paired producer,
candidate and original again. Each retains its unchanged unpaired producer
control. Ordinary and MoE complete cycles include the consuming projection,
2048 tokens, 100MiB rotating original-layout F16 weights, five alternating
samples of sixteen iterations, and allocation-role reversal. Original full
output comparisons and independent limits remain; inherited down failures
and actual exit1 are not suppressed. No model is loaded in this window.

The [frozen plan](../config/q2-norm-fixed-plan.json) requires exact outputs,
no new independent failures, at least1% complete-cycle improvement for both
paths against both controls, and at most2% drift of the unchanged path. Only
a passing component selects the same fixed model point. A full curve remains
deferred until fixed-point parity with UD.

The new component-only launcher scopes pass22/22 Debug and22/22 ASan/UBSan
on `.157`, with six zero command exits and seven verified artifacts.
A local audit initially expected an older CTest summary string and failed;
the corrected audit checks the actual summary and all22 Passed records,
without rerunning the successful remote tests. The failure is retained.
[Host qualification](../config/q2-norm-fixed-host-results.json).

GPU admission and component measurements remain separate from this checkpoint.
