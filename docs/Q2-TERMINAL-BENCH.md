<!-- SPDX-License-Identifier: MIT -->
# Q2 arithmetic: real task qualification

The owner selected [Terminal-Bench Mini](https://github.com/kyuz0/terminal-bench-mini)
to test whether the scaled-input numerical error causes practical failures.
The prepared comparison is qualified Q2, retained `hc-up-chains` Q2 and
experimental `scaled-input` Q2, using the same original weights on `.157`.
The paired smoke comparison is complete: **all three variants pass the one
original git-leak-recovery task on attempt one**. Full Core-19 remains in
progress. Neither that one task nor a KL threshold establishes general quality
equivalence or harm.

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

The three smoke arms now establish the complete request/agent/container/
verifier path. The [plan](../config/q2-terminal-bench-plan.json) records the
sequential full-suite comparison; full-suite scores remain pending.

The saved-export [comparison tool](../tools/analyze-q2-terminal.py) refuses
incomplete denominators, missing conditional attempts, changed task provenance
and mismatched agent/serving settings. It computes exact-reward pass@1/pass@2,
baseline-only/candidate-only outcomes and a task matrix in JSON/CSV; it does
not modify the upstream scores or waive numerical gates. The completed three-arm smoke export is validated in
[JSON](../config/q2-terminal-smoke-results.json) and
[CSV](../config/q2-terminal-smoke-results.csv).

## Completed paired smoke result

Each variant passes all five original verifier checks: recovery output, clean
committed history, preservation of legitimate commits, clean unreachable
objects, and repository contents checksum.

| Arithmetic route | Pass@1 | Original verifier checks | Agent steps | Output tokens | Peak context | Task seconds |
|---|---:|---:|---:|---:|---:|---:|
| Qualified Q2 | 1/1 | 5/5 | 8 | 1691 | 4113 | 325.667 |
| Retained hc-up-chains | 1/1 | 5/5 | 8 | 1792 | 4645 | 279.337 |
| Scaled input | 1/1 | 5/5 | 9 | 2159 | 5374 | 304.758 |

Pass@2 is also 1/1, because a first-attempt pass skips the conditional second
attempt. This is **one task across three implementations**, not three distinct
tasks or five independent benchmark tasks. All 69 raw job/export files and 33
supervisor artifacts are collected/hash verified. No exception, GPU/thermal
stop, model stat change or postflight KFD client is observed. All three
model/agent/serving profiles and task provenance agree after removing only the
arm tag. Maximum per-response output is 302/327/358 tokens, below 4096.

The candidate has no observed functional regression on this task, while using
one extra agent step and 20.48% more output tokens than the retained path.
Trajectories differ. This is not evidence that every numerical difference is
harmless, nor a general efficiency improvement. Task durations include agent
commands, environment preparation and verifier work; the first run also pulls
the image. Do not substitute these times for the controlled C1 PP/TG results.
The maximum exercised context here is 5374, not 256K or 128K.

The runtime inventory records ROCm 7.2.4, kernel 7.2.2-1-cachyos, Python 3.12.13
and all 90 private Harbor packages in
[environment metadata](../config/q2-terminal-harbor-environment.json). The
[setup record](../config/q2-terminal-bench-setup.json) preserves exits 1/1/0 for
the missing-fixture unit-test sequence and 107/107 final success. Final Q2
CTest/ASan/UBSan also passes 14/14, including six synthetic scoring guards.
Those fixtures are not additional model-task passes.

Full Core-19 is running in persistent job `q2-terminal-qualified-full-r1`.
The full server/MMQ build completed at 2026-10-03 10:52:24.873 UTC and the
benchmark command started at 10:52:38.079 UTC. A live observation confirms
Harbor has started the first task, `break-filter-js-from-html`, with 19 tasks
selected and the owned supervisor alive. Retained and scaled full arms follow
sequentially; they have not started. Each full arm uses the same serving limits
and the original up-to-two-attempt policy. It may run for many hours; this
report does not contain a completed 19-task score. The Q2 GPU
window remains owned while the campaign is active; no release is claimed.

At the 2026-10-03 10:59:36 UTC observation, the qualified baseline has completed
one first attempt: `break-filter-js-from-html` receives reward 0 from its
original verifier, with no task exception. `build-cython-ext` is next. The
conditional second attempt is pending; this partial outcome is neither a final
Core-19 score nor evidence of a scaled-input regression.
