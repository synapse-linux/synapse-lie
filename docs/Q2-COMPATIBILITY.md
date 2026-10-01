# Antirez Q2 compatibility — first host slice

Status: **host storage/configuration/binding implemented and CPU-validated**.
A subsequent [private HIP candidate](Q2-HIP.md) now implements the routed paths
and passes 64 limited synthetic GPU cases. Full-format/model qualification,
memory admission and benchmarks remain **not run**. The production
provider and original qualified binaries remain unchanged. Q2 is **not yet a
runnable LIE inference model** and has no PP/TG benchmark result.

This begins the requested Q2 work before Q4. It extends the transitional Gufo
provider; it is not an autonomous C17 model loader/executor or a reimplementation
of the whole engine. The frontend, scheduler and benchmark remain C17.

## Implemented

`adapters/gufo-q2/host-edits.json` describes exact, hash-guarded changes to six files
in Gufo `f783fedb9bea2ec7de941f6da4e02f4a4596b29e`:

- GGUF type **39 / MXFP4** storage recognition and 32-element/17-byte geometry.
  Needed to parse the Q2 file's stored predictor descriptors even with MTP off.
  No MXFP4 decoder, MTP or Q4 execution route is enabled by this recognition.
- **IQ2_XXS** routed gate/up and **Q2_K** routed down storage/binding geometry.
- **F16 hyperconnection inject** accepted by the host binder. The existing dense
  path already has an F16 representation, but its real-model numerical behavior
  is not qualified by these host tests.
- Q2 down binding retains **physical 768 columns**, logical activation width
  **640**, row stride **252 bytes**, expert stride **645120 bytes** for 2560 rows,
  and **330301440 bytes per 512-expert tensor**. No reinterpretation as a shorter
  contiguous row and no weight conversion. Missing/partial/wrongly typed or
  inconsistent padding metadata and wrong tensor formats/shapes are refused.
- A scoped rule for this Q2 export's **omitted mRoPE section metadata**, described
  below. Present malformed metadata is never replaced.
- An explicit pre-device-weight-allocation refusal for Q2/IQ2 in the generated
  `DeviceModel::Upload`: `LIE Q2 HIP execution is not implemented: ...`.
  This is a source-level safety guard, not a tested GPU failure path. Do not
  remove it just to make a model launch pass.

The recipe changes reader enum/string representation, quantized storage sizing,
configuration, binder and that upload refusal. It does **not** patch `.deps`,
qualified archives or `cmake/gufo-runtime`. It contains no sibling DS4 project
source, recipe, configuration or executable. Original source/licenses/notices
remain with the independently acquired Gufo tree.

## Missing mRoPE sections: observed failure and bounded compatibility

The first full-header-derived bind failed with:

```text
missing GGUF array qwen4exp.rope.dimension_sections
```

The actual file omits that key. Its `ds4.qwen4.ngram.source_repository` and
`source_revision` identify `Qwen/Qwen3.8-Flash-Next` at
`de4b8e4d43b917e7706784d8bb445c9af86a3540`. An independent fetch of official
`config.json` at that revision confirms `mrope_section=[11,11,10]`;
Gufo's fourth section is the zero pad. Config SHA256:
`889658f2508e8c61d409b02e70e0d78d8d4452ec65aaafbe129805d213d2e74b`.

The rule applies only when the key is **absent**, trunk binding is requested,
both padding markers are uint32 640/768, and repository/revision markers exactly
match. All the existing strict architecture/shape checks still apply. Unmarked
files, wrong markers/types, malformed explicit sections and predictor-only
configuration retain refusal. This is a versioned compatibility interpretation,
not an edited GGUF, a generic default for unknown models or a retry/fallback
following inference failure. Marker identity does not independently authenticate
weights or qualify numerical equivalence.

The official configuration and accompanying **Qwen Community License 1.0** are
retained in ignored `evidence/q2-config-reference-r1/`. Only the architectural
parameter facts were used; no Qwen model-forward code was imported. First-party
MIT and Gufo notices do not relicense model/configuration assets. The retrieved
license includes separate conditions for commercial model/AI-assistant services;
no distribution/deployment or license eligibility is asserted by this work.

