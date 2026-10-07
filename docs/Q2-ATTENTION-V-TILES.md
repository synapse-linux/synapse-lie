<!-- SPDX-License-Identifier: MIT -->
# Transient value tiles for prefill attention

The retained original-128K trace attributes 11.668 seconds to attention.
Its mean chunk cost rises from 137.166 ms in the first quarter to 211.019 ms
in the last. The sparse WMMA kernel reads one value key per lane so that its
LDS transpose remains conflict-free; those global reads are strided.

This component keeps the exact encoded half bits but packs values into
`[KV head][16-dimension slice][context token][16]` temporary storage. Four
adjacent selected keys then occupy one 128-byte segment. It changes only
the value-load addresses; sorted selections, query/key computation, softmax,
PV accumulation, gating, early/late prefetch and thread geometry remain.
It does not change precision, the persistent KV layout or the decode path.

The full existing context is copied on every candidate call. Both this copy
and attention are inside the complete timer; consumer-only time is secondary.
Temporary storage is one value-cache payload for the current layer, about
126 MiB at the timed 128K shape. Any future engine integration must account
for its allocation, reuse and lifetime. No persistent second KV cache or
incremental-update shortcut is assumed in this trial.

The earlier V-staging trial only changed early/late prefetch and was negative.
This candidate changes global layout while keeping the retained early/late
dispatch. It is also distinct from the rejected selector-key tiling experiment.
Neither older trial is rerun or promoted.

The synthetic fixture uses full 2048-row shapes at start positions 28672 and
126976, plus untimed real 1901-row and small allocation-boundary tails.
Six measured pairs have balanced order after two warmups. Both timing scopes,
every complete output comparison, guards, all input/packed bytes and sampled
independent FP64 errors are retained. Finite differences preserve timings
and return exit 1; unsafe outputs stop with exit 2. The previous 0.01 absolute
operator limit is unchanged. Passing this fixture is not model-quality proof.
Synthetic masks are not claimed to reproduce the original model's selections.

Local compilation succeeds. Both original control functions are byte-exact
to retained R3; early/late kernels use the same 231/223 VGPRs and zero private
scratch in both arms. Their function sizes are unchanged. The packing kernel
uses 9 VGPRs and zero scratch. This establishes no performance improvement.

All 1032 parent provider files verify against the retained manifest. The
control and derived candidate preserve Gufo's MIT notice and independent
upstream pin f783fedb9bea2ec7de941f6da4e02f4a4596b29e. No DS4 source is used.

At preparation, GPU execution is pending fresh .157 coordination and CPU
window checks. No production dispatch or model reference changes. New work
prioritizes prefill; beneficial decode-only changes remain retained separately.

[Source binding](../config/q2-attention-v-tiles-source.json),
[device audit](../config/q2-attention-v-tiles-static.json),
[candidate](../experiments/q2-attention-v-tiles.inc),
[fixture](../tests/q2_attention_v_tiles.hip).

## Measured full-context layout: rejected

The .157 component exits 0, with all 18 full-output pairs exact and all eight
independent FP64 checks passing (maximum absolute error 4.101635e-6).
Every packed/input byte and guard check passes. Six measured pairs per depth
all regress, in both run orders. HIP event intervals are positive.

| Shape | Original complete, ms | Packed complete, ms | Packing, ms | Candidate attention alone, ms | Complete latency change |
|---|---:|---:|---:|---:|---:|
| full32 | 23.878620 | 29.545492 | 0.505534 | 29.039958 | +23.731992% |
| full128 | 42.893054 | 57.380795 | 1.546260 | 55.834536 | +33.776427% |

These are component arithmetic means, not new model throughput references.
The packing-free consumer is also slower, so copy overhead alone does not
explain the result. No model integration or full-model trial follows.
[All warmup/measured pairs](../config/q2-attention-v-tiles-results.json).

Source e1f58fb9 and plan 32c7fbed; CPU fixture/verify/admit/run/release all 0.
All 36 artifacts (891525 bytes) verify at 20:51:09 UTC before release at
20:51:33, SHA 2a4264681b27fa1fd4277d00393e1239c1631ea9e85a4132ef61eeb0605e5e34.
Independent 20:52:41 closure checks registry, 19 identities including the
supervisor/groups, KFD, five leases and seven model stats. Core/GLM receive
closure; no Q2 reservation remains.

## Bounded four-key refinement

A distinct follow-up keeps the four keys of each sparse selection block
together: `[four-key block][KV head][slice16][key in block][16]`. It preserves
128-byte slice segments without placing each dimension slice an entire
context apart. Improved cache/page locality is a hypothesis, not a measured
cause of the earlier regression.

The full-context copy remains inside the timer; this is not an incremental
cache shortcut. The last block is padded to four rows in temporary storage
only, with checked zero padding and no invented prompt tokens or arithmetic
changes. Original KV operands still end at their actual allocation boundary.
Its GPU result and model qualification are pending separate admission.
