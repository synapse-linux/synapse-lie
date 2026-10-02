<!-- SPDX-License-Identifier: MIT -->
# Q2 format contract — proposal 1

This is an implementation requirement, not a new exported C ABI. It applies to
the transitional official-Gufo adapter and can later be implemented by the C17
model-family module without changing the GGUF or HTTP contract. Upstream C++
types, HIP streams and kernel layouts stay inside the numerical implementation.

## Exact file and roles

The [manifest](../config/antirez-q2-contract.json) derives from LIE's retained
2026-10-01 header observation. No payload was read again and the historical full
hash was not recomputed. Architecture `qwen4exp`: 49 stored layers, 1 predictor,
48 AR layers, hidden width 2560, 512 experts, top-k 10, logical FF width 640,
native context 262144. No YaRN or 1M capability follows from quantization support.

| Role | Count | Encoding | GGUF shape | Encoded row bytes |
|---|---:|---|---|---:|
| AR gate/up | 96 | IQ2_XXS: 256 values / 66 bytes | `[2560,640,512]` | 660 |
| AR down | 48 | Q2_K: 256 values / 84 bytes | `[768,2560,512]` | 252 |
| AR HC inject | 96 | F16 | `[10240,4]` | 20480 |
| Stored predictor gate/up | 2 | Q4_K: 256 values / 144 bytes | `[2560,640,512]` | 1440 |
| Stored predictor down | 1 | MXFP4: 32 values / 17 bytes | `[640,2560,512]` | 340 |
| PLE table | 1 | BF16 | `[160,320001536]` | 320 |

Other dense/norm/embedding roles retain their recorded F32/F16/BF16/Q8_0 types.
The complete type counts and selected tensor identities are in the manifest.
Do not infer uniform quantization from `Q2` in the filename.

## Binding and activation invariants

- Keep logical FF width **640**. The file explicitly records
  `ds4.qwen4.down.logical_input=640` and
  `ds4.qwen4.down.physical_input=768`; both must agree with architecture and
  every affected AR down tensor. The predictor has separate unpadded geometry.
- Represent logical input length, stored column count, encoded row stride,
  expert stride, format, and optional packed-layout version separately.
  For Q2_K down, expert stride is `252 * 2560 = 645120` bytes. Never floor
  `640 / 256` to derive a stored stride; never change the shared expert width.
- Gate/up produce 640 live values per `(token, selected expert)`. Down consumes
  these plus **128 zero activation lanes**. Either explicitly pad in bounded
  device scratch or fuse logical-read/physical-write padding into activation
  quantization. Never read 768 floats from a 640-float allocation. Row and expert
  strides must be correct for C1, chunked PP and each supported batch size.
- Zeros must be defined every time scratch is reused, including final partial
  chunks. Quantized down weights in padded columns need not themselves be zero;
  padded activations remove their contribution. Keep every live Q2 block intact.
- Validate all descriptors, including unused MTP tensors, with checked block,
  dimension, offset, multiplication, extent and alignment arithmetic. Unknown
  types or contradictory padding metadata refuse before device submission.
  Recognizing MXFP4 storage in the unused predictor does not enable its forward.
- Preserve original GGUF bytes and tokenizer/template identities. No conversion,
  re-quantization, weight substitution or global metadata-width rewriting.

## Numerical packing and performance

Both PP and TG operate on quantized expert weights. Reuse official Gufo's
licensed GGML-derived tile/dot primitives where appropriate. Wire explicit
IQ2_XXS and Q2_K routes, instantiations and activation quantization, plus
shared-input gate/up handling; do not fall back to per-element CPU decoding or
full dense expert expansion to claim loading success.

The official tile source also contains optional IQ2/Q2 structure-of-arrays
loaders. Their presence does not establish an uploader or qualified execution
path. Any repacking must be lossless, versioned, independently checked, bounded
and timed separately at load. Do not copy the sibling project's packing code or
cache artifacts. Preserve raw/packed allocation lifetimes and peak bytes.

Numerical qualification must catch IQ2 codebook/sign/scale mistakes, Q2 scale
product rounding, block tails, expert gathers, SwiGLU ordering and aliasing.
Changing to lower-precision intermediates is a numerical change, not merely a
format adapter. A kernel microbenchmark never substitutes for full PP/TG.

F16 HC inject needs a correct numerical route as well as binder acceptance.
Evaluate load-time exact widening of the 96 AR inject tensors separately from
an F16 fused path. Widening would add 7864320 bytes to their final representation;
peak source/staging overlap is additional. Preserve all other dense dispatch.

## Ownership, resource and state boundary

The family binding owns the logical model schema. The numerical implementation
reports supported `(role, dtype, logical shape, storage shape)` combinations,
selected packing identity, persistent allocation bytes, load scratch and
per-submission scratch. Do not leak Gufo structs into the C17 engine contract.
Unavailable combinations return a capability refusal, not CPU fallback.

Encoded bytes derived from the observed descriptors are 43287498240 for AR
excluding PLE, 1508088832 for `blk.48.*`, and 102400491520 for PLE. These are
storage totals, not RAM/GPU fit estimates. Admission also covers representation
changes, upload overlap, tail guards, sessions, hybrid state and working memory.
MTP-off must not reserve active predictor state or execute its weights.

Keep PLE access bounded and identify row-I/O policy. Do not charge its entire
file as resident device memory, silently bypass memory admission, or describe
OS page-cache warming as KV/prefix-cache reuse. No global cache flush or tuning.

The adapter continues to report completed work through LIE's existing execution
boundary. No new per-token host synchronization, reactive scheduling policy,
cross-request cache, MTP or vision behavior is introduced by this format change.
Future snapshots identify original weights, numerical/packing version, model
family and state schema; a differently packed device buffer is not portable
state just because its public dtype has the same name.
