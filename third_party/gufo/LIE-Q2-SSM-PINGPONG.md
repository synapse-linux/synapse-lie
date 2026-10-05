<!-- SPDX-License-Identifier: MIT -->
# LIE alternating SSM activation stages

The candidate derives from LIE's separately retained compact-LDS SSM source,
ultimately from independently fetched official Gufo revision
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`. Existing upstream MIT notices and
licenses remain. No sibling workspace or other-agent DS4 source is imported.

The first-party generator allocates two logical activation slots inside the
existing shared-memory arena, preserves wave-owned weight rows, substitutes
wave retirement for per-stage block retirement, and retains final block
retirement before transpose reuse. It changes no arithmetic helper or launch
grid. Full inventories, a complete patch against the saved model parent and
integer ownership/version checks are retained.

The compact-LDS operator fixture and independent oracle are reused unchanged,
with a distinct provider manifest. Static resource and compilation checks are
not GPU memory-ordering, numerical or throughput qualification. See the
[mechanism and evidence](../../docs/Q2-SSM-PINGPONG.md).
