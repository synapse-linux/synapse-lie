<!-- SPDX-License-Identifier: MIT -->
# Deferred IQ2 prefetch experiment provenance

The provider derives from independently fetched official Gufo at
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, through the saved compact IQ2
provider in `config/q2-iq2-halfbyte-perm-formatted-source.json`. Its complete
1025-file inventory is verified before copying. No sibling CachyOS/DS4 project
code, build, service, cache, profile or model artifact is imported or changed.

Only `src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp` changes.
First-party MIT modifications defer existing IQ2 expansion from fetch to
LDS commit and retain raw group/header values in the one-stage prefetch.
Original Gufo and ggml code, tables, licenses and notices remain intact.
The MIT literal control copies the complete measured compact-parent routed
kernel with only its symbol renamed; its shared helpers remain unchanged.

`config/q2-iq2-raw-prefetch-source.json` binds all files, the parent manifest,
saved parent model evidence, patch and literal control. The candidate owns
no additional tensor, persistent cache, table, stream or ABI. Qualification
and actual failures are recorded separately in the frozen plan and reports;
source compilation is not GPU/model quality or performance evidence.
