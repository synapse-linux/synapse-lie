<!-- SPDX-License-Identifier: MIT -->
# Strix Point UD port — .161

Status: **gfx1150 compilation, link and no-model startup pass; original-weight
GPU qualification blocked, not run**. This branch is `feature/strix-point-ud`, based
on shared-core checkpoint `02a9464`. It retains the C17 reactive engine, direct
bench and HTTP composition; numerical execution remains delegated to the pinned
Gufo adapter. No CPU model forward, re-quantization or architecture override.

## Target and model identity

Read-only SSH inventory on 2026-10-02 identifies `pop@192.168.5.161` as Ryzen AI 9
HX 370 / Radeon 890M, x86_64, KFD target version `110500` (`gfx1150`), wave32,
Pop!_OS 24.04, kernel `6.16.3-76061603-generic`. MemTotal is 132545421312 bytes;
the reported GTT limit is 66272710656 bytes (61.72 GiB), with a separate reported
2 GiB VRAM aperture. These share physical RAM; adding them is not a capacity
proof. No memory/BIOS/driver setting was changed.

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

## Completed tests on .161

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

## Remaining gates

1. Obtain the actual .161 handover. `llama-router.service` PID2211125 holds KFD
   and can autoload models; it was preserved. A zero busy reading is insufficient.
   Agree .161-specific campaign/lease ownership and recheck under the lease;
   .157's DS4 lease paths do not apply on this host.
2. Qualify the prepared gfx1150 binaries with the actual device and the target's
   different ROCm runtime. Compilation, target headers, link and no-model startup
   already pass, but they do not exercise lazy BLAS plans/kernels or GPU memory.
3. Stage the exact four UD trunk shards in a LIE-owned persistent model directory,
   after coordinated I/O admission; bind source revision/content and destination
   stat identities. No model payload has yet been read or downloaded here.
4. Start with bounded C1 AR, context4096, chunk2048, greedy/thinking off; verify
   actual device, memory allocations, completed prefill/decode, logits and output.
   Preserve allocation failures as failures; do not weaken guards or change GTT
   to manufacture a pass. The reported GTT limit alone does not prove model fit
   or OOM, and total GGUF size is not the resident GPU working set.
5. Compare direct reference, shared core and HTTP using identical physical inputs,
   then fresh contexts 2K/8K/32K/128K as measured fit allows; warmup plus three
   measured repetitions, and C1/2/4 separately. Record fresh PP, TG, total-wall
   throughput, TTFT, actual threads/memory/temperature and all failures. Keep
   RAM-hit and cold-prefill rows separate; SSD/MTP/vision require their own gates.

No Strix Point PP/TG number, numerical parity, long-context fit or GPU speedup
is claimed. The existing Halo results remain historical, platform-specific
evidence rather than a measured .161 comparison.
