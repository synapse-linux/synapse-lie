# State envelope design — not implemented

This is a compatibility/lifecycle contract for increment D, not a claim that
snapshot save/restore works in synapse-lie today. No snapshot files are produced
by the current server; no DS4 payload is imported or converted.

## Two distinct kinds

`prefix_checkpoint`: immutable model frontier at an exact list of processed
physical tokens. A new request gets its own sampler/RNG and parser state.

`resumable_session`: model frontier PLUS exact continuation state: sampler
configuration, RNG/draw state, penalties/history, accepted-but-not-emitted token
bytes/UTF-8 remainder, stop matcher/parser, tool-call state and turn metadata.
Predictor/controller state must be saved or reconstructed by a specified replay.
No exact resume claim if any of these are omitted.

Qwen Flash Next is hybrid. Gufo `SessionSnapshot` stores tokens, last logits,
attention caches, recurrent state, draft block/history and the speculative
length controller. Its external `SamplerState` is not magically included. The
inspected payload version is 14. It is not compatible with DS4 native19 just
because weights or token counts match.

## Proposed on-disk framing (must be frozen and tested before writer code)

Little-endian envelope with magic, envelope version, fixed header length,
kind, total length, metadata length, token count, payload length and checksum
algorithm. Bounded canonical metadata and LE int32 token array precede the
opaque backend payload. SHA-256 covers the declared metadata + tokens + payload;
lengths and identity must validate before backend admission.

Compatibility identity must cover full weight/shard identities and quantization,
model config, tokenizer vocabulary/normalization, actual template/reasoning mode,
physical/rotary positions and RoPE settings, context/prefill/execution policy,
state dtype/representation, backend payload version and relevant arithmetic
build identity. No promise of cross-HIP/CUDA, quantization, capacity or build
portability. Model publisher terms remain separate from the state format.

## Write/restore lifecycle

1. Only the device owner selects a completed, confirmed frontier. No in-flight
   kernel may reference captured storage. Retain it until immutable host capture
   completes. Enqueue bounded disk work, not a full write on every token.
2. Write a same-directory exclusive temporary regular file; check ownership,
   reject symlinks/hardlinks, bound lengths and space. Flush data with fsync,
   atomic rename, fsync parent. Intended durability: acknowledged commit survives
   process restart and ordinary power loss subject to filesystem/device guarantees.
3. Read/validate the entire bounded candidate into controlled staging before GPU
   upload. Corruption, incompatible identity or missing file => clean miss then
   prefill. After a mutating restore is admitted, any failure is fatal to that
   session, NOT miss-and-forward. Record read/deserialize/transfer separately.
4. Account logical/allocated SSD bytes and staging memory. Idle-cache eviction
   cannot remove a payload still pinned by an in-flight reader/capture.
5. A longer recurrent state cannot be trimmed to an arbitrary common prefix.
   Reuse only exact checkpoint frontiers, otherwise select an earlier valid
   checkpoint plus replay or recompute. Tool/template boundaries use processed
   tokens, not similar visible strings.

## Required validation before enabling

Same-process and restart save/resume, isolated clones, exact future continuation,
AR and then MTP rollback, corrupt/truncated/oversized/foreign files, atomic-write
failure phases, interrupted workers, quota/eviction races and incompatible model,
template, context, dtype and payload versions. Benchmark restore wall time,
transfer and avoided prefill against recomputation; SSD is not assumed faster.
Active-state paging and weight streaming are explicitly outside this version.
