<!-- SPDX-License-Identifier: MIT -->
# Q2 arithmetic: real task qualification

The owner selected [Terminal-Bench Mini](https://github.com/kyuz0/terminal-bench-mini)
to test whether the scaled-input numerical error causes practical failures.
The prepared comparison is qualified Q2, retained `hc-up-chains` Q2 and
experimental `scaled-input` Q2, using the same original weights on `.157`.
There is **no completed task-quality comparison yet**. Neither identical short
greedy output nor a KL threshold establishes practical task success or harm.

## Frozen benchmark and scoring

The independently fetched benchmark is pinned to
`07034484346dc724d0e2c47c821fd196add1d6fb`. It supplies Core-19 1.0.0,
Harbor 0.20.0 and Terminus-2 2.0.0. Original task instructions, environments,
verifiers and solutions are unchanged. Solutions are never sent to the model.
Its own manifest validates task content digests before execution.

The full tier contains 19 tasks; smoke contains only `git-leak-recovery`.
Report those denominators separately. One task runs at a time. Preserve the
default three-hour agent timeout and up to two attempts, with attempt two only
after failure. That conditional task policy does not authorize retrying a GPU
fault or restarting a poisoned inference process.

An attempt passes only with final reward exactly one. Compare pass@1 and
pass@2 separately, including baseline-only passes and candidate-only passes.
Equal aggregate rates can hide different failing tasks. Distinguish verifier
failures, model/agent timeouts, output/context truncation and infrastructure
errors. Preserve original transcripts, rewards and actual command exits.
Sampling/serving differences and nondeterministic task state can also change
results; a small paired suite cannot prove general numerical equivalence.

## Actual serving path

The endpoint uses the first-party C17 LIE HTTP/worker/flow implementation from
commit `ae9c34ef26b0bb12ae5c995cb2ec99131da5aefd`, with its explicit in-process
Gufo HIP adapter linked to each experimental Q2 numerical target. It does not
use a Python HTTP proxy or a CPU model forward. The core thread worktree and
qualified provider-verification mechanism remain unchanged. This is an
experimental composition, not a released LIE provider qualification.

Common settings are port 8000, C1, context capacity 262144, prefill chunks 2048,
MTP/thinking/prefix cache off. A shared three-file serving patch advertises the
actual worker capacity in `/v1/models` and changes the omitted-max-tokens
default from 128 to the existing maximum of 4096. All arms use the same patch.
The existing per-response ceiling is **4096 output tokens** and the HTTP
request timeout ceiling is **1800 seconds**. These limits are recorded in the
profile: this is not an uncapped serving comparison. Truncation must never be
attributed to arithmetic without further evidence.

The [source manifest](../config/q2-terminal-core-source.json) preserves both
base and serving-variant hashes; the [patch](../experiments/q2-terminal-core.patch)
and [preparation tool](../tools/prepare-q2-terminal-core.py) reproduce the
changes. The [composition](../cmake/terminal/CMakeLists.txt) checks all frozen
core files before building. Every model variant retains a full MMQ compilation;
no archive from a different arithmetic route is reused.

## Admission and durable execution

Runtime checks use `.157` only. Every GPU build/run takes fresh nonblocking
leases on the original four lock identities, with KFD/process observations,
model stat witnesses and the 98 C inclusive thermal guard (or lower exposed
hardware threshold). Only owned processes and exact benchmark Compose projects
may be stopped. No foreign service, cache, model, source or hardware policy
is changed. The owner explicitly approved private Harbor dependencies and
benchmark container images; no system package or driver installation follows.

Harbor lives under the persistent task-owned `run/q2-terminal-bench/uv-cache`,
with its Python runtime under `run/q2-terminal-bench/python`. Sources, jobs,
transcripts and reports are outside `/tmp`. The launcher requires a detached
persistent supervisor for scored task runs. A successful launch receipt says
`DETACHED_STARTED_NOT_COMPLETE`, never that the benchmark passed.

Qualified Q2 endpoint admission `q2-terminal-qualified-probe-r1` passed on
2026-10-03: full server/MMQ build, original-model HTTP response `45` to `17+28`,
EOS after two output tokens, and the pinned benchmark's `doctor`. Its input
was **28 tokens**. Advertising/reserving 262144 tokens does not establish
correctness or performance at that actual prompt depth.

The unchanged core and shared serving patch each pass 25/25 Debug and
ASan/UBSan tests. Revised Q2 launch guards pass 13/13 in both profiles. Initial
benchmark unit-test attempts lacked upstream documentation/result fixtures;
their nonzero exits are preserved, and the original pinned fixtures are then
staged. The complete pinned suite subsequently passes 107/107 tests on `.157`.
Such harness-preparation failures are not model-quality failures.

The first scored smoke cohort is launched with:

```sh
python3 tools/q2-remote.py q2-terminal-smoke q2-terminal-qualified-smoke-r1 --detach
```

Its persistent directory on `.157` is
`/home/paperboy/workspace/projects/synapse-linux/synapse-lie/run/q2-terminal-qualified-smoke-r1`.
Read `results/result.json`, `results/terminal-session.json`,
`results/terminal-command-1.log` and `runner-console.log`; inspect live process
identities as well as receipts. The exact Harbor job is
`run/q2-terminal-bench/benchmark/jobs/q2-terminal-qualified-smoke-r1`.
Its conditional second attempt, if needed, has suffix `-attempt2`.

The underlying original runner command uses:

```sh
python3 terminal_bench.py run --endpoint http://127.0.0.1:8000/v1 --tier smoke \
  --platform strix-halo --model-name Qwen3.8-Flash-Next \
  --engine synapse-lie-q2-experiment --backend rocm \
  --engine-version ae9c34ef-gufo-f783fedb --quant Q2 \
  --inference-profile ar-thinking-off-prefix-off-output4096 \
  --tag q2-terminal-qualified-smoke-r1 --job-name q2-terminal-qualified-smoke-r1
```

Core-19 full and the other two arms remain pending admission of this complete
request/agent/container/verifier path. The [frozen plan](../config/q2-terminal-bench-plan.json)
records the intended paired comparison, not invented scores.

The saved-export [comparison tool](../tools/analyze-q2-terminal.py) refuses
incomplete denominators, missing conditional attempts, changed task provenance
and mismatched agent/serving settings. It computes exact-reward pass@1/pass@2,
baseline-only/candidate-only outcomes and a task matrix in JSON/CSV; it does
not modify the upstream scores or waive numerical gates. No three-arm export
is available to this reader yet.

### First real task result

Qualified Q2 completes `git-leak-recovery` at 2026-10-03 10:26:25.561 UTC,
reward **1.0 on attempt one**, with all five original verifier checks passing:
recovery output, clean committed history, preservation of legitimate commits,
clean unreachable objects, and repository contents checksum. The task takes
325.667 s, eight agent steps, 22068 total input and 1691 output tokens, with
maximum observed context4113 and no cached tokens or exception. All 23 raw
job/export files are collected and hash verified. This establishes the complete
real task path. It does not yet compare numerical variants or qualify deep
context. Retained smoke `q2-terminal-retained-smoke-r1` is running; scaled smoke
and full Core-19 remain pending. Six synthetic scoring-guard tests pass on
`.157`; those fixtures are not additional model-task passes.
