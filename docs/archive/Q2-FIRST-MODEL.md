# First real antirez Q2 test — passed, performance qualification open

> Historical technical record. See [current usage](../guides/USAGE.md) and
> [benchmark tables and graphs](../benchmarks/README.md). Results below retain
> their original build, protocol and limitations.

> Archived experiment. The owner withdrew this port; its active source/tools
> were removed. Commands below are historical, not current instructions.
> See [the replacement plan](REPLAN.md); recover source from Git `a208760`.

On **2026-10-01 10:14:42–10:15:04 UTC** (supervisor scope),
`q2-model-first-gpu-r1` loaded the actual `Qwen3.8-Flash-Next-Q2.gguf` on `.157`
and completed two fresh-session requests through the LIE synchronous executor
ABI and private embedded Gufo adapter. **This is real model execution**, not a
header, scalar fixture or isolated operator test. It is not production enablement.

## Observed result

Model loading took **11.638014675 seconds**. Context 9216, prefill chunk 2048,
greedy AR, thinking/MTP/vision/prefix reuse off, one sequence at a time.

| Sample | Physical input | Emitted tokens | Completed PP seconds | PP tok/s | Completed TG seconds | TG tok/s |
|---|---:|---:|---:|---:|---:|---:|
| Arithmetic | 31 | 1 | 0.367700934 | 84.307646 | 0.050222671 | 19.911327 |
| Counting | 458 | 128 | 1.243970358 | 368.175975 | 6.466882489 | 19.793154 |

Arithmetic produced exactly **`4`**, then EOS. Counting produced the consecutive
integers **1 through 46**, newline-separated, stopping at the 128-token budget.
The second sample does not claim to have a 512-token prompt. Full physical input
IDs, output IDs/bytes, positions, and nanosecond timings are retained. Frontier
logits were checked finite after prefill and every decode call. EOS work is timed;
only emitted tokens enter the TG numerator. Tokenization, sequence creation,
logit copying/checking, output conversion and cleanup are outside PP/TG timers.

These are **two preliminary samples, without benchmark warmup or repetitions**;
the second follows the first within the same loaded process. Both sessions are
fresh, not prefix-cached. The result does not establish independent numerical
parity, matched performance, regression bounds, server/HTTP throughput or TTFT.
The counting TG rate is below the historical UD rate around 26 tok/s, but different
formats, inputs and measurement protocols prevent labeling that difference a
matched regression. No preserved-performance or optimization claim is made.

## Dedicated-machine memory policy

The operator explicitly authorized GPU testing and stated the machine was wholly
dedicated to the model. The proposed **53.5 GB cumulative HIP cap and fixed 32 GiB
reserve were removed before this GPU run**. Both recorded fields are zero.
There is no automatic retry, CPU model-forward fallback or memory-policy fallback.

The test binds the actual layout before HIP allocation and checks available RAM
against the non-PLE weight/conversion/tail estimate, **44952325888 bytes**. This is
not a complete resident-fit prediction. The existing production UD gate is unchanged.
The **102400491520-byte PLE table remains disk-addressed**, not uploaded in full.
The isolated weight/PLE readers require direct I/O and refuse buffered fallback;
virtual GGUF mappings must not be equated with resident payload. This is existing
model row access, not a new SSD prefix/session cache or model conversion.

At load completion, provider-reported weights were 43148148224 bytes, session
storage 376777748 bytes and deferred workspace 7946240 bytes. These are provider
reports, not an independently measured process peak. Wrapped `hipMalloc` and
`hipHostMalloc` requests totaled 46112950296 bytes over the attempt: **cumulative
requested bytes include freed requests and are not live/resident memory**, nor do
they account for every allocation internal to shared libraries. Twenty telemetry
samples observed minimum **global MemAvailable 79222382592 bytes**. This supports
this successful bounded run, not arbitrary-context/concurrency memory qualification.

## Isolation, identity and closure

- Production upload/link refusals and provider recipes remain unchanged. Only the
  private test overlay permits admitted routed Q2 upload. It fixes the tested
  architecture, context, concurrency and disabled MTP/vision scope.
- `tools/build-q2-model-test.py EXCLUSIVE-LABEL` prepares/builds locally, serially,
  GPU masked. It runs host checks only, never model inference. It currently uses
  the retained `q2-admission-linked-r1` source tree as its isolated base.
- `q2-model-first-build-r1` preserves a source-preparation filename failure before
  compilation. `q2-model-first-build-r2` built the provider and capped test locally;
  that capped executable was **not GPU-run**. `q2-model-first-relink-r1` rebuilt the
  C driver/accounting and adapter guard against the unchanged r2 provider archives,
  removing the cap/reserve. **The relinked executable is the one actually run.**
- Binary source identity is base Git commit `c0d6c6d` plus retained build diffs;
  provider and driver receipts remain distinct. The run manifest derives its binary
  binding from the selected relink receipt, not a copied stale source-SHA field.
- All four existing leases were held EX|NB, with expected inode/device and FD/path
  checks, current in-lease preflight, start/end registration and telemetry. Formal
  DS4 ACK was absent. Desktop/denied-FD observations limit exclusivity claims.
- Child/supervisor exited 0; staged artifacts and model stat identity stayed
  unchanged. No new full model hash was computed. At **10:18:10.344270 UTC**, both
  owned PID/start identities were retired, KFD empty and all four unchanged lease
  files free. No service, listener, waiter, installation, tuning or DS4 change.

Raw results: `evidence/q2-model-first-gpu-r1/remote-results/`.
Build/source records: `evidence/q2-model-first-build-r2/` and
`evidence/q2-model-first-relink-r1/`. Local host checks do not substitute for the
GPU result above. The completed one-shot window is not standing authorization.

**Next:** matched UD before/after and Q2 versus an equivalent Q2 reference, including
fresh PP512/2048/8192 and TG128. Full quality, failure/reload, batching and production
admission remain open. Q4 has not been loaded or measured.
