<!-- SPDX-License-Identifier: MIT -->
# Original-F16 HC up projection and F32 mixer fusion

This experiment passed GPU operators and full-model timing on `.157`. The
original-F16 up/mix fusion reaches **1287.19 prefill tokens/s and 22.95 decode
steps/s** at C1 pp2048/tg128, compared with 1250.82/22.97 for its fresh packed
reference. Prefill improves 2.91%; decode is unchanged within these samples.
The fresh same-window UD control reaches 1682.77/24.30, so Q2/UD parity remains
unmet. The separate scalar HC up vector experiment is in
[Q2-HC-UP-VECTOR.md](Q2-HC-UP-VECTOR.md).

## Measured motivation

The retained packed trace spends 88.353 ms in the 96 raw-F16 HC up projections,
98.070 ms in F32 HC mix/inject epilogues and 74.626 ms across all 289 narrowing
calls. These are marked diagnostic kernel sums, not unprofiled wall timings.
The current path writes a full F32 gate matrix `[tokens][4*2560]`, then reads
it immediately to form `[tokens][2560]` mixed rows. UD already has a fused
projection/mixer for its Q8 weights and F16 normalized streams.

The candidate adapts that official Gufo WMMA epilogue to **original F16 Q2
weights and the existing F32 normalized streams**. It does not select the UD
activation precision or quantize the HC weights. It preserves the two F32
K16 accumulation chains and their final addition, then uses the original ordered
four-stream FMAs, sigmoid and scale. Equality is required by the proposed
arithmetic contract, not assumed from those algebraic expressions.

## Data flow and resource contract

The existing HC down and SiLU/scale calls are unchanged. The low-rank result is
narrowed to the same F16 representation as before, into the unused prefix of
`hc_gate`. The fused up kernel reads those rows and F32 `xn`, writes F32 mixed
rows and their rounded F16 copy into the existing `x_half`, then sets the same
input-cache identity fields used by other producers. Low-rank input and mixed
half output are distinct allocations. All operations use the executor's existing
stream, with the cache invalidated before rewriting mixed rows.

The gate tensor remains allocated for the other dispatches; this candidate
removes its wide-route materialization, not the session's reserved bytes.
It adds no persistent buffer. The original inject dot products, per-part layout
and reduction order run in a specialization of the existing F32 epilogue that
omits gate reads and mixed-row writes. Their cost is not presumed eliminated.

Dispatch is restricted to original F16 down/up weights, HC streams=4,
hidden=2560, rank=320, at least 96 tokens within the existing scratch capacity,
and F32/absent injection. Other shapes, formats and scalar decode retain their
existing dispatch. The internal API rejects unsupported geometry and missing
required pointers before launching. This is a numerical-kernel experiment;
no C17 core, HTTP, reactive scheduling or KV-cache policy changes are introduced.

## Static iterations

The first 256×128 tile compiled but required 256 VGPRs and 492 private bytes
per work item. Its source and assembly are retained. The prepared 128×64 tile
uses 181 VGPRs, zero private bytes and 18,432 LDS bytes; the existing separate
128×128 HC up kernel uses 256 VGPRs and 84 private bytes. Compiler metadata
does not establish dynamic spill traffic, occupancy or a model speedup.

The smaller tile's mix transpose enables only the threads for its 16 token
rows while every thread still reaches the block barriers. The LDS assertion
now checks the actual allocated pool, including its existing transpose reserve.
No weight or activation accumulation is reordered to obtain the smaller tile.

[Source reconstruction](../config/q2-hc-up-fused-source.json) verifies all 1019
files against the measured packed tree and the generated patch. Official
formatting passes 486 files. Device assembly and host-only fixture/executor
syntax pass. The [static report](../config/q2-hc-up-fused-static.json) preserves
the current resources and earlier tile receipt. These checks run on the editing
host without GPU execution or model access.

## GPU qualification

Seven independent synthetic GPU cases cover 96/97/129/2048 token counts,
ordinary, tiny and alternating inputs, disabled injection and disabled half
output. F32 normalized inputs deliberately contain values not representable
in F16. The reference uses the existing separate raw up, F32 mixer and narrowing
kernels. Complete mixed, half and inject buffers must compare byte for byte.
Full buffers are saved; all outputs have prefix/suffix guards and NaN fill to
detect missing writes. Disabled outputs must stay untouched. Every input is
copied back and checked unchanged.

Sampled FP64 projection/sigmoid/mixing and inject oracles cover every tile and
token/hidden boundary, with the existing HC 0.00002 RMS/error-over-peak limits.
All seven GPU cases pass the independent FP64 checks. Nineteen complete mixed,
half and inject buffers are byte-exact against the existing route, across
13,817,136 compared values. The largest FP64 relative RMS is 7.43e-7 for mix
and 1.20e-7 for inject, below the unchanged 2e-5 thresholds. All commands
exit zero, 42 operator artifacts are hash verified, and the
[operator report](../config/q2-hc-up-fused-operators.json) retains each case.

`tools/analyze-q2-hc-up.py` audits all seven cases and nineteen complete buffer
pairs after collection. It verifies artifact hashes, exact output sizes, finite
values, oracle sample counts, original thresholds and agreement with the actual
process exit. A complete numerical failure produces a report and exit 1;
interrupted runs, missing output, runtime failures or inconsistent verdicts are
refused. Exact equality, changed-value counts, maximum absolute differences and
relative L2 are retained separately for mixed, half and inject outputs.
Five Python CPU reader fixtures pass a focused CTest on `.157` at 12:02:42 UTC,
after R5 terminates and while core prepares R6. Both command exits are zero,
two artifacts are collected/hash verified, and runner/command retirement is
checked. This subsecond fixture opens no model and uses no GPU or C/C++ build;
pre/post KFD observations are empty. Its [receipt](../config/q2-hc-report-host.json)
binds the tested reader and fixture sources.

```sh
python3 tools/analyze-q2-hc-up.py evidence/q2-hc-up-operators-r1 --output config/q2-hc-up-fused-operators.json
```

The `.157` CPU capsule completes 9/9 Debug and 9/9 ASan/UBSan, including five
remote-guard methods covering nine refusal cases. All six commands exit zero;
seven artifacts are collected/hash verified in
[the host receipt](../config/q2-hc-up-fused-host.json). CPU mode explicitly
disables GPU visibility and opens no models. It does not exercise the new HIP
operator. Initial source-generation and local report-summary parsing failures
are retained under `evidence/q2-hc-up-fused-*`; neither is hidden as a runtime pass.

The `.157` GPU jobs used fresh four-lease admission after core returned R7.
The measured commands were:

```sh
python3 tools/q2-remote.py hc-up-operators q2-hc-up-operators-r1 --source-variant hc-up-fused
python3 tools/q2-remote.py q2-bench2k q2-hc-up-reference-r1 --source-variant packed --rebuild-mmq
python3 tools/q2-remote.py q2-bench2k q2-hc-up-model-r1 --source-variant hc-up-fused --rebuild-mmq
```

Both model arms use C1 pp2048/tg128, one warmup plus three measured sessions,
15-second idle outside timing and a complete MMQ rebuild. All 21 saved model
files are byte-exact between arms; all twelve F32 frontiers and token files
match the retained packed checkpoint, and each arm passes nine replay checks.
The [full report](../config/q2-hc-up-fused-results.json) retains every sample,
duration, exit code and thermal maximum. The fused arm peaked at GPU 82 C and
CPU 92.375 C, below the unchanged 98 C inclusive Q2 guard. This isolated 2K
screen does not establish sustained serving, long-context behavior or parity.
