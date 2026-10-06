<!-- SPDX-License-Identifier: MIT -->
# HC final-scale ownership compiler probe

The [private include](../../experiments/q2-hc-norm-owner-draft.inc) derives the
ordinary `HcCombineF32HalfKernel` and half-input
`HcCombineMoeHalfDeferredNormKernel` from this repository's retained
`ssm-fixed-bounds` provider. Its official Gufo lineage remains independently
fetched pin `f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, with MIT notices intact.
No sibling CachyOS or foreign DS4 source, artifact, model or cache is imported.

LIE changes only final scale ownership: four CTA threads finish the original
four ordered totals and floating division/rsqrt, write separate16-byte LDS
storage, then publish through one added barrier. Source arithmetic and the
original partial storage remain. No production dispatch, executor lifetime,
stream, persistent allocation or public C17 contract changes.

[Generator](../../tools/prepare-q2-hc-norm-owner-draft.py),
[source manifest](../../config/q2-hc-norm-owner-draft.json) and
[static audit](../../config/q2-hc-norm-owner-draft-static.json) pin the parent
inventory and generated source. Compilation preserves all162 production
bodies/resources. Both new probes use65 instead of84 VGPRs, zero private
bytes,16 more LDS bytes and one additional barrier. Compiler occupancy stays16.
These are static facts, not performance, numerical equality or quality evidence.

Full guarded residual/scales/F32/F16 output and complete-cycle timing on .157
must precede any isolated model trial. All experiments and failed commands
remain retained; qualified parent binaries and controls are not rebuilt/run.
[Current qualification boundary](../../docs/Q2-HC-TARGET-CANDIDATES.md).
