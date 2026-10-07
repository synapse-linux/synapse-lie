<!-- SPDX-License-Identifier: MIT -->

# User-authorized IOMMU measurement on .157

The owner explicitly requests disabling IOMMU and measuring the result.
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
Prepared work does not establish that IOMMU has been disabled or measured.
