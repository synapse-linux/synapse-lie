<!-- SPDX-License-Identifier: MIT -->
# Decode and prefill through 128K

The owner paused fixed-point Q2/UD parity after the final HC-down component
was slower. This track prioritizes small changes with a substantial possible
contribution to completed decode or full prefill through 128K. The saved
[original measurements](Q2-FULL-PREFILL128.md), physical input tokens,
capacity, chunk size, timers and control binaries remain the references.
The long-prefix replies contain eight decode calls; they do not establish a
long-context TG128 curve. No prompt padding or intermediate partial chunks are
introduced to make a candidate look faster.

## First candidate: four Q8 rows per block

The saved 1571-provider diagnostic trace attributes 261.537326 ms of
533.881388 ms decode GPU service time to dense Q8 GEMV, about 49%. It predates
the retained 1587 provider and uses a 2048-token input with 15 decode calls;
it is a prioritization clue, not a current 128K attribution.

The private candidate groups four independent 32-lane row reductions in one
128-thread block. It preserves each row's encoded Q8_0 weights, Q8_1 operands,
dot calls, accumulation and reduction tree. Selection is limited to one-token
dense calls with at least 1024 rows divisible by four. Short rows, grouped
tokens and prefill keep their existing dispatch. There are no new buffers,
streams, callbacks, public ABI or model-state changes. This is a numerical
dispatch experiment; any speed gain must not be attributed to reactive work.

Static compilation preserves all 28 original dense Q8 device bodies against
the saved assembly. The two added kernels have no scratch or LDS allocation,
with 15/21 descriptor VGPRs versus 14/20 in the scalar plain/gated controls.
The different historical IQ2 bodies are inherited changes, not Q8 changes.
[Source](../config/q2-decode-q8-rows4-source.json),
[static audit](../config/q2-decode-q8-rows4-static.json).

The component checks all actual timed outputs before overwrite, full byte
agreement, guards, unchanged inputs and sampled independent FP64 formulas.
It rotates at least 48 MiB of encoded weights with the production hipMalloc
placement, using four timed shapes and a K2592 tiny-input tail. It excludes
the activation quantizer and model executor; this boundary is explicit.
Finite numerical disagreement retains timings and its exit code. Unsafe
outputs or device failures stop subsequent GPU work. Saved model controls,
Q4 and full curves are not rerun for this component.

Preparation preserves the initial fixture's C++17 compile failure: its hash
helper needs C++20. The corrected fixture compiles, while the production
numerical translation unit stays C++17. The first host capsule omitted the
new private includes; the frozen-plan check rejected it before GPU admission.
The archive list was corrected and the host suite repeated. The official
format checker reports inherited formatting failures in unchanged files;
its exit and diagnostics are preserved without rewriting the retained source.

### Completed component — 2026-10-06 UTC

All 303 full-output pairs are exact and all 606 independent FP64 checks pass.
Every timed destination is checked before reuse. The completed monotonic wall
times below are means of the five saved samples; raw ranges remain in the
[result](../config/q2-decode-q8-rows4-results.json). All 56 HIP event durations
are zero and therefore invalid; they are not substituted for wall time.

| Shape | Original µs | Four rows µs | Time change |
|---|---:|---:|---:|
| M16384/K2560 plain | 200.730900 | 202.016800 | +0.641% |
| M2560/K6144 plain | 77.590400 | 77.662300 | +0.093% |
| M2560/K640 plain | 11.149083 | 11.024193 | −1.120% |
| M1280/K2560 gated | 34.977750 | 37.069700 | +5.981% |

There is no general improvement to promote. Keep the small shared-down
observation available, with overlapping ranges; do not run the entire model
or curve for this marginal result. The large plain projection reads 44.56 MB
in about 201 µs, approximately 222 GB/s of logical weight traffic. This is a
bandwidth clue from a synthetic component, not measured memory-controller
utilization. Extra stream overlap cannot remove those required bytes.

Current host Debug39/39 and ASan/UBSan39/39 pass. The component ends with three
zero exits and four artifacts collected before release21:28:17.275015 UTC /
f08fa953. Main/remote mirrors match, 1744 process identities and1393 groups
are retired, KFD is empty and original leases/model stat tuples are unchanged.
Core is notified before analysis. No model result or performance default changes.

