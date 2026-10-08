<!-- SPDX-License-Identifier: MIT -->
# Scaled Q2 wave-row experiment provenance

The provider derives from independently fetched official Gufo commit
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, through the retained LIE shared-Q8
pair manifest. No source or artifacts are imported from the sibling CachyOS
workspace or the separately owned DS4 checkout. Upstream MIT notices remain.

`tools/prepare-q2-scaled-wave-pack.py` verifies the complete parent inventory,
changes only `src/models/qwen38_flash_next/kernels/rocm/q2_scaled_input.inc`,
and records all1027 provider files and the generated patch. The wave-owned
packing change and fixture are first-party MIT. The test-only control is the
literal retained parent packing kernel with a distinct symbol.

The changed numerical boundary remains full-row maximum, bounded dyadic
scaling, F32 product and round-to-nearest-even F16 storage. Weight formats,
matrix accumulations, output layout, buffer ownership and scalar decode are
unchanged. Static or parent agreement cannot qualify independent model tasks.
Rejected sources, actual failures and evidence remain preserved per owner
instruction. No default promotion, merge or publication is implied.
