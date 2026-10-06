<!-- SPDX-License-Identifier: MIT -->
# New candidates for the fixed Q2 target

Retained Q2 remains **1585.308983 PP /25.16079073 TG** on the original
exact2048/tg128 benchmark. Fixed UD remains **1685.777092 PP /24.34174251 TG**.
Closing the PP gap needs6.337447% more throughput or76.991736ms less prefill.
The new work below has no GPU performance result. Saved comparators are not
rebuilt or rerun; Q4 and the context curve remain deferred.

The priorities favor a specific removable operation and a bounded change in
an active path. They are engineering judgments, not numerical probabilities.
The costs below come from the saved1571 profile, not a new1585 trace, and refer
to complete regions rather than the amount each candidate can remove.

| Order | New mechanism | Historical region | Prepared evidence and remaining gate |
| --- | --- | ---: | --- |
| 1 | Reuse normalized mix inputs for injection and stage coefficients once per CTA. |39.548835ms separate injection;85.284003ms affected mix |Complete raw/raw-Q8/deferred fixture compiles;165 bodies/resources exact to the private draft. Run it on .157, qualify borrowed workspace, then run only the new original-model candidate. |
| 2 | Assign the four final RMS scales to four threads, then publish them. |72.901302ms ordinary combine;72.901858ms MoE combine |Two new compiler probes preserve162 production bodies. VGPR84→65, zero private bytes; extra barrier and16 LDS bytes. Prepare complete residual/norm/scale/half checks and cycle timing before model integration. |
| 3 | Give a producer ownership of all640 values needed by the expert row scale. |239.499759ms IQ2 gate/up;17.096259ms packing |Source boundary established; no implementation or measurement. Preserve whole-row maximum and producer reuse. Avoid repeating F32 conversion in20 down consumers. |

## Complete injection-reuse fixture

The [fixture](../tests/q2_hc_inject_reuse.hip) compares the actual retained
production raw-F16, raw-F16-plus-Q8 and deferred-norm launchers with the private
[LDS coefficient draft](../experiments/q2-hc-inject-reuse-draft-v3.inc).
Its42 cases yield57 replay sets,200 complete output comparisons,57 logged
scratch checks and42 timings. Outputs include mixed F32, optional half,
injection partials and all Q8 payload/padding. It covers tokens96/97/127/128/
129/257, two finite input magnitudes, null-half controls and the full2048 shape.

Six timed up-weight rotations span39,321,600 bytes, above32MiB MALL. Two warm
and five measured repetitions alternate arms. Timers bracket six complete
mix/injection cycles; allocation, uploads, resets, hashes and comparisons stay
outside. Monotonic wall time includes submission of HIP events and terminal
stream synchronization: it is complete-cycle wall time, **not pure GPU elapsed
or model throughput**. Raw HIP durations have a separate validity flag.
Nonfinite durations use JSON null plus exact F32 bits; zero durations remain
zero and invalid. This avoids turning an invalid timer into a fabricated speed.

All output prefixes/suffixes are guarded; F32/half outputs and compact dots
must be written and are checked for finite values. Both Q8 arms have independent
scale checks and checks over the whole allocated128-token padding. Code bytes
may legitimately equal the poison byte, so code write coverage is differential,
not an independently claimed per-byte write stamp. Input and weight hashes
remain checked after completion. Safe numerical differences retain full arrays
and all timings with exit1. Guard/unwritten-output/device faults stop with exit2.

The component uses independent test-owned buffers. It does **not** qualify the
proposed reuse of executor `down_e`, independent model quality or production
adoption. Its [component-only source binding](../config/q2-hc-inject-reuse-component-source-v2.json)
pins the1027-file parent and rejects model, replay and persistent launch modes.
The launcher, runner and HIP target are wired, but no host or GPU runtime tests
have run for this new wiring. Current host syntax/device-only compilations exit0;
the [preparation audit](../config/q2-hc-inject-reuse-component-preparation-v2.json)
verifies all165 fixture bodies against saved draft assembly. Earlier fixture,
source binding and preparation receipt are retained before the padding/timer
metadata refinement; no numerical device body changes in that refinement.

## Four-owner RMS scale draft

Both active combine kernels finish four sequential totals of eight wave
partials, divide by the runtime hidden width and apply rsqrt. The saved compiler
bodies execute four rsqrt instructions in each consuming wave. The private
[new include](../experiments/q2-hc-norm-owner-draft.inc) lets threads0..3 each
finish one original total and scale. They publish into a separate16-byte shared
array and an added barrier precedes every scale reader. Original wave partials
are retained until their four owners have read them; no in-place publication
race or change to their order is introduced.

The expert/shared FMA chains, residual update, square contraction, WaveSum,
runtime floating divisor and F32/F16 output boundaries stay unchanged in source.
Their compiled floating contraction and runtime byte equality still need
qualification. There is no buffer allocation, stream, model representation,
executor state or production selector change. This differs from already measured
fixed-width and wider expert tile trials; those are not rerun.

| Compiler fact | Ordinary parent → draft | MoE parent → draft |
| --- | ---: | ---: |
| Instructions |1634→1623|1763→1740|
| VGPR |84→65|84→65|
| LDS bytes |128→144|10368→10384|
| Private bytes |0→0|0→0|
| Static rsqrt instructions |4→1|4→1|
| Extra block barriers |1|1|
| Compiler occupancy metadata |16→16|16→16|

The [static audit](../config/q2-hc-norm-owner-draft-static.json) verifies all162
original production bodies/resources against retained assembly. Lower registers
have not increased that compiler occupancy field. The full145.803160ms combine
region is **not** a saving estimate: expert accumulation, normalization and
output traffic remain. The added barrier, shared loads and scheduling may erase
the benefit. There is no measured t/s increment, projected model rate or quality
acceptance for this draft. [Recipe](../tools/prepare-q2-hc-norm-owner-draft.py)
and [source binding](../config/q2-hc-norm-owner-draft.json) retain official Gufo
lineage and MIT notices; no DS4 or sibling workspace source is imported.

## Current remote boundary

Core freshly confirms own non-use of `.157`. The next Q2 Core-closure/lease
check nevertheless fails before remote connection: SSH exit255, `No route to
host`. No staging, remote build, host test, model read, admission, GPU lease or
reservation starts. The raw command/stdout/stderr remain in
`evidence/q2-hc-inject-reuse-component-preparation/core-handover-*`.
The last verified release stays04:27:46UTC/e64145d6; it is historical closure,
not current remote availability. No waiter, automatic retry, cleanup, driver
change or tuning is scheduled.

On connectivity recovery, revalidate Core closure, registry, retired identities,
original lease identities and model stat tuples. Run current host Debug/ASan
checks on .157, freeze a new component-only window, and measure the complete
injection-reuse fixture. Safe numerical or timer rejection does not substitute
for performance; guard/runtime faults stop dependent GPU work. Only after
collected safety evidence and workspace lifetime qualification should a new
provider run the unchanged original2048 model test. The target remains open.
