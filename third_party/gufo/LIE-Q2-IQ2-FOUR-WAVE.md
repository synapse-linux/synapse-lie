<!-- SPDX-License-Identifier: MIT -->
# IQ2 four-wave provenance

The provider derives from retained ssm-fixed-bounds1585 and independently
fetched official Gufo f783fedb9bea2ec7de941f6da4e02f4a4596b29e. Its original
MIT notices and all inherited numerical-port provenance remain. Only the
listed HIP kernel/launch file changes;1027 provider files are inventoried.

The new first-party MIT ownership mapping preserves the parent quantization,
codebooks and ordered WMMA. Its wave-local transpose adapts the previously
retained local wide-pair experiment's epilogue while using a different launch
geometry. The control is the literal retained1585 kernel with a private name.
No sibling workspace source/artifact or other agent's DS4 implementation is
imported. [Bindings and limits](../../docs/Q2-IQ2-FOUR-WAVE.md).
