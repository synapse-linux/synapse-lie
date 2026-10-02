<!-- SPDX-License-Identifier: MIT -->
# Strix Point UD port — .161

Status: **gfx1150 original UD short-prompt inference passes; all four copied
shards verified, source files retained unchanged**. Long-context, independent
numerical parity and comparative performance remain unqualified.
The [full qualification report](STRIX-POINT-RESULT.md) consolidates all recorded
samples, prefill/cache/decode timings, resource and thread graphs, validation,
failures and remaining coverage. Its portable CSV/JSON/PNG/SVG bundle reproduces
offline without another GPU run.
This branch is `feature/strix-point-ud`, based
on shared-core checkpoint `02a9464`. It retains the C17 reactive engine, direct
bench and HTTP composition; numerical execution remains delegated to the pinned
Gufo adapter. No CPU model forward, re-quantization or architecture override.

## Target and model identity

Read-only SSH inventory on 2026-10-02 identifies `pop@192.168.5.161` as Ryzen AI 9
HX 370 / Radeon 890M, x86_64, KFD target version `110500` (`gfx1150`), wave32,
Pop!_OS 24.04, kernel `6.16.3-76061603-generic`. Initial MemTotal was 132545421312 bytes;
the initial reported GTT limit was 66272710656 bytes (61.72 GiB), with a separate reported
2 GiB VRAM aperture. These share physical RAM; adding them is not a capacity
proof. The subsequently authorized TTM96 change and post-boot HIP verification
are documented below; the current total reported by HIP is 96 GiB. No BIOS
setting or driver package was changed.

The requested UD identity is the existing **Qwen3.8 Flash Next UD-Q4_K_XL**,
Unsloth revision `38bb39ee97821de2c9009abb7e93950eec396e66`: four trunk shards,
111334654784 bytes in total (103.69 GiB). The first shard is metadata-only.
The optional MTP sidecar is not part of the initial AR test. Existing Qwen3.8
27B UD and Gemma files found under `/home/pop/llama-models` are different models;
no substitution is permitted. Flash Next was not found in the inspected known
model directories. This bounded observation is not an exhaustive disk search.

AMD's [ROCm 7.2 Ryzen matrix](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-7.2/docs/compatibility/compatibilityryz/native_linux/native_linux_compatibility.html)
lists the HX 370 and gfx1150; its listed OS is Ubuntu 24.04.3. That does not
qualify this Pop!_OS/kernel/toolchain combination or these quantized kernels.
The existing private ROCm 7.2 runtime contains rocBLAS/hipBLASLt gfx1150 code
objects, but the inspected installation lacks `hipcc` and the HIP development
header. The host has C/C++ compilers, but no CMake/Ninja on PATH. No packages
were installed and no foreign runtime directory was changed. A complete SDK on
the target is not required for the prepared path: compile on the editing host,
then use the existing .161 container/runtime with an isolated test bundle.

## Implemented platform boundary

`LIE_HIP_ARCHITECTURE` explicitly selects `gfx1151` (default, Halo) or `gfx1150`
(Point). The Qwen-only build requires one matching CMake HIP target. The build
receipt records the architecture and the target-policy hash; link admission
checks both against the hashed CMake cache and requested provider. A gfx1151
archive cannot silently satisfy a gfx1150 build. Historical Halo receipts still
require their matching cache and existing source/archive verification.

Before numerical model loading, both the embedded adapter and direct reference
validate the real HIP architecture and wave32 capability. Wrong targets return
`LIE_UNSUPPORTED`; unavailable HIP properties return `LIE_BACKEND_FAILED`.
`HSA_OVERRIDE_GFX_VERSION` is rejected before HIP initialization. Feature suffixes
on a matching HIP architecture name are accepted. These are additive admission
checks, with no executor ABI/layout or scheduler change.

