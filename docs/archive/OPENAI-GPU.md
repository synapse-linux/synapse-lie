# OpenAI reactive original-weight run on .157

> Historical technical record. See [current usage](../guides/USAGE.md) and
> [benchmark tables and graphs](../benchmarks/README.md). Results below retain
> their original build, protocol and limitations.

Branch `feature/openai-reactive-api`; worktree now at
`/home/paperboy/workspace/projects/synapse-linux/synapse-lie/worktrees/openai-reactive-api`.
Historical runs below used `/tmp/synapse-lie-pi-tools` before its verified relocation.
The final `openai-reactive-api-r3` HIP binary ran on `192.168.5.157`, original
UD-Q4_K_XL weights, context 4096, chunk 2048, two interleaved sequence slots,
thinking/MTP/vision disabled. The numerical engine remains embedded upstream
Gufo at the independently fetched LIE pin `f783fedb`.

Run `openai-reactive-gpu-r3`: 2026-10-01T13:51:40.155673+00:00 to
2026-10-01T13:52:14.039602+00:00. It acquired all four existing nonblocking leases in their
recorded order and ran current in-lease process/device/DSO/model-stat preflight.
The operator requested `.157` GPU tests. No formal DS4 ACK or universal desktop
GPU exclusivity is claimed. Only owned LIE processes were started/retired.

## Verified behavior

- Original-weight READY, arithmetic and UTF-8 JSON/SSE pairs all passed.
- Cancellation during owner prefill/decode, stalled TCP/SSE backpressure, peer
  isolation and runtime reuse passed the existing lifecycle protocol.
- Stateless Responses JSON and sequenced typed SSE produced READY, with the
  proper final event and no Chat `[DONE]` sentinel.
- Two fresh stochastic sessions using the same seed/temperature/top_p/penalties
  returned identical choices and usage in this bounded test.
- A named native `read` function call contained the expected path; its correlated
  tool result led to the exact `LIE-GPU-TOOL-OK` response. The test client supplied
  the result through the ordinary OpenAI protocol; LIE did not execute a tool.

Server and helper exit codes are 0. Model stat identities and binary hash are
unchanged. Postflight at 2026-10-01T13:54:02.763280+00:00 found the owned identities absent,
empty KFD and all four unchanged lease files free. Final management sampling
occurred before one last job retired (active=1, failed=0); this is retained,
not rewritten as a zero-active sample. Subsequent successful shutdown and
postflight establish retirement of the run's processes.

## Evidence and limits

Local collected evidence: `evidence/openai-reactive-gpu-r3/`. The collection
verifies 9 file hashes, 56 source-file hashes, the linked
binary and the source capsule. The manifest binds modified source paths rather
than pretending the base commit alone describes the tested binary. The prior
`r2` success and compile failure/exit receipts remain separate and intact.

Final CPU verification on `.157`, `openai-reactive-cpu-r3`, passes 16/16 CTest
suites in debug and 16/16 under ASan/UBSan, including maximum JSON escaping for
4096 full-size fixture chunks. This CPU case is not original-weight inference.
The real-model tests do not establish strict-schema decoding, every seed/model,
independent numerics, performance gains, GPU faults, full memory fit or the
complete OpenAI platform. No Pi CLI GPU run or native batching is claimed.
[The capability matrix](../reference/OPENAI-REACTIVE.md) records remaining functionality.
No deployment, package installation, GPU tuning, foreign termination, publication
or DS4 modification occurred. This completed window is not a standing lease.
