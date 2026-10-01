# Antirez Qwen3.8 Flash Next — prefill and decode benchmark gate

**Required:** benchmark the actual antirez Q2 and Q4 artifacts, including **full
fresh prefill** and decode. UD-Q4_K_XL results are not substitute measurements.
Status: **NOT RUN — backend format gaps confirmed before GPU model loading**.
No rate, speedup, regression bound or memory-fit result exists for these files in
LIE yet. This work takes priority over claiming any cache-related speedup.

The user selected **Q2 first**. The subsequent [host compatibility
slice](Q2-COMPATIBILITY.md) implements the private reader/configuration/binder
changes and binds the actual saved Q2 header without accessible tensor values.
It is not linked into the production provider. A subsequent [HIP routing
candidate](Q2-HIP.md) passes 64 limited synthetic GPU operator cases, but has not
loaded/executed the model. GPU PP/TG remain blocked pending full-format/model
qualification and memory admission.
The original pristine-provider gaps below are retained with their scope.

## Actual files, read-only layout observation

On 2026-10-01, `tools/gguf-layout.py` read only metadata/tensor descriptors on
`.157`, capped at 24 MiB per file. No payload read, mmap/model load, HIP, full
weight hash, conversion, installation or DS4 modification occurred. Both file
stat identities still matched the inherited inventory (size/device/inode/mtime/
ctime). Historical full hashes are retained in `config/models-157.inventory.json`,
not represented as newly verified content hashes.

Paths under `/home/paperboy/ds4-launcher/models/gguf/`:

| File | File bytes | Declared encoded tensor bytes | Header bytes read |
|---|---:|---:|---:|
| `Qwen3.8-Flash-Next-Q2.gguf` | 147207127040 | 147196078592 | 11025350 |
| `Qwen3.8-Flash-Next-Q4.gguf` | 177280286720 | 177269238272 | 11025109 |

Each contains 1256 tensors, metadata `block_count=49` / `nextn_predict_layers=1`:
48 AR layers plus a stored predictor layer. MTP remains disabled for the proposed
AR baseline, but the reader must still understand the file's descriptors.
Neither is a uniform quantization inferred from its filename:

| Role | Q2 artifact | Q4 artifact |
|---|---|---|
| AR routed gate/up | 96 IQ2_XXS tensors, `[2560,640,512]` | 96 Q4_K tensors, same shape |
| AR routed down | 48 Q2_K tensors, **`[768,2560,512]`** | 48 MXFP4 tensors, `[640,2560,512]` |
| Predictor routed gate/up/down | Q4_K / Q4_K / MXFP4 | Q4_K / Q4_K / MXFP4 |
| Hyperconnection inject | F16, `[10240,4]` | F16, same shape |
| PLE table | BF16, `[160,320001536]` | BF16, same shape |

The PLE table alone occupies **102400491520 encoded bytes**. File/encoded bytes
are **not** equivalent to all-resident GPU memory: binding, optional predictor,
CPU-mapped PLE row access, upload representation, workspace and active context
need separate accounting. These files are not sparse in the observed allocated-
byte accounting. Neither their large size nor a conservative admission refusal
is an OOM/fit result. The current original-UD supervisor's whole-trunk-file size
estimate must not be silently removed or reused as a correct antirez RAM budget.

Q2 metadata explicitly records logical down input 640 and physical input 768.
Reinterpreting that as an ordinary unpadded 640-column tensor would use incorrect
row/expert strides. Correct activation padding and completed PP/TG are required.

Header SHA256 (not payload/full-model SHA256):

- Q2: `2c1fe3665e20b93beeaffe73bb6329ec010eee5882a1a84f768392d0787f434d`
- Q4: `06c6270356fd5e2fd32a1f4194798794c37c5f044e5ae0cc6b6e88101312401d`

The first inspection correctly left type 39 unknown. Independent retrieval from
**official upstream** `antirez/ds4` at
`c05cd8e2bd35047196d95709f89d0ea2aff96df2` identifies it as **MXFP4**, 32 elements /
17 bytes per block (`ds4.c` format table and static assertions). It is not Q4_0.
The second inspection adds only this storage geometry and validates all declared
extents/alignment/non-overlap; the header hashes remain identical. No decoder,
model forward, recipe or local DS4 project artifact was imported. Upstream MIT
license/notices and URL/status/hash receipts are preserved in
`evidence/antirez-format-reference-r1/`.

## Confirmed gaps in the current LIE provider

