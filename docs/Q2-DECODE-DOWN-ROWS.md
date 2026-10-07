<!-- SPDX-License-Identifier: MIT -->
# Reuse native Q2_K decode inputs across more output rows

## Completed component: retain four rows for model evaluation

| Rows per wave | Median complete cycle us | Change versus two rows |
|---|---:|---:|
| Original2 |49.80915625|0%|
| Candidate4 |46.34237500|-6.960128%|
| Candidate8 |65.60171875|+31.706143%|

All five measured rotations favor four rows and reject eight rows. These
durations include the original activation quantizer and down projection,
64 graph calls with82.575MB rotating weights. They are not model token rates.
The retained model binary is unchanged. The next model candidate should use
four rows only in the qualified single-token, non-prefill Q2_K down operation.
Do not extrapolate this6.96% component reduction to whole-model decode.

The original numerical expressions do not guarantee exact compiled rounding:
898 of906 full output comparisons differ. All1359 independent FP64 checks
pass the unchanged0.002 limit; maximum relative RMS9.21618842429e-8.
In the64 preserved four-row buffer pairs,1837 of1638400 cells differ,
maximum absolute2.98023223877e-8 and relative L2 2.12964639998e-9.
The differences are real; they are not an oracle failure. They establish
neither task degradation nor unchanged model quality. No weights or
intermediate storage format is reduced. Actual component exit1 is preserved,
and all performance measurements complete despite that exact-replay failure.

Every timed replay is checked before its buffer is reused. Failed-output
filenames identify input step/arm but not repetition: the saved buffers are
the final pair for each step, not all repeated failure frontiers. The complete
906 replay decisions and1359 numerical reports survive in stdout. A future
fixture revision should add repetition to failed-output filenames.

CPU success/failure fixtures, preflight and admission pass. The component
finishes13:51:19.260631UTC with no thermal stop, CPU/GPU peaks41/45C.
All284 artifacts collect/hash before release13:53:01.034806UTC, SHA
9954b78f2c76846bed0074ba73cf02ca1898429efd9916bb751d6db2bbdc4e25.
Latest registry matches;1974 identities/1580 groups retired, KFD empty,
five original leases free and seven model stats unchanged. Core receives
closure; no Q2 remote job/client/lease/window/reservation remains.

[Audited result](../config/q2-decode-down-rows-results.json),
[every timing](figures/q2-decode-down-rows-samples.csv),
[frozen plan](../config/q2-decode-down-rows-plan.json),
[analyzer](../tools/analyze-q2-decode-down-rows.py).

The following describes the prepared source and fixture.

The retained scalar Q2_K down launcher computes two output rows per wave.
Q8 and Q5_1 already have wider short-input routes, but Q2_K has no corresponding
specialization. This private component instantiates the original numerical
template for four and eight rows. It retains the source dot, block accumulation,
descending wave reduction, padded K768/live K640 and negative-ID expressions.
Compiled exact replay is qualified separately, with differences recorded above.
Only row ownership changes. Prefill and model dispatch remain unchanged.

For a single original-model decode step, ten expert slots become two token
groups (eight and two waves). At2560 output rows the original grid has2560
blocks; four/eight-row variants have1280/640. They reuse the same quantized
input across more output rows but spend more registers. This is a mechanism
to measure, not a throughput prediction or a different quantization.

The fixture links the existing qualified MMQ archive directly for the original
quantizer and consumer, without rebuilding it. All83 common device functions
are byte-identical to retained native servera4afb757. Only two new bodies are
added: four rows use78 VGPR; eight rows use104; neither has private scratch.
Common RelWithDebInfo/-O3/fast-math options match. The initial build fails after
formatting reorders a dependent include; that failure remains preserved. A
dependency comment restores the required order; object and link then exit0.

The measured complete cycle includes the native F32-to-Q8_1 input preparation
and Q2_K projection. It rotates128 synthetic experts (82575360 encoded bytes)
over64 calls with distinct output buffers. Two warmups and five three-arm
rotations retain every completed host-wall sample. Every timed output is
checked before reuse, with exact full buffers and guards plus an independent
FP64 formula over the actual encoded weights/quantized inputs. The original
0.002 relative-RMS/peak-scaled limit stays fixed. Ragged rows, one/eight/nine/
ten/eleven slots, inactive IDs, tiny/zero/cancellation inputs are covered.
Finite numerical differences retain timing and failed output files.

Local compilation and static checks are preparation only. The .157 component
used fresh coordination, CPU supervisor checks and its own admission. No
model access, full curve, retained-control rebuild, dependency or cleanup is
part of this experiment. Any later model selection is decode-only at the
qualified shape; other phases and shapes keep the retained path.

[Bound source and static resources](../config/q2-decode-down-rows-source.json).

## Private original-model integration prepared

The1032-file provider derives from retained isolated HC up/mix. It adds the
measured four-row body in a separate HIP file and selects it only outside
prefill for one input token, ten slots, one expert per slot, Q2_K down with
2560 outputs,640 logical/768 stored inputs and512 experts. The entire prefill
body, including one-token tails, retains its old branch. Other shapes/formats
fall through to the retained executor. A one-token verification operation
with identical geometry also qualifies; this is an operation/shape guard,
not a claim to have qualified the whole speculative pipeline.

The wrapper uses the same original MMQ context, pool allocation of11520 bytes,
input quantizer, padded pitch1024, stream and allocation lifetime as the
existing entry. It adds no persistent tensor or new stream. The existing
MMQ archive is reused without rebuild. All333 frozen C17/core files and all
1032 provider files verify. All922 existing device functions remain byte-exact,
and the sole new four-row function is byte-exact to the measured component:
78 VGPR, no scratch. Common RelWithDebInfo settings remain unchanged.

Configure/build and added HIP formatting pass. A single added declaration's
indentation is corrected before the final build and source binding. The shared
provider formatting check retains exit1 on inherited files; its output remains
preserved. Native input/lifetime fixtures and the unchanged130925/8 .157 trial
follow under a separate admission. No model throughput or task-quality result
is established by compilation. Component rounding differences remain explicit.

[Source](../config/q2-decode-down-rows-model-source.json),
[build and instruction audit](../config/q2-decode-down-rows-build.json),
[reconstruction generator](../tools/prepare-q2-decode-down-rows-model.py).
