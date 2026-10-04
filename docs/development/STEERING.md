<!-- SPDX-License-Identifier: MIT -->
# Directional steering implementation

The C17 shared library now owns direction-bank loading, bounded host allocation,
immutable values and identities. GPU activation edits and public HTTP/bench
controls are **not implemented by this increment**. Loading a bank is not model
inference and does not qualify steering quality or performance.

## Shared bank contract

[`lie/steering.h`](../../include/lie/steering.h) defines independent ABI 1.
Callers supply the loaded model's trunk-layer count, hidden width and an explicit
host vector budget. No model family or platform is hardcoded. The loader requires
exactly `layers * width * 4` bytes of headerless little-endian IEEE754 binary32,
matching DS4's flat `.f32` direction files on the supported little-endian targets.
Each layer occupies one contiguous hidden-width row. Values are copied exactly;
the loader does not normalize, quantize or compress them. Finite zero directions,
negative zero and subnormals are preserved.

Malformed sizes, overflowing geometry, invalid ABI tags, nonfinite values,
symlinks and nonregular files are refused. FIFO admission is nonblocking.
Read-only descriptor stats are witnessed before and after bounded reads; a file
change refuses admission. Failure leaves the caller's output handle unchanged.
The original file is never modified or retained as a mutable mapping.

The loaded bank is immutable and has explicit thread-safe owned references.
A borrowed float span remains valid while its owner holds a reference, including
after the source file is changed or unlinked. Reference operations do not create
threads; numerical operations remain on the eventual device owner.

`file_sha256` identifies exact file bytes. `scope_sha256` is SHA-256 over:

```text
ASCII "synapse-lie.steering.v1" + NUL
uint32 little-endian layer count
uint32 little-endian hidden width
original file bytes
```

Identical bytes interpreted with different tensor geometry have different
scopes. A future cache binding must additionally include model identity and
effective steering scales/history; this bank digest alone does not implement
cache compatibility. Existing state and DS4 KVC payload formats are unchanged.

## Recorded provider binding requirements

Read-only official DS4 source at `0aaea5a238fb41a35106a551e73c8409dfb751ac`
places Qwen attention edits on the projected hidden-width block output before
the HC residual combine. FFN edits act on every HC residual branch after the
FFN combine. The separate MTP predictor is unsteered; drafts are verified by the
steered target. The documented positive scale removes a direction and negative
scale amplifies it. [Upstream description](https://github.com/antirez/ds4/blob/0aaea5a238fb41a35106a551e73c8409dfb751ac/dir-steering/README.md).

The pinned Gufo HIP provider fuses residual combine and the following grouped
normalization. Editing its residual after that combine invalidates the prepared
normalization. The binding must refresh that normalization, including quantized
and half-precision cached views, before the following mixer. An edit on only the
MoE block output is not the required per-HC-residual FFN edit.

Per-session scale changes must run on the exclusive device owner, preserve past
KV state, and invalidate incompatible captured graphs and pending speculative
proposals/correction assumptions. Define and retain the effective scale history
when capturing RAM/SSD state; a token-only prefix must not reuse state produced
under different steering. No extra provider/HTTP thread is introduced.

Remaining work in roadmap item 5 is the actual HIP binding, shared admission and
session controls, cache scopes, HTTP and native bench exposure. GPU gates on
`.161` must prove unchanged output with steering absent/zero, malformed input
refusal before model mutation, prompt/decode edits, scale transitions, independent
AR/MTP checks and measured quality/cost. The user-visible naming follows DS4's
`--dir-steering-file`, `--dir-steering-ffn`, `--dir-steering-attn` once those
controls are implemented; they are not available CLI flags yet.

## Validation

Four focused Debug checks and the same four ASan/UBSan/LSan checks pass.
The bank fixture covers exact little-endian values and independent known SHA
oracles, alternative geometry, partial/trailing/nonfinite data, allocation bounds,
ABI/output preservation, multichunk reads, file types, concurrent references and
snapshot lifetime after source mutation/unlink. The other checks exercise shared
core context admission, lifecycle and semantic events with CPU fixtures.
[Commands and scope](validation/steering-bank-host-2026-10-04.json).