The independently downloaded upstream pin remains
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, archive SHA-256
`4b61a3f23e5ab51f7c95d6a7b6d2d82c8f7976e39f9566196f75323ab5eb2110`.
Its Qwen MMQ vendor header already classifies both gfx1150 and gfx1151 as
RDNA3.5. The five gfx1151-specific branches inspected in `mmq.hpp` concern IQ2
decompression/unrolling; the UD routed Q4/MXFP4 path is not converted into IQ2.
Wave64 translation units retain their explicit upstream flags; they are not
globally changed to wave32. No numerical source or upstream top-level policy
was patched. The LIE Qwen-only recipe is a separate experimental composition,
not a claim that upstream's Halo-only release build qualifies Strix Point.

Local compile-only commands, subject to the thermal guard:

```sh
python3 -B tools/thermal-run.py --timeout 5400 --output evidence/point-libraries-thermal -- \
  python3 -B tools/build-gufo.py point-libraries --qwen-only --state-access --hip-arch gfx1150
cmake -S . -B build/point-runtime -G Ninja \
  -DLIE_GUFO_RUNTIME=ON -DLIE_GUFO_STATE_ACCESS=ON \
  -DLIE_HIP_ARCHITECTURE=gfx1150 \
  -DLIE_BUILD_ID=point-runtime \
  -DGUFO_SOURCE="$PWD/.deps/gufo-state-access-point-libraries" \
  -DGUFO_BUILD="$PWD/build/point-libraries"
```

The outer guard evidence label differs from the inner build label because both
refuse existing directories. The build helper forwards termination to its owned
compiler process group before retiring, so nested compilation is also stopped.
The equivalent `point-libraries-r1` build completed all 38 steps; ten extracted
device ELF headers from three numerical archives identify gfx1150. The server,
bench and direct reference link successfully. These binaries run inside the
existing .161 Arch-based container; native Pop!_OS ABI compatibility is not
claimed. The local-only build
helper continues to refuse SSH invocation; no remote lease bypass was added.

## Initial headless tests on .161

All retained results are **synthetic CPU / NOT-INFERENCE**:

| Run | Result | Observed CPU peak |
|---|---|---:|
| `strix-point-cpu-161-r1` | C17 target matching and actual C++ device-admission wrapper with synthetic HIP API pass under ASan/UBSan; four Python receipt tests pass; all five commands exit 0 | 35.5 C |
| `strix-point-core-161-r2` | Headless shared core, reactive SSD waits, RAM retention, state contracts and target identity: CTest **6/6**, ASan/UBSan; configure/build/test exit 0 | 47.625 C during build; 44.375 C during tests |

On the editing Halo, `strix-point-local-r3` passes the full **34/34** CTest suite
with ASan/UBSan, including HTTP fixtures, target admission and forwarding
interruption to the owned compiler group. Test peak CPU80.125/GPU60 C.
The gfx1150 numerical build peaks at CPU95.125/GPU70 C with explicit local98 C
admission. Its helper source is retained next to the build receipt; a subsequent
supervision-only revision replaces asynchronous exceptions with signal polling,
covered by the final interruption fixture. Numerical sources/flags are unchanged.

The first linked bootstrap used the default `unrecorded` build label; its
no-model checks remain retained. The separately built candidate is labelled
`strix-point-ud-r2`. Debug symbols are stripped only from new private copies;
original linked binaries stay intact and both hashes are recorded.
`strix-point-runtime-161-r3` passes server help, bench identity and reference
identity on .161, all exit0, with `build_id=strix-point-ud-r2`. The 08:13:41 UTC
postflight still records the same llama-router PID/start identity, unchanged
reported VRAM/GTT usage and no additional observable KFD client. Permission-denied
process observations remain explicit; this is not universal exclusivity proof.

The headless tests use the existing Synapse builder image
`sha256:29e3b2b4b984ddb2614068271b2967bdc941664690468390c907508b5da8c2ac`,
whose recorded source is `SynapseLinux-PKGBUILDS`, with official binary package
dependencies. It has no network or GPU device passthrough, runs as UID 1000,
and writes only the private test checkout and container temporary files. Read-only
sysfs exposes temperature sensors. No sibling workspace sources/artifacts were
imported. This image lacks llhttp, so it was used for the headless core only.

