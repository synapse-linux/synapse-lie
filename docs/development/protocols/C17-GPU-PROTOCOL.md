<!-- SPDX-License-Identifier: MIT -->
# C17 sampling and integrated GPU qualification

The owner requests completion of the remaining GPU tests on `.157`, with CPU
development as the fallback while that machine is occupied. The Q2 campaign
records its release at **2026-10-03 17:37:05.108908 UTC**, with no scheduled
restart. Fresh observation verifies empty KFD, all four original leases free,
unchanged UD/MTP model stat witnesses and port 8000 available. Root notifies
the existing Q2 thread before taking this window.

Source checkpoint: `f0f58b3`. Independently acquired official Gufo pin:
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`. The verified provider includes the
C17 dense selector; model execution and compact MTP distributions remain
delegated. Builds and fixtures already pass locally with GPU visibility masked.
Original weights are used read-only; no source/artifact comes from DS4.

## First functional arms

Each arm starts a private temporary HTTP listener on loopback port 8000 and
retires it afterwards. Context is 4096, chunk 2048, at most eight active jobs.
RAM cache retains its default 4 GiB budget; SSD remains off.

1. AR: original-weight arithmetic and JSON/SSE equivalence; seeded top-p with
   frequency/presence penalties; bias and finite token/top logprobs; stop
   suppression; three choices and aggregate SSE; strict schema/functions and
   correlated tool results; stored completion CRUD/filtering; retained Responses
   retrieval, live/replayed/cursor events, conversation continuation, background
   cancellation and oldest-turn truncation; repeated RAM prefix accounting.
2. MTP: explicit shared Q8 predictor, three requested draft tokens; completed
   TG128 with actual drafted/accepted counters; controlled AR fallback for
   bias/logprobs; repeated RAM prefix accounting.
3. Combined MTP/vision: same predictor plus the original Q8 projector; generated
   256×256 red PNG as a declared fixture, actual image description and repeated
   output/usage; ordinary text MTP and controlled AR fallback; RAM accounting.

These are same-provider functional checks. A correct color/arithmetic answer
does not establish independent numerical equivalence, exact MTP rejection
rollback, image-key isolation or performance parity. Missing gates remain open.
Failed/incomplete arms retain their own directories and actual exits. No
unchanged failed arm is automatically retried.

## Following gates

After the initial arms: exact AR state/logit continuation and SSD restart;
matched C1/C2/C4/C6/C8 and 8K–128K/full-256K context controls against the compiled
legacy sampler; original-weight MTP/vision cache continuation and differing-image
isolation; rejection/cancellation/backpressure and peer progress; sampler host
cost/scratch peaks. Preserve actual output IDs, input/frontier hashes, EOS,
prefill, decode, restore and client latencies separately. Do not infer reactive
speedup from callbacks, OS thread counts or restored-token rates.

The current native context limit is 262144. A 1M context needs a separate RoPE /
YaRN implementation and quality/resource gate; raising a CLI integer is not a
valid experiment. Unimplemented model/platform executors are not test passes.

## Admission and closure

Persistent private capsule and evidence: `run/gpu-functional-f0-r1` on `.157`,
`evidence/gpu-functional-f0-r1` in this worktree. No source is placed in `/tmp`.
Every arm independently acquires the four original EX|NB leases in established
order and verifies their device/inode identities. It checks current model stats,
capsule/binary/DSO identities, available memory and KFD/DRM observations before
launch and records start/end in the append-only shared register.

Telemetry records temperatures, fans, OS threads/RSS, GPU and memory at 0.5 s.
The explicit Strix Halo operating guard is 98 C, with lower exposed hardware
limits and 85 C NVMe guards retained. A supervisor stops only its owned child;
this is a software policy stop, not hardware shutdown or proof of memory fit.
No device, power, fan, service, installation or foreign process is changed.
Desktop activity, denied FDs and absence of formal DS4 ACK limit isolation claims.

Closure must verify owned process retirement, empty KFD, unchanged/free leases,
unchanged file/model identities and collected hashes before returning the window.
Per-arm lease release does not invite interleaving into this enclosing campaign.

## Prepared clocked performance follow-up

`gpu-perf-clocked-r1` is prepared at runtime checkpoint `15c6082`, with GPU
admission disabled. Renew its handover witness and notify peers before staging
or running it; the previous root vision window has been returned to Q2.

The first two arms fill the missing 12288-token depth for C17 and the compiled
C++ control: PP2048/TG128, one warmup and three samples, capacity 133760. The
following eight arms isolate the prior PP1500/TG128 slowdown at fixed capacity
262144. No-warmup processes follow C17/CPP/CPP/C17; two-warmup processes follow
CPP/C17/C17/CPP. Each has three measured samples and fresh sequence state.
Keep first-process samples and subsequent repetitions separate in the analysis.
Do not flush OS caches or change device policy; no cold-file claim is permitted.

Native sample records bind complete monotonic PP/TG intervals. The private
supervisor records read-only optional clock/power/busy fields, CPU frequencies,
load and temperature in the same monotonic domain; missing fields are explicit.
Require exact input/output/full-frontier witnesses and validated phase durations
before comparison. Preserve all samples and failures. A newer run cannot erase
the retained 16.64% slowdown, and greedy GPU argmax does not isolate dense host
sampler cost. Sampler cost, MTP/vision performance and matched HTTP concurrency
remain separate gates. See the
[preparation receipt](../validation/performance-followup-preparation-2026-10-03.json).
