<!-- SPDX-License-Identifier: MIT -->
# Exact Q8 integer-half pair lookup

This new candidate starts from the measured compact IQ2 provider, PP1498.799455 /
TG25.16866636 on the original exact2048/tg128 input. It changes the Q8-weight
branch of the dense F16 matrix-core projection, keeping the compact IQ2 change
and all prior parent composition. Fixed Q2 remains1443.672867 /25.09595499 and
fixed UD1685.777092 /24.34174251. No qualified control or old component cohort
is rerun. GPU/model results are pending coordinated admission; no gain is claimed.

The saved parent profile assigns293.725ms,21.183% of its prefill kernel work,
to Q8/F16 dense projections. That diagnostic is reused rather than profiled
again. Removing this stage's integer-to-half preparation is a new hypothesis,
distinct from the already measured grouped decode/store scheduling barrier,
Q2 affine-palette staging, raw code-byte caching and half-wave exchanges.

## Mechanism and scope

Every signed Q8 integer is exactly representable as F16. A generated65536-entry
table maps two original encoded bytes to their exact two half values. The
table occupies262144 device bytes. It contains only the full signed-int8 domain,
not model weights or an expanded model cache. This size is an explicit added
resource cost even though no runtime allocation or model conversion is needed.

Two indexed32-bit loads replace each four-code word's byte permutations and
magic half additions. The original packed half FMA applies the same F16 scale
and zero bias. Weight fetch, stage layout, LDS stores, activation halves, tile
geometry, K16 WMMA order, epilogues and fused SSM convolution are unchanged.
F16-weight projections, routed IQ2/Q2 and integer W8A8 bodies remain unchanged.
There is no new stream, launch, public ABI/state/metrics contract or CPU model
forward. Added indexed loads can be slower or compete with activation/weight
caches; fewer conversion operations are not a predicted runtime improvement.

All131072 scalar integer checks pass. These use the complete byte-pair domain
and an independent reconstruction of the parent's exact1152+q magic operand;
they are host format checks, not original-weight inference or model quality.
Matched local gfx1151 assembly changes eight Q8 dense bodies and preserves149
other bodies exactly. All affected bodies keep their LDS size, VGPR demand and
zero private scratch. Static half adds change16/32 to zero; half FMA counts
are unchanged. The SSM body grows4027 to4082 instructions because indexed
lookup/address work replaces the removed operations. The saved parent assembly
is reused without rebuilding its source or qualified binaries.

## New-only component and model plan

The new component contains the literal retained parent dense kernel. Static
source comparison verifies that control matches this candidate's compact
parent; it is a test control in the new binary, not a qualified cohort rerun.
The GPU format replay exhausts65536 code pairs at16 scale edges, with
1048576 entries and2097152 packed word comparisons. Low/high word inputs
differ by xor0x5aa5. Scale edges include signed zero, subnormals, signed normals,
overflow, infinity and NaN payloads. Raw-bit comparisons and unique write stamps
retain exceptional values rather than treating them as finite-output failures.

Whole guarded output comparisons cover ragged129x257x96, fused SSM
2048x16384x2560 and output2048x2560x6144, each at three immutable weight
rotations. All allocations have64-byte guards on both sides. Output data starts
with a nonfinite poison so two missed stores cannot pass as equal zeros.
Initialization, uploads, launches and readback share one owned nonblocking stream.
Numerical failures save complete arrays and keep all timing samples; guard or
runtime faults stop GPU work. SSM/output weight rotations occupy133693440 /
50135040 bytes, both above32MiB MALL. Two warmup and five measured pairs alternate
order and time three kernel launches per sample. Transfers, allocations, checks
and hashes remain outside the timing scope; this is not model throughput.

One new original-weight model follows even if the numerical or timing verdict
rejects the component, subject to safe runtime/guards. It preserves the original
exact2048 input, capacity9216, chunk2048, warmup plus three measured sessions,
128 output tokens/127 timed decode calls and15-second waits outside timers.
Only the new candidate is built/run; saved Q2, compact parent and UD are read-only
references. A full-context curve still waits for original-point parity.

## Local checks and provenance

Production device assembly, fixture device compilation and host syntax pass.
All84 launch guards pass before any staging or SSH. The shared provider CI
formatter retains exit1 for seven byte-identical inherited files. A separate
new-file formatting invocation initially omits the explicit Gufo style used to
format the fixture; the corrected invocation passes without changing its bytes.
The first static analyzer refuses that unclassified local failure. The final
static receipt retains both failures and the successful check, with no numerical
failure reclassification or altered qualified evidence.

The new `.157` CPU cohort passes25/25 Debug and25/25 ASan/UBSan CTest.
All six commands exit0; these checks access no model or GPU and are separate
from the pending new component and original-weight performance evidence.

The isolated provider has1026 files:1024 inherited files stay exact, one kernel
file changes and one generated table is added. It derives from this workstream's
independently fetched official Gufo pin
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`. First-party generator/table/delta are
MIT; original upstream notices and licenses remain unchanged. No sibling DS4
source, build, model, cache, profile or qualification artifact is imported or
mutated. Source and remote runs stay in persistent project directories, with
no cleanup, dependency installation, tuning, deployment or publication.

[Generator](../tools/prepare-q2-q8-halfpair.py),
[source identity](../config/q2-q8-halfpair-source.json),
[static report](../config/q2-q8-halfpair-static.json),
[new fixture](../tests/q2_q8_halfpair.hip),
[frozen plan](../config/q2-q8-halfpair-plan.json),
[provenance](../third_party/gufo/LIE-Q2-Q8-HALFPAIR.md).
