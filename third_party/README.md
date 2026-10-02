<!-- SPDX-License-Identifier: MIT -->
# Gufo provenance

`patches/gufo-q2.patch` modifies independently downloaded official Gufo
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`; its archive receipt is
`config/gufo-source.json`. Gufo's original MIT license, notice and full third-party
notice are retained here. The quantized HIP kernels retain their upstream
llama.cpp notices and formatting. Antirez material was consulted for the file
format; no antirez Qwen engine source is incorporated. No sibling project's
source, binary or cache was imported.

The patch keeps quantized expert weights, separates logical and physical down
widths, and exactly widens the small F16 HC injection matrices at load. The
standalone qualification harness is first-party MIT. Its IQ2 oracle uses the
official format codebook generated from the pinned source at build time, with
independently evaluated unpacking and dot-product arithmetic.

`experiments/q2-hc-four-wave.patch` is first-party MIT numerical work against
the same independently fetched official pin. It changes F16 HC down work
distribution without importing another engine or changing weight precision.
Its qualification harness inherits upstream numerical flags; bounded model
checks may reuse this workstream's unchanged, identity-verified MMQ archive.
The original upstream and llama.cpp notices remain applicable to that archive.

`experiments/q2-hc-prefill-wmma.patch` specializes the same official Gufo raw-F16
WMMA template for the two original Q2 HC prefill projections. It is a separate
experimental delta after the HC4 decode patch, with first-party MIT synthetic
checks and unchanged upstream arithmetic/weight formats. The source receipt
records both modified translation units and all 1019-file inventory coverage.
No antirez engine or sibling workspace source/artifact is incorporated.
