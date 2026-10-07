<!-- SPDX-License-Identifier: MIT -->
# Original-F16 scalar HC up/mix fusion

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
