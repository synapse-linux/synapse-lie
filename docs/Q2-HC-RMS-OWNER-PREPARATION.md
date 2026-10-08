<!-- SPDX-License-Identifier: MIT -->
# Four-owner HC RMS: complete fixture prepared

The standalone ordinary/MoE fixture is prepared and both HIP host syntax and
device assembly compilation exit0. All164 numerical bodies/resources match
the earlier private compiler probe:162 original production bodies and two
owner drafts. The retained1027-file provider is unchanged. This is source and
compiler evidence; no GPU behavioral test or performance measurement has run.

The fixed original-model target stays Q2 **1585.308983 PP /25.16079073 TG**
versus UD **1685.777092 PP /24.34174251 TG**. Required PP saving remains
**76.991736ms**, or **6.337447%** more throughput. Old comparators, the complete
context curve and Q4 are not rebuilt or rerun.

## One mechanism and its measured boundary

Four owner threads finish the original eight sequential partial additions and
the runtime hidden-width division/rsqrt, then publish four scales in separate
LDS storage. Other threads read these scales after one additional block barrier.
Residual updates, expert/shared accumulation, squared norms, wave reductions
and F32/F16 boundaries are preserved in the draft source.

Both compiler probes use65 VGPR versus84 in the original, zero private bytes,
and16 more LDS bytes. Ordinary LDS is144 bytes; MoE LDS is10,384 bytes.
Compiler occupancy stays16. The extra barrier and LDS reads can outweigh
reduced duplicate calculation. Instruction/register counts establish no latency
saving. The historical145.803160ms combine region is not a removable-time
estimate and comes from the1571 profile rather than a fresh1585 trace.

## Complete numerical coverage prepared

The [fixture](../tests/q2_hc_norm_owner.hip) launches the actual retained
ordinary F32/half combine or the retained half-expert/deferred-norm combine,
then compares its complete outputs against the corresponding private draft.

| Cases | Shapes and checks |
| --- | --- |
|30|n1/17/97/129/257 × ordinary/aligned-MoE10/misaligned-MoE10 × normal/tiny inputs.|
|2|n129 ordinary and MoE with gamma absent: residuals written, normalization outputs remain untouched.|
|1|n129 MoE with half output absent: residual/scales written, half remains untouched.|
|2|n129 MoE with1 and16 experts, including the complete ordered expert sum.|
|1|n129 ordinary with ten injection parts instead of three.|
|2|n2048 ordinary/MoE10: whole pre-timing and post-timing outputs and complete-cycle timings.|

Expected records:38 immutable-input checks,120 complete output records and28
timings. Ordinary compares residual-F32, normalized-F32 and half. MoE compares
residual-F32, all four scales per token and half. Every output has64-byte
guards on both ends, explicit unwritten markers and finite checks where it
is produced. Absent/nonselected outputs must retain their entire original
marker payload. Misaligned experts use a four-byte offset, exercising the
existing fallback while retaining half2 alignment. Gate stride is three.
All input buffers are hashed before and after their case.

Safe numerical differences preserve both full guarded arrays and every timing,
with exit1. Device, guard and unwritten-output faults use exit2. No tolerance,
reference output or independent quality gate is weakened.

## Complete-cycle timing prepared

Each n2048 arm has an83,886,080-byte residual payload, larger than the32MiB
MALL. Two warm/five measured alternating pairs time six complete combines.
Each arm resets from the same immutable residual before its own cycle,
outside the timer. Input upload, output reset/copy, allocation, readback and
hashing are outside the timer. The final six-update residual/norm outputs
are checked in full after the last measured pair.

Monotonic wall includes event submission and terminal synchronization.
The raw HIP float value and bits are retained, with zero/nonfinite values
marked invalid. Neither timing is substituted for the exact2048/tg128 model
comparison; no model rate is projected from these components.

## Current preparation and next execution gate

The initial generator uses an incorrect CUDA flag spelling and terminates1
before compilation. Its receipt and partial exact fixture/argv are preserved.
The correction uses HIP offload flags and resumes only byte-identical
preparation files. Generation, host syntax, device assembly and ISA audit now
exit0. All compiler warnings remain in the raw logs.

No CMake target, remote variant, component plan or new admission exists for
this fixture yet. Runtime plumbing and its focused .157 host checks must
be qualified before freezing a fresh bounded window from the released
HC receipt dcb9d12a. The fixture is synthetic and runs no CPU model forward.
There is no production selector, executor scratch borrow, model arm, new
persistent allocation or public C17 ABI/state/metrics change.

The previous [HC injection-reuse result](Q2-HC-INJECTION-REUSE-RESULTS.md) is
retained independently, including its marginal Q8 observation and tiny
injection differences. No qualified component is rerun by this preparation.

[Preparation manifest](../config/q2-hc-norm-owner-component-preparation.json),
[complete ISA/static audit](../config/q2-hc-norm-owner-component-static.json),
[draft provenance](../third_party/gufo/LIE-Q2-HC-NORM-OWNER-DRAFT.md).
