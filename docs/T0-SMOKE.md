# One-shot original-model smoke — operator window

After the read-only 18:34–18:37 UTC inspection on 2026-09-30 showed no DS4/Gufo
inference, no KFD clients, idle DS4 containers and unheld known qualification
locks, the operator explicitly said **“ok procedi”**. This authorizes this bounded
LIE test window. It is **not** an ACK forged on behalf of DS4, nor permanent
shared-runner adoption. No `ds4-ack.json` is written. Future campaigns retain the
coordination requirements in COORDINATION.md.

The existing verified binary is copied from `.155` to an exclusive LIE-owned
`run/t0-model-smoke-r1` directory on `.157`. No installation, remote compilation,
permanent service, foreign process stop, model download/conversion/hash or tuning.
Its local source commit is `ad33a5e`, build `t0-linked-r4`; exact binary and helper
hashes, target ELF dependencies and unchanged model stat identities are recorded.
The observed target filesystem is not shared with the editing host.

## Admission and cleanup

The supervisor nonblockingly locks existing files: outer DS4 campaign pipeline,
then download and qualification locks in their declared order, then the LIE shared
lock. Any contention/identity drift refuses this attempt, never waits in a
conflicting order. It does not rewrite or delete locks. The supervisor retains
all leases through child exit and appends start/end records to the shared register.

Fresh KFD/DRI observations, model stats, available memory and ports precede launch.
RAM admission compares available bytes with trunk file size as a coarse estimate,
**not a fit proof or fixed 32 GiB reserve**. Loaded workspace cost is not known in
advance. GPU/device and RAM samples are recorded; new observable GPU clients abort
only the owned child. Existing desktop clients remain, and permission limits
mean global exclusivity is not proved. No performance conclusion is permitted.

Private HOME/cache/temp, no inherited DS4/Gufo overrides, GPU index 0, no core dump.
The parent handles interruption, stops only its Popen child, waits for retirement,
and records the actual exit. Loading deadline 900 s; request deadline 120 s;
SIGTERM shutdown grace 120 s, then owned-child kill if required (a failure, not a
clean shutdown). No automatic model retry or fallback. Each results directory is
exclusive; a failed run is never overwritten/replayed.

## Workload and predeclared smoke oracle

Original UD-Q4_K_XL four-shard trunk; MTP sidecar stat-checked but not used.
Context 4096, prefill chunk 2048, one active sequence, greedy, thinking disabled,
no tools, no MTP/vision, fresh sessions. Test strings and expected answers are in
the immutable per-run manifest **before execution**. Each request is performed
nonstream and streaming, with identical messages/output budget. Output is decoded
strict UTF-8; no post-hoc widening of the expected-text comparison.

Require: genuine delegated provider, readiness, nonempty model-generated output,
valid stop/length/usage, exact expected text after whitespace stripping, identical
nonstream/SSE content/usage/finish, one SSE DONE and no SSE error, consistent worker
accounting, clean process shutdown, disappearance of the owned KFD process and
unchanged model stats/binary. An observed failure remains a failure.

This proves at most **bounded real-model HTTP/SSE smoke**, not full numerical,
quality, concurrency, cancellation-in-flight, long-context, memory-fit, performance
or release qualification. In particular it is not the pristine comparator gate:
physical token/frontier/full finite-logit comparison still needs its separately
specified harness. No serving or pure-inference speedup follows from wall times.

## Earlier admission outcomes — r1/r2, no model execution

- `t0-model-smoke-r1`, 18:49:35 UTC: exclusive outer pipeline lock acquired, then
  download lock returned EAGAIN. Exit 1; `model_attempted:false`. A foreign KFD
  process 1550255 was observed during closure and had exited by the 18:50 check.
- `t0-model-smoke-r2`, 18:51:54 UTC: new exclusive directory and same binary/oracles;
  admission again refused on the download lock, exit 1, before model open. Foreign
  KFD PID 1550811, GPU busy 99%, GTT used 46877753344 bytes were recorded.
- At 18:53:24 UTC the active KFD process was PID 1551680, `native-perf` at
  DS4's `build-gufo-formats/native-perf`, running the `gufo-formats-Q2-warm-b-r1`
  phase. GPU busy 98%. Parent PID 1551661 held download, qualification and shared
  LIE/DS4 locks; native-perf also held `/tmp/ds4.lock`. No process was stopped.
