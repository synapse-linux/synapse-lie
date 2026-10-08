<!-- SPDX-License-Identifier: MIT -->

# Exact 128K IOMMU comparison

The owner has authorized the IOMMU-off repetition of the complete
[IOMMU-on curves](Q2-COUNTING-CURVE128.md). Preparation is complete; this
document does not yet contain measured IOMMU-off results.

[Frozen OFF plan](../config/q2-counting-curve128-off-plan.json):
`631ea5b145b49e311af1bb1a64f395fb3cdd3dc5df2f9791c072eca8bff8d3c0`.
It binds boot `be3e89fd-955b-47a4-a385-11c3ad98bb78`, the verified boot closure,
and the identical retained `b701e948` native benchmark executable. No build is
needed. Numerical source, model files, prompt contents, and measurement
semantics remain those of control plan `ca98934d`.

The serial order is Q2 chunk2048, UD chunk2048, Q2 chunk4096, Q2 chunk8192.
Each curve includes every exact multiple of its chunk size through131072:
64+64+32+16 measured points, with one warmup and one measured repetition each.
Each point starts from empty sequence state and measures the complete prompt
between initial and final monotonic timestamps. Capacity133760, TG128,
C1 reactive greedy AR, MTP off, no prefix restoration and no inserted pauses
match the control. Model residency spans each curve. The performance/120W
mode, fan82 configuration, inclusive98C gate and pre-arm60C cooldown also match.

The OFF runner changes only boot/IOMMU and coordination bindings and adds a
CPU qualification receipt. A focused CPU fixture compares every benchmark,
telemetry, thermal, accounting, and retirement function against the frozen ON
runner and rejects changes to the workload or model identity. Native benchmark
CPU qualification is reused because its executable and source did not change.

The current kernel command line contains `amd_iommu=off`; there are zero
IOMMU groups. The original boot configuration is already restored for later
boots. This experiment requires no reboot, tuning or service change.
The enclosing GPU window continues through artifact collection, hash
verification, release and independent closure. Results will compare every
requested point, including all intermediate lengths, for both PP and TG.

One measured repetition per point describes this run; an ON/OFF difference
alone is not a distribution of repeated measurements or broad quality evidence.
