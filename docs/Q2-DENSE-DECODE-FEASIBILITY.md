<!-- SPDX-License-Identifier: MIT -->
# Dense Q8 traffic and bounded representation screen

The active C1 target is at least30 token/s. The saved native32K warm interval
is38.606–38.681ms, so the complete step needs at least5.27–5.35ms less work.
An older profiled 2048-token source assigned261.537ms of533.881ms device
kernel time over15 decode calls to Q8-weight/Q8-activation GEMV (49%). Those
device times are from an older executable, not a current128K attribution.
The current synthetic large plain projection reads44.56MB in about195µs,
roughly228GB/s of logical weight bytes. Reducing scalar instructions alone
did not materially speed this projection.

The original .157 Q2 GGUF directory reports337 `Q8_0` tensors occupying
3,896,606,720 bytes. The largest families are 1,002,700,800 bytes in36
attention QKV tensors, 675,430,400 bytes in the vocabulary output,
601,620,480 bytes each in36 attention gate and36 SSM output tensors, and
434,503,680 bytes in13 attention query tensors. This is encoded storage, not
a measured memory-controller transfer count or per-step required traffic.

Two read-only probes use the independently fetched Gufo GGUF parser at pin
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`. They check all five recorded
model stat fields and empty KFD before and after, read at most12.75MiB and
3.1875MiB respectively from four representative Q8 tensors, and neither
hashes nor rewrites the model. The scripts live in
[`tools/q2-dense-q8-sample.py`](../tools/q2-dense-q8-sample.py) and
[`tools/q2-dense-q8-requant-probe.py`](../tools/q2-dense-q8-requant-probe.py).
Both pass local Python syntax and synthetic block checks; the remote copies
match the local script SHA-256 values. The recorded commands exit0.

| Sampled tensor | Marginal code entropy, bits/code | Minimum range width for every sampled 32-code block | Q6 extra weight RMS |
| --- | ---: | ---: | ---: |
| Output |7.6529|8|2.262%|
| Attention QKV, layer0 |7.6121|8|2.525%|
| Attention gate, layer0 |7.6361|8|2.364%|
| SSM output, layer0 |7.5447|8|2.619%|

Each entropy/width observation covers98,304 blocks per tensor, from three
separated ranges. A hypothetical per-block range codec that stores a minimum,
width and the original F16 scale cannot shrink any of those sampled blocks:
every block needs eight code bits; falling back to the original34-byte block
is cheaper. Marginal entropy suggests limited gain from simple independent-code
entropy coding, but does **not** bound a codec that exploits cross-code or
cross-block correlations. This weight-only screen did not time a compressed
GPU kernel; the later private Q5 component is reported below.

The separate narrower-format screen uses24,576 blocks per tensor and a
symmetric signed per-32 maximum with nearest-even codes and an F16-rounded
scale. It measures **weight-domain error only** against the present Q8 bytes.
Q5, Q6 and Q7 would use22,26 and30 bytes per32 weights, respectively, versus
34 now. Across these four samples, Q5 relative RMS is4.67–5.38%, Q6 is
2.26–2.62%, and Q7 is1.13–1.35%. These are not model logits, task quality,
or performance evidence. The chosen quantizer is only one possible design.

Even an ideal Q6 representation would cut the 3.897GB of encoded Q8 weights
by at most0.917GB if every Q8 tensor were converted. At228GB/s that is about
4.02ms of ideal traffic time per complete read, before unpacking cost and
without proving every byte is read on each step. The native32K target needs
more than5.27ms. Thus Q6 alone cannot be credited as a30-token/s solution;
it would require a measured kernel gain plus another stage improvement and an
independent model-quality gate. Q5 has a larger theoretical byte saving but
roughly twice Q6's sampled weight error. No representation is promoted.

[Exact aggregate Q8 sample](../config/q2-dense-q8-sample.json) and
[narrow-format precision screen](../config/q2-dense-q8-requant-probe.json)
preserve the complete bounded results. The cold-prefill priority remains the
complete routed-expert chain, which these weight-only samples do not address.

## Private Q5 decoder gate

A private one-token Q5_0 kernel now uses the pinned provider's existing
`vec_dot_q5_0_q8_1` arithmetic. The synthetic fixture packs equal-effective-
weight Q8_0 and Q5_0 matrices, rotates more than 48 MiB of each arm's encoded
weights and compares independent guarded outputs on active dense shapes. It
does not convert or load the original model or change production dispatch.
The local gfx1151 HIP build passes. Static metadata reports 14/20 VGPR for
plain/gated retained Q8 versus 36/60 for private Q5, with zero spill and
private scratch in all four kernels. The Q5 decoder therefore has a concrete
unpacking/occupancy cost to measure against its smaller weight traffic.
[Source](../config/q2-decode-q5-source.json),
[static resources](../config/q2-decode-q5-static.json).

The first coordinated .157 component stops at the first tiny shape, before
any timed case, with exit2 from its independent FP64 oracle. The Q8 arm passes;
the Q5 arm was compared to the wrong reference formula. `Q8_1.s` holds an
F16-rounded activation sum, while the Q5 helper subtracts that stored sum;
the first fixture oracle subtracted the exact integer sum times `Q8_1.d`.
A deterministic CPU replay of the tiny inputs gives about 2.12e-4 relative
RMS between those formulas, beyond the fixture's 2e-5 operator tolerance.
This explains a plausible false rejection but does not prove the GPU output:
the failed run did not preserve its Q5 values. The source now computes the
Q5 reference from the encoded `Q8_1.s` and will need a distinct GPU window.
The failed exit, stdout/stderr hashes and complete release are retained in
[r1 failure evidence](../config/q2-decode-q5-r1-failure.json). Release
verifies empty KFD, all five original leases free, seven unchanged model stat
tuples and no remote cleanup. That first run has no Q5 speed result.

The corrected r2 component runs to completion under a separate .157 window.
It uses the exact same gfx1151 device image as r1; only the host oracle changes.
All six shapes pass, including 60 independent FP64 row-oracle records, 30
whole-output pair diagnostics and 56 interleaved timing records. The maximum
sampled operator error against its encoded-format oracle is 1.37e-7 relative
RMS. Equal-effective-weight Q8/Q5 whole outputs differ by at most 4.81e-4
RMS because the Q5 path uses the stored F16 `Q8_1.s` correction. That
difference is a component arithmetic observation, not a model-quality score.

All 56 HIP event durations are invalid zero. These are medians of five
**completed host-wall** samples per arm after two warmups, with at least 64
distinct guarded output destinations per sample. Each timed arm rotates more
than 48 MiB of its own encoded weights, above the 32 MiB gfx1151 Infinity
Cache listed in [AMD's ROCm specifications](https://rocm.docs.amd.com/en/latest/reference/gpu-specs.html).
The same original synthetic inputs and effective weights reach both arms.

| One-token dense component | Retained Q8 µs | Private Q5 µs | Q5 time change |
| --- | ---: | ---: | ---: |
| SSM input, 16384×2560 |195.579|126.203|−35.472%|
| Attention output, 2560×6144 |75.575|50.069|−33.749%|
| Shared down, 2560×640 |11.068|8.738|−21.050%|
| Gated, 640×2560 |18.629|13.162|−29.345%|

The five paired measured repetitions stay negative on all four shapes.
The [validated result](../config/q2-decode-q5-r2-results.json) retains each
paired change and the raw evidence hashes. Release
`6e6a7bc62d447edb7031cfa2b88f35680143c284be9e1f5f243435858671d940`
is the verified latest .157 registry event after this window: 1,954 retired
identities and 1,560 groups, empty KFD, five free original leases, seven
unchanged model stat tuples, no cleanup.

This establishes a **component** speed benefit from fewer encoded weight
bytes on gfx1151 despite the higher Q5 register count. It does not establish
whole-C1 30 token/s, any cold-prefill gain or safe Q5 re-quantization of the
original model. The immediate next gate is a bounded family-selective test
with real Q8 weights and saved activations, preserving the original GGUF and
separating quantization error from decoder arithmetic. Any opt-in model arm
then needs original-input numerical/task-quality and native C1 measurements
before production dispatch changes.

## Decode-only overlay: original-model trial rejects shared-down Q5

The next private provider variant keeps every original Q8_0 device tensor for
the unchanged batched prefill path. At load it can additionally encode Q5_0
device overlays for one explicitly selected dense family; only one-token
decode dispatches use those overlays. The original GGUF is read as before and
is never rewritten. The default, with no opt-in, uses the original Q8 path.
`LIE_EXPERIMENTAL_Q5_DECODE` accepts `ssm-in`, `attn-out`, `shared-down`,
`shared-gated`, or `all` (these four families). This is a private experiment,
not a supported server setting or a promoted model format.

The [reconstructible patch](../experiments/q2-q5-decode-overlay.patch)
changes only the private provider's device upload, one-token dense dispatch
and pinned MMQ numerical tier. Applying it with zero fuzz reproduces all six
candidate source files from the previous private provider. Local gfx1151
builds of the conversion fixture, model fixture and original C17 direct
benchmark exit 0; [source and binary hashes](../config/q2-decode-q5-overlay-source.json)
are frozen. The coordinated `.157` guarded converter/oracle fixture also exits
0 on 257 by 2560 synthetic Q8 weights: Q8-to-Q5 weight relative RMS is
3.1859%, while the Q5 decode kernel differs from an independent FP64 oracle
by 1.513e-7 relative RMS. The latter measures decoder arithmetic against its
*quantized* operands, not preservation of original-model logits. The
[result and raw evidence hashes](../config/q2-q5-overlay-converter-results.json)
record empty KFD, five free original leases, seven unchanged model stat tuples
and no remote cleanup at release. That fixture is not an original-model
performance or quality result.

The [read-only GGUF header inventory](../config/q2-context-header-audit.json)
confirms that the original antirez Q2 checkpoint contains **no Q5 tensors**:
337 tensors are `Q8_0`, 96 are `IQ2_XXS` and 48 are `Q2_K`. This Q5 overlay
was a private, lossy re-quantization of selected original `Q8_0` weights in
device memory, not support for an existing format in the original model.

A coordinated original-model `shared-down` trial uses the unchanged exact
2048-token counting input, context 9216, chunk 2048, greedy output 128 and
127 timed decode calls in both arms. The same frozen binary runs default Q8
then opt-in Q5, each with one warmup and three measured sessions. Both arms
exit 0 and reproduce the saved physical input hash. Q8 median decode is
25.611559 calls/s; Q5 median is 25.636525, a **0.0975%** rate change. All
four prefill-logit arrays and generated 128-token sequences are byte-identical
between arms. Final logits differ by **7.7198% relative RMS** in every
session. This is insufficient for the 30 token/s C1 target and does not
establish task quality; the direct-executor 2K result is also not a native
32K C1 measurement. The original Q8 production path remains selected.
[Full samples, numerical checks and raw hashes](../config/q2-q5-model-shared-down-results.json).

The model window released at 09:59:15 UTC with two command exits 0, 42 saved
model files verified before release, empty KFD, five original leases free,
seven original model stat tuples unchanged and no remote cleanup. Further
lossy Q5 overlay trials are stopped. The decode track returns to the native
`Q8_0`, `IQ2_XXS` and `Q2_K` paths; the complete 128K cold prefill target
remains unproven.
