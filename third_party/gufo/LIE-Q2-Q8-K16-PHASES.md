<!-- SPDX-License-Identifier: MIT -->
# Wide Q8 K16 phases provenance

The provider derives from independently fetched official Gufo at
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, through the measured IQ2 raw-prefetch
provider in `config/q2-iq2-raw-prefetch-source.json`. Its complete1025-file
inventory is checked before copying. No sibling CachyOS/owned DS4 source,
build, service, cache, profile or model artifact is imported or modified.

First-party MIT modifications affect only the wide Q8 branch of
`src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp`. They reorder
independent output updates into low/high K16 phases while preserving every
individual accumulator's original order. The literal control is the complete
retained-parent dense kernel with its symbol renamed. Shared helpers, original
Gufo/ggml code, tables, licenses and notices remain intact.

The source manifest binds all files,parent manifest,saved parent model,patch
and literal control. No new tensor/cache/table/stream/ABI is introduced.
Qualification,actual command failures and performance stay separate from source
compilation. Existing model controls and component cohorts are not rerun.
