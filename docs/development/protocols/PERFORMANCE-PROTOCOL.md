# Current-runtime performance protocol

User request: a complete performance test on .157 with the GPU. This covers the
implemented LIE text/function runtime, not unimplemented vision/MTP, an internal
reactive optimization, general quality or a matched DS4 comparison. DS4 is only
read-only reference evidence; no DS4 executable, source or cache is used here.

## Declared matrix

The original UD-Q4_K_XL model and LIE's independently fetched Gufo pin remain
unchanged. Context is 9216, prefill chunk 2048, greedy, thinking/MTP/vision off.
One device owner; HTTP allows two independently interleaved sequences, not native
batching. Four existing nonblocking leases, current in-lease preflight, private
HOME/cache, observed device clients, append-only start/end registration and owned
cleanup are required separately for each run. No tuning, install or weight hash.

1. Direct C execution: targets 512/2048/8192 physical prompt tokens, actual counts
   recorded; 128 maximum generated tokens, EOS honored. One warm-up per profile,
   three measured rounds ascending/descending/ascending. Full finite frontier
   logits, token IDs and repeated hashes must match the warm-up. Existing C1
   completed-call boundaries remain unchanged. Padding-line counts are added to
   evidence so HTTP uses the exact same user content and physical prompt counts.
2. Chat HTTP: the same three prompts, JSON and SSE, concurrency 1 and 2. One
   warm-up per configuration and five measured repetitions. Every concurrent
   group starts together, drains before the next; configuration order reverses
   on alternate rounds. Each request must report the expected physical prompt
   count. Sessions are fresh; no cached-prefix claim.
3. Responses: medium prompt, JSON/SSE, one client, one warm-up and five measured
   repetitions. Native function output: named read call, JSON/SSE, one client,
   one warm-up and five measured repetitions. Function arguments must match;
   tools are not executed by the server.
4. Admission: one 24-client simultaneous burst. 200 and capacity 429 outcomes
   are retained separately; refusals are not successful performance samples.
5. Existing original-model lifecycle suite: in-flight cancellation, TCP stalled
   peer/backpressure, peer isolation, recovery and retirement. Its timing windows
   are correctness evidence, not a throughput benchmark.

## Timing and statistics

- Executor PP/TG includes required provider synchronization and sampling, excludes
  model load, rendering, full-logit witness copies/hashes and network delivery.
- HTTP end-to-end starts immediately before the request send and ends after the
  response read. Headers/TTFB is separate from TTFT. JSON has no observable TTFT.
- Streaming TTFT is first nonempty visible text delta. First structured output
  is separate, especially for buffered function calls. Delta-gap times describe
  transport signals, not individual physical token/kernel intervals.
- Concurrent throughput is the sum of actual generated tokens divided by the
  interval from first client start to last client completion in the group.
- Raw samples, actual EOS counts, warm-ups, errors and admission refusals remain.
  No request retry, dropped outlier, forced EOS override or speed-target stop.
- Summaries show median, min/max, all samples and nearest-rank p95. Five groups
  do not establish a production p95/SLO or statistically precise tail estimate.
- Device/system telemetry is sampled once per second; report observed memory,
  GPU utilization/clocks/temperature and available power metadata. This is not
  allocation-exact peak memory, integrated energy or GPU-only kernel profiling.
- Loopback HTTP does not qualify a remote network or Internet deployment.

CPU accounting/client fixtures run on .157 and remain NOT-INFERENCE. The actual
server binary is the previously GPU-verified runtime; only benchmark/client and
supervisor code changes. Every staged artifact, source capsule, command and
actual process exit is bound in the run manifests/evidence. Occupied leases
cause refusal; no waiting, foreign termination or campaign-gap admission.