The first container attempt failed before launching CMake because its default
sysfs view contained an inaccessible hwmon symlink. R2 exposes host sysfs read-only;
R1 exit 1 remains retained. Local attempts R1/R2 refused before spawning CMake
at CPU89.25/93.875 C, guard exit 125, no child exit. The thermal threshold remains
85 C or the lower exposed sensor max/critical limit on .161, sampled once per
second. The root thread's subsequent owner-authorized 98 C ceiling for the
verified Halo 395 editing host is carried from `8bc6f74`; it is explicit opt-in,
does not raise NVMe limits and is rejected on the HX 370. No fan/power/clock
changes or foreign process signals occurred.

`tools/strix-point-remote.py` supplies bounded, fixed-target `inventory`,
`cpu-tests`, `core-tests` and `runtime-check` actions. Fresh labels create persistent exclusive
paths under `/home/pop/workspace/synapse-lie/`; local receipts include source
hashes, exact commands, actual exits, raw logs and thermal samples under
`evidence/`. The runtime action mounts existing ROCm read-only and uses five
private official system DSOs (llhttp, libdrm, libdrm_amdgpu, libpng and libjpeg),
with package versions and hashes. Its first attempt retained loader exit127 for
missing libpng; the completed bundle starts server help and both bench identities
with exit0. No model, listener or GPU is opened; successful startup is not GPU
inference or numerical compatibility. It does not install dependencies or alter
services. [Condensed source-bound receipts](benchmarks/2026-10-02/strix-point/receipt.json)
identify retained local and remote evidence, including failures.

## Qualification history and remaining gates

### Authorized GPU diagnostic — 08:52 UTC

The operator explicitly permitted stopping llama. `strix-point-gpu-probe-r2`
acquired the persistent LIE-only campaign lease, stopped the named user service,
waited for its known process/KFD identity to retire, and admitted the diagnostic.
HIP reports `gfx1150`, Radeon 890M, driver/runtime `70226015`; a 48-byte device
allocation, copies and rocBLAS SGEMM pass with four exact expected outputs.
Child and supervisor exit 0. The owned container was removed, observed KFD was
empty before restoration, and `llama-router.service` returned to active/running
before lease release at **08:52:45.935940 UTC**. Sampled peak CPU36.5/GPU36 C.
The [first-GPU receipt](benchmarks/2026-10-02/strix-point/first-gpu-receipt.json)
retains exact runner snapshots, commands, telemetry, exits and source identities.
The small missing `amdgpu.ids`
diagnostic message is retained; no dependency was installed.

R1 is retained as a **pre-launch refusal**, not a GPU failure: the kernel KFD
entry briefly outlived the stopped service. The correction waits at most five
seconds for that exact previous service identity, still rejecting any other new
client. Synthetic supervision fixtures cover the delayed retirement, interruption,
lease contention, restoration and evidence retention. No process other than the
explicitly authorized service and LIE-owned children is signalled.

This validates the target HIP/runtime/BLAS path, **not** Qwen quantized kernels,
original-model outputs, model capacity or performance. `tools/strix-point-campaign.py`
implements the bounded remote phases, with exclusive persistent receipts,
source/artifact identity, 85 C temperature limit and service restoration in cleanup.
`tools/strix-point-launch.py` stages immutable per-run source copies over SSH.
Neither helper uses .157/.158 resources or treats a private lock as other owners'
agreement; .161 admission derives from the operator's scoped handover.

### Original-weight shared-core smoke — completed 11:14 UTC

`strix-point-core-ud-r1` runs the original UD in the C17 shared reactive core
with the independently built gfx1150 Gufo adapter (`strix-point-ud-r3`). Actual
GPU inference passes: one warmup and three repetitions, each with32 generated
tokens and identical output IDs. The physical raw-text prompt has **9 tokens**;
4096 is the configured capacity, not the exercised context length. There is no
HTTP layer, MTP or vision in this test. The default RAM prefix cache remains on;
SSD persistence remains off.

