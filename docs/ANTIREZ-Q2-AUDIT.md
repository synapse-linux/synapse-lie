<!-- SPDX-License-Identifier: MIT -->
# Q2 audit — 2026-10-02

The target is Gufo support for antirez's **weight formats**, independently of
the future LIE C17 engine port. User priority: Q2 first, no performance loss.
Reading format documentation from antirez is not adopting its Qwen engine.

## Pinned sources and reference verdict

| Source | Git revision | Finding |
|---|---|---|
| Active LIE Gufo dependency | `f783fedb9bea2ec7de941f6da4e02f4a4596b29e` | Existing UD serving baseline; exact Q2 unsupported |
| Official Gufo inspected independently | `594a623913b4109e4499885e9f73ed4d4ad3698e` | Same Q2 binding/dispatch gaps; pin update alone is insufficient |
| Official llama.cpp | `a868c3e3c56657f7e8a6231190dbbe90e7dd86c0` | Concrete padded-Q2 shape blocker in loader; not an executable same-file reference established by this audit |
| antirez format/runtime documentation | `0aaea5a238fb41a35106a551e73c8409dfb751ac` | Documents exact quantization mix, but ROCm unsupported; runtime excluded from the implementation by the user |

These are source-derived findings, not new runtime refusal or speed results.
Selected source files were fetched directly from their official repositories at
these revisions. No sibling-workspace source or binary was imported.

The llama.cpp model reads `expert_feed_forward_length=640`, then creates
`ffn_down_exps` with `[640,2560,512]`. The actual Q2 descriptors say
`[768,2560,512]`. Its loader checks every dimension and throws on a mismatch.
Merely enabling generic IQ2_XXS/Q2_K HIP kernels does not resolve that model
binding. Changing the single shared FF width to 768 would break gate/up and
the shared expert. This is a blocker even if other earlier checks also fail.
See [Qwen binding](https://github.com/ggml-org/llama.cpp/blob/a868c3e3c56657f7e8a6231190dbbe90e7dd86c0/src/models/qwen4exp.cpp#L277)
and [dimension validation](https://github.com/ggml-org/llama.cpp/blob/a868c3e3c56657f7e8a6231190dbbe90e7dd86c0/src/llama-model-loader.cpp#L880).

The antirez documentation explicitly excludes ROCm for this model. It cannot
provide a same-device throughput baseline on `.157` without another port, and
its engine is outside this implementation's scope. See
[upstream model documentation](https://github.com/antirez/ds4/blob/0aaea5a238fb41a35106a551e73c8409dfb751ac/docs/QWEN38_FLASH_NEXT.md).

No ready independent implementation for the exact Q2 artifact on `.157` was
established among these audited candidates. This is not a claim that none
exists anywhere. A different GGUF, another GPU, historical smoke, or a mutable
DS4 binary cannot silently replace that reference.

## Confirmed Gufo work

1. **Reader:** IQ2_XXS and Q2_K have type identities, but MXFP4 type 39 is absent
   from the core type list. Q2 contains MXFP4 in its stored predictor, so AR-only
   loading still needs correct descriptor geometry. The earlier LIE reader
   fixture at `f783fedb` recorded this refusal; no new parser test was run here.
2. **Binder:** `FormatOf` and the routed-format list omit IQ2_XXS/Q2_K/MXFP4.
   Down binding requires 640 columns, and HC inject excludes F16. The logical
   architecture check deliberately remains 640. See
   [weights](https://github.com/gufo-org/gufo/blob/594a623913b4109e4499885e9f73ed4d4ad3698e/src/models/qwen38_flash_next/weights.cpp)
   and [configuration](https://github.com/gufo-org/gufo/blob/594a623913b4109e4499885e9f73ed4d4ad3698e/src/models/qwen38_flash_next/config.cpp).
3. **Numerical routes:** reusable quantized tile code exists for IQ2_XXS/Q2_K
   (and MXFP4), but the Qwen adapter instantiates and exposes Q4_K/Q5_K/Q5_1/Q8_0.
   Vector type admission, PP dispatch, paired/fused gate-up, and down dispatch
   must all be covered. Existing low-level code is not evidence of working
   Qwen support. See [adapter](https://github.com/gufo-org/gufo/blob/594a623913b4109e4499885e9f73ed4d4ad3698e/src/models/qwen38_flash_next/kernels/rocm/mmq/qfn_mmq.hip.cpp)
   and [tile implementations](https://github.com/gufo-org/gufo/blob/594a623913b4109e4499885e9f73ed4d4ad3698e/src/models/qwen38_flash_next/kernels/rocm/mmq/mmq.hpp).
4. **Activations:** the current executor allocates gate/up scratch at logical
   width 640 and passes it directly into down projection. Accepting a 768-column
   weight alone would produce incorrect activation reads/strides. Both vector
   decode and tiled prefill need the format contract below.
5. **HC inject:** F16 can use an existing dense projection, but the current fused
   inject epilogue requires F32. Binder acceptance alone therefore does not
   preserve the fused execution path. A lossless load-time F16-to-F32 expansion
   of these small tensors, or a qualified F16 fused operation, must be compared.
   This is not permission to expand the routed experts into dense weights.
   See [executor](https://github.com/gufo-org/gufo/blob/594a623913b4109e4499885e9f73ed4d4ad3698e/src/models/qwen38_flash_next/kernels/rocm/executor.cpp).
6. **PLE and admission:** BF16 PLE is already an accepted binder format. Its
   102400491520-byte table requires bounded row access and separate accounting;
   it is not a missing quantization. Disk/page-cache residency is distinct from
   model-prefix reuse. File size is not live device allocation.

The minimal proposed change connects the existing quantized numerical primitives
behind Gufo's private model boundary, introduces explicit physical down width,
and preserves shared UD routes. It does not replace the model graph with antirez
code, create a CPU forward, or restore the withdrawn LIE Q2 patch.

## Handoff and next gate

[Q2-FORMAT-CONTRACT.md](Q2-FORMAT-CONTRACT.md) specifies binding, packing,
activation and memory invariants. [Q2-VALIDATION.md](Q2-VALIDATION.md) defines
the comparison before implementation, including per-profile PP/TG verdicts.

The inherited `REPLAN.md` requires a working independently acquired reference
before another port. That gate remains open because of the blockers above.
Resolving it requires an exact-layout implementation independently established
on `.157`, or an explicit revision of the reference-first gate. A locally patched
llama.cpp would be another unqualified port, not an already proven reference.
No GPU/remote build is authorized by this audit; coordinated admission still
precedes those operations. Runtime completion is not claimed.
