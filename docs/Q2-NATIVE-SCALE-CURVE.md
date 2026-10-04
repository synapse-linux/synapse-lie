<!-- SPDX-License-Identifier: MIT -->
# Native canonical benchmark for the IQ2 scale candidate

The next model campaign keeps the measured C17 server, timers and Q2/UD
providers, while the independently qualified native C `synapse-lie-bench`
executes the canonical Gufo workload. The selected scale candidate has
[component evidence](Q2-IQ2-PREFILL-REUSE.md), not a model prefill gain.
Whole-curve parity and the broader [acceptance matrix](Q2-CURVE-PARITY.md)
remain open.

## Composition

The server remains the exact `15c6082152c3df0cb1f40d89ba5329692f307d7b`
snapshot in `config/q2-curve-source.json`. The new benchmark is a separate
executable built from a clean, committed core worktree with
`LIE_GUFO_RUNTIME=OFF` and legacy Python tests disabled. It uses HTTP on
loopback port 8000 and does not embed or load the provider.
`prepare-q2-native-bench.py` records the full client source inventory and
copies its core qualification receipt into persistent evidence. No dirty core
source is imported. The source receipt is required before any model staging.

The wrapper's `--native-curve` is restricted to ordered Q2, scale-reuse Q2 and
pristine UD. `q2-curve-scale` requires this flag and a full MMQ rebuild. It
cannot silently select the historical Python curve driver. The C client owns
prompt generation, calibration, prefix requests, measured requests, JSONL,
offline protocol reconstruction and graphs. Python retains only the existing
remote process/lease supervision and evidence auditing role.

The session checks the actual C1 backend identity, prefix cache and idle
scheduler before and after the client. The server and native client binaries
must remain unchanged. Both children inherit the supervised process group;
timeout and thermal handling remain in the existing owned-process supervisor.
No persistent server is deployed and no foreign process is terminated.

## Frozen workload and order

[Campaign plan](../config/q2-native-scale-curve-plan.json):

1. Ordered Q2 reference, `q2-native-scale-before-r1`.
2. Scale-reuse Q2, `q2-native-scale-candidate-r1`.
3. Repeated ordered Q2, `q2-native-scale-after-r1`.
4. Pristine UD, `q2-native-scale-ud-r1`.

Each arm uses C1 AR, greedy prose, pp2048/tg128, one warmup and one sample at
each cached-prefix depth 0/4/8/12/16/32/64/128K. Capacity 133760, chunk 2048,
eight-token prefix reply, tolerance, retry history and the 16 GiB RAM prefix
budget remain unchanged. MTP, thinking, vision and SSD are off.
No file-cache drop or cold-cache claim. PP/TG use completed executor calls;
HTTP wall time and first output are additional client observations.

The entire Q2 request/reply history must match across controls and candidate,
including calibration, warmup, prefix replies and physical token counts.
Every curve must complete all 128 output tokens at all eight accepted points.
All mismatches and actual command exits are retained. UD prefix replies may
differ; its workload recipe and timers must match. Independent quality remains
a separate requirement.

## Host qualification and current gate

The new Q2 wrapper and admission guards pass 22/22 Debug and 22/22 ASan/UBSan
on .157. All three host cohorts each have six zero command exits
and seven verified artifacts. The final cohort also covers the isolated
`native-curve-cpu` mode, which builds only the frozen C client and its three
native contracts, without acquiring GPU leases or loading models. The host capsule
binds eleven harness files. Tests cover native-only scale admission, wrong
provider rejection, source inventory tampering and busy/mismatched backend
rejection. [Initial host receipt](../config/q2-native-curve-host-results.json),
[current host receipt](../config/q2-native-curve-host-r3-results.json).

The prepared analyzer checks source inventories, qualified harness bytes,
model/lease identities, completed child exits, the C report against its raw
JSONL and all Q2 request/reply histories. Tracked reports retain semantic
payload hashes; the complete prompts/replies remain in the verified raw
artifacts. Every PP/TG value is checked against actual counts and completed
executor durations. The fresh-admission script includes all three wrapper cohorts
and the native client conformance cohort in process retirement.

The native C client is frozen from clean core commit
`b598e4c1e6aba26b0bacd6ad243503009360c869`: all 1287 source files and the
separate core qualification receipt are preserved. On .157 its three native
contracts pass in Debug and ASan/UBSan, six commands exit zero and seven
artifacts verify. [Conformance receipt](../config/q2-native-bench-conformance-results.json).
The native client and model server have independent frozen source inventories.

The current plan is **not GPU-admitted**. No model performance result is
inferred from host tests. Fresh ownership, original leases, KFD, model-stat
and thermal checks remain required. No changes to core ABI, persistent state
or metrics contracts occur.
