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

## Completed component result

The .157 run on2026-10-07 exits0. All517 full-output comparisons are bit-exact
and all1034 independent FP64 checks pass. The maximum relative RMS error is
9.2161884e-8 and scaled maximum1.4727265e-7 against the unchanged0.002 limits.
All guarded outputs, immutable inputs and zero padded codes/scales pass.

| Measured round | Retained four-row cycle, us | Omit padding cycle, us |
|---|---:|---:|
| 2 | 46.196625 | 45.715531 |
| 3 | 46.167859 | 45.922094 |
| 4 | 46.239906 | 45.809750 |
| 5 | 46.104750 | 45.907406 |
| 6 | 45.886625 | 45.413047 |
| 7 | 45.687422 | 45.603344 |
| Mean | 46.047198 | 45.728529 |

The complete quantization/down cycle improves0.692049%, saving0.318669us;
all six pairs favor the candidate. Retain the exact small improvement for
composition, without extrapolating its percentage to model token/s. Original
model validation is still pending; this is not a new prefill/decode reference.
The [bound result](../config/q2-decode-down-live-results.json) contains all
warmup/measured timings and the hash/path of all1568 raw events.

A [single-file model patch](../experiments/q2-decode-down-live-model.patch)
is prepared against the retained provider; `git apply --check` passes. It
preserves the existing non-prefill one-token shape gate, quantizer and pool.
The [patch binding](../config/q2-decode-down-live-model-patch.json) records
both source hashes and the measured result. It has not been applied to the
retained provider or compiled/tested as a model; no new buffers are introduced.

Source5962e2c2, plan21948d04, binary1a1fc05b. CPU fixture/verify/admit/run/release
all exit0. Run19:19:22→19:19:23 UTC; all36 artifacts hash-verify19:21:12 before
release19:23:30.657517 SHA
9343ed9cf3edb63074e13215c80b9905a0f44e7218059169a63c0048c4bb883a.
Fresh19:24:39 closure verifies registry, twelve retired identities/groups plus
supervisor, empty KFD, five free leases and seven unchanged model stats.
No model access, remote build, service, tuning, dependency or cleanup action.
