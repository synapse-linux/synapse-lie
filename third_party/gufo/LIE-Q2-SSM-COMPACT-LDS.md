<!-- SPDX-License-Identifier: MIT -->
# LIE compact SSM shared-memory experiment

The candidate derives from independently fetched official Gufo revision
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e` through the retained LIE
register-scatter provider. Existing Gufo MIT notices and licenses remain.
No sibling workspace or other-agent DS4 source/artifact is imported.

The first-party generator changes only the SSM dense specialization: BK1
staging, a padding-free XOR transpose and corresponding convolution reads.
It preserves original arithmetic helpers, launch grid and history boundary
kernel. Source inventory, complete patch, integer address proof and assembly
comparison are retained. No qualified control is rebuilt or rerun.

`tests/q2_ssm_compact_lds.hip` derives from the MIT SSM row-group fixture.
Its replay/timing logic is retained, with distinct output names and new HIP
resource-limit metadata. The copied FP64 oracle changes only its event name.
The existing control include remains literal to the saved parent. Compilation
and address proofs are not GPU numerical, memory-safety or performance results.

See [mechanism, risks and evidence](../../docs/Q2-SSM-COMPACT-LDS.md).
