<!-- SPDX-License-Identifier: MIT -->

# IOMMU-off transition on .157

The owner-authorized reboot completes on 2026-10-08 after all 176 IOMMU-enabled
measurements, 352 total samples, verified evidence collection and presentation
of the full comparative table. [All Q2/UD curves](Q2-COUNTING-CURVE128.md) use
exact counting prompts and full prefill from empty state. No inference or
performance measurement has run with IOMMU disabled yet.

The new boot is `be3e89fd-955b-47a4-a385-11c3ad98bb78`; the prior boot was
`8b9cbb46-c7d4-47c3-b5cc-32e1fdad0653`. Kernel `7.2.2-1-cachyos` and its
initramfs are unchanged. The command line contains `amd_iommu=off`, and the
IOMMU group count changes from 32 to zero. Limine selects the temporary
`Synapse-LIE-IOMMU-off` entry and consumes the one-shot request.
The exact original configuration SHA256
`8c7c638757fa2d6bb48533eef5c1dea317bea2eba92fd5cef9ea6c0dcf0e3349`
is restored at 06:21:15 UTC, preserving mode0700 and the original default.
IOMMU remains disabled in this running boot; future normal boots use the
restored original configuration.

Readbacks retain APU performance mode at120W and all three fan curves:
ramp-up40,50,60,70,82; ramp-down35,45,55,65,78. No power/fan tuning is applied.
The kernel logs `amdxdna ... aie2_init: Running without IOMMU not supported`;
NPU initialization is therefore unavailable in this boot.

The user ComfyUI unit autostarts as PID1073/start980 after reboot. The separate
service-only plan60531161 uses the owner's existing authorization to stop it
with an empty queue and leave it stopped. Both queue counts are zero; the
exact user-unit stop exits0 at06:28:52. Its configuration and enabled state
remain unchanged. The earlier system-manager readback alone did not describe
this user-manager instance. Final KFD is empty.

Boot plan60345fc3 binds the actual curve release36a39711, complete table
presentation and fresh Core/GLM non-use. Seven private CPU fixture tests pass
on .157 at06:18:19; their boot commands are mocked. Apply exits0 at06:18:52.
The remote reboot command has actual exit0 at06:19:07; its SSH transport exits
255 when the host closes the connection. The absent outer invocation receipt
is preserved as absent. Restore, epoch bootstrap and authorized service stop
all exit0. No GPU fixture, build, model conversion, installation or cleanup
is performed by the transition.

All23 transition artifacts/241189bytes hash-verify at06:30:49, followed by three
final closure artifacts. Strong closure06:33:49 SHA
`9afc50dc121ab87ebca4a318726e3d9b1a5a1557b3f49ac107b8371e43165690`
checks all five original leases free, model identities unchanged, the service
process retired and KFD empty. New-boot baseline01919b3c preserves its initial
ComfyUI observation; the final `boot_transition_release` supersedes it for
readiness. The old ledger records `host_reboot_completed`. Q2 owns no host,
job, lease, window or reservation; no future GPU admission is granted.

[Machine-readable result](../config/q2-counting-iommu-boot-result.json),
[release](../config/q2-counting-iommu-window-release.json),
[boot plan](../config/q2-counting-iommu-boot-plan.json),
[separate service plan](../config/q2-counting-iommu-comfyui-stop-plan.json).
Raw receipts remain under `evidence/q2-counting-iommu-transition-r1` and
`evidence/q2-counting-curve128-preparation`.

The earlier f8716328 server-based boot proposal remains deferred and unapplied.
Its unaligned130925-token IOMMU-enabled observations (1076.934433/1321.570237
prefill,25.567541/26.097557 decode) and the earlier chunk tables are preserved
as historical evidence, not substituted for the corrected counting curves.
Any OFF comparison must retain the exact native inputs, executable, timing
contract and all recorded conditions of the completed ON campaign.

The [Linux7.2 parameter documentation](https://www.kernel.org/doc/html/v7.2/admin-guide/kernel-parameters.html)
defines `amd_iommu=off`. The [Limine12 configuration documentation](https://github.com/limine-bootloader/limine/blob/v12.x/CONFIG.md)
describes one-shot entry precedence and remembered-entry behavior.
