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

## Observed admission outcomes — no model execution

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

The portable binary is staged only under the two private LIE run directories,
not installed as a service. Its target DSO compatibility and real-model behavior
remain untested because both admissions failed before no-model binary preflight.
