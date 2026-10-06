<!-- SPDX-License-Identifier: MIT -->
# HC up short accumulation chain

The retained fixed result remains **1587.893545 PP / 25.12414406 TG** against
the unchanged UD **1685.777092 PP / 24.34174251 TG**. The previous whole640
integration regressed to1576.766972 PP. The component now completes on .157
with safe finite outputs and all independent formula checks passing. Its
completed wall times improve; original-model performance remains unmeasured.

## Collected component result

All468 independent reports pass (234 per arm), with candidate mixed-output
relative RMS at most1.6932891e-6 and peak-scaled error2.0759471e-6 against the
unchanged2e-5 limits. Complete mixed outputs differ by at most8.9406967e-8;
232/232 enabled injection comparisons are exact. F16 copies differ where
changed F32 rounding crosses a half boundary, maximum2.44140625e-4.
The explicit exactness rejection remains exit1, following build exits0,0.
It is not a memory/device failure or an independent formula rejection.

| Path | Parent completed wall us | Candidate completed wall us | Time change |
|---|---:|---:|---:|
| Ordinary | 1358.049500 | 1279.984950 | -5.7483% |
| Deferred normalization | 1396.577300 | 1300.389388 | -6.8874% |

These are means of the five original measured wall samples per arm, including
HIP launch and completion overhead. Every candidate sample is below every
parent sample in its path. All28 HIP-event values are invalid zeros; no GPU
event aggregate or kernel-only speed claim is made. The first analysis
explicitly rejected those zeros; its failure is preserved. The final report
keeps event aggregates null and wall observations in separate fields, without
substitution. All raw samples remain in the
[component report](../config/q2-hc-up-short-chain-results.json).

All68 component and7 host artifacts collect before20:15:48.994636UTC release
79baceee.1692 recorded process identities and1350 groups are absent, KFD is
empty and original leases/model stat identities are unchanged. No retained
model reference or already qualified component is rerun.

## Private original-model candidate

A separate1029-file provider connects the exact measured ordinary/deferred
bodies to the existing original-F16 executor branches. The two call targets,
their declarations and a private include are the only changed parent files;
all166 device bodies/resources are instruction-exact to the measured probe.
Scalar, small-shape and raw-Q8 branches are unchanged. No device allocation,
stream, public ABI, scheduler or resource-accounting contract changes.

The model plan retains the exact2048 input, capacity9216, chunk2048,128 output
tokens/127 timed decode calls, C1/MTPoff, one warmup, three measured sessions
and15s cooldown outside timing. It runs only the new candidate, with saved
Q2/UD/best-parent controls. Finite numerical differences and task quality are
separate from throughput. Original-weight results are pending.

## Why this path

The [saved-profile reassessment](../config/q2-hc-focus-reassessment.json)
binds the historical Q2 diagnostic trace at1571 PP and the historical UD trace
to the same physical2048-token input. It separates generic F16 projections
from HC up, and includes deferred-normalization HC up and half-output HC down.
Earlier raw profiles and reports are preserved.

| Kernel family | Saved Q2 GPU ms | Saved UD GPU ms | Difference ms |
|---|---:|---:|---:|
| HC down | 89.376337 | 40.902157 | +48.474180 |
| HC up | 85.327322 | 55.498440 | +29.828882 |
| Packing | 25.107216 | 6.916515 | +18.190701 |
| HC injection epilogues | 39.551355 | 24.933282 | +14.618073 |
| Ordinary HC combine | 73.714882 | 61.269555 | +12.445327 |
| Expert gate/up | 239.499759 | 241.982604 | -2.482845 |
| Expert down | 161.558060 | 194.073296 | -32.515236 |
| SSM projection | 160.217893 | 163.133309 | -2.915416 |

[All families](figures/q2-hc-focus-reassessment.csv) reconcile the two saved
traces. These noncontemporaneous profiles guide investigation; their deltas
are not a causal decomposition of the current74.889015ms fixed-reference gap.
The HC-down whole-row candidate already has negative evidence and is not rerun.
Installed FETCH_SIZE counters failed calibration, so they do not establish a
bandwidth bottleneck and are not silently rescaled.

## Mechanism and arithmetic

For original-F16 HC up, K=320 contains only20 K16 operations. The retained
256x128 tile uses512 threads: paired waves independently accumulate the ten
low and ten high fragments and add their F32 sums. The private candidate
uses256 threads and one ascending20-operation chain. Original weight bits,
input conversions, sigmoid, four-stream mixing, injection, allocation,
streams and scalar decode stay as in the retained source. Both ordinary and
deferred-normalization paths are included.

The changed FP32 reduction order is deliberate. Exact agreement is recorded
separately from the independent formula test with its existing2e-5 relative
RMS and peak-scaled limits. A finite disagreement does not suppress timings.
Unwritten/nonfinite outputs, guard corruption or device errors stop GPU work.

The first unphased draft compiles but spills68/292 bytes per thread for the
ordinary/deferred paths. The selected phased draft bounds operand lifetime
with compiler scheduling barriers: both paths have248 VGPR,24KiB LDS and
zero private scratch. Final block barriers decrease24 to16; the K loop keeps20.
All164 original device bodies and their resources remain exact in both
compiler probes. Compiler occupancy annotations do not measure GPU occupancy.

Two separate SSM resident-tile drafts are preserved as compiler-only probes.
The fenced32KiB version compiles without scratch and with158 actual VGPR;
it combines previously explored ingredients and has no runtime qualification.
Neither SSM draft belongs to the HC-up GPU plan.

## Component boundary

The new fixture covers twelve ordinary/deferred cases:96,97,129,2049 rows,
tiny values, cancellation, repeated rows, optional outputs and full2048 timing.
Timed weights rotate across16 independent matrices,100MiB total. Each arm has
16 distinct output states. Two warmups and five measured repetitions alternate
arm order; GPU events measure complete up/mix plus unchanged injection.

Every actual timed buffer is read and checked before it can be overwritten.
All outputs are compared, and independent FP64 dot/sigmoid/mixing/injection
samples cover token and channel boundaries. Inputs must remain unchanged,
disabled outputs retain poison and every enabled value must be finite/written.
All28 timings,702 complete-buffer pair reports and468 formula reports are
retained, including finite failures. Representative full buffers are saved.
Exit1 denotes a completed finite comparison failure; exit2 denotes an unsafe
or incomplete run. Neither is relabeled as a pass.

The frozen component plan follows actual .15739/39 Debug and39/39 ASan/UBSan
qualification (six command exits0, seven collected artifacts),
then a fresh lease/registry/process/KFD/model-stat admission. Collect and
publish closure before analysis. No model control, Q4 or full curve is rerun.
The exact2048/TG128 model contract remains unchanged; model integration and
its original-weight trial require a separate frozen plan.

Source and compiler bindings: [static report](../config/q2-hc-up-short-chain-static.json).
Provenance: [private drafts](../third_party/gufo/LIE-Q2-HC-UP-SHORT-CHAIN.md).
