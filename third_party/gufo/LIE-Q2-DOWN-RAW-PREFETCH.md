<!-- SPDX-License-Identifier: MIT -->
# Scaled Q2 down deferred extraction provenance

The provider derives from independently fetched official Gufo at
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, through the measured IQ2
raw-prefetch provider in `config/q2-iq2-raw-prefetch-source.json`. Its complete
1025-file inventory is checked before copying. No sibling CachyOS or owned DS4
source, build, service, cache, profile or model artifact is imported or changed.

Only `src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp` changes.
First-party MIT modifications defer existing Q2 bitplane extraction into LDS
commit for scaled down only. Original Gufo/ggml code, data tables, licenses and
notices remain intact. The MIT literal control is the full retained-parent
routed kernel with its symbol renamed; shared helpers stay unchanged.

`config/q2-down-raw-prefetch-source.json` binds all files, parent manifest,
saved parent model, patch and literal control. No additional persistent tensor,
cache, table, stream or ABI is owned. Qualification and actual failures remain
separate from source compilation, with original command exits retained.
