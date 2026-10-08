<!-- SPDX-License-Identifier: MIT -->
# Bounded sparse attention capacity correction

Official Gufo is independently fetched at
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`. Both private providers derive from
the recorded `config/q2-curve256-headroom-source.json` compositions, preserving
their original MIT license and notices. No sibling CachyOS or DS4 project code,
artifact, build or model is imported.

`experiments/q2-attention-capacity-{q2,ud}.patch` changes only the sparse WMMA
mask capacity/scan/launch guard in
`src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp` and adds the
first-party C17 `lie_q2_attention_capacity.h`. The common compact-list limit
and all floating arithmetic remain unchanged. The complete inventories,
parent identities, patches and generator hashes are in
`config/q2-attention-capacity-source.json`.

The first-party GPU fixture includes the original Gufo
`tests/models/qwen38_flash_next/attention_ops_test.cpp` with its main renamed,
reusing its unmodified FP64 formula and allocation/input helpers. Its original
test main is not executed. The new cases, guards, launch rejection checks and
timing loop are MIT first-party work. It also compiles the candidate numerical
file directly, as the other isolated operator fixtures do.

Only local compilation/static evidence exists at preparation. The original
parent is not rebuilt or rerun. Host checks, GPU/operator results and
original-model quality/speed must remain distinct. No public ABI, persistent
state or metric-schema change is introduced.