| Observation | Result |
|---|---:|
| Load to core ready (files recently copied/cached) | 13.440 s |
| First sample: fresh9-token prefill | 377.705 ms |
| First sample: TTFT | 519.029 ms |
| Measured decode rates | 10.560 / 10.544 / 10.563 token/s |
| Mean measured decode | 10.556 token/s |
| Mean warm TTFT | 112.853 ms |
| RAM prefix restore | 4.482 / 4.450 / 4.452 ms |
| CPU / GPU / NVMe peak | 74.25 / 58.00 / 63.85 C |
| Sampled GTT usage maximum (1 Hz) | 85505114112 bytes |
| Observed process thread counts | 1 / 28 / 44 |

Each measured sample hits all9 prompt tokens in the RAM cache and records zero
prefill calls. Its TTFT and restore duration are **warm-cache measurements**.
The nine-token first prefill is a smoke timing, not a representative PP benchmark.
GTT usage is sampled whole-device accounting, not an exact allocator peak.
Thread counts include runtime threads; they are not configured worker counts
or evidence of a reactive speedup. A matched serial/reference comparison is
still required for that claim.

The container and supervisor both exit0; no OOM or cleanup error occurs, all
model stat identities stay unchanged, the container is removed, llama is restored
and the private lease released. Fresh postflight verifies both owned processes
absent and the lease free. The [core receipt](benchmarks/2026-10-02/strix-point/core-receipt.json)
contains every input/output token ID, all timing/cache rows, stderr, source and
artifact identities, thermal summary and exact cleanup. This is original-weight
inference evidence for the recorded small case, not independent numerical
qualification, long-context fit, HTTP serving or a platform speedup comparison.

### Direct copy of existing original weights — complete

The operator explicitly selected copying the existing .157 weights, with all
source files retained unchanged. WAN R3 retired cleanly at 10:27:42 UTC after
the intentional signal (child -15, supervisor1, llama restored, lease released).
Its verified first shard and 31584485376-byte second-shard partial were fsynced.
No Internet fallback is scheduled.

[`strix-point-copy-direct.py`](../tools/strix-point-copy-direct.py) stages the
private controls and runs the sender/controller on .157; model data goes over
one direct SSH connection to .161. Existing local authentication is exposed
only through a temporary SSH agent constrained to these two hops, with a finite
lifetime and cleanup. The private key stays on the editing host, public host
keys are pinned from its existing trust file, and no global SSH configuration
or authorized_keys file is changed. Neither model nor project source is staged
under `/tmp`.

The shared copy helper keeps four established .157 leases, source identities,
read-only/O_NOATIME access and registered start/end events. On .161 it retains
the service stop/restore grant and private lease. It hashes the preserved prefix,
appends the exact remaining bytes and only publishes a shard after complete
SHA-256 agreement. All four shards must verify before `SOURCE.json` exists.
The new four-hour bound permits slower Wi-Fi without assuming wired throughput.
The source files are never moved, renamed or removed. The local six tiny
integrity fixtures, a seventh real-pipe EOF/ACK regression and focused CTest 4/4
pass, including the core contract under
ASan/UBSan.

R1 copied the remaining **79739222784 bytes** after Q2's release and core's
handover. All four destination digests passed, but Python's standard stdout
buffer retained its underlying descriptor when closed, leaving sender and
receiver waiting for ACK/EOF. The sender was deliberately retired through its
verified pidfd; source/controller exit1 and successful destination verification
are retained. The helper now atomically redirects the flushed descriptor to
`/dev/null`, delivering real EOF before waiting for ACK. A subprocess regression
proves that ordering; no source model file is changed by this fix.

