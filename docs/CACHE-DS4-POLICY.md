# DS4 cache policy in the shared core

Implementation checkpoint, 2026-10-02. This is C17 policy shared by HTTP,
`--suite core` and future clients. The numerical executor remains the explicit
Gufo adapter. **The native checkpoint file is not a DS4 KVC file.** Existing
GPU reports qualify their recorded builds, not this new policy automatically.

## Implemented behavior

| Capability | Current implementation |
|---|---|
| Persistent utility | Creation/use timestamps and hit counts survive SSD restart; six-hour half-life; purpose and superseded-prefix weighting |
| Progressive checkpoints | Cold prefix, stable chat anchor, periodic prefill/decode frontier, normal retirement and graceful shutdown |
| Text-prefix reuse | Longest matching byte prefix, exact saved token history, suffix-only tokenization with vocabulary/context validation |
| Extension metadata | Bounded owned text/trailer bytes and key-kind flags in RAM and SSD; client supplies protocol serialization |
| Dynamic index | RAM and SSD tables grow geometrically inside explicit index bounds |
| Quota change | An exclusively owned private SSD store evicts entries when reopened with a smaller quota |
| Context growth | Smaller saved context may restore into a larger context after component/geometry validation; numerical qualification pending |
| Reactive operation | One device owner and one SSD worker; a row awaiting checkpoint I/O yields while eligible peers continue |

The policy defaults follow the reviewed official
[ds4_kvstore.c](https://github.com/antirez/ds4/blob/main/ds4_kvstore.c)
contract: minimum 512 tokens, cold maximum 30000, continued interval 10000,
boundary trim 32 and alignment 2048. The aligned continued interval is 10240.
Utility is `(1 + decayed_hits) * tokens / stored_bytes`, with factor 2 for
cold/evict/shutdown anchors. A superseded continued checkpoint has factor
`0.05 + 0.45 * h / (h + 1)`, where `h` is the decayed hit count. Text keys and
visible-key kind must match; a larger-context incoming checkpoint does not
supersede a smaller, more widely reusable SSD checkpoint. Logical file bytes
score SSD entries, while both logical and allocated bytes enforce disk quota.

LIE uses bounded recoverable allocation failures and its existing asynchronous
store. `evict` means normal sequence retirement here. Periodic captures operate
on the completed live frontier, including confirmed generated tokens, and never
rewind recurrent state. Normal completion can become visible before the final
SSD write is durable; STOPPED requires the writer to drain. Client cancellation
skips a new capture. A graceful core stop captures a valid completed frontier
before retiring an active sequence.

## Controls and accounting

`LIE_DS4_CACHE_POLICY`, `LIE_CACHE_UTILITY` and
`LIE_CHECKPOINT_COMPRESSION` are independent default-ON build switches.
The first disables admission of the progressive policy when compiled OFF;
its ON build can select the previous capture schedule with `--cache-policy legacy`.
Utility OFF selects LRU. Compression OFF removes the optional codec dependencies.
SSD persistence remains disabled unless its directory and limits are explicit.

Both the server and `synapse-lie-bench --suite core` accept:

```
--cache-policy ds4|legacy
--cache-text-prefix on|off
--cache-capture-finish on|off
--cache-min-tokens 512
--cache-cold-max-tokens 30000
--cache-continued-tokens 10000
--cache-trim-tokens 32
--cache-align-tokens 2048
```

Zero continued interval disables periodic captures; zero cold maximum leaves
the cold length uncapped. Zero trim/alignment disables that boundary adjustment.
Policy selection does not enable a zero-budget RAM pool or an unconfigured SSD
store. Text keys are bounded to 8 MiB and extension trailers to 1 MiB, with
admission copies included in the 32 MiB request arena. Rendering additionally
reserves at most 8 MiB + 1 byte and `(context + 1) * sizeof(size_t)` for offsets
per active job; these buffers live until the last job reference is released.

RAM payload/descriptor/extension allocation and restore workspace remain under
`prefix_cache_bytes`. Its separate index allocation has a cap of
`min(prefix_cache_bytes, 16 MiB)`. SSD retains a separate index cap equal to its
configured staging cap, in addition to the one-operation staging reservation.
Index bytes include SSD entry records and cached text/extensions. Index-budget
exhaustion at startup refuses admission; it does not silently drop files from
quota accounting. Allocator internals, filesystem metadata and thread stacks
remain outside these explicit byte pools.

`/actuator/llm.cache.checkpoint_policy` reports effective settings; RAM and SSD
expose `index_bytes` / `index_budget_bytes`. Core benchmark identities include
all policy settings. Explicit cache-build comparisons are required when settings
differ. The strict physical-token benchmark rejects comparisons if text-prefix
retokenization changes the physical prompt witness; that is not hidden as a
performance gain.

## Native file version 3

The native LIE v1/v2 payload envelope remains readable. Store writes use v3 with
an appended 64-byte `LIECACH1` metadata header, then exact text and trailer
bytes. Offsets within that header are: hits u32 at 8, reserved zero at 12,
last-use u64 at 16, creation u64 at 24, reason u32 at 32, flags u32 at 36,
text length u32 at 40, trailer length u32 at 44, reserved zeros at 48..63.
All integers are little-endian. Native SHA-256 covers immutable metadata,
text and trailer; hit/use bytes 8..23 are zeroed when hashing. An SSD hit updates
only those 16 advisory bytes, avoiding a full tensor rehash. A process restart
retains completed updates; individual hit updates are not fsynced and do not
promise power-loss atomicity. Payload commits retain file/rename/directory fsync.
Failed extension replacement preserves the previously committed file.

## Qualification and remaining parity

CPU evidence under persistent `evidence/ds4-policy-*` includes the complete
33-test ASan/UBSan/LeakSanitizer suite, optional-feature OFF core suite, 81-entry
SSD restart/quota handling, BPE-boundary divergence, context growth, metadata
corruption rejection, failed extension rewrite, progressive captures and shutdown.
These are NOT-INFERENCE. Initial build/test failures are preserved, including
LeakSanitizer under ptrace and a wrong Python interpreter lacking Matplotlib;
the successful complete run explicitly uses `/usr/bin/python3`.

Remaining gates: original-weight policy/context-growth correctness and timing;
DS4 KVC/payload binary import/export; cross-quantization reuse; and frontend
serialization of DS4-specific tool/visible-thinking/session extensions. The core
can retain opaque extensions but does not manufacture those protocol histories.
Cross-quantization reuse remains refused by full weight identity.

The inspected DS4 Qwen payload contains full raw index history, pooled keys,
eight n-gram slots and position triples. LIE/Gufo retains an unpooled index tail,
two n-gram slots and lazily produces pooled keys after the sparse boundary.
An envelope rename cannot translate that numerical representation. Implementing
KVC import/export needs a model-specific converter and independent device
qualification; emitting LIE tensors under a KVC header would be incompatible.
Neither this policy nor DS4's store adds a high-ratio active Qwen KV codec.
The existing lossless packing benefit gate and F16/F32 model representation
remain described in [STATE.md](STATE.md).
