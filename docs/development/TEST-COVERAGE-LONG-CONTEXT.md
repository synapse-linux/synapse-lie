# Benchmark closure and the 1M context gate

Current implementation: the shared core and derived provider expose explicit
YaRN2/YaRN4 profiles through 1,048,576 total tokens. Independent CPU operator
and physical-token lifecycle tests pass; original-weight short-profile gates
pass on `.161`. Short-input capacity gates now pass at 512K and 1M after the
authorized GTT112 reboot. Physical PP1,048,448 completes and stops naturally
after 43 output tokens; the required TG128 gate fails with child exit 0 and
supervisor/controller exit 1. Collection and ownership closure pass. Fixed-output
extended-context qualification, recall quality and performance remain open.
See the [current context guide](../guides/CONTEXT.md) and
[memory estimate](validation/context-memory-point-2026-10-04.json).
The source audit and old estimate below describe the earlier pristine/native
checkpoint; the old estimate omits the complete raw index history now reserved
by the DS4 state binding and must not be used for current 1M admission.

The [current Point results](../benchmarks/models/qwen3.8-flash-next/strix-point/README.md)
include the completed 40-window served HTTP AR/MTP concurrency campaign and
16-window cold HTTP depth campaign through near 256K. The native Gufo HTTP
conversation-curve client/report is implemented without Python; its extended
GPU/quality campaigns remain separate. New OpenAI-control GPU gates and full
Terminal Bench task evaluation remain pending. See the
[current roadmap](../BACKEND.md#current-roadmap--2026-10-04-utc).

## Historical audit — 2026-10-02

The matrix and source estimates below describe the earlier checkpoint, including
gaps subsequently closed above. They must not be read as current feature status.

Audit date: 2026-10-02. The qualified GPU endpoint at that checkpoint was native 262144 total
tokens. A client capable of sending a million-token prompt is not evidence that
the server can execute it. The new `long-context` HTTP preset is a client-side
workload; it does not change LIE's model configuration or claim a 1M GPU result.

## What remains to close the selected benchmark documentation

Historical results remain under their original conditions. "Measured" below
means the linked experiment, not every variant in a referenced document.

| Area | Existing LIE evidence | Remaining work |
|---|---|---|
| Single AR at occupied 0..128K | Direct executor pp2048/tg128, exact inputs/output/frontiers versus direct pinned Gufo | Paired original-weight HTTP cached-prefix/context-depth performance campaign; RAM cache qualification is separate |
| Concurrent AR C1/2/4/6/8 | Common-window direct TG, scalar versus ready/native batch; three repetitions. Native prepared HTTP client now supplies the reference corpus, preparation barrier and individual-rate sum | GPU qualification of the new HTTP client, retaining both summed server rates and common-wall throughput |
| Single and concurrent MTP | Shared-core MTP, original-weight functional/state/cancellation gates; prepared HTTP client supplies mixed/repetitive corpora | Repeated paired single/concurrent mixed/repetitive performance; independent acceptance/RNG/rollback quality remains separate |
| Full fresh PP through 258794 | Six points, n=2, TG128; HTTP PP through actual 131063, n=2 | HTTP 256K performance repetitions, predeclared higher repetition count/order, diverse recorded corpus; capacity smoke is separate |
| Ten served prompt shapes | Ten original shapes, one sample each, actual output256 | Three repetitions each; exact exported corpus on comparator; same AR/thinking/cache settings, then separate speculative experiments |
| Agent and function-call throughput | Real Pi read/edit/read acceptance; text-only tool-dialogue in shape suite | Six actual tool-history/coding trajectories, output400, repeated timings, thinking variants; MTP/lookup require implementations |
| 100K conversation | Two actual turns, 69.76/71.79s; all history re-prefilled | Twenty actual turns already supported by client; cache-off timing can run now, RAM reuse is now GPU-qualified separately; actual multi-turn cached timing remains |
| State reuse, RAM/disk restart | C17 RAM and SSD restart qualified through 128K; exact extension and core off/RAM/SSD timings; [HTTP SSD restart/C2/cancellation](../archive/CACHE-FEATURES-GPU.md) passes on raw states | [Compressed-state exact restore](../archive/CACHE-COMPRESSION-GPU.md) passes at 128K; compressed HTTP/C2, device faults, 256K checkpoint fit and extended-context gates; see [completed SSD result](../archive/SSD-GPU-COMPLETION.md) |
| Cache priorities and extra compression | LRU retention; Qwen F16 K/V with native hybrid state preserved | Utility-based retention, separate lossless checkpoint codec and model-qualified active KV compression; [boundary and gates](../reference/STATE.md#retention-policy-and-compression-boundary) |
| Loading | One AR load per binding under existing file-cache conditions | Cold target plus predictor to HTTP readiness, explicit file-cache conditions; no global cache drop implicit in a test |
| Memory | Upstream size estimates and sampled telemetry | Peak live HIP allocation including idle baseline, scratch and retained state; quantify host pressure separately |
| Native 256K correctness | Chat JSON / Responses SSE at 262075 input tokens and overflow rejection | Retrieval at multiple needle positions, continuation and numerical reference; short READY output is not a retrieval test |
| Extended 512K/768K/1M | Client workload only | YaRN-capable provider, memory admission and quality gates below; no LIE inference beyond 256K measured |
| Reactive responsiveness | Credit/cancellation/isolation correctness, homogeneous batch throughput; SSD HTTP GPU read-cancellation/slow-client witnesses and percentile client | Paired mixed arrivals, long prefill versus decode, unequal positions; SSE event gaps are not individual-token latency |
| Internal reactive execution | Completed synchronous calls | Profile launch/wait/allocation critical path first; no operator dependency graph or asynchronous lifetime ABI implemented |
| QUALITY-style numerical checks | Exact within-provider scheduler replay/frontier witnesses | Independent FP64 operators, full-logit/KL checks at depth, chunk/tail equivalence, quantized/BF16 quality reference; same-provider equality is not an independent oracle |
| Sampling and penalties | Existing AR per-sequence controls and replay fixtures | Full published sampling/filter matrix, greedy ties, MTP acceptance/residual/RNG checks; unsupported controls first |
| Vision / reasoning / constrained tools | Text/function API only, thinking disabled | Implement these features, then image/text isolation, histories, cancellation/restart and numerical checks; plain text tests do not cover them |

The reference [Gufo method](../archive/BENCHMARKING.md#pinned-reference-methodology) has
different historical releases for different rows. New main-branch quality checks
are useful requirements, not evidence inherited by the older pinned provider.
No fresh external server, converted checkpoint or independent numerical backend
was measured in the last campaign. The archived Q2 work remains withdrawn and is
not implicitly restarted by this matrix. Full OpenAI platform coverage is a
separate API objective, not something the benchmark suite establishes.

## A concrete extended-context client

The C executable implements `--suite http` natively; no adjacent script or
Python interpreter is required. The preset defaults to targets **258794, 524288, 786432, 1004581**, output budget
64, three measured repetitions, zero discarded warmups and a 3600-second HTTP
socket timeout. The endpoint's own deadline and the supervising campaign deadline
must also cover the work; a socket timeout is not a total campaign deadline.

Example for a separately admitted, already 1M-qualified endpoint:

```sh
synapse-lie-bench --suite http --url http://192.168.5.157:8000/v1 \
  --model qwen3.8-flash-next --server-label 'exact build / weights / AR / YaRN4' \
  --server-kv-cache off --preset long-context \
  --context-capacity 1048576 --rope-scaling yarn4 \
  --corpus-seed 77 --export-requests long-corpus.jsonl \
  --output long.jsonl --graphs long-charts
```

**This invocation is not currently executable against LIE's 256K backend.**
To exercise only its native point after ordinary GPU admission, use
`--sizes 258794 --context-capacity 262144 --rope-scaling native`.
Neither declaration reconfigures or independently verifies the server.

The original deterministic corpus contains varied three-digit numeric records,
not a repeated maintenance paragraph. It is a synthetic throughput stressor,
not natural-language quality evidence or a reproduction of someone else's text.
Three small 8/16/32-record probes infer tokens per record. Every actual prompt's
reported physical count must equal its calibration prediction or the run fails
and preserves the observation. Tokenizers without this linear property must use
an explicitly prepared `--requests` corpus. Targets round down to whole records;
only actual usage is used in rates. No large-prompt prefill calibration is hidden.
The model and file cache can be warm from startup/probes; cache-off denotes no
prefix reuse, not cold disk pages. Server cache policy is an operator declaration. Since RAM now defaults on,
cache-off serving runs must explicitly start the server with `--prefix-cache-mib 0`.

Each sample retains the exact request, hash, byte count, actual input/output,
SSE, finish reason, first output and total wall, plus available executor timings.
Early EOS remains visible and is not replaced with a nominal 64-token count.
Prompt/HTTP-wall includes generation; use executor PP or a separate `--tg 1`
run for the corresponding prefill metric. Export/replay the same corpus for
comparisons. Reports refuse different declared capacity or RoPE configuration;
they already refuse different requests, token counts and cache policy.

## What a real 1M LIE implementation needs

The [model card](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) prescribes static
YaRN for extension beyond its native 262144. Factor 4 targets the 1M profile;
factor 2 is appropriate for a separate 512K profile. Static scaling changes
short-context behavior too. Merely accepting a larger integer or changing a
GGUF header does not implement its frequency/attention transformation.

Source audit of independently fetched Gufo `f783fedb`:

- `engine.cpp:Model::Load` rejects `max_context > config.context_length`.
- ROCm `Executor::CreateSession` independently enforces that bound.
- `Config`/`ModelOptions` expose theta and rotary sections, no YaRN controls;
  attention and indexer RoPE calls must be audited together. The LIE ABI also
  lacks a scaling configuration and identity field.
- Scratch mask/scoring dimensions use `config.context_length`, not just the
  requested sequence capacity. Extending only allocation/admission would miss
  these arrays. Session KV, pooled index keys, position arithmetic and all bounds
  need review, including selected-block limits and memory pressure.
- Server/worker and direct benchmark still cap capacity at 262144. HTTP body is
  8 MiB and formatted text 32 MiB; token count does not bound arbitrary UTF-8 byte
  count. The server deadline is 600s by default, configurable up to 1800s. These
  limits need explicit qualification for a larger profile, not silent removal.

The old measured allocation **estimate** at 256K is 6786984980 session bytes.
For this architecture, twelve attention layers add 25344 bytes per position
across KV and pooled keys. Holding other terms fixed extrapolates to
26718317588 bytes (**24.88 GiB**) per 1M AR session, plus **76.73 GiB** of reported
resident model bytes, before workspace, lookup paging, driver and host needs.
This is about 101.61 GiB before those additional costs, not a fit measurement.
One active sequence is the initial candidate; eight 1M sessions do not follow
from the short-context C8 result. No new model payload/hash or GPU allocation was
needed for this source-based estimate.

Required gates, in order:

1. Add a versioned, explicit scaling/profile contract and independently derived
   YaRN implementation in an owned numerical boundary; preserve pristine Gufo
   as a reference. Validate frequencies/operators against an independent oracle.
2. Qualify memory/lifetimes and numerical finite frontiers at short lengths,
   256K scaled and unscaled, then 512K and 1M. No CPU model forward.
3. Run retrieval at multiple depths and positions (including start/middle/end),
   multiple needles and real continuation. Measure short-context quality cost
   and corpus perplexity/KL where a qualified reference is available.
4. Admit actual GPU performance runs under the existing four leases, retaining
   full samples, physical counts, settings, power/clock/pressure observations,
   exact exits, failures and cleanup. Benchmark 258794 under both native and
   extended profiles to expose scaling/profile cost before comparing 1M.

## Isolating reactive value from native batching

The 4.11x result compares old scalar interleaving with ready-row dispatch **plus
native batching**. It is not a 4.11x gain over Gufo. Historical C8 direct Gufo
107.03 and LIE ready/batch 107.15 tok/s are effectively similar observations
from different sessions; they cannot establish a small relative speedup.
There is one GPU-owner worker, not eight CPU inference threads.

A useful next A/B holds batch width, numerical code, physical work, sampling,
arrival trace and power settings constant. Retain a direct native-batch control,
the LIE ready-batch path and the old scalar path as three distinct labels. Measure
homogeneous throughput separately from mixed-arrival/slow-client fairness and
latency. The existing direct-reference executable supplies the homogeneous
control; it is not a matched full HTTP server with an alternative scheduler.
No reactive-specific throughput, PP, TTFT or p99 advantage over native Gufo has
yet been demonstrated.

## Client verification

The `.157` CPU-only capsule `reactive-cpu-r6` passes 21/21 CTest cases in debug
and 21/21 with ASan/UBSan, all six configure/build/test commands exit 0. The six
HTTP client fixtures include near-1M synthetic usage, exact request replay,
missing declarations, reserved-output overflow and differing RoPE identities.
Eight collected evidence files match their recorded hashes. See the
[receipt](../benchmarks/2026-10-02/long-context-cpu-receipt.json).
This does not qualify tokenization of the corpus by the real model or real 1M
inference; the eventual endpoint run must pass the physical-count checks itself.
