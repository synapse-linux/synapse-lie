<!-- SPDX-License-Identifier: MIT -->
# Private HC-up and SSM compiler drafts

The four `experiments/q2-{hc-up-short-chain*,ssm-resident*}-draft.inc` files
derive from LIE's retained original-F16/Q2 provider, whose manifest is
`config/q2-iq2-fixed-bounds-source.json` (1028 files, SHA256
`2e81463dbbe134190c300f2b008684d584f0d75f60f36f16eb25b765c2c4b45c`).
That provider originates from independently fetched official MIT Gufo at
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, plus the recorded first-party
changes. The original Gufo license and third-party notices remain applicable.
No sibling-workspace code, DS4 artifacts or model data is imported.

First-party MIT generators extract the retained templates into private names.
HC up changes only its short FP32 reduction topology and operand lifetime;
SSM combines row128, compact transpose and phased operands as a separate
compiler hypothesis. The static report binds every draft, command and assembly,
verifying all164 original device bodies/resources remain unchanged.

The new HIP fixture and Python/CMake tooling are first-party MIT. The fixture
uses the retained provider directly as its in-process operator control, plus
an independent FP64 formula. No production model dispatch or public C ABI is
changed by these drafts. Local object compilation is not GPU correctness,
original-weight inference, occupancy or performance evidence.
