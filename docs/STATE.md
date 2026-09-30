# State envelope design — not implemented

This is a compatibility/lifecycle contract for increment D, not a claim that
snapshot save/restore works in synapse-lie today. No snapshot files are produced
by the current server; no DS4 payload is imported or converted.

## Optional SSD persistence — required feature, explicit opt-in

The user requires an optional SSD save/restore facility in addition to in-memory
prefix reuse. The ordinary per-sequence attention KV already used by inference,
retaining a reusable frontier across requests, and persisting that frontier across
process restarts are distinct capabilities. None of the latter two is implemented
in the current server.

- SSD persistence is **disabled by default**. In-memory reuse must work without
  it. Disabled means no persistent-state directory creation, scanning, reading or
  writing; no implicit spill to disk when RAM becomes scarce.
- Enabling the persistent store requires an explicit server option. Expose its
  directory and disk quota, independently of the RAM-cache budget. CLI spelling
  and config schema are not frozen yet; there is no working SSD flag today.
- Use only a LIE-owned private directory (proposed default when enabled:
  `$HOME/.local/state/synapse-lie/sessions`), never discover or reuse DS4 caches.
  State is sensitive conversation-derived data; use private directory/file
  permissions. Persistence does not imply encryption at rest.
- Save/restore complete compatible hybrid state, not an attention-KV-only dump.
  Restart reuse, bounded staging/I/O, atomic writes, eviction and admission retain
  the lifecycle and validation gates below. SSD reads/writes must not block the
  HTTP loop; no per-token disk writes or unbounded background queue.
- Disabling persistence stops using the store; it must not implicitly delete
  existing files. Explicit cleanup may affect only eligible LIE-owned entries,
  never an in-flight/pinned payload or another application's state.
- Benchmark RAM reuse, SSD restore and recomputation separately. SSD support is
  a required capability, not a promise that restoring is always faster or that
  active-state paging/weight streaming is supported.

## Two distinct kinds

`prefix_checkpoint`: immutable model frontier at an exact list of processed
physical tokens. A new request gets its own sampler/RNG and parser state.

`resumable_session`: model frontier PLUS exact continuation state: sampler
configuration, RNG/draw state, penalties/history, accepted-but-not-emitted token
bytes/UTF-8 remainder, stop matcher/parser, tool-call state and turn metadata.
Predictor/controller state must be saved or reconstructed by a specified replay.
No exact resume claim if any of these are omitted.

Qwen Flash Next is hybrid. LIE must own and capture its token history, logits,
attention KV, recurrent/SSM and convolution state, positions and, when supported,
MTP carry/history/rollback and controller state. Sampling/RNG must be included
explicitly for resumable sessions. The transitional adapter may initially capture
Gufo state, but it must be identified as delegated, complete and build/version-
qualified; it does not establish owned backend state. See [BACKEND.md](BACKEND.md).

The inspected Gufo `SessionSnapshot` and external `SamplerState` illustrate the
coverage requirements. A transitional Gufo v14 payload would need explicit engine,
version and compatibility admission plus the extra continuation state. Neither
it nor DS4 native19 is an implicitly accepted future owned-LIE restore payload,
even with identical weights/token counts. No capture/restore is implemented yet.

## Proposed on-disk framing (must be frozen and tested before writer code)

Little-endian envelope with magic, envelope version, fixed header length,
kind, total length, metadata length, token count, payload length and checksum
algorithm. Bounded canonical metadata and LE int32 token array precede an
engine-tagged, versioned payload with an explicit component/layout contract.
During transition it may be a documented Gufo-specific encoding; the eventual
owned encoding needs its own identity/qualification, not reinterpretation of
upstream bytes. Unsupported cross-engine state is refused before mutation, unless
an explicit versioned migration is implemented and qualified. SHA-256 covers the
declared metadata + tokens + payload; lengths, coverage and identity must validate
before restore admission.

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

Disabled mode with zero persistent-store I/O, RAM-only reuse independent of SSD,
explicit enable/path/quota validation, private permissions and no deletion on
disable; same-process and restart save/resume, isolated clones, exact future
continuation, AR and then MTP rollback, corrupt/truncated/oversized/foreign files,
atomic-write failure phases, interrupted workers, quota/eviction races and incompatible model,
template, context, dtype and payload versions. Benchmark restore wall time,
transfer and avoided prefill against recomputation; SSD is not assumed faster.
Active-state paging and weight streaming are explicitly outside this version.
