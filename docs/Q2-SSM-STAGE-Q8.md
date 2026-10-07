<!-- SPDX-License-Identifier: MIT -->
# Transient original-Q8 stages for prefill SSM

This local candidate targets the retained original128K profile's 10.146181 s
fused SSM input projection, part of 23.017440 s total dense work. It has no
GPU result or model integration yet. Retained R3 remains 1337.972303 PP /
26.101627 TG; the V-blocks model result is unpromoted.

The original Q8 loader reads two 16-byte code groups from two-byte-aligned
34-byte blocks at row-strided addresses. A separate integer-only kernel copies
those exact code and scale bits into the order the existing SSM tile consumes:
256 output rows by two K32 groups, two contiguous uint4 code planes followed
by 512 original 16-bit scales. Each stage is 17408 bytes. All 40 stages and
64 output-row tiles occupy the same 44564480 bytes (42.5 MiB) as the original
matrix. The weight allocation remains intact; no dequantized F16 mirror,
requantization or persistent expert/weight cache is introduced.

The consumer retains BM256/BN128/BK2, the original eight-wave assignment,
LDS transpose, K16 accumulation, Q8-to-half arithmetic and rounding, fused
interior convolution and original boundary-convolution launch. Only weight
addresses/loads change. The complete component timer includes packing anew
for every projection, followed by both projection/convolution kernels.
The extra copy, transient storage and cache effects can outweigh better
load alignment; no speedup follows from this design or compiler evidence.

This differs from the rejected cooperative aligned-pair loader: there is no
per-stage cross-lane scale exchange or shifted payload reconstruction in the
consumer. It also differs from the negative expanded-F16 mirror and tile/
wave/K-stage experiments; none of those saved models is rebuilt or rerun.

Object, device assembly and link compile locally. The original SSM projection
and boundary convolution are byte-exact to R3. Candidate projection uses
219 actual VGPR versus 220, with the same 49152 LDS bytes and zero private
scratch; packing uses 17 VGPR and zero private scratch. Among all 165 common
functions, 153 are byte-exact and 12 unrelated functions have changed bytes,
with no changed sizes/resources. Do not describe the whole binary as byte-exact.
The instruction-mix tool counts 3877/3859 static instructions, with the same
148 static global loads, 64 WMMA instructions and 232 LDS reads. The proposed
benefit is contiguous operand access, not a large instruction-count reduction.
Neither register count nor instruction count establishes throughput.

Owned C++ files pass the focused formatting check. The shared provider check
exits 1 with 100 diagnostics in unchanged source; that failure is retained.
Source, retained link objects and executable hashes verify. No runtime test
is represented by those preparation checks.

The prepared fixture checks all 65536 scale bit patterns and all code bytes
in a packing-only pass, including nonfinite encodings without performing
floating arithmetic. Model-shaped numerical cases use finite operands at
1024, 1025, 1057, 2048 and 2049 rows; weights end at the allocation boundary.
Every packed byte, immutable input, output guard and required output value is
checked. The retained raw-projection live mask, independent FP64 oracle and
0.002 bound remain. Three weight rotations total 133693440 bytes, above
32 MiB MALL. Two warmup pairs and six balanced measured pairs retain every
actual output for comparison before reuse. The 78 full-output comparisons,
156 independent checks and sixteen complete timing records are planned counts,
not executed passes. Finite disagreement retains timings; unsafe output stops.

This is a prefill component, with no decode or executor dispatch change.
Future model integration would need an explicit phase/shape/byte-capacity
contract and scratch last-reader proof; the existing 200 MiB expert allocation
is only a potential workspace. A favorable operator result must then survive
the unchanged original130925/8 model workload, including packing cost.

The current GPU successor is the separately coordinated GLM experiment.
Q2 owns no .157 job, lease, admission, waiter or reservation. CPU checks and
a new concrete GPU plan must follow verified GLM closure before execution;
local compilation does not authorize a remote run. There is no remote build,
model access, installation, tuning or cleanup in this preparation.

[Source binding](../config/q2-ssm-stage-q8-source.json),
[static audit](../config/q2-ssm-stage-q8-static.json),
[candidate](../experiments/q2-ssm-stage-q8.inc),
[fixture](../tests/q2_ssm_stage_q8.hip),
[reproduction](../tools/prepare-q2-ssm-stage-q8.py).
