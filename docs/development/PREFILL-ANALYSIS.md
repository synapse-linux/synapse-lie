# Long-context prefill: measurements and optimization boundaries

A stable token rate does not mean a constant time to first output. For prompt
length N, a rate R gives approximately N/R seconds of prefill. Separately, a
full-prompt average from an empty sequence differs from the cost of a 2048-token
suffix processed after a long existing prefix. `fresh` and `single` now measure
these two cases separately; see [the benchmark contract](../archive/CONTEXT-COMPARISON.md).
HTTP timings additionally include template rendering, tokenization, queueing and
transport. Cached follow-ups are another metric and must expose cached/new work.

## Findings in the actual pinned implementation

This is a source audit of independently fetched Gufo `f783fedb`, not a GPU profile.

- `src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp:1888`,
  `SelectScoreKernel`: each query row scores all completed causal blocks. A key
  is reused across four heads, but loaded again for the next query row. A fixed
  selected-attention budget does not make this work independent of context.
  Reusing keys across query rows is a measurable optimization candidate; retain
  FP32 queries, the FMA/reduction order and selection boundaries.
- `kernels.hip.cpp:1980`, `SelectMarkKernel`, launched at line 5767: exact top-k
  selection uses one 256-thread workgroup per query (`dim3(n_tokens)`). It scans
  live block scores and initializes the full allocated mask pitch. Single-row
  decode therefore uses one workgroup for this stage regardless of context
  depth. Distributing selection across workgroups is a plausible long-context
  target; its share of LIE's elapsed time has not been measured. Preserve the
  lowest-index tie rule, complete masks and captured-graph replay positions.
- `kernels/rocm/executor.cpp`: sparse selection and fused wide-batch attention
  already exist. Intermediate operator timings, scratch, occupancy and launch
  gaps must be measured before assigning a bottleneck.
- LIE `adapters/gufo.cpp:lie_sequence_prefill` checks the full token prefix for
  every completed chunk; upstream `engine.cpp:Session::Sync` also finds the common
  prefix before feeding only the new tail. The repeated host scan scales with
  accumulated length. Its actual contribution is unmeasured and may be small.
- LIE's worker calls completed chunks up to 2048 tokens sequentially. Ready-row
  batching accelerates concurrent decode, not these prefill operations.
- `ngram.cpp:205` and `executor.cpp:2000`: model lookup reads already use a
  worker pool (up to 32, limited by hardware concurrency), row deduplication,
  a bounded cache and asynchronous `StartRead`/`WaitRead`. Decode queues its
  preceding layers before waiting at the injection boundary. Cold SSD reads
  and warm lookup costs need separate measurement; this table is model data,
  distinct from persisted KV/recurrent state.

## Practical priorities

Live hybrid-state prefix reuse is now implemented in the shared core, including
RAM and optional SSD checkpoints. It retains recurrent and attention state,
model/template identity, divergence handling, bounded ownership and cancellation.
The historical conversation below predates that implementation; it establishes
the cost of its recorded cache-off runtime.

For cold long prompts, first capture a separate profile of dense/MoE projection,
index scoring/selection, attention, host prefix scans and synchronization at
8K/32K/128K/256K. Evaluate one change against that profile, preserving full
frontiers and selection boundaries before running unprofiled repeated timing.
Larger chunks, key tiling, precise completion dependencies or scratch reuse are
candidates, not promised gains. Chunk changes also affect mixed-request fairness.
No host power, IOMMU, firmware or kernel settings were changed for this work.

Use the following order when a profile confirms the corresponding cost:

| Candidate | Intended benefit | Acceptance boundary |
|---|---|---|
| Distribute block selection across GPU workgroups | Reduce single-row decode's context-dependent selection cost | Exact block lists, ties and masks; stable graph scratch; account for extra launches |
| Reuse block keys across prefill query rows | Reduce repeated key reads | Exact scores and lists; no register spill or short-context regression |
| Tune projection and routed-expert shapes | Increase matrix work per device time | Record weight format and kernel plan; qualify any changed rounding separately |
| Raise the current 2048-token prefill capacity | Amortize fixed chunk and projection costs | Explicit provider/scratch capacity, bounded memory, cache identity, cancellation and mixed-request fairness |

