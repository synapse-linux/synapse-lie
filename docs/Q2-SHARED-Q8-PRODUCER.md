<!-- SPDX-License-Identifier: MIT -->
# Raw-HC producer for shared Q8 prefill

This isolated experiment derives from the exact mixed-Q2 source behind the
fixed1443.672867 PP / UD1685.777092 comparison. It enables the already existing
tiled-Q8 output in the raw-HC F16 GEMM epilogue for the FFN mixer only. The
shared gate/up immediately consumes that same tile. No device kernel body or
numerical formula changes; the old raw-HC entry remains intact as a control.
[Source identity](../config/q2-shared-q8-producer-source.json),
[patch](../experiments/q2-shared-q8-producer.patch).
[Frozen component plan](../config/q2-shared-q8-producer-plan.json),
[host qualification](../config/q2-shared-q8-producer-host-results.json).

The executor invalidates the existing half/Q8 cache before rewriting mixed
rows and publishes both identities only after the new launch path succeeds.
It uses the same stream and bounded allocated buffers. Other raw-HC callers,
including attention, narrow/decode and MTP, keep the default existing path.
The retained norm-fixed candidate is not automatically composed here.

## Bounded component protocol

One directly compiled fixture contains the unchanged reference producer plus
separate quantization and the new producer. Controls and candidate share one
binary; they are not rebuilt between samples. At2048, measure reference before,
candidate and reference after in each of15 repetitions, after warming both
paths. Rotate16 complete HC/shared weight sets, exceeding the32MiB MALL.
HIP events cover all queued work, including intervening launch gaps, and
exclude allocation, input generation, warmup, readback and verification.

Record both producer time and the complete cycle: raw-HC mix/inject/F16/Q8,
shared Q8 gate/up, SwiGLU to private F16, and shared down. Producer-only timing
cannot establish a complete-cycle gain. These are synthetic GPU component
measurements, not original-weight model throughput or a changed model baseline.

Whole mixed/F16/Q8/inject/gate/up/SwiGLU/down buffers must match byte for byte,
including padding and output guards, on96/97/127/129/2048 rows. Cases include
all-zero and small unsaturated inputs, disabled half/inject outputs and a
nondefault stream. An independent scalar Q8 format oracle checks every live
scale and code, including inactive padded bytes. Existing independent HC
projection/mix checks retain their2e-5 RMS/scaled-maximum limits. Invalid shape,
null weight/Q8 and missing inject output requests must launch nothing and
preserve output. Original inputs must remain unchanged.

Before a fixed-point model experiment, require exact outputs and passing
independent checks, positive complete-cycle median savings against both
controls and at least12 of15 per-repetition wins against both controls.
Producer medians must also improve against both controls. All samples and
failures remain visible. A marginal result is preserved rather than deleted;
no full context curve is admitted until fixed-point UD parity.

Whole control-binary replay for model tests still needs its qualified source,
binary and shared-library identity contract. This component avoids repeated
control compilation through its shared fixture; it does not claim that the
model replay launcher is implemented. GPU execution still requires a new
coordinated four-lease admission after Debug/ASan host checks on `.157`.
