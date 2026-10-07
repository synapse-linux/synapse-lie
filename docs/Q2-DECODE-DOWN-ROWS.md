<!-- SPDX-License-Identifier: MIT -->
# Reuse native Q2_K decode inputs across more output rows

The retained scalar Q2_K down launcher computes two output rows per wave.
Q8 and Q5_1 already have wider short-input routes, but Q2_K has no corresponding
specialization. This private component instantiates the original numerical
template for four and eight rows. It preserves every dot, block accumulation,
descending wave reduction, padded K768/live K640 and negative-ID behavior.
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
requires fresh coordination, CPU supervisor checks and its own admission. No
model access, full curve, retained-control rebuild, dependency or cleanup is
part of this experiment. Any later model selection is decode-only at the
qualified shape; other phases and shapes keep the retained path.

[Bound source and static resources](../config/q2-decode-down-rows-source.json).