More host threads do not address the single-workgroup GPU selection path. The
native attention fixture below verifies the attention operation after selection;
it neither qualifies indexer scoring/selection nor measures their speed.

The [reactive audit](../INFERENCE-REACTIVE.md#implementation-audit-how-far-the-reactive-flow-reaches)
separates the implemented readiness/batch layer from unimplemented operator-level
asynchronous execution and from HTTP/cache responsiveness.

## Why this is not just an HTTP reactor

The production worker and direct C benchmark call the same readiness dispatcher.
At C8 the completed aggregate decode gain is measured without HTTP, so the change
is demonstrably inside the inference scheduling path. It remains a change to
which sequences share a completed forward, not to the operations within that
forward. C8 aggregate 107.15 tok/s is approximately 13.39 tok/s per sequence for
these homogeneous peers; it does not mean each of eight users receives 107.15.

A long prefill and an already-ready decode still compete for the one device
owner. Neither network callbacks nor more host threads remove this competition.
Moving the prefill/decode boundary is a serving-latency tradeoff requiring its
own measurements, independently of the successful homogeneous batch throughput.

## Measured follow-up cost

The historical [HTTP campaign](../archive/FULL-PREFILL-HTTP-RESULT.md) records the
cache-off cost on actual traffic: 99995 prompt tokens take 69.76s; the next turn
with 100419 tokens takes 71.79s and processes all of them again. The added
physical prompt length is only 424 tokens. This is one two-turn observation,
not a twenty-turn latency distribution or a measurement of the current cache.

## Long-workspace component qualification

The owned provider variant keeps the original 2,048-word sparse WMMA kernel for
short visible spans and adds a default-ON 8,192-word specialization through 1M.
`LIE_LONG_CONTEXT_WMMA=OFF` provides a separate control; it is not the sampler-OFF
reference. The runtime build with verified state access includes a native C17
development client:

```sh
lie-attention-qualify --run --output-dir attention-run
```

Run only during an admitted GPU window. The output directory must be new. The
client loads no model: it generates 13 sparse fixtures at 16K, 256K, 512K and 1M,
including partial query groups, compact/noncompact key unions, the exact compact
list boundary, empty selections and zero queries. A monotone key mapping
preserves ordered K/V values and causal membership in a short-context reference.
Complete finite float32 outputs must match bit for bit. A separate uniform-
softmax scalar sanity check has a predeclared absolute-error bound of `1e-6`
because the pinned kernel uses fast reciprocal math; that bound does not relax
the complete long/short equality requirement.

`attention.jsonl` binds every case to complete `.deep.f32`, `.short.f32`,
`.blocks.u32`, `.deep-mask.u32` and `.short-mask.u32` files by SHA-256 and byte
count. Disabled long paths must refuse deeper spans without modifying their
sentinel output. HIP errors, partial output and cleanup failures cannot count as
expected refusals. The Point supervisor's `modern-attention-fixture` profile
runs without model mounts and its `attention-fixture` collector retains partial
artifacts on failure. No Python dependency is added to the native client.

This qualifies generated component behavior only. Original-weight logits,
long-context recall, serving faults, measured memory and comparative performance
remain separate final acceptance gates.

The current `120e2fce` ROCm10 build on `.161` now passes all 13 generated
cases with the feature ON: complete long/short outputs compare bit for bit
across 270,336 finite values. Offline review verifies every saved mask, ordered
key mapping and artifact, and independently checks both zero-query outputs
against exact rational uniform means under the predeclared bound. CPU peaks at
37.125 C; the run is collected and strictly closed, with the router restored.
The [component receipt](validation/attention-fixture-point-2026-10-07.json)
retains all raw outputs, source/build identities, telemetry and actual exits.
No model weights are loaded. The disabled-feature GPU control, full model,
indexer, faults and matched performance remain separate open gates.
