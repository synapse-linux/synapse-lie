<!-- SPDX-License-Identifier: MIT -->
# Original-F16 scalar HC up/mix fusion

The .157 component passes64 complete exact output comparisons and50
independent FP64 checks. With injection, completed operation time falls
42.970453 to34.630484us (-19.408613%); without injection it falls35.839672
to34.132219us (-4.764143%). All five measured pairs favor the candidate
in both modes. This qualifies an original-model integration trial; model
token/s, long-context benefit and inherited task quality remain unmeasured.

This private decode component joins the native F16 HC up projection and the
following mix/injection into one launch. The retained provider is unchanged.
The original shape is hidden2560, low-rank320, four HC streams and ten
256-element injection slices. The proposed kernel retains each projection's
F32 FMA sequence and wave sum, each mix FMA and each injection reduction.
It adds no rounding or quantization boundary. Exact GPU replay is required;
compilation alone does not establish equivalence or speed.

One wave owns one hidden position and its four gates. Eight waves share a
block; ten designated blocks also compute the original injection slices.
The mixed result is written directly, eliminating the40KiB gate plane and
one kernel launch. This changes scheduling and register pressure:44 VGPR,
128bytes LDS and no private scratch/spills, versus19 VGPR for the original
projection and22 for its separate mixer. Logical traffic is not a measured gain.

The standalone fixture directly calls the retained original kernels as its
control. Six guarded input families cover small activations, cancellation,
signed zero and half/float subnormals, with and without injection. Complete
gate/mix/injection outputs require byte equality. A separate FP64 formula
checks sampled gates/mixes and all injection partials at unchanged2e-5
relative RMS/peak-scaled limits; F32 subnormals instead retain the GPU's
original arithmetic-mode replay requirement. Finite numerical failures are
preserved and do not suppress performance measurements.

Performance measures completed HIP graphs containing64 complete operations,
rotating16 independent original-F16 matrices totaling100MiB, beyond the
32MiB MALL. Two warmups precede five alternating-order paired measurements
per injection mode. Allocation, upload, poisoning and output checks stay
outside timers. The candidate's timed graph must never write the removed
gate plane. Raw GPU event times are valid only if finite and positive.

This is synthetic component qualification, not original-model PP/TG or
independent task quality. The scoped supervisor admits one300second .157
window after fresh coordination/lease/model-stat/KFD checks, with no model
access, remote build or cleanup. CPU child-lifetime tests precede admission.
Original source provenance is the independently fetched Gufo pin and the
1028-file retained provider in the [source manifest](../config/q2-hc-scalar-up-mix-source.json).
[Static resources](../config/q2-hc-scalar-up-mix-static.json) and local compiler
commands under evidence/q2-hc-scalar-up-mix-preparation are retained.

## Completed .157 result — 7 October 2026

| Complete operation | Original median us | Fused median us | Latency change |
|---|---:|---:|---:|
| HC up + mix + injection | 42.970453 | 34.630484 | -19.408613% |
| HC up + mix, no injection | 35.839672 | 34.132219 | -4.764143% |

Both modes use two graph warmups and five measured paired replays. All28 raw
device event times are zero/invalid; the table uses completed wall duration,
including synchronization, divided by64 complete graph operations. No timing
is inferred from those invalid event values. The largest independent relative
RMS error is2.52710553715e-7, below the unchanged2e-5 limit. Every differential
pair is byte-exact, inputs/guards survive and deleted gate planes stay unwritten
in the timed candidate. No precision or weight representation is reduced.

The CPU supervisor's success/failure lifecycle cases, preflight and GPU
component exit0. Local object/assembly/link and changed-file formatting pass;
the provider-wide formatting command retains exit1 on unchanged inherited
files, with its logs preserved. No retained provider source is edited.

Fresh coordination and preflight precede admission10:47:51.889888UTC.
The GPU process completes10:48:02.565352UTC; all11 raw artifacts collect and
match remote hashes before release10:49:10.590347UTC. Receipt64e2f31e records
1959 retired identities/1565 groups, empty KFD, five free original leases
and seven unchanged model stat tuples. Peak CPU/GPU37/37C. No model access,
remote build, service change or cleanup occurs; Core receives the release.
No GPU job/client/handle/lease/window/waiter/reservation remains.

[Audited results](../config/q2-hc-scalar-up-mix-results.json),
[all28 timing samples](figures/q2-hc-scalar-up-mix-samples.csv),
[frozen plan](../config/q2-hc-scalar-up-mix-plan.json),
[offline auditor](../tools/analyze-q2-hc-scalar-up-mix.py).

Next: integrate only the original scalar F16 HC eligibility into a private
provider, preserving invalidation and injection-part ownership, then run the
unchanged original-Q2 model comparison. Do not extrapolate the component's
percentage to whole-model decode or count it toward the30TG goal yet.

## Private model integration prepared

The [integration generator](../tools/prepare-q2-hc-scalar-model.py) copies the
retained1028-file provider and changes only executor.cpp, kernels.hpp,
kernels.hip.cpp and one new include. The include is byte-identical to the
qualified component. All1029 resulting source files reconstruct from the
saved patch; the original provider is unchanged. The scalar eligibility
requires n_tokens1, original F16 down/up matrices at2560/320/four streams,
F32 or absent injection, F32 normalized inputs and `!MatrixRows(n_tokens)`.
That last condition excludes the single-logit head inside a prefill phase,
which originally uses the matrix path and its existing arithmetic.

The up Dense launch is skipped only for that eligibility. The fused call
occurs after the existing input-cache invalidations and leaves the existing
ten-part injection bookkeeping intact. No allocation, stream, model state,
C ABI or metrics change is introduced. Existing wide-prefill optimizations
and their inherited task-quality limitation remain as documented.

The complete original CMake Release target, including its own unchanged MMQ,
builds locally with the frozen counting harness; configure/build exit0.
Executor object relocation references the new launcher. No retained control
is rebuilt. [Source](../config/q2-hc-scalar-model-source.json),
[build identities](../config/q2-hc-scalar-model-build.json).
The next .157 window admits only this new original-Q22048/tg128 process,
one warmup and three measured sessions, using saved parent/control results.
The model result is pending; component speed is not model throughput.
