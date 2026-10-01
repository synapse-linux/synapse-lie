# Read-only DS4 coverage comparison

Inspected 2026-10-01 against LIE `213c91e` and the DS4 Gufo integration workspace.
The DS4 column retains that dated read-only inspection; the LIE column is updated
for `0e2bd45` and the [reactive GPU campaign](REACTIVE-INFERENCE-RESULT.md).
This compares the actual DS4 frontend/adapter and historical sealed evidence,
not every function in its vendored upstream library. No DS4 file, executable,
cache, model or qualification artifact was modified or imported into LIE.
A capability's presence is separate from qualification of its current binary.

| Capability | DS4 Gufo port | LIE current runtime |
|---|---|---|
| Models, Chat text, JSON/SSE, usage | Present; original-weight HTTP evidence | Present; original-weight GPU evidence |
| Responses text/functions | Present; stateless and checked live continuation | Present; stateless full-history replay |
| Legacy `/v1/completions` | Present | Missing |
| Anthropic `/v1/messages` | Present | Missing; separate from OpenAI parity |
| Function calls/results | Present, bounded exact sampled-tool replay/cache facilities | Present, typed correlation and complete-turn validation; fresh prefill |
| Required/named tool choice | Responses explicitly rejects it; Chat mainly honors none and skips other targets | Declared choice checked against generated complete calls; no constrained decoder |
| Temperature/top_p/seed | Present; defaults differ | Present, per-sequence sampler |
| top_k/min_p/ignore_eos/stop | Exposed in relevant frontend requests | Missing; honors model EOS |
| Frequency/presence penalties | Not implemented in inspected HTTP parser | Present in Chat sampler |
| Thinking/reasoning outputs | Present in frontend/model controls | Thinking disabled; missing reasoning output/control |
| Inline image input | Present; bounded PNG/JPEG paths and original-weight tests | Missing |
| MTP/speculative execution | Present; bounded Q4 evidence, Q2 prose blockers retained | Explicitly disabled/missing |
| Native grouped model decode | Adapter has batch and speculative-batch APIs; bounded tests | Present: shared C readiness/credit dispatcher, native AR batches through eight rows; direct GPU comparison at C1/2/4/6/8 and original-weight HTTP C2 checks |
| Live prefix reuse | Present | Missing; every request re-prefills complete input |
| Hybrid-state snapshots/disk restart | Present; validated identity/frontiers and bounded restart evidence | Missing |
| Long AR context/YaRN | Historical bounded AR/frontier evidence through 128K | Direct AR measurements with physical prefix 131072 plus 2048 new tokens; exact serial/batch scheduling comparisons. HTTP Chat/Responses verified at 262075 physical prompt tokens, capacity 262144; no independent long-context numerical oracle |
| Adapted IQ2/Q2/MXFP4 kernels | DS4-specific changes and numerical/performance receipts | Not adopted or qualified; upstream pin is independently fetched |
| Strict JSON/JSON Schema grammar | Explicitly unavailable through DS4 ABI | Missing |
| Durable previous_response_id/conversations | Explicitly rejected by inspected Responses parser | Missing/rejected |
| HTTP logprobs/logit_bias | No implementation in inspected HTTP parser; top-logprob C ABI exists | Missing in HTTP and current generation contract |
| Audio/image generation/embedding API | No such routes in inspected DS4 server | Missing |

LIE additionally owns the C reactive token-demand/loan/cancellation contracts,
separate management observability and per-request completed-call timings. Those
contracts alone do not imply numerical parity or a speedup over DS4. Native
batching now has its own bounded original-weight evidence; no fresh DS4 timing
comparison was performed.
No claim that DS4 has the entire OpenAI API is justified by its current frontend.

The main parity gaps are stop/sampling extensions, reasoning, live prefix/state
reuse and persistent hybrid snapshots, vision, MTP and
independent numerical qualification. Legacy Completions is an additional OpenAI route gap.
Anthropic compatibility is independent of the user's OpenAI requirement.

## Read-only sources

DS4 canonical workspace:
`/home/paperboy/workspace/projects/cachyos/ai/ds4-gufo`.

- `source-branch/docs/SERVER.md`: actual routes, images, sessions/cache behavior.
- `source-branch/ds4_server.c`: Chat parser around 4105; Responses parser around
  5292; route dispatch around 15376. Unsupported/ignored fields are distinguished
  from implemented controls.
- `source-branch/gufo_adapter/constraint_boundary.cpp`: native JSON grammar refusal.
- `source-branch/gufo_adapter/ds4_gufo_adapter.cpp`: batch APIs around 1216 and
  snapshot/model-mode admission boundaries.
- `NATIVE-ORIGINAL-STATUS-r1.md`, `IMPORT-CLOSURE.md`,
  `REFERENCE-FOR-SYNAPSE-LIE.md`: sealed bounded results and surviving blockers.
  Native19/HTTP historical results do not automatically qualify later changed
  kernel sources. 300K was policy-stopped, not proved impossible/OOM.

LIE sources: `src/chat.c`, `src/server.c`, `src/responses.c`, `src/worker.c`,
`src/inference.c`, `include/lie/executor.h`; qualification scope in
OPENAI-GPU.md/C1-BASELINE.md/REACTIVE-INFERENCE-RESULT.md.
This is a source/evidence audit, not a new DS4 run or independent performance
comparison. Fresh performance measurements use only LIE-owned artifacts.
