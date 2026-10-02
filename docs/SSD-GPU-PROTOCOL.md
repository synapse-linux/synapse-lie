# SSD checkpoint qualification protocol

## Operator thermal revision for the next continuation

After R1 stopped, the user clarified that Strix Halo supports operation through
98 C. AMD lists [Tjmax 100 C for the Ryzen AI Max+ 395](https://www.amd.com/en/products/processors/laptop/ryzen/ai-300-series/amd-ryzen-ai-max-plus-395.html).
The next separately declared campaign uses an explicit 98 C CPU/GPU stop ceiling
on a verified `Ryzen AI Max+ 395` host, while retaining any lower exposed max/crit.
This is an operator-selected operating guard, not a new claim of a separately
specified GPU temperature rating. NVMe retains 85 C or lower sensor limits.
Default helper policy remains 85 C on all platforms; no hardware setting changes.

R1 stays FAILED under its original policy below. Its successful 512-token arms
remain narrow evidence; R2 prepares the remaining 14 arms at 8K/extension/128K
and core off/RAM/SSD. The numerical executable is unchanged. CPU regression
checks verify the explicit override, lower hardware limits, SSD separation and
refusal on unrelated hosts. Q2 currently owns `.157`; preparation is local and
launch waits for its explicit handover plus fresh four-lease admission.

## Original R1 declaration (retained)

This campaign follows the user's roadmap/SSD implementation and `go next`.
Q2 records a completed handover at 2026-10-02 07:13:11.718 UTC in its coordination
ledger and persistent `run/q2-hc-window-release.json`. This is campaign
coordination, not exclusivity or a substitute for fresh admission.

Use unchanged official Gufo `f783fedb` state-access numerical archives and the
C17 store/core. CPU fixtures and ASan/UBSan must pass on actual source. Local
compile/link does not rebuild numerical archives. No model execution, weight
hash or checkpoint hash runs outside the four established EX|NB leases.
No foreign source/process/model changes, deployment, installation, remote build,
conversion, tuning or publication.

## Sequential arms

Inputs reuse sealed physical token IDs from the RAM campaign. Context is
262144, chunk 2048, native AR, identical executable/libraries/model/device/
configuration/environment across restarts. SSD quota is 8 GiB per dedicated
store, staging 4 GiB. Reserve RAM separately from staging; require free disk
space at least the quota. These are admission estimates, not fit evidence.

1. `--suite state --state-ssd-mode write`, then a separate `read` process, at
   512/512, 8192/8192, 8192/4096 and 131072/131072 prompt/checkpoint tokens.
   Write requires an empty private store and exactly one durable commit. Read
   requires exactly that checkpoint; fallback or fresh capture cannot replace
   it. Compare every float logit after prefill and each of up to 16 AR steps,
   output IDs, positions and stop with full recomputation. Three pairs cover
   greedy, seed-123 sampling and an independent greedy clone. Any mismatch fails.
2. Shared-core C1 at 8192 and 131072 tokens, TG128: cache off; default RAM; empty
   SSD with RAM off; then SSD with RAM off after process restart. Off/RAM use
   one warmup plus three measured repetitions, the SSD producer one cold
   repetition, and the SSD reader three repetitions without discarding the
   first restarted read. Require matching physical input/output IDs and counts.
   Off/cold SSD must have zero reused tokens, warm RAM and all restarted SSD
   requests must fully reuse. Preserve cold/capture samples separately.

State pairs qualify complete disk state numerically; core arms qualify its
reactive consumer and timings. Neither proves independent model correctness.
Do not average different policies or report fresh PP tokens/s for a full hit.
Report model load and full-content identity separately from capture, durable
write, lookup/checksum read, owner upload, TTFT, executed PP and TG. Record
actual threads, RSS/staging/disk and temperatures. Identity/inventory hashing
warms OS file caches; there is no cold-device or reboot claim.

## Admission, failure and closure

`run-bench.py` accepts only explicit SSD budgets and the bound `prefix-store`
argument. The manifest authorizes model identity and checkpoint hashing. A new
store must be absent. Reuse binds a successful preceding sibling producer by
result SHA-256 and preserved checkpoint inventory. Refuse arbitrary paths,
unsealed producers, symlinks, unexpected entries and budget drift. The C store
also enforces private paths/ownership and its exclusive lock. The supervisor
never cleans or repairs a store.

Sample CPU/GPU/NVMe sensors before launch and each monitoring iteration. Refuse
at 85 C or lower exposed max/critical limits. On crossing, SIGTERM only the owned
model child, allow five seconds, then SIGKILL that child if necessary. Preserve
thermal failures and actual exits. Sampling cannot guarantee the physical
temperature never crosses the ceiling. No automatic rerun or hardware changes.

Each arm checks current lease inode identities, foreign KFD/DRM observations,
model stat witnesses, staged files and DSOs. Stop on the first failure. Verify
owned PID/start identities retired, KFD empty and unchanged/free leases; collect
and SHA-verify evidence before returning the window. Formal DS4 ACK absence and
denied-FD/desktop observations remain limits on exclusivity claims.

Synthetic corruption, quota, filesystem faults, cancellation and reactive peer
progress retain separate contract tests. This first campaign does not inject
GPU faults. Original-model HTTP SSD, 256K fit, 1M, active KV paging, PLE streaming,
sampler-session resume, MTP and vision remain separate gates.