R2 rehashed the already complete destination files, sent **zero** source payload
bytes and passed with all three exits0 at 11:11:58 UTC. All **111334654784 bytes**
are verified against four official SHA-256 digests. Source model stat identities
are unchanged, owned source processes are absent, KFD empty, four source leases
free, and both temporary agents retired. Llama is restored and the destination
lease is free. Core and Q2 received the verified handover. The
[copy receipt](benchmarks/2026-10-02/strix-point/copy-receipt.json) preserves
both the failed first control completion and successful revalidation. Historical
WAN and slower relay outcomes below remain preserved.

### TTM96 applied and verified — 09:47 UTC

The operator authorized the concrete TTM96/initramfs/reboot proposal with
`procedi con il tuning`. The owned WAN downloader was deliberately interrupted
through its verified pidfd; child exit -15 and supervisor exit 1 are retained,
with successful llama restoration and lease release. Its verified first shard
and 17129537536-byte second-shard partial were fsynced before reboot.

Only `/etc/modprobe.d/90-synapse-lie-ttm.conf` was added, root-owned mode0644,
with the exact [tracked configuration](../config/strix-point-ttm96.conf).
The current kernel `6.16.3-76061603-generic` initramfs was backed up, rebuilt
(exit 0), checked for the new config, and confirmed as the GRUB default boot
entry. Kernelstub's live-mode warning was retained; GRUB uses the updated file.
The reboot command exited 0; its SSH connection closed with exit255, followed
by a verified new boot ID. No clocks, fan controls, power limits or page-pool
override were changed.

| Observation | Before | After reboot |
|---|---:|---:|
| TTM pages limit (4096 B/page) | 16179861 | 25165824 |
| GTT and actual HIP total, bytes | 66272710656 | 103079215104 |
| GTT and actual HIP total, GiB | 61.72 | 96.00 |
| HIP free before diagnostic, bytes | 66079281152 | 102919798784 |

`strix-point-gpu-probe-ttm96-r1` passes actual HIP allocation/copies and the four
rocBLAS SGEMM output checks, child/supervisor exit 0; the container retires,
llama is restored active, and the private lease is released at 09:46:29 UTC.
Its explicit allocation is only 48 bytes: it verifies the runtime and reported
limit, **not** a 96 GiB allocation or original-weight model fit. GPU card numbering
changed across reboot, so campaign telemetry now follows the admitted
`renderD128` node rather than assuming `card1` exists.

The boot also reports COSMIC `Backend initialized without output`: no connected
display is detected; greeter retries exhaust the start limit of it and
`gpu-manager`. The latter's actual detection commands previously exited 0.
The kernel additionally reports an amdxdna NPU firmware-protocol mismatch.
These observations are retained separately from the successful HIP compute
test; their causal relationship to TTM is not established. No display/NPU
configuration or package was changed to hide them.

Backup and rollback are persistent under
`/home/pop/workspace/synapse-lie/strix-point-ttm96-r1/`: `initramfs.before.img`,
`prepare-result.json` and `rollback.py`. In an admitted maintenance window,
`sudo -n python3 /home/pop/workspace/synapse-lie/strix-point-ttm96-r1/rollback.py`
checks and removes only this exact owned config and rebuilds the same kernel's
initramfs; a subsequent reboot is required. The original initramfs SHA-256 is
recorded if recovery from the backup is necessary. Rebuilding later kernels or
reapplying this host-specific configuration requires their own verification.

The [tuning receipt](benchmarks/2026-10-02/strix-point/ttm96-receipt.json)
binds the configuration, administrative scripts, before/after identities,
actual probe result, thermal observations and test exits. Raw evidence and
the initramfs backup remain in the persistent run directories.

After a separate root/Q2 handover, a read-only .157-to-.161 copy held all four
established source leases (09:52:28–09:57:00 UTC). The relay crossed Wi-Fi at
each machine and transferred only about10 MB/s, so it was intentionally stopped
to return .157 to Q2. Both exits1 and the receiver's truncated-payload result
are retained. The source process is absent, KFD empty, all four unchanged leases
free, and all original model stat identities unchanged. The .161 partial was
preserved and llama restored. WAN R3 resumes from that prefix with complete
SHA-256 verification and an eight-hour bound; its09:59 UTC snapshot is19.35 GB
of111.33 GB, **not completed staging**. Source/destination temperature peaks
and exact cleanup are included in the receipt. No original UD inference or
PP/TG measurement follows from these transfer or runtime checks.

