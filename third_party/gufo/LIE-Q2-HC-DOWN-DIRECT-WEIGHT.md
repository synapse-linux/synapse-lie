<!-- SPDX-License-Identifier: MIT -->
# HC-down direct original-weight loads

The private include derives from retained Q2 source manifest
`config/q2-iq2-fixed-bounds-source.json`, official Gufo lineage
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`. Its HC-down body includes the
previously recorded MIT GSQHalo adaptation at
`5fc881b114c1ea130f5df6a30a98be2f8d397de6`; the original ggml copyright and
full MIT notice remain in the derived include. No new upstream import occurs.

The new first-party generator removes only weight LDS staging, preserves the
original F16 operand bits and two K16 accumulation chains, and adds a private
wrapper. Existing original bodies remain unchanged. The fixture independently
reconstructs FP64 projection/SiLU formulas and checks every output and original
input/weight immutability. New source/tooling carries MIT SPDX markers.

No DS4 or sibling CachyOS source, artifact, cache, model or evidence is imported
or modified. No public ABI, persistent state, metric or scheduler contract changes.
