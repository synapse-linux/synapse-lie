# Reactive inference candidate — implementation checked, GPU admission unavailable

The C17 readiness/credit dispatcher is implemented in `src/inference.c` and
shared by the production worker and `synapse-lie-bench`. Ready prefilled rows
with output capacity enter one completed native decode batch; one ready row
uses the existing scalar decode, zero rows submit nothing. No batching timer
waits for peers. The numerical kernels and their internal synchronization are
unchanged; this is concurrent inference scheduling, not an internal asynchronous
model-forward graph or an independent numerical backend.

The server accepts `--max-active 1..8` (default 1). The additive C ABI admits
the selected capacity at model load and returns independent per-row outcomes.
Cancellation suppresses the affected row after completion. Invalid frontiers
or an execution failure suppress all outputs from that dispatch and poison
the worker. Terminal metadata is published before releasing an error reservation.
Per-request batch durations overlap; they must not be summed as GPU time.

`synapse-lie-bench --execution reactive` is the default; `--execution serial`
retains the earlier interleaved scalar path for matched comparisons. Reactive
samples record scalar calls, batch calls and selected batch rows. The report
validator checks these counters against actual completed output. Existing
SVG/PNG/CSV/JSON exports remain available.

## Validation

Private `.157` CPU capsule `reactive-cpu-r3` passed **19/19 debug and 19/19
ASan/UBSan** suites, all six configure/build/test command exits 0. They include
zero-credit suspension, immediate scalar fallback, different sequence positions,
cancellation during a batch, malformed-peer suppression, all eight worker slots,
HTTP seeded heterogeneous requests against serial results, and benchmark dispatch
accounting. Fixtures use no model forward and have GPU visibility disabled.
The final HIP-linked binaries were compiled locally as `reactive-inference-r3`
against the unchanged independently fetched Gufo pin and verified private archives.
Compilation does not qualify GPU execution.

The earlier candidate `reactive-suite-r1` attempted admission at
**2026-10-01 18:51:29 UTC**. The first pipeline EX|NB lease returned EAGAIN;
postflight observed all four existing leases occupied and unchanged. The helper
and controller exited 1; `model_attempted=false`, no server/GPU child was launched,
and owned helper/controller PIDs were subsequently absent. No foreign owner was
interrupted and no retry entered gaps in the enclosing campaign.

Consequently **no reactive GPU correctness or speedup result is claimed**. The
earlier [serial LIE versus direct Gufo measurements](BENCHMARK-RESULTS.md) remain
historical baseline evidence, not qualification of this implementation. The small
last review fix orders worker error metadata before aborting batch reservations;
its regression is in the final r3 CPU capsule.

## Prepared comparison awaiting an available GPU window

The private persistent `run/reactive-suite-r2.tar.gz` binds the final r3 binaries,
source hashes and CPU receipt. It has not been launched or uploaded for replay.
The controller first runs original-weight HTTP lifecycle, seeded heterogeneous
serial/batch equality and OpenAI regressions, then runs serial/reactive pairs:

- Multi: users 1/2/4/6/8, physical pp2048/tg128, capacity 4096.
- Single: occupied prefixes 0/16384/131072, pp2048/tg128, capacity 133760.
- Each point: one warm-up and three retained measurements; no outlier removal.
- Physical input/output IDs and full PP/TG frontier hashes must agree across arms.
- A C1 decode median regression over 5% fails the predeclared comparison gate.

Every arm requires a fresh four-lease nonblocking admission and in-lease
stat/client/DSO checks. The controller stops on the first failure and retains
actual exits. The campaign is prepared for a newly available operator window;
the previous admission refusal is not standing permission to retry.

## Checkpoints and evidence

The persistent feature worktree is
`/home/paperboy/workspace/projects/synapse-linux/synapse-lie/worktrees/openai-reactive-api`.
Benchmark/graph checkpoint: `ad02a01`. The former `/tmp` worktree was removed
after SHA-256 verification of all 1608 transferred files and Git registration
repair. Raw receipts live under `evidence/reactive-{cpu,build}-r3` and
`evidence/reactive-suite-r1`; compact receipts are versioned in
[`benchmarks/2026-10-01/reactive-candidate`](benchmarks/2026-10-01/reactive-candidate/).
No merge, push, deployment, model conversion or dependency installation occurred.