## Actual-header-derived binding, not a model load

A bounded read-only capture preserved exactly **11025350 header bytes** from the
protected Q2 file on `.157`, with the same header SHA256 and size/device/inode/
mtime/ctime identity as the previous inspection. No payload or full-model hash
was read/recomputed, no GPU admission was attempted, and no model was modified.

`tests/q2_header_bind.cpp` gives the actual pinned reader and `ModelWeights::Bind`
those bytes in a shifted anonymous virtual mapping. The entire declared tensor
payload region starts at a page boundary and is **PROT_NONE**, including its first
byte. Tensor values are absent. Only header pages are readable; virtual address
reservation is **not** physical allocation, resident weight capacity or fit proof.
An accidental tensor read would fault rather than silently read invented weights.

With the compatibility rule, GCC and Clang probes both bind the actual **1256
stored descriptors / 48 AR layers**, checking all IQ2 gate/up, physical Q2 down
strides, F16 inject roles and the BF16 PLE view. The predictor remains unbound for
inference. Status:
`ACTUAL_Q2_HEADER_BINDING_PASS_NOT_MODEL_LOAD_OR_INFERENCE`.

## Verification and source isolation

```sh
# New labels only; neither command runs HIP or opens model weights.
python3 -B tools/q2_port.py q2-private-source-example-r1
python3 -B tools/verify-q2-host.py q2-host-check-example-r1
```

The preparer verifies every pristine file and exact before/after hashes, rejects
ambiguous/overlapping replacements, creates a fresh private source tree, and
records all resulting hashes in `LIE-Q2-SOURCE.json`. It copies verified bytes,
never applies edits in place. `runtime_link_allowed=false`; the existing
production source/archive checker also rejects this private variant. No provider
ID, source pin or original qualified receipt is relabeled as this experiment.

- `q2-host-red-r1`: six behavioral failures / seven tests against pristine source;
  the legacy-format control passes. Compilation succeeds, CTest exits 8.
- `q2-host-green-r1/r2`: initial storage/binder tests pass GCC/Clang/ASan/UBSan.
- `q2-header-binding-r1`: actual-header-derived bind fails on absent mRoPE sections;
  exit 1 preserved, no numerical/model request was attempted.
- `q2-host-green-r3`: test compilation fails under `-Werror=range-loop-construct`;
  fixed by taking a const reference, not by weakening compiler flags.
- `q2-host-green-r4/r5`: eight host CTest cases pass GCC/Clang/ASan/UBSan; includes
  canonical-omission, malformed/present/unidentified metadata refusal and legacy
  binding regression tests. No HIP link or model forward.
- `q2-header-binding-r2`: actual saved header binds with GCC and Clang, exit 0.
  Sanitizers cover the small generated fixtures, not the large virtual view.
- `q2-source-contract`: seven development-tool tests; default CTest does not
  require a fetched optional Gufo tree. The dedicated host verifier additionally
  verifies/materializes all 1019 pinned files and refuses production linkage.
- `q2-host-closure-r1`: all fifteen default CPU suites pass GCC/Clang/ASan/UBSan
  with serial builds and the original adapter header check. C++ fixture formatting
  passes the installed clang-format check; no independent review is claimed.

## Next implementation gate

The [subsequent HIP candidate](Q2-HIP.md) implements vector/tiled/grouped routes,
reserved scratch and direct **quantized padding 640→768** without an extra FP32
row copy. It reuses pinned upstream numerical helpers. Compilation and host
contracts alone do not prove GPU execution. The subsequent 64-case GPU run
passes only the documented initial operator subset; broader format/shape,
tail/lifetime and full-model qualification remain required.

Keep original-UD paths and `kTailMargin` safety intact. Then qualify tiny kernel
oracles, full-model frontiers and numerical behavior against a separately pinned
reference. The BF16 PLE table is CPU-addressed storage, not an excuse to equate
147 GB file size with all-resident GPU memory or bypass admission. Add a bounded,
role-aware memory plan before the first real model load. All actual GPU work
requires fresh coordination/leases. Only then run the matched
[prefill/decode protocol](ANTIREZ-BENCHMARKS.md); no performance claim is made now.
