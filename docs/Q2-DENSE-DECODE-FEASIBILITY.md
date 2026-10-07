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
cross-block correlations. No compressed GPU kernel was built or timed.

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
preserve the complete bounded results. The next GPU experiment should first
prove that a chosen compressed decoder saves time with production memory
placement and rotated weights; original-model output and quality qualification
must precede any serving change. The cold-prefill priority remains the complete
routed-expert chain, which these weight-only samples do not address.

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
tuples and no remote cleanup. There is no Q5 speed or model-quality result yet.
