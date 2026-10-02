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