## Reactive contribution to decode

The retained executor already overlaps asynchronous n-gram reads with the
first layers. `PleFetch` starts a bounded read into the pinned buffer;
`Forward` queues the prefix graph without synchronizing; only the suffix
waits for the PLE data. Eligible decode shapes already use HIP graph replay.
Quantized inputs alternate between two buffers, and shared scratch reuse
relies on the current stream order. Adding another worker is not evidence
of useful overlap.

The saved diagnostic trace contains 79.979815 ms between kernels over 15
decode calls: 5.331988 ms per token, versus 35.592093 ms kernel service time.
These gaps include graph scheduling, CPU sampling, transfers, instrumentation
and real dependencies. Eliminating every gap would give a mathematical
14.98% increase in rate for that profiled span; this is **not** an achievable
estimate, a measured improvement, or a projection for 128K. A current timeline
must isolate an actually removable wait first.

The useful hypotheses are:

- C1: overlap residual n-gram preparation or independent branches only where
  the timeline shows waiting on the critical path. A token's successor still
  depends on its completed state and sampled token. Final synchronization
  cannot be removed while the host consumes unfinished logits.
- Multiple requests: schedule ready rows into genuine model batches to reuse
  weights. Report aggregate completed-token throughput and per-request latency
  separately; a batching window may make a single request slower.
- Buffer ownership: retire or reuse scratch after its last consumer. This can
  reduce memory pressure or permit more active sessions, but does not by itself
  make the single-sequence decode faster. Independent streams require disjoint
  scratch and explicit joins; bandwidth contention can cancel their benefit.

[Bound diagnostic evidence](../config/q2-decode-reactive-reassessment.json).
No additional reactive decode speedup has been measured in this track.

Further [offline gap locations](../config/q2-decode-gap-locations.json) show
13 pauses around2ms between runtime copies at successive token boundaries.
Neighbouring dispatches include the next embedding. The original diagnostic
harness scans finite logits and selects the CPU argmax after each completed
forward; runtime and profiling overhead also contribute. These gaps cannot
all be labelled scheduler or PLE delay. A larger3.175ms gap follows an early
HC combine before a copy/quantize sequence; GPU ordering alone does not prove
its CPU cause. The diagnostic harness and its saved comparisons remain frozen.

For serving, the useful distinction is between reducing a synchronous transfer
or sampling dependency and hiding independent preparation behind GPU work.
Moving sampling to the GPU would require qualification of sampler semantics,
logprob reporting and state, and would not itself be a reactive scheduling win.
No present evidence supports promising a C1 percentage at128K from these gaps.

## Prefill priority

At the saved 128K point, the complete input is 130925 physical tokens: 63 full
2048-token chunks and the original 1901-token final tail. Improving only the
tail cannot explain a large gain across the full prefix. Capacity repairs for
256K are outside this 128K optimization scope.

Attention selection is a depth-dependent candidate. Its existing implementation
already bounds FP32 load scheduling and uses exact partial top-k. The pinned
upstream experiments rejected paired FP32 selector lanes as slower despite
exact scores, so that rejected experiment must not be presented as a new
optimization. A distinct cooperative layout requires a focused score-plus-mark
comparison at real depths before any full-prefix trial. Repeated dense
projections remain relevant across all complete chunks.

The next [exact query-pair component](Q2-SELECT-QUERY-PAIR.md) tests key reuse
at the actual last complete32K/128K chunks and original128K tail. It retains
the complete score-plus-top-k consumer and benchmarks the register tradeoff;
static compilation alone is not a performance result.

The query-pair trial is exact but slower and is not promoted. The following
[live-grid trial](Q2-SELECT-LIVE-GRID.md) preserves every numerical kernel and
omits only score blocks beyond the known eager-prefill extent. It keeps the
original allocation, score pitch and graph-safe decode grid.

Keep model trials on the original saved requests and 2048 chunking; expand
measurement only after a useful component result. Any changed output budget
or newly instrumented profile must be labeled separately from saved benchmark
observations.
