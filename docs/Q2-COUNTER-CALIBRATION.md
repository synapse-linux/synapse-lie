<!-- SPDX-License-Identifier: MIT -->
# Synthetic GPU counter calibration

This campaign checks profiler measurements on .157 before diagnosing the saved
Q2 model. It does not load models, change numerical inference or add PP/TG
samples. The retained result remains1585.308983/25.16079073; fixedQ2 and UD
controls remain unchanged.

The [plan](../config/q2-counter-calibration-plan.json) binds105 fixture files,
four installed profiler file/library identities and the existing .157 ownership
protocol. The standalone HIP fixture has16384 threads in256-thread blocks,
explicit wave32 compilation and512 expected waves. It verifies all16384 output
words and64 guard words for each of ten repetitions. Its memory control reads
256MiB of deterministic mixed uint32 values with coalesced uint4 loads and
defined unsigned accumulation, beyond the32MiB shared cache. Complete expected
output is calculated independently by a host scatter over the input vectors.
This CPU calculation is synthetic fixture validation, not model inference.

After compilation, two unprofiled output controls precede three profiler runs:

| Pass | Kernel | Metrics | Predeclared check |
| --- | --- | --- | --- |
| waves | Small deterministic integer kernel | SQ_WAVES_sum | Every one of ten dispatches equals512. |
| mixed | Same kernel | SQ_WAVES_sum, GRBM_COUNT | Waves still512 on every dispatch; finite positive clock counts. |
| fetch |256MiB read/reduction | FETCH_SIZE | All ten values within5% of262144KiB. |

Each profiled run repeats the complete output and guard checks. CSV and JSON
outputs, per-dispatch values, logs and actual exits are preserved. A successful
profiler exit alone does not qualify its counts. A calibration failure remains
evidence and does not cause a corrected factor, counter-definition edit or
runtime upgrade. Passing qualifies these controls and counter combinations;
it does not establish all derived metrics, DRAM bandwidth or a model bottleneck.

Fresh host qualification on .157 completes at2026-10-06T00:54:41UTC:31 Debug
and31 ASan/UBSan tests pass, six commands exit0 and seven artifacts verify.
The new path uses the existing process/group/thermal supervisor and four
original leases. Invalid source variants, flags, changed fixture/installation
and missing admission are rejected by focused host checks. GPU execution still
requires its own fresh admission after compact-LDS releasea47f405b.

The source is MIT and independent of the official ROCm reproducer; the
[preceding audit](Q2-RETAINED-COUNTERS.md) records its diagnostic motivation and
upstream references. Provider source is packaged by the existing qualification
launcher but is neither compiled nor called by this standalone fixture.

Prepared state: GPU build and calibration are pending. No performance gain is
claimed. No saved reference is rebuilt or rerun; no cleanup occurs on .157.