### UD transfer and memory finding — historical 09:15 UTC snapshot

The official first shard is downloaded and SHA-256 verified. Sequential R1 was
intentionally interrupted to improve transfer throughput; its supervisor exit 1,
signal 15, partial data and successful service restoration are retained. Its
older cleanup implementation did not record the interrupted child's actual exit;
that value is unknown, not inferred. R2 rehashes the saved prefix and downloads
up to eight ordered 16 MiB ranges, with at most eight queued payloads and full
final SHA-256 before publication. Truncated, oversized or corrupt files retain
only `.part` names. Source and weights stay under persistent LIE paths.

At 09:15 UTC, R2 had staged about 7.51 GB of the 111.33 GB total; this is a progress
snapshot, not a completion receipt. The target was around CPU40/GPU39 C, KFD
empty, with llama temporarily inactive inside the admitted I/O window. The
supervisor restores its original state on completion/error. No model inference
has started. A faster read-only LAN copy was requested from the other owners;
their .157 campaign is still active, so no .157 payload access has occurred.

The real HIP probe reports total GPU memory **66272710656 bytes / 61.72 GiB**.
The same UD's measured resident-weight estimate on Halo is **82384141824 bytes /
76.73 GiB**, excluding session/scratch state. This predicts a capacity problem
with the current limit; it is not an observed allocation failure on .161 yet.
The kernel initially exposed TTM `pages_limit=16179861` with 4096-byte pages,
matching the reported limit. The [96 GiB TTM configuration](../config/strix-point-ttm96.conf)
uses 25165824 pages and leaves about 27.44 GiB of total system RAM outside that
limit. It raises a maximum, not a reservation. It was subsequently authorized
and applied as documented above. The procedure writes only a new owned modprobe
file, updates the current kernel's initramfs and reboots. Rollback removes that owned
file, rebuilds the initramfs and reboots. AMD documents the
[TTM limit and reboot requirement](https://rocm.docs.amd.com/en/docs-7.2.0/how-to/system-optimization/strixhalo.html);
that Halo guidance alone does not qualify Point model fit.

The prepared C1 phase uses the shared reactive core, context4096/chunk2048,
one user, 32 output tokens, one warmup and three repetitions, with the default
RAM cache policy. Warm hits and fresh prefill must be reported separately.
`lie-bench` now preserves the backend's exact model-load error in failed output
instead of hiding it behind `core readiness failed`. Its focused ASan/UBSan
fixture passes. Candidate `strix-point-ud-r3` compiles/links against the same
gfx1150 numerical archives and passes no-device startup on .161.

### Follow-up diagnostic and model plan — 08:37 UTC

`lie-hip-probe` is now compiled and linked for gfx1150. Its C17 driver reuses
the provider's device admission and failure-quiescence wrapper. An explicit
`--run` checks real HIP identity, memory reporting, a 48-byte allocation,
host/device copies and a 2x2 rocBLAS SGEMM with four known outputs. rocBLAS may
allocate its own workspace. This is a small runtime diagnostic, not a model-fit,
quantized-kernel, model-output or performance qualification. It is deliberately
excluded from automatic CTest execution; real `--run` still requires the GPU
window and supervised device access below. No model or HTTP listener is opened.

The separate fixture labels its output `SYNTHETIC_CPU_NOT_INFERENCE`. Twenty
subprocess cases cover command/admission controls, allocation/copy/BLAS failures,
wrong/non-finite output, cleanup failures and unquiesced-device exit 70. They
pass ASan/UBSan locally and on .161 without GPU devices or a ROCm runtime in the
fixture container. Local focused CTest passes 2/2. The first local attempt's
exit 8 is retained: LeakSanitizer was incompatible with the execution sandbox's
ptrace, so the successful check ran outside it without disabling sanitizers.
The real binary's `--help` also loads successfully with the existing .161 ROCm
runtime in `strix-point-probe-startup-r2`, still without GPU passthrough.
These results do **not** mean the real SGEMM has executed on the GPU.
The final target fixture peaks at CPU36.375/GPU36 C, below the 85 C ceiling;
the focused local check peaks at CPU78.375/GPU60 C. The
[source-bound preparation receipt](benchmarks/2026-10-02/strix-point/probe-receipt.json)
retains commands, actual exits, source/binary hashes, temperatures and failures.

`tools/strix-point-remote.py probe-tests LABEL` runs the synthetic controls;
`probe-check LABEL --bundle build/point-probe-bundle-r2` tests only the real
binary's help path. Both retain the existing no-device/no-network container
isolation and 85 C target ceiling. The diagnostic and test code are persistent
in this worktree, with private artifacts under `build/` and `evidence/`.

[The pinned download plan](../config/models-161.plan.json) contains independent
official URLs, sizes and SHA-256 for the four trunk shards, verified against the
[upstream repository metadata](https://huggingface.co/api/models/unsloth/Qwen3.8-Flash-Next-GGUF/tree/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL).
Only 1391 bytes of metadata were fetched; no weight payload was downloaded or
hashed. It agrees with all four historical UD content identities and targets
the private persistent directory
`/home/pop/workspace/synapse-lie/models/qwen38-flash-next-ud-38bb39ee`.

The 08:24 UTC inventory and 08:36:57 UTC service check still identify the same
active `llama-router.service` PID2211125. No established connection on its 8080
listener was observed; that snapshot is not a handover. A temporary service
stop followed by restoration has been proposed to the operator, but has not
been authorized explicitly or executed. `AGENTS.md` forbids foreign process
termination. No private lock is being represented as an adopted .161 lease.

The concrete pending sequence is: agree the .161 campaign window and ownership;
retire the router through its owner or an explicitly authorized temporary stop;
verify KFD empty and acquire the agreed lease; run the small diagnostic under
temperature/foreign-client observation; stage and verify the pinned shards;
run the bounded AR/model checks below; retire owned children, release the lease
and restore the prior service state if an authorized stop was used. No background
waiter, service mutation or automatic GPU retry has been installed.

### Current original-weight gates

1. **Completed for the recorded runs:** explicit .161 handover, fresh private
   lease, authorized llama stop/restore and observed client/temperature checks.
   Every future GPU campaign still needs current admission; .157's DS4 lease
   paths do not apply to the .161 device.
2. **Completed for the small cases:** real gfx1150 HIP/rocBLAS probe and original
   UD shared-core prefill/decode. Broader numerical/operator parity remains open.
3. **Completed:** four official UD shards in the persistent .161 LIE directory,
   all SHA-256 verified, source files unchanged and destination identities bound.
4. **Bounded C1 smoke completed:** capacity4096, chunk2048, raw prompt9 tokens,
   greedy AR32 output tokens, one warmup/three samples, identical output IDs.
   This validates that case's allocation and execution, not independent logits
   parity, long-context memory fit or general quality. Keep actual failures and
   resource guards; any further system tuning requires separate authorization.
5. **Remaining:** compare direct reference, shared core and HTTP using identical physical inputs,
   then fresh contexts 2K/8K/32K/128K as measured fit allows; warmup plus three
   measured repetitions, and C1/2/4 separately. Record fresh PP, TG, total-wall
   throughput, TTFT, actual threads/memory/temperature and all failures. Keep
   RAM-hit and cold-prefill rows separate; SSD/MTP/vision require their own gates.

The recorded short-prompt timings are .161 evidence with explicit cache bounds.
Independent numerical parity, long-context fit and comparative/reactive speedup
remain unqualified. Existing Halo results remain platform-specific evidence
rather than a matched .161 comparison.