Numerical provider remains pristine Gufo
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`; no source/archive/kernel was modified.
These are concrete blockers, not an exhaustive claim that all other roles work:

1. **GGUF reader:** type 39 is absent and encoded size is zero. A local CPU probe
   against the actual pinned `gguf_reader.cpp` / `ggml_dequant.cpp` accepts valid
   synthetic Q8_0/Q2_K/Q4_K/IQ2_XXS storage, but rejects valid MXFP4 with
   `Invalid GGUF tensor shape or unsupported storage type: fixture.weight`.
   This is a storage-parser test, **NOT a real-model load or inference test**.
   Both real files contain MXFP4, including the Q2 predictor even with MTP off.
2. **Qwen binder:** `weights.cpp::FormatOf` and the routed accepted-type list omit
   IQ2_XXS, Q2_K and MXFP4. Routed down binding requires logical 640 columns, not
   the Q2 file's physical 768. `Mixer` also excludes F16 for `_inject.weight`.
3. **HIP routes:** the current routed MMVQ dispatch selects Q5_1/Q8_0/Q4_K/Q5_K,
   not these missing types. PP tiled/grouped routes, decode, upload geometry,
   fused gate/up, down projections and tail handling all need a role-specific
   implementation and numerical/performance tests; adding enum recognition is
   not support. Preserve the existing tail/allocation safety rules.
4. **Memory admission:** account actual selected live representations and bounded
   PLE staging/access, not a guessed RAM floor or a silent budget bypass. Cold
   PLE/OS-cache effects must not be mislabeled as cached-prefix inference.

No GPU launch is attempted merely to rediscover this known parser refusal.
No CPU model-forward fallback, weight replacement, implicit conversion or use of
another agent's mutable DS4 executable is acceptable.

## Required benchmark protocol

Each quantization has its **own** model identity, comparator and result table.
A Q2 output need not equal a Q4 output. Preserving performance means comparison
with that format's reference under matched conditions, not Q2=Q4 or substitution
of UD-Q4_K_XL results.

Initial AR/C1 lane, based on the existing **C17** `lie-executor-bench` protocol:

- full fresh prefill targets **512 / 2048 / 8192** physical tokens, recording
  actual renderer/tokenizer counts and full input IDs, never relabeling a nearby
  count as an exact target;
- fixed context 9216, chunk 2048, greedy, thinking off, one owner, no MTP, vision,
  prefix reuse or SSD state; up to **128 output tokens**, honoring EOS;
- one declared warmup per profile, then three measured rounds ascending /
  descending / ascending; preserve all samples, errors and early EOS;
- PP milliseconds and **newly completed physical input tokens / PP seconds**;
  TG milliseconds and **emitted output tokens / completed decode seconds**;
  executor synchronous wall time, not kernel-only time, enqueue time or TTFT;
- full finite PP/TG frontier witnesses and within-format repeatability, plus a
  separately pinned, immutable independently built reference. Same physical
  tokens, template, context, chunking, sampling and EOS/completion policy;
- no global cache drop, power tuning, conversion/download or opportunistic entry
  into another campaign. Every actual run needs current coordination, all leases,
  raw identities/telemetry/exit records and owned cleanup.

A **separate HTTP/server C1 lane** must exercise the updated worker using matched
inputs/settings and `lie_timings`; collect client TTFT/delivery separately if
implemented. A direct ABI rerun bypasses the worker and cannot prove the new
server has no regression. The definitive `synapse-lie-bench` remains C17; Python
inspection/supervision/analysis is intermediate tooling, not that finished tool.
Longer context, cached-prefix depth, concurrency, MTP and graphs are subsequent
capability-gated lanes, not invented results when unavailable.

Until complete loading and numerical gates pass, PP/TG entries are **not_run /
blocked**, with rates absent or null — never zero or copied from another model.

## Validation and retained evidence

- `antirez-layout-red-r1`: draft inspector accepted invalid boolean/alignment
  metadata and blocked opening a FIFO; three CPU regressions fail, exit 1.
- `antirez-layout-green-r1/r2`: fourteen CTest suites pass across GCC/Clang/
  ASan/UBSan and adapter header check, including fifteen synthetic GGUF cases in
  the final scanner suite. No model/GPU execution.
- `antirez-layout-readonly-r1/r2`: actual bounded remote descriptors/stat identities,
  first unknown type 39 then complete MXFP4 geometry; neither is inference.
- `antirez-reader-refusal-r1`: CPU in-memory fixture probe of the pristine reader,
  positive storage controls and MXFP4 refusal, exit 0. No HIP link/model access.

The inspector opens only regular files without FIFO blocking, verifies identity
before/after, hashes exactly the consumed header, rejects bounds/shape/type/extent
errors and preserves unknown types with incomplete geometry. Array values are fingerprinted without semantic interpretation; this
is not a full GGUF/model semantic validator. It does not read or validate tensor
values, qualify model correctness, estimate resident fit, or claim inference
support from storage recognition.
