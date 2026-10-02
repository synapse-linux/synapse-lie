<!-- SPDX-License-Identifier: MIT -->
# Strix Point ROCm 10.0.0 comparison

This experiment tests three ROCm 10.0.0 container stacks for the unchanged LIE
`gfx1150` numerical slice on `pop@192.168.5.161`, with the recorded ROCm 7.2
baseline on the same HX 370. The Fedora 43 candidate uses AMD's `gfx1150`
tarball; the Fedora Minimal 44 and AlmaLinux 10.2 candidates use AMD's signed
RHEL 10 RPMs. Fedora follows the distribution/package method of the Strix Halo
image found on `.157`.
The candidates change the compiler, HIP runtime and math libraries together;
eventual throughput differences would describe complete stacks, not an isolated
ROCm library effect.

AMD publishes an official [ROCm 10.0.0 developer image for Ubuntu
24.04](https://hub.docker.com/r/rocm/dev-ubuntu-24.04/tags). The only AMD
`dev-fedora` image found is [Fedora 24 with ROCm
1.6.4](https://hub.docker.com/r/rocm/dev-fedora-24/tags), unsuitable for this
test. This experiment instead uses the [Fedora Project base
image](https://www.fedoraproject.org/wiki/Container_SIG) at the amd64 manifest
`sha256:71fb350cb108e8864a11ce70ae7ef2df9167570ba8215d8b7de839a680dea751`
and AMD's official [gfx1150 ROCm 10.0.0
tarball](https://rocm.docs.amd.com/projects/install-on-linux/en/latest/install/install-overview.html).
The tarball URL is
`https://stable.repo.amd.com/rocm/core/tarball/therock-dist-linux-gfx1150-10.0.0.tar.gz`;
the downloaded 1770580920 bytes have SHA-256
`e2fc089e2874dcff88384f387d5bb0553ac1392d5cd1c96d6ade0233a94a8c4b`.
The [Dockerfile](../docker/strix-point-rocm10-fedora43.Dockerfile) verifies that
hash before extraction. No host ROCm or driver packages are replaced.

Read-only inspection of `.157` found the community
[`kyuz0/strix-halo-ds4-toolbox:rocm-10.0` image](https://hub.docker.com/r/kyuz0/strix-halo-ds4-toolbox/tags),
with local digest `sha256:4b446536c1ed6d551b0df49356852772c414b6a1335a2290433ec3eeae3f0c04`
and image creation time `2026-09-23T22:39:58Z`. Its labels identify Fedora
Minimal **44**; its build history adds the signed AMD RHEL 10 repository at
`https://stable.repo.amd.com/rocm/core/packages/rhel10/x86_64`, installs
`amdrocm10.0-gfx1151`, and exposes `/opt/rocm/core-10.0`. The publisher's
[source history](https://github.com/kyuz0/strix-halo-ds4-toolbox/commits/main/toolboxes/Dockerfile.rocm-10.0)
contains a ROCm 10 Dockerfile, but the image metadata does not identify an
exact source commit. The live Docker Hub tag is mutable; the local digest is
the evidence for the image actually present on `.157`.

The independently authored [Fedora Minimal 44 RPM candidate](../docker/strix-point-rocm10-fedora44-rpm.Dockerfile)
uses AMD's corresponding `amdrocm-core-devel10.0-gfx1150` package, which AMD
[documents for this GPU](https://rocm.docs.amd.com/projects/install-on-linux/en/latest/install/install-methods/multi-version-install/multi-version-install-rhel.html).
It mirrors the distribution and package method, not DS4 source or binaries.
Each candidate is a separate stack and retains its own image ID, HIP receipts
and benchmark results.

The [AlmaLinux RPM candidate](../docker/strix-point-rocm10-almalinux10-rpm.Dockerfile)
uses the [official AlmaLinux 10.2 minimal image](https://hub.docker.com/_/almalinux)
at its `linux/amd64` manifest digest
`sha256:385fe0d1cd8434c6051ee4cd6317e6035c043f32f042b84a5e38521b8d37d4cf`.
It installs the same AMD `amdrocm-core-devel10.0-gfx1150` 10.0.0-4 RPM as the
Fedora 44 candidate, then uses that image's `hipcc --offload-arch=gfx1150` to
compile a [native HIP smoke program](../tools/strix-point-hip-smoke.cpp).
This tests the primitive runtime independently of Python `ctypes`. It does not
compile the full LIE server or run model inference.

AMD's [ROCm 10 compatibility
matrix](https://rocm.docs.amd.com/en/latest/compatibility/compatibility-matrix.html)
does not qualify Fedora or Pop!_OS for this Ryzen APU. Container build success
alone cannot establish kernel-driver/runtime compatibility. A GPU probe, exact
prompt/output parity, full output completion, thermal/client/lease receipts and
fresh collection remain required before performance claims.

The baseline is the completed [Strix Point direct benchmark
report](STRIX-POINT-BENCHMARK-RESULT.md). The comparison uses the same verified
four-shard model, fixed Gufo source pin, LIE source, benchmark executable,
workload profiles, `gfx1150` target, one-second observer, lower published sensor
limits and manifest-scoped 100 C ceiling. The new image is identified by its
local Docker image ID and each compiled artifact by SHA-256. `single`,
`fresh-128k`, `fresh-256k`, `multi` and the independent Gufo reference are the
intended matched profiles. A failure is retained as a failure; there is no
automatic retry or inferred throughput.

The [one-shot campaign runner](../tools/strix-point-campaign.py) selects ROCm 10
only for an explicit `rocm10-fedora43`, `rocm10-fedora44-rpm` or
`rocm10-almalinux10-rpm` manifest and
pinned image ID. The Fedora 43 LIE compile action runs without `/dev/kfd`,
`/dev/dri` or network. The Fedora 44 image build also ran without GPU devices;
both use the same .161 lease, foreign-client checks, service stop/restore and
sensor guard as inference. The ROCm 7.2 path remains the default for historical
manifests. The
[compile helper](../tools/strix-point-rocm10-compile.py) retains actual exits,
logs, library hashes and linked binary hashes under the persistent .161 LIE
directory. The official Gufo source was independently fetched at
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`; no sibling project source
or artifact is used.

The Fedora 43 tarball image `sha256:89c6f9da64694da226948bca7b50d5e4e38caab9e138cb5cbe8678b7778cbe7e`
built and compiled the LIE `gfx1150` slice with exit 0. Its first GPU probe
failed on the copy path (`copy_inputs: HIP status 1`), unchanged by
`seccomp=unconfined`. The no-model diagnostic enumerated one device and a
successful 48-byte `hipMalloc`, then reported `hipErrorOutOfMemory` from
`hipMemset` and `hipErrorInvalidValue` from pageable and pinned `hipMemcpy`.
That first GPU probe was the `lie-hip-probe` executable built and linked inside
the Fedora 43 ROCm 10 container, not a binary carried over from ROCm 7.2.
The build receipt records successful library, CMake and link exits and SHA-256
for `synapse-lie-server`, `synapse-lie-bench`, the Gufo reference and the probe.

The Fedora Minimal 44 RPM image build passed under a fresh .161 lease with
Docker image ID `sha256:de9a979b0a53c91749d122b9f60712318175daca40fbdeac14e6793654a69a54`.
The installed AMD `amdrocm-core-devel10.0-gfx1150` RPM is `10.0.0-4`; the
image uses the officially documented amd64 Fedora Minimal 44 base manifest
`sha256:dbc66957b83be679a2fb8ed8964a8b47c60a75567b527a7362976cc714e70a3c`.
All 386 build telemetry samples stayed below the guard (CPU 71.125 C, GPU
46 C, NVMe 46.85 C maxima). Docker build and supervisor exited 0; the named
service was restored and the private lease released.

| .161 runtime and container mode | 48-byte `hipMalloc` | `hipMemset` | Host/device copies | 8-float round trip | Campaign |
| --- | --- | --- | --- | --- | --- |
| ROCm 7.2 control, existing image | success | success | all success | exact | PASS, exit 0 |
| ROCm 10 Fedora 43 tarball, restricted | success | out of memory | invalid value | failed | FAIL, exit 1 |
| ROCm 10 Fedora 44 RPM, seccomp open | success | out of memory | invalid value | failed | FAIL, exit 1 |
| ROCm 10 Fedora 44 RPM, IPC host + SYS_PTRACE | success | out of memory | invalid value | failed | FAIL, exit 1 |
| ROCm 10 Fedora 44 RPM, published Docker security profile | success | out of memory | invalid value | failed | FAIL, exit 1 |
| ROCm 10 AlmaLinux 10.2 RPM, native HIP program | success | out of memory | invalid value | failed | FAIL, exit 1 |
| ROCm 10 AlmaLinux 10.2 RPM, Python `ctypes` | success | out of memory | invalid value | failed | FAIL, exit 1 |

The Fedora 44 variants, AlmaLinux Python run and ROCm 7.2 control use the same
byte-identical bounded
`hip-diag.py` (SHA-256 `f134f3d55c157bbb6b869b81781f802bd44311b6d0e18a86d842baad72f8a4a9`);
the earlier Fedora 43 run used its R1 version. All report 1 GPU with 96 GiB
HIP total memory. The ROCm 7.2 control returns the exact eight input floats;
all ROCm 10 variants fail the same primitive operations before model loading.
The AlmaLinux native and Python runs used separate fresh leases, the same pinned
image, and the full published container profile. Both report 96 GiB total and
102919798784 free HIP bytes, a successful 48-byte allocation, HIP status 2 on
`hipMemset`, HIP status 1 on pageable and pinned copies, and eight zero output
floats. In both cases the diagnostic child exited 0 after printing all steps;
the supervisor correctly marked the campaign failed with exit 1. The compiled
native result removes Python's calling convention as a sufficient explanation
for the failure.

The Fedora 44 experiment uses `ctypes` against its own `libamdhip64.so` and
does not compile or execute a Fedora 44 LIE binary. The byte-identical
diagnostic succeeds with the ROCm 7.2 runtime on the same host, checking its
argument sequence against that stack; the independently compiled Fedora 43
probe also fails at a primitive host-to-device copy. A native Fedora 44 build
has not independently checked this runtime's ABI.

The final Fedora 44 run omits the extra read-only, capability-drop and
no-new-privileges settings while retaining a non-root user, private work mount,
network isolation and the supervised lease. Every run retired its owned child
and supervisor, freed the lease, restored `llama-router.service`, and had no
cleanup failure. The earlier ROCm 7.2 control R1 lacked private runtime DSOs;
R2 was rejected before launch because one SHA-256 manifest value was mistyped.
Their failed exits are preserved, and R3 is the valid passing control.

For the initial campaigns the host was Pop!_OS 24.04, kernel
`6.16.3-76061603-generic`. AMD's
[ROCm 10 compatibility matrix](https://rocm.docs.amd.com/en/latest/compatibility/compatibility-matrix.html)
does not qualify this host combination. This is a plausible compatibility
lead, not a proven kernel root cause. No host kernel, driver, firmware, clocks
or power settings were changed for this experiment.

Upstream has reports in the same failure area, but no confirmed match for this
exact stack. [ROCm issue #6191](https://github.com/ROCm/legacy-rocm-build/issues/6191)
reports a Radeon 890M / `gfx1150` where `hipMalloc` succeeds and the first
`hipMemset` hangs or faults; it uses ROCm 7.2.x and kernel 6.17 and records a
`gfxhub` page fault. [amdgpu issue #213](https://github.com/ROCm/amdgpu/issues/213)
reports `hipMemcpy` GPU page faults on `gfx1150` with ROCm 7.1.1 and kernel
6.17, absent with kernel 6.14. Our ROCm 10 / Pop!_OS kernel 6.16.3 runs
instead return HIP status 2 (`hipErrorOutOfMemory`) from a 48-byte `hipMemset`
and status 1 (`hipErrorInvalidValue`) from copies. A read-only search of the
accessible `.161` kernel journal over the probe windows found no `amdgpu`,
KFD or `gfxhub` fault. These reports show that first-use HIP failures on this
GPU are known, but neither identifies our root cause or establishes a fix for
ROCm 10 on this host.

The AlmaLinux image build completed with image ID
`sha256:fa243e504d1ae3d460c8bed01cf646ef48e06ef665f56bef563de8c13e2cb49e`;
the compiled `/opt/lie/hip-smoke` has SHA-256
`e049f6562f67f1450bae5b0661ac0b0d6d722506df2a614825a620ee42ad5076`.
Its image-build child and supervisor exited 0. Across 379 one-second build
observations, maximum CPU/GPU/NVMe temperatures were 71.375/46/41.85 C,
below the guard and each sensor's lower published limit. Native and Python
diagnostic CPU/GPU maxima were 38.875/38 C and 38/37 C, respectively, over
five observations each. Both diagnostic children exited 0, and both
supervisors exited 1 because of the HIP errors. Fresh read-only checks found
the private lease free, the named service active, all six owned
supervisor/build/container PIDs absent, and remote/local
SHA-256 identical for every retained source and result file. The initial local
Python launcher could not open an SSH socket (exit 255); its failed receipt is
retained, while the successful build used the byte-identical staged runner via
direct SSH. None of these windows touched the model files or installed ROCm on
the host.

At that point there was **no valid ROCm 10 original-weight throughput
comparison**: the primitive HIP gate failed, so the Fedora 44/AlmaLinux LIE
compile and matched `single`, `fresh-128k`, `fresh-256k`, `multi` and direct
Gufo runs were not started. The ROCm 7.2 report remains the qualified .161
full-depth performance result.

## Pop!_OS kernel 7.1.5 follow-up

On 2026-10-02 the operator requested a kernel update to test the ROCm 10
failure. After `apt-get update`, Pop!_OS APT selected
`7.1.5-76070105.202607241434~1787955023~24.04~38a419f`. The simulated and
actual package transaction upgraded five packages, installed four and removed
none. System76 DKMS autoinstall and initramfs generation exited 0. GRUB has
separate entries for the new kernel and the retained
`6.16.3-76061603-generic` fallback. A warning that the separately built
`system76_acpi` module matched the in-tree module did not fail DKMS. The
machine rebooted from boot ID `7ada622d-f3c6-45aa-ad5d-4eb69b8e4857` to
`00a38eef-12f6-4354-8aec-6783c34c7208`, and `uname -r` confirms
`7.1.5-76070105-generic`. No host ROCm package, GPU firmware, power or clock
setting was changed. This Pop!_OS combination is still outside AMD's
[ROCm 10 published OS/kernel matrix](https://rocm.docs.amd.com/en/latest/compatibility/compatibility-matrix.html),
which lists Ubuntu 24.04.4 with OEM 6.17 for this APU.

The same pinned AlmaLinux image
`sha256:fa243e504d1ae3d460c8bed01cf646ef48e06ef665f56bef563de8c13e2cb49e`,
Fedora 43 image
`sha256:89c6f9da64694da226948bca7b50d5e4e38caab9e138cb5cbe8678b7778cbe7e`,
and their previously staged binaries were reused. Each check had a fresh
one-shot .161 lease, foreign-client admission, one-second thermal observer and
named `llama-router.service` stop/restore.

| Unchanged ROCm 10 test | Kernel 6.16.3 | Kernel 7.1.5 |
| --- | --- | --- |
| AlmaLinux in-image native HIP | `hipMemset` status 2; copies status 1; supervisor FAIL | All 13 HIP calls status 0; exact 8-float round trip; PASS |
| AlmaLinux Python `ctypes` | Same primitive errors; supervisor FAIL | All 13 HIP calls status 0; exact 8-float round trip; PASS |
| Fedora 43 ROCm 10-linked `lie-hip-probe` | Host/device copy status 1; FAIL | Copy and four-element SGEMM verification pass; PASS |

This controlled before/after result makes the old host kernel or its interaction
with ROCm 10 the strongest observed explanation for the primitive failure;
it does not identify an individual kernel change. The Fedora 44 image was not
retested on 7.1.5.

The existing Fedora 43 ROCm 10-linked `synapse-lie-bench` then completed a
bounded original-weight UD shared-core run: nine physical input tokens, one
warmup and three measured 32-token outputs, with child/supervisor exits 0,
unchanged model file identities and completion marker. The warm outputs were
identical within this run. It reports 14.039 s load-to-ready and measured
output rates 10.576, 10.578 and 10.590 token/s; the three measured prompts
were RAM-prefix-cache hits, so these are **not fresh-prefill figures**.
The physical input IDs equal the earlier ROCm 7.2 core test, but generated IDs
do not. This short run establishes working model execution, not numerical
equivalence or long-context performance.

The matched original-weight `single-parity` direct runs used PP2048/TG128,
one complete measured 128-token output each at depth 0 and 4096, and the same
verified UD model and Gufo source pin. Both LIE reactive and direct Gufo pass
with child/supervisor exit 0, model stat identity unchanged and exact
same-stack prefill-logit hashes, decode-logit hashes and output IDs at both
depths. Their one-sample PP/TG rates are respectively 480.848/10.415 and
480.308/10.414 token/s at depth 0, then 441.313/10.404 and
442.061/10.408 at depth 4096. These are bounded parity samples, not the
complete comparative performance campaign.

Against the earlier ROCm 7.2 matched direct tests, the ROCm 10 logits hashes
differ at both depths. Generated IDs first differ at zero-based index 92 at
depth 0 (`67909` on ROCm 7.2, `11` on ROCm 10) and index 4 at depth 4096
(`42770` versus `24491`). LIE and Gufo agree within each stack. The source
diff between the ROCm 7.2 build checkpoint `3ea2f3c` and ROCm 10 source
checkpoint `1877b03` has no model implementation changes, but stack, compiler
and libraries changed together; the numerical cause needs a focused comparison
before claiming cross-stack quality equivalence.

The first Gufo direct run wrote both samples and the completion marker and its
Docker container exited 0, but the supervisor exited 1: Docker briefly
reported `Running=true` after its PID had disappeared, causing a `/proc` lookup
error. The failed R1 receipt is preserved. The campaign runner now tolerates
that exit race and re-inspects Docker state; a fresh R2 run passed with exactly
the same LIE/Gufo frontiers. The campaign control suite now covers both
PID-0 and disappearing-PID races. Across these seven fresh windows, observed
maxima were 72.25 C CPU, 75 C GPU and 70.85 C NVMe, below the selected and
sensor-specific limits. Collection matched SHA-256 for all 80 remote files.
Final postflight shows 7.1.5 booted, no LIE container, the private lease free,
`llama-router.service` active and its PID the only KFD client; the current-boot
kernel journal has no matching GPU fault/error since these tests began.
Focused local `core-headless-lifecycle` and `strix-point-campaign-controls`
CTest suites pass 2/2 under ASan/UBSan with leak detection disabled. The
initial leak-enabled run failed because LeakSanitizer could not run under the
local tracing environment; both actual command exits are preserved under the
same evidence directory.

The new kernel clears the ROCm 10 runtime gate. The later Distrobox `single`
campaign below covers all eight occupied-prefix depths; `fresh-128k`,
`fresh-256k` and `multi` remain unmeasured on ROCm 10. The numerical
discrepancy must be investigated or accepted explicitly before using
cross-stack throughput as a like-for-like quality comparison. The ROCm 7.2
long-context report remains the qualified same-stack LIE/Gufo reference.
The new local receipts are under `evidence/strix-point-kernel715-r1/` and
`evidence/rocm10-point-{alma-native,alma-ctypes,probe,core}-kernel715-r1/`,
`evidence/rocm10-point-bench-lie-parity-kernel715-r1/` and
`evidence/rocm10-point-bench-gufo-parity-kernel715-{r1,r2}/`.

Raw local receipts are under `evidence/rocm10-157-image-provenance-r1/`,
`evidence/rocm10-point-image-fedora44-rpm-r1/`,
`evidence/rocm10-point-hip-diag-fedora44-rpm-{r1,profile-r2,full-r3}/`,
`evidence/rocm72-point-hip-diag-control-r3/`, and the earlier
`evidence/rocm10-point-{build,probe,probe-seccomp,hip-diag}-*/` runs. The
collection receipts include file SHA-256, actual process exits, service state,
owned-process retirement and lease closure.
The AlmaLinux image, native and Python receipts are under
`evidence/rocm10-point-image-alma-r1/`,
`evidence/rocm10-point-alma-native-r1/` and
`evidence/rocm10-point-alma-ctypes-r1/`; their fresh hash/closure check is
`evidence/rocm10-point-alma-verification-r1.json`.

## Full LIE `single` profile in Distrobox

The operator-requested Docker-managed Distrobox 1.7.0 run on `.161` reused the
pinned Fedora 43 ROCm 10 image and compiled LIE executable under kernel 7.1.5.
The original four-shard UD model was mounted read-only. The one-shot runner
stopped only the authorized `llama-router.service`, held the private GPU lease,
checked foreign clients and temperatures every second, then restored the
service and released the lease. Distrobox was installed on the host with APT;
the host ROCm stack was not changed.

The first Distrobox entry failed before model execution because an extra
`--network none` flag conflicted with Distrobox's namespace setup. Its
supervisor and child exited 1, and its failed receipt is retained. A fresh
run without that flag passed with supervisor and child exit 0. The `single`
profile used a 2,048-token new prefill tail after each occupied prefix,
followed by 128 decode tokens, one warmup and one measured sample at every
depth. All 16 samples finished their 128-token outputs.

| Occupied prefix | ROCm 10 PP tok/s | ROCm 10 TG tok/s | Earlier ROCm 7.2 PP tok/s | Earlier ROCm 7.2 TG tok/s |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 479.936 | 10.433 | 472.581 | 10.292 |
| 4,096 | 439.211 | 10.414 | 433.310 | 10.261 |
| 8,192 | 427.143 | 10.411 | 415.064 | 10.251 |
| 12,288 | 420.799 | 10.394 | 419.773 | 9.891 |
| 16,384 | 418.574 | 10.397 | 434.701 | 10.203 |
| 32,768 | 407.723 | 10.343 | 425.131 | 10.173 |
| 65,536 | 394.419 | 10.241 | 404.108 | 10.045 |
| 131,072 | 357.117 | 9.227 | 389.786 | 9.862 |

At 128K, the measured new prefill tail took 5.735 s and the 128-token decode
took 13.873 s. The ROCm 10 rates are 8.38% lower for PP and 6.44% lower for
TG than the earlier ROCm 7.2 rates. Kernel, ROCm and container mode changed,
so this is an observed cross-stack difference rather than a causal ROCm result.
Physical input token IDs match at all eight depths, while prefill/decode
frontier hashes and generated IDs differ at all eight depths. One measured
sample per depth gives no variability estimate or quality-equivalent ranking.

The successful run sampled CPU/GPU/NVMe peaks of 91.125/90/66.85 C under the
operator's 100 C ceiling and lower sensor limits. The four model files were
unchanged; fresh collection verified all 27 remote files across both runs by
SHA-256. Postflight found `llama-router.service` active, its PID the only KFD
client, no remaining LIE Distrobox and the private lease free. The
[portable raw receipts, graph and offline reproducer](benchmarks/2026-10-02/strix-point/rocm10-distrobox-single/README.md)
contain the full per-sample values and validation. The local full collection,
including container home/cache files, is under
`evidence/rocm10-point-distrobox-single-kernel715-{r1,r2}/`; the report bundle
includes the relevant raw benchmark, telemetry and lifecycle receipts.
