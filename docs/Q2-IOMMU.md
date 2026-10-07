<!-- SPDX-License-Identifier: MIT -->

# User-authorized IOMMU measurement on .157

The owner explicitly requests disabling IOMMU and measuring the result,
then clarifies that the4K/8K curves must run first with IOMMU enabled.
Initial readback: kernel7.2.2-1-cachyos, Limine12.7.0, 32 IOMMU groups and no
IOMMU override on the command line. Group presence alone does not identify
translated versus passthrough mode.

Use the retained R3 server (SHA f8a5210c), saved native C benchmark client
(87d856cf), original four requests (fcee51ef), chunk2048, context133760, C1 AR,
zero cached tokens and unchanged original130925/8 prefix. Two separately
started server runs per boot expose first-run versus repeated-run effects;
all rates are reported individually, including thermal/clock observations.
The default-boot and disabled-IOMMU tests use the same binaries and inputs.
No4K/8K chunk change is mixed into this A/B.

The prepared boot change appends a temporary entry using the current kernel
and initramfs with their existing hashes, adding only `amd_iommu=off` to the
kernel arguments. It temporarily disables remembered-entry selection, keeps
the original default and uses the bootloader's one-shot selection for the
test entry. The original configuration is restored byte-for-byte once the
host reconnects. No persistent kernel argument or BIOS setting is changed.
The explicit exception covers this boot test and its restoration, not general
driver/service tuning. DMA isolation is absent during the test boot and NPU
availability can change.

GLM R3 on .157 has released all ownership and preserved its evidence. The
owner directs future GLM tests to .155. Every Q2 GPU admission still needs
fresh coordination, the five original leases and executable/input/model-stat
checks. After reboot, a new persistent boot epoch rebinds surviving inode
identities; old-boot PID numbers cannot establish current ownership.

Preparation and measurements live under `evidence/q2-iommu-preparation` and
separate `q2-iommu-{on,off}-native128-r1` directories. No model or .157 evidence
is removed. Source/checkpoint and the rollback configuration are persistent.
The enabled baseline completes both original130925/8 runs: first1076.934433
PP /25.567541 TG; repeat1321.570237 PP /26.097557 TG. All56 artifacts verify
before release d4022589 at22:32:38 UTC; independent closure22:32:58 checks
39 retired identities/groups, empty KFD, five free leases and unchanged model
stats. The two values are retained individually; neither replaces the prior
qualified R3 measurement.

Boot plan f8716328 is deferred without application. Configuration and EFI
variables are untouched and no reboot has been requested. A replacement plan
must name the new predecessor release after the chunk curves. The prepared
disabled-IOMMU measurement is not an observed result.

The enabled chunk curves are now complete and released at22:58:03 UTC,
receipt a6110bdf, with independent closure22:58:18. The owner requires the
complete2K/4K/8K tables before reboot, so execution stops after presenting
them. At22:59:01 the original boot ID,32 IOMMU groups and exact original
Limine SHA8c7c6387 still match. No boot plan is applied. Any later transition
must bind the new release and freshly coordinate all ownership checks.
