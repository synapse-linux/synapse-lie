<!-- SPDX-License-Identifier: MIT -->
# LIE shared-down storage and tile experiments

These component providers derive from independently fetched official Gufo
revision `f783fedb9bea2ec7de941f6da4e02f4a4596b29e` through LIE's retained
register-scatter provider. Existing third-party licenses/notices are preserved;
no sibling workspace source or artifacts are imported. MIT first-party
generators retain complete source inventories and patches against that parent.

The existing Q8-to-F16 converter preserves the qualified integer-formula
conversion. Original Q8, generic F16, fixed Q8 and fixed F16 paths preserve
the original single K16 accumulation chain. The .157 component produces exact
outputs and passing independent operator checks but all three alternatives are
slower than original Q8. Source and measured failures are retained.

The subsequent `shared-down-n64` provider changes only the two fixed paths'
token tile from 128 to 64. It compiles without spills and preserves all 164
other kernels, including original Q8, generic F16 and the converter. This
changes resource use and weight reuse; it has no GPU timing or numerical
qualification yet. None of these providers changes model upload or dispatch.
No new whole-model throughput or independent task-quality claim follows.

[Mechanisms, complete measurements and status](../../docs/Q2-SHARED-DOWN-MIRROR.md).