- This is changing hardware activity, not a failure of LIE model loading: **no
  LIE model or request was run**. No start/end model-run record was appended
  because neither attempt passed admission. Both private result sets preserve
  command exit, lock identity, unchanged model stats and binary hash.
- Two DS4 containers were idle during the earlier 18:37 inspection; that dated
  observation is not rewritten. The later benchmark campaign precludes taking
  a brief between-job gap and perturbing its warm-up/measurement cache state.
  No further retry or background waiter is scheduled. Resume only after a real
  handover of the campaign window; ACK/register remained absent at 18:53:55 UTC.

At the end of r1/r2, the portable binary was staged only under private LIE run
directories, not installed as a service. Target DSO compatibility and real-model
behavior were then untested because both admissions failed before binary preflight.

## Resumed operator window — 2026-09-30 20:01–20:07 UTC

The operator explicitly said **“ok per ora riprendi lo sviluppo lie che le
macchine sono libere”**. This is a fresh development/test handover, not reuse of
the old authorization or an ACK written for the DS4 owner. The new read-only
`t0-node-activity-r2` probe observed GPU busy 0% in five samples, no KFD clients,
no observable inference candidates/model handles/HIP mappings and no holder of
the known leases. Permission-denied observations remain recorded; this is not
proof of global exclusivity. Each new run still acquired all four existing locks
nonblockingly and retained them through cleanup.

### r3 — runner defect, preserved failure

`t0-model-smoke-r3` acquired all leases and passed `--build-info`, ELF/DSO checks
and original-model stat admission. At 20:03:53 UTC it launched the owned server,
then immediately failed because the Python function `http` shadowed the imported
`http.client` module. The child exited -15 during cleanup; the server log was
empty, no readiness or generated output was observed, and the supervisor exited 1.
This is a runner failure, not evidence of model-load failure or OOM.

The module now has the explicit alias `http_client`. The CPU-only regression in
`tests/test_smoke_model.py` reproduced the error before the fix, then passed GET,
UTF-8 POST, non-200 status preservation and response-size refusal after the fix.
It is the ninth CTest suite, `model-smoke-helper`. No runtime C/C++ source or
model oracle changed. `t0-smoke-http-red-r1`, `t0-smoke-http-green-r1` and
`t0-smoke-runner-fix-r1` preserve the focused and GCC/Clang/ASan/UBSan results.

### r4 — bounded original-weight HTTP/SSE smoke PASS

A new exclusive directory/manifest used the corrected helper, the same original
weights and the same predeclared requests. The real server became ready at
20:07:40.366 UTC and retired cleanly at 20:07:42.302 UTC.

| Case | Exact content | Reported prompt tokens | Emitted tokens | Finish | JSON/SSE |
|---|---|---:|---:|---|---|
| ready | `READY` | 25 | 1 | stop | identical |
| arithmetic | `4` | 31 | 1 | stop | identical |
| unicode | `caffè 🙂` | 24 | 3 | stop | identical |

Worker totals: six completed requests, ten emitted tokens, zero failed/cancelled,
zero queued/active after retirement. Each stream had exactly one DONE. Both server
and helper exited 0. No foreign GPU clients were observed; KFD was empty before
and after. All five original model stat identities and the binary hash remained
unchanged. The MTP sidecar was only stat-checked, not used. No package installation,
model conversion, foreign-process termination, tuning or permanent service occurred.

Executed binary: `build/t0-linked-r4/synapse-lie-server`, SHA256
`22e0023465e67f860081fe32c2280bb64673339532b74bbd5bac0f97324d3fbc`.
Corrected runner SHA256:
`99dd271d638a90ed139fc10b816ed891184523da3b646aafc4c42b8f90456464`.
Authoritative result: `evidence/t0-model-smoke-r4/remote-results/result.json`;
assessment, process exit, DSO hashes, server log and 24 one-second telemetry samples
are retained alongside it. The shared register contains actual start/end records;
no DS4 ACK was fabricated.

This closes the **first real-model serving smoke**, not the complete T0 acceptance
gate. Physical-token/frontier/full-logit comparison against a separately qualified
pristine reference, real cancellation/backpressure/concurrency, broader quality,
capacity and performance remain open. Whole-device GTT and system MemAvailable
samples are not exact LIE allocation/peak accounting. `hardware_qualified` and
`inference_verified` diagnostics remain false; this smoke does not redefine them.
