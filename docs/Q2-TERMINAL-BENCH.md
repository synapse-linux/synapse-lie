<!-- SPDX-License-Identifier: MIT -->
# Q2 arithmetic: real task qualification

**Thermal policy update, 2026-10-03:** after the preserved full-campaign stop,
the owner clarifies that 98 C applies to CPU and requests new fan curves with
maximum at 82 C. The [applied configuration](Q2-FAN-CURVE.md) records that change.
Earlier receipts retain their original shared CPU/GPU cap. Future cohorts must
identify the corrected guard and cooling policy, with identical settings across
compared variants. The failed/incomplete baseline is not reclassified as complete.

The owner selected [Terminal-Bench Mini](https://github.com/kyuz0/terminal-bench-mini)
to test whether the scaled-input numerical error causes practical failures.
The prepared comparison is qualified Q2, retained `hc-up-chains` Q2 and
experimental `scaled-input` Q2, using the same original weights on `.157`.
The paired smoke comparison is complete: **all three variants pass the one
original git-leak-recovery task on attempt one**. The full Core-19 baseline
was interrupted by its thermal guard after two completed tasks; retained/scaled
full arms have not started. Neither that one smoke task nor a KL threshold establishes general quality
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

The running server also reports an **8 MiB request body** ceiling and at most
**1024 messages**, preserved in the timestamped
[serving observation](../config/q2-terminal-serving-observation.json).
At 11:25:25 UTC on 2026-10-03, 26 POST requests have completed with 2xx status,
no POST 4xx/5xx, and no scheduler failure or cancellation. The separately
counted 132 GET 4xx have no path attribution. Recorded trajectories reach
28883 prompt tokens and at most 1771 output tokens per response; none reaches
4096. ATIF does not retain finish_reason here, and metrics/trajectory reads
are consecutive snapshots. These observations do not qualify the advertised
262144-token depth. HTTP latency includes acceptance through response enqueue,
so it cannot be reported as separate prefill/decode timing.

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

Completed supervisor and task evidence are collected separately:

```sh
python3 tools/q2-remote.py collect q2-terminal-qualified-full-r1
python3 tools/collect-q2-terminal.py q2-terminal-qualified-full-r1
```

Full Core-19 collections permit at most **2 GiB of uncompressed file content
per archive**, plus up to 1 MB of task-manifest overhead for the second command.
The mode-specific bound accommodates long telemetry and task transcripts
without truncation; exceeding it still fails. Short supervisor collections
retain 128 MB (the existing PLE first-access exception is 384 MB); smoke task
content retains 256 MB. File digests stream through bounded memory. The task
collector requires matching completed local/remote modes, exact export tags,
regular safe archive paths and file hashes, and refuses overwrites.

On `.157`, `q2-terminal-collection-host-r1` passes 15/15 Debug and ASan/UBSan
checks, including seven synthetic task-collection cases. The GiB boundary tests
use synthetic member sizes; the archive round trip uses small real files and
a mocked SSH transport. No real GiB campaign archive has yet been collected.
All seven host-run artifacts are collected/hash verified; see the
[test receipt](../config/q2-terminal-collection-host.json). CPU checks run
during the task-quality campaign, another reason not to interpret task wall
times as controlled kernel-performance measurements.

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

Full Core-19 started in persistent job `q2-terminal-qualified-full-r1`.
The full server/MMQ build completed at 2026-10-03 10:52:24.873 UTC and the
benchmark command started at 10:52:38.079 UTC. A live observation confirms
Harbor has started the first task, `break-filter-js-from-html`, with 19 tasks
selected and the owned supervisor alive. Retained and scaled full arms follow
sequentially; they have not started. Each full arm uses the same serving limits
and the original up-to-two-attempt policy. It may run for many hours; this
report does not contain a completed 19-task score. The following observations
precede the thermal stop and verified window release recorded below.

At the 2026-10-03 10:59:36 UTC observation, the qualified baseline has completed
one first attempt: `break-filter-js-from-html` receives reward 0 from its
original verifier, with no task exception. `build-cython-ext` is next. The
conditional second attempt is pending; this partial outcome is neither a final
Core-19 score nor evidence of a scaled-input regression.

At 2026-10-03 11:56:34 UTC, the same supervisor/session/server/wrapper remain
live. `build-cython-ext` has completed with reward 1 and no exception at
11:45:52.746 UTC after 32 agent steps. The baseline now has two completed
first attempts out of 19, one pass and one verifier failure;
`cobol-modernization` is active. The conditional second attempt and both other
full arms remain pending. The [partial progress record](../config/q2-terminal-full-progress.json)
preserves this timestamp and original outcomes without presenting a final score.

## Engine feature audit and interrupted full campaign

The owner asks whether missing engine features could explain the failure.
In the frozen serving composition, `adapters/gufo.cpp` fixes
`ChatTemplateOptions.enable_thinking` to false and `src/chat.c` rejects an
`enable_thinking: true` request. This is an integration limitation, not an
established limitation of the model. It could affect task quality; no paired
thinking-on comparison has measured that effect. All three arithmetic arms
share the same limitation, so their results apply only to this serving profile.
The omitted temperature also defaults to greedy zero. Profile equality helps
isolate arithmetic changes, but does not establish full model capability.

Terminus requests JSON with analysis, plan, shell keystrokes and a completion
flag. It executes those commands and sends terminal observations back to the
model. This task does not require native API `tool_calls`: the ATIF trajectory
normalizes its command protocol into tool-call records. The observed commands
and their outputs are present. Missing native tool features therefore do not
explain this failure. This run also does not qualify native tool compatibility.

For `break-filter-js-from-html`, the qualified baseline reads both source files,
creates an HTML candidate and twice invokes `python /app/test_outputs.py`.
That file only defines a pytest test; it has no entry point that invokes it.
The agent interprets the silent return to the shell as successful verification.
The original task instruction suggests running that file to verify, without
specifying pytest, so the instruction is ambiguous as well. The official
verifier does invoke pytest, collects one test and observes no alert within
five seconds. It reports one failure in 7.70 s, reward 0, no task exception.
The precise browser-level reason for the missing alert is not established.
No solution, correction or diagnosis is supplied to subsequent evaluated agents.

This failed task reaches 4806 prompt tokens and 1771 output tokens, below the
configured 262144/4096 ceilings. ATIF lacks finish_reason, so this is not a
complete wire-level truncation audit. Cache, MTP and native batching are off;
their absence is not an observed cause of this task failure. Any future thinking,
template or core-feature experiment must use a separate matched cohort, retaining
the original task instructions, graders and arithmetic comparison profile.

At 2026-10-03 12:25:27.557 UTC the full baseline supervisor records FAILED:
GPU 99 C exceeds 98 C; CPU 96.5 C remains within its limit. The session exits -15
under the thermal guard and exact-task container cleanup exits 0. The older
terminal-session receipt still says READY because termination interrupted its
normal finalizer; the terminal supervisor receipt and fresh process checks
determine the actual state. This is distinct from the earlier HTML task failure.
Only two first attempts finish (one pass, one fail). COBOL is interrupted after
31 agent steps, with peak prompt 57330 and peak output 1806. No final Core-19
score, conditional second attempt or retained/scaled full result exists.

All 11 supervisor artifacts and 34 raw job files are collected with verified
hashes. The failed job archive is explicitly partial and has no normalized
successful-run export. At 12:30:15 UTC, ten recorded PIDs and owned process
groups are absent, no owned task containers remain, readable KFD is empty and
all four original lease identities are acquired EX|NB and released. GPU 50 C,
CPU 51.125 C. Restricted proc visibility remains recorded. The persistent remote
`run/q2-terminal-thermal-window-release.json` and shared registry record release;
the outgoing core-thread message failed at the local transport, so delivery is
not claimed. No GPU restart or other arm is queued. The
[audit receipt](../config/q2-terminal-engine-audit.json) preserves outcomes,
collection identities, feature evidence and closure. Task data and scores remain
unchanged; these documentation/evidence updates require no new runtime test.
