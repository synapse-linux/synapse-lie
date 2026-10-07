<!-- SPDX-License-Identifier: MIT -->

# Q2_K decode: omit known-zero input padding

This isolated candidate derives from the retained four-row Q2_K down kernel.
It targets the original antirez shape:640 live input columns,768 stored weight
columns,1024-column Q8_1 scratch pitch,2560 output rows and ten routed slots.
No model quantization, input quantizer, row grouping, reduction or prefill path
changes. Original model dispatch is not changed by preparing this component.

The original Q2 dot uses16 lane offsets per256-column weight block. Offsets
8..15 read Q8_1 blocks4..7, corresponding to columns128..255 within that block.
For the third physical block these are columns640..767, whose activation codes
and scales the original quantizer writes as zero. A per-lane loop bound omits
only that third block for those offsets; all live products retain their order.
The new body supports this640/768 shape only. Its static assertions restrict
it to non-gated Q2_K with four-row ownership and the original256/16/1 layout.

The fixture compares against the retained four-row kernel, with both complete
quantization-plus-down operations included in the timer. The original saved
MMQ archive is linked without rebuild. Five common device functions, including
the invoked quantizer and four-row control, match the retained model bytes.
The sole new kernel has2880 code bytes and80 VGPRs versus2928/78 for control;
both use zero private scratch. These are static observations, not speedups.

The timed synthetic weight bank is82575360 bytes across128 experts, exceeding
the32MiB MALL. Each graph runs64 calls with varying expert IDs and distinct
output buffers. Two warmup and six measured rounds alternate both arms, with
three first and three second positions each. Every call output is checked
after the pair completes; numerical disagreements retain their actual exit,
timings and separate per-repetition output files. Additional cases cover
ragged2559-row output,1/8/9/11 slots, inactive IDs, tiny values, zeros and
cancellation. Checks include full output comparisons, independent sampled
FP64 dequantization/dots, every padded Q8_1 code/scale, guards and input identity.
The unchanged independent tolerance is0.002; a finite disagreement is not
automatically a task-quality failure and does not suppress performance timing.

Source/static bindings are `config/q2-decode-down-live-{source,static}.json`.
Preparation and compiler logs remain in `evidence/q2-decode-down-live-preparation`.
The first build was never run; its artifacts remain separately after improving
the fixture to preserve every repetition's disagreement file. No production
buffer lifetime or C17 runtime contract changes. GPU execution requires a new
coordinated .157 admission; no model token-rate gain is claimed at preparation.
