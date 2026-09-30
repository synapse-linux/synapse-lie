# Environment and baseline admission

Reconnaissance: 2026-09-30, read-only. Detailed dated inventory is in
`evidence/inventory-157-r1.json`; reproducible script `tools/inventory.py` runs
through the already authorized SSH account. No device initialization or complete
weight scan. `config/models-157.inventory.json` keeps identities/metadata hashes.

## Machine

Target `.157` = `paperboy@192.168.5.157`, reached from `.155` (not guessed).
AMD Ryzen AI MAX+ 395, 16 cores/32 threads, Radeon 8060S gfx1151, amdgpu,
x86_64 CachyOS Linux 7.2.2-1-cachyos. Observed:

- MemTotal 131001532 KiB; MemAvailable about 123406468 KiB at the initial probe.
- Driver sysfs: VRAM aperture 536870912 B, GTT total 134145568768 B; GPU busy 0%
  at one instant. **These are not separate RAM pools or an allocation/fit proof.**
  Current HIP-accessible allocation capacity has not been probed in this fork.
- /home SSD approximately 207.5 GB available. No cleanup of DS4 data.
- Host GCC 16.2.1, HIP 7.2.53211 / AMD clang 22, ICU 78.3, libuv 1.52.1,
  json-c 0.19, curl 8.21.0. Existing Alma container has its separately pinned
  ROCm/ABI environment; do not compare host builds as if that runtime were equal.
- Ports already seen: SSH22, local8090/8091,8080 and desktop/system listeners.
  ComfyUI remains inactive with MainPID0 in the targeted follow-up. MCP Blender
  bridge processes exist; no service was stopped. A process/listener scan and
  zero busy% do not prove global GPU exclusivity.

Editing host `.155` also has the C dependencies, llhttp 9.3.1, compiler and
ROCm headers. All LIE compilation/tests so far are here, with no GPU workload.

## Models (same family does not mean same weights/quantization)

Original Gufo reference resource:
`/home/paperboy/ds4-tests/gufo-qwen38-38bb39ee/model`.
Unsloth `Qwen3.8-Flash-Next-GGUF` revision
`38bb39ee97821de2c9009abb7e93950eec396e66`:

| File | Bytes |
|---|---:|
| Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf | 10946624 |
| ...-00002-of-00004.gguf | 49859583136 |
| ...-00003-of-00004.gguf | 49376141504 |
| ...-00004-of-00004.gguf | 12087983520 |
| mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf | 2786568256 |

All are present. SHA-256s already qualified by the inherited download/performance
receipts are recorded, not recomputed; size/dev/inode/mtime/ctime still match the
sealed receipt for all five. Shard 1 is GGUF v3 metadata-only (zero tensors),
not an empty or missing model. Architecture `qwen4exp`, tokenizer gpt2/qwen35,
248320 entries; exact length-prefixed vocabulary hash
`b7f4906b5bf6a845baf3f41fdcdcd70f0f2f234eb702aabb830ce1536604e5d6`.
Trunk template: 9993 bytes, SHA256
`12827f24b742ea4e80cdc12dbcf9622227056b9f797252a3149263d4f9aaadce`.
MTP template is the 8952-byte official form
`c3cf9e34abf4f9e36c2d72165aa9c132d3e2a725b6c2586aaa3a8af9d7a81041`.
The inspected upstream Qwen renderer explicitly recognizes both hashes. Use
trunk tokenizer/template identity, not sidecar template as an override.

Separate DS4 resources under `/home/paperboy/ds4-launcher/models/gguf`:
`Qwen3.8-Flash-Next-Q2.gguf` (147207127040 B), GGUF v3, 1256 tensors,
name explicitly says IQ2_XXS imatrix trunk / padded Q2_K down / MTP. Its
vocabulary hash matches, but its template is the 8952-byte official form.
`Qwen3.8-Flash-Next-Q4.gguf` (177280286720 B) and the Q8_0 vision projection
(616703104 B) were stat-inventoried, not tensor/metadata-qualified in this fork.
Their historical hashes are marked as such. Do not treat the Q2 resource as the
original UD-Q4_K_XL or silently swap it in to pass a test.

No weights are downloaded/moved/requantized. Full hash rereads, if required,
must be scheduled with DS4, not overlap benchmark cache behavior.

## Existing validated path: historical, not rerun here

The inherited native19 DS4→Gufo port at DS4 `c05cd8e2...` / vendored Gufo
`982bffea...` has a sealed functional short-context matrix and AR retrieval through
128K. Its `native-perf-closure-r1` records 42 measured +14 warmup cases, C facade
versus direct API of **that same modified backend**, with bit-identical outputs.
At fresh pp131072/YaRN2: C PP 694.45 / direct 684.25 tok/s; TG128 20.92/20.96.
Those are not synapse-lie results or independent pristine Gufo measurements.
Historical binaries/hashes, fixtures and conditions remain in the receipt;
none is executed or copied into LIE. The other agent can keep building them.

The previous 300K stop was an assistant-imposed 32GiB reserve with 30.469GiB
still available, NOT OOM or evidence that 300K does not fit. LIE inherits no
such arbitrary memory claim or default floor.

## Fresh independent baseline gate (pending)

Source pin: upstream Gufo `f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, independently
fetched into this project's `.deps`. Archive SHA256
`4b61a3f23e5ab51f7c95d6a7b6d2d82c8f7976e39f9566196f75323ab5eb2110`.
The pristine reference source is unmodified. Gufo's release CMake owns **only
this comparator build**, not the LIE backend build. Register compiler/flags and
loaded DSOs, and keep comparator binaries in a content-addressed test-owned
directory. The reference-only interoperability object check is NOT that baseline
build, nor an implementation of the LIE backend. See [BACKEND.md](BACKEND.md).

After shared lease/admission, first verify upstream with the first original
shard, AR, context4096, one session, no MTP/vision, greedy/thinking-off, known
literal prompt and bounded output. Record physical rendered input IDs/template,
output IDs/logits if available and completed GPU execution. Only then compare
LIE's reimplemented executor with the same exact physical workload/configuration.
The candidate must execute its own model graph/state and selected ported numerical
operations, not call the reference Model/Session through a facade.
Example upstream server command to verify against the pinned CLI before use:

```sh
OWNED_GUFO serve llm --model ORIGINAL_FIRST_SHARD --host 127.0.0.1 --port 19881 \
  --sessions 1 --context 4096 --prefill-chunk 2048 --think off --speculative off
```

Future matched benchmark axes are separate: same weights/quantization across
engines; AR vs MTP; C1 vs C2/4/8; cold/RAM/SSD prefix. Start 16K/32K before long
contexts; refuse when measured budgets cannot admit. Include long-prompt arrival,
tool wait/resume, cancellation and slow clients. Aggregate throughput = completed
confirmed tokens / common wall window, not summed per-request rates. Record TTFT,
queue/request duration, per-token vs SSE-group spacing and all relevant memory.
Warmups excluded; fixed paired order and enough repeats for observed variance;
no silent outlier removal. Serial fallback is not shared GPU batching.

Gufo's published “128K” PP is roughly pp2048 AFTER a cached prefix, unlike the
historical full fresh pp131072 above. Published rates are neither acceptance
thresholds nor directly comparable without matching those workloads.
