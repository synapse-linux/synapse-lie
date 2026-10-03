<!-- SPDX-License-Identifier: MIT -->
# Corrected decode measurement and the original UD baseline

## Original C17 comparison completed — 2026-10-03

**UD starts from about 26 token/s at 2K.** Its original 2042-token reference is
26.049385991 token/s, and the fresh original-C17 control reproduces it at
26.061301587. Q2 reaches 25.514301055: **2.0989% below fresh UD**, or
**0.822636 ms more per completed token**. The earlier strict diagnostic's
25.463 UD value is a different timing path and does not lower the target.

Medians below exclude one warmup per prompt and retain all three measured
rounds. Both models complete 128 decode steps per sample, C1 AR without MTP.

| Physical prompt tokens | Q2 PP token/s | Fresh UD PP token/s | Q2 TG token/s | Fresh UD TG token/s | Q2 PP delta | Q2 TG delta |
|---:|---:|---:|---:|---:|---:|---:|
| 502 | 967.871770 | 1002.727381 | 26.18439268 | 26.86494328 | -3.4761% | -2.5332% |
| 2042 | 1362.818601 | 1663.578946 | 25.51430106 | 26.06130159 | -18.0791% | -2.0989% |
| 8191 | 1375.884735 | 1624.557799 | 25.48272965 | 25.96974824 | -15.3071% | -1.8753% |

| Physical prompt tokens | Model | Median PP seconds | Median TG seconds |
|---:|---|---:|---:|
| 502 | Q2 | 0.518663748 | 4.888408205 |
| 502 | UD | 0.500634579 | 4.764573618 |
| 2042 | Q2 | 1.498365225 | 5.016794296 |
| 2042 | UD | 1.227474058 | 4.911496825 |
| 8191 | Q2 | 5.953260323 | 5.023009770 |
| 8191 | UD | 5.041987430 | 4.928811740 |

The historical UD decode medians at 502/2042/8191 were
26.851351194/26.049385991/25.964753259. Fresh UD reproduces all 36 original
witnesses exactly: twelve output-ID sequences, twelve prefill-frontier hashes
and twelve final-frontier hashes. Q2 matches all twelve original output-ID
sequences, with different logits. Its twelve 2042-token witnesses match the
preceding strict Q2 diagnostic, including full frontier hashes. These replay
checks do not establish general task quality or clear the existing operator
failures and qualified-reference KL 0.002996 > 0.002 rejection.

Changing from strict diagnostic sampling to the original C17 timing raises
the measured Q2 rate from 25.080 to 25.514 and UD from 25.463 to 26.061.
No GPU kernel changes were introduced by this benchmark composition. The
sampler paths differ, but no isolated measurement attributes the entire timing
difference to one host operation. The scalar HC candidate remains outside
these full-model runs; its component saving is recorded separately.

[Complete verified JSON](../config/q2-original-baseline-results.json),
[all 36 historical/fresh samples and durations as CSV](figures/q2-original-baseline.csv),
[SVG](figures/q2-original-baseline.svg) and [PNG](figures/q2-original-baseline.png).
All warmups are retained and marked. UD's 8191-token measured TG durations
4.980317538/4.928811740/4.918753286 seconds are kept without outlier removal.

![Historical and fresh original C17 Q2 and UD benchmark](figures/q2-original-baseline.svg)

### Frozen benchmark and validation

The private `q2_original_baseline` target now rebuilds the actual benchmark
behind UD's **26.049385991 token/s** reference. The benchmark, ABI header, adapter, binding,
failure drain and MIT license are byte-exact first-party files from clean LIE
commit `7f85ef8090506c32998780a8249aa0e10cd9e091`. Their hashes are checked at
configuration. Numerical code comes from the independently pinned Gufo source;
no old binary or MMQ archive is reused. This historical ABI exists only inside
the benchmark composition and does not replace the current serving contract.

This preserves the actual physical inputs **502/2042/8191**, context 9216,
chunk 2048, production greedy sampler, EOS behavior, 128 completed-token budget,
one warmup per prompt and three measured rounds in ascending/descending/ascending
order. The complete original C17 timing loops and checks are unchanged. It
measures Q2 `library-norm-bound` and pristine UD through the same original ABI.
The existing strict diagnostic executable remains unchanged; its different
sampling cost must not be called a GPU optimization.

The original sampler skips isolated nonfinite logits. Original full-vocabulary
checks at PP/final TG endpoints, exact warmup replay and hashes stay outside
timing. This replica is an absolute-performance control, not a substitute for
strict per-step diagnostic checks, independent operators or task quality.
Inherited Q2 operator failures and KL rejection remain.

Host Debug and ASan/UBSan each pass 17/17 on `.157`. Both original-model
providers and MMQ archives are fully rebuilt there from frozen source. The
whole host/HC-component/Q2/UD campaign verifies 90 unique artifacts and 4079
source-file instances; all 19 remote commands exit zero. The HC component
passes its scalar checks but saves only 0.3345%, so it remains component-only.
Model-run maximum temperatures are CPU 88.75 C and GPU 90 C, with no thermal
stop or policy change. No model conversion or file modification occurs.

The [20:00:42.449978 UTC release](../config/q2-hc-original-window-release.json)
verifies all 23 recorded PIDs/groups absent, KFD empty and all four original
leases free. No Q2 workload, waiter or automatic restart remains. The current
campaign's [validation summary](../config/q2-hc-original-campaign-validation.json)
links source, artifact, replay and closure evidence. Parity remains unmet.

- [Historical source manifest](../config/q2-original-baseline-source.json)
- [Static command/source evidence](../config/q2-original-baseline-static.json)
- [Runtime plan and exact commands](../config/q2-original-baseline-plan.json)
- [Frozen-source generator](../tools/prepare-q2-original-baseline.py)
- [Fresh-versus-historical analyzer](../tools/analyze-q2-original-baseline.py)

To reproduce after a fresh `.157` handover and admission, choose unused labels:

```sh
python3 tools/q2-remote.py cpu q2-original-host-r2
python3 tools/q2-remote.py collect q2-original-host-r2
python3 tools/q2-remote.py q2-original-baseline q2-original-baseline-q2-r2 --source-variant library-norm-bound --rebuild-mmq
python3 tools/q2-remote.py collect q2-original-baseline-q2-r2
python3 tools/q2-remote.py ud-original-baseline q2-original-baseline-ud-r2 --rebuild-mmq
python3 tools/q2-remote.py collect q2-original-baseline-ud-r2
python3 tools/analyze-q2-original-baseline.py --q2 evidence/q2-original-baseline-q2-r2 --ud evidence/q2-original-baseline-ud-r2 --host evidence/q2-original-host-r2 --output config/q2-original-baseline-results.json
python3 tools/plot-q2-original-baseline.py
```

Archive the previous report/export cohort before replacing those outputs.

## Earlier strict diagnostic results — separate timing scope

The following retained results precede the original-C17 comparison above.
They preserve full per-step finite checks and their own timing boundaries;
their lower UD throughput is not a replacement baseline.

The target remains the historical UD rate of **26.049385991 token/s** on `.157`.
The preceding diagnostic control at 24.318 token/s does not lower that target.
This experiment removes benchmark overhead and aligns a second measurement
with the historical physical input and completed-token accounting. It does
not optimize GPU decode kernels or qualify the inherited numerical changes.

## Observed results — 2026-10-03

Medians exclude one warmup per scope; all measured samples follow below.

| Scope | Model | PP token/s | PP seconds | TG completed calls/s | TG seconds |
|---|---|---:|---:|---:|---:|
| pp2048 | Q2 | 1438.974691 | 1.423235595 | 25.08944287 | 5.061890002 |
| pp2048 | UD | 1613.123062 | 1.269586957 | 25.47501740 | 4.985276281 |
| historical2042 | Q2 | 1372.864940 | 1.487400501 | 25.08011422 | 5.103645018 |
| historical2042 | UD | 1662.671982 | 1.228143628 | 25.46337169 | 5.026828401 |

The correction raises Q2's current-prompt measured decode rate **4.1204%** and
UD's **4.7572%** relative to their previous diagnostic cohorts. This is removed
benchmark cost, not a faster GPU kernel. Q2 prefill is unchanged within 0.021%.
The fresh historical-prompt decode gap is **−1.5051%**, or **0.600130 ms per
completed token**. Q2 remains below the historical 26.049385991 target, too;
neither difference establishes production parity.

Fresh UD current 2K prefill varies 1611.173–1672.432 token/s (median 1613.123),
compared with the preceding 1666.902 median. The raw Q2 deficit of 10.796% in
this cohort must not be presented as a new prefill gain: Q2 kernels/timing
are unchanged at this shape, and the UD control varies. On the historical
prompt Q2 is 17.430% below fresh UD prefill. The 2042 shape takes the native HC
consumer while 2048 takes the library consumer; the prompt/routing histories
also differ, so this campaign does not isolate their respective cost.

Every one of the **21 previously saved model files** matches for each model.
Both scopes pass 9/9 internal whole-file repeats per model (**36/36** total);
all 40 saved full-vocabulary frontiers are finite. Historical UD also exactly
reproduces all four original output-ID sequences, four prefill-frontier hashes
and four final-frontier hashes (**12/12**). Q2 produces the same historical
output IDs; its logits differ from UD, as expected for a different quantization.
Token agreement is not an independent task-quality qualification. Existing
operator failures and Q2 qualified-reference KL 0.002996 > 0.002 remain rejected.

Static investigation confirms the original production greedy sampler scans
once, testing finiteness when selecting a new maximum; it skips isolated
nonfinite logits. The corrected diagnostic still performs a strict full
finite scan followed by max_element. Thus the host work remains different;
no assertion is made that this alone explains the entire remaining baseline
difference. The later pinned original-C17 comparison above resolves the
absolute reference while retaining this strict diagnostic independently.
This diagnostic cohort's matched gap is about 0.60 ms/token; the later
original-C17 comparison measures 0.82264 ms/token. HC down was the next
component examined, with its marginal result recorded separately.

[Full verified JSON](../config/q2-decode-baseline-results.json),
[static boundary analysis](../config/q2-decode-baseline-boundaries.json),
[all measured samples as CSV](figures/q2-decode-baseline.csv),
[SVG](figures/q2-decode-baseline.svg) and [PNG](figures/q2-decode-baseline.png).

![Corrected Q2 and UD benchmark](figures/q2-decode-baseline.svg)

### Every model sample

Rep 0 is excluded warmup. TG denominators are 127 for pp2048 and 128 for
historical2042; all samples emitted 128 tokens without EOS.

| Scope | Model | Rep | PP token/s | PP seconds | TG calls/s | TG seconds |
|---|---|---:|---:|---:|---:|---:|
| pp2048 | Q2 | 0 | 1424.409463 | 1.437788819 | 24.47092413 | 5.189832609 |
| pp2048 | Q2 | 1 | 1439.726450 | 1.422492446 | 25.09394392 | 5.060982060 |
| pp2048 | Q2 | 2 | 1438.205855 | 1.423996428 | 25.08817640 | 5.062145529 |
| pp2048 | Q2 | 3 | 1438.974691 | 1.423235595 | 25.08944287 | 5.061890002 |
| pp2048 | UD | 0 | 1666.237720 | 1.229116335 | 23.76569094 | 5.343837901 |
| pp2048 | UD | 1 | 1613.123062 | 1.269586957 | 25.47294584 | 4.985681703 |
| pp2048 | UD | 2 | 1672.431524 | 1.224564337 | 25.47728344 | 4.984832873 |
| pp2048 | UD | 3 | 1611.172527 | 1.271123958 | 25.47501740 | 4.985276281 |
| historical2042 | Q2 | 0 | 1202.114111 | 1.698674012 | 24.15320436 | 5.299503871 |
| historical2042 | Q2 | 1 | 1372.864940 | 1.487400501 | 25.08011422 | 5.103645018 |
| historical2042 | Q2 | 2 | 1374.105753 | 1.486057384 | 25.08411062 | 5.102831905 |
| historical2042 | Q2 | 3 | 1371.887637 | 1.488460093 | 25.07934655 | 5.103801239 |
| historical2042 | UD | 0 | 1655.236184 | 1.233660803 | 25.45982745 | 5.027528182 |
| historical2042 | UD | 1 | 1662.671982 | 1.228143628 | 25.45903367 | 5.027684933 |
| historical2042 | UD | 2 | 1662.825961 | 1.228029901 | 25.47305680 | 5.024917150 |
| historical2042 | UD | 3 | 1656.688703 | 1.232579178 | 25.46337169 | 5.026828401 |

### Validation and closure

All 17 host tests pass in both Debug and ASan/UBSan on `.157`. The full source and
fixture inventories match the frozen host/model capsules: 3059 source-file
instances and 85 artifacts verify. All 14 remote commands exit0. No thermal stop
occurs; maximum model-run CPU 82.5 C/GPU 74 C. Fan 82 and the existing CPU 98/exposed
GPU bounds are unchanged. The shared upstream formatter exits1 on the same
five untouched upstream-test violations as the parent source; changed
first-party C++ files pass. Python syntax and git whitespace checks pass.

Verified release at **2026-10-03T17:37:05.108908+00:00** finds all 17 recorded PIDs and owned
groups absent, KFD empty and all original four leases free. Remote/shared/local
receipts record release; no Q2 job, waiter or automatic restart remains. Direct
thread delivery is unavailable, so the agreed persistent receipts provide the
handover without claiming message delivery. The performance goal remains open.

## Measurement contract

Both original models use context 9216, max_batch 2048, greedy, no MTP, no prefix
reuse, fresh sessions, one warmup plus three measured repetitions per scope.
A 15-second cooldown precedes every request, outside PP/TG timers. Every model
binary and MMQ archive is rebuilt from source; no archive reuse or weight
conversion occurs. Source/models/fixtures, binary identities and complete
outputs are retained in the frozen capsules and runner receipts.

- `pp2048`: the existing exact 2048-token padding/counting prompt, 128 outputs,
  127 timed Forward calls and a final engine position of 2175. This preserves
  the prior diagnostic denominator, allowing the correction to be compared.
- `historical2042`: the exact 2042 physical IDs from first-party LIE
  `t0-c1-perf-r2`, 128 outputs and 128 completed Forward calls, final position 2170.
  One interval encloses sampling, stop checks and all 128 synchronous forwards.
  The final completed frontier is checked outside that interval.

The historical source measurement SHA256 is
`c60dba6a099ec97f9cbe98048601ab4850a805b49d6dbc7f97b9c57a563afc7a`.
Its immutable IDs and witness hashes are in the static manifest. The original
benchmark called LIE's C ABI and the upstream Session/SamplerState path. This
fixture calls Executor directly and retains full finite checks inside each
sampling call. Matching the prompt and completed work does not make those
host boundaries identical. Saved output/frontier hashes test replay explicitly.
No isolated CPU time is subtracted from a model measurement.

## Implementation and provenance

`tests/q2_argmax.hpp` performs the same full finite-logit scan and first-maximum
selection as before, constructing the exception only when a check fails.
The former Require call constructed 248320 temporary strings per generated
token. The earlier independent CPU probe found 248320 allocations becoming 0;
its 1.801 ms median difference is a host diagnostic, not a model speedup estimate.
All NaN/infinity rejection, tie behavior and error text remain covered by the
host fixture. Runtime samples also report `completed_output` and
`final_position` so emitted tokens cannot be confused with completed steps.
These fields belong to the experimental evidence schema; no public ABI or
persistent model-state format changes.

The isolated Q2 source is derived from the preceding paired-norm/library
candidate. Only one executor predicate changes: paired output is selected at
n = 2048, where the actual library consumer is selected. Other shapes use the
original norm producer, avoiding the known adverse interaction with the
native consumer. All GPU kernel files and 1019 other source files are
unchanged. The current2048 path and scalar decode arithmetic are unchanged.
`tools/prepare-q2-decode-baseline.py` records the complete source inventory,
checks the parent inventory and historical receipt, and refuses overwriting.
Official Gufo pin remains `f783fedb9bea2ec7de941f6da4e02f4a4596b29e`;
all upstream licenses/notices remain. No sibling project source is imported.

## Reproduction

Within a freshly admitted `.157` window:

```sh
python3 tools/q2-remote.py cpu q2-decode-baseline-host-r1
python3 tools/q2-remote.py collect q2-decode-baseline-host-r1
python3 tools/q2-remote.py q2-decode-baseline q2-decode-baseline-q2-r1 --source-variant library-norm-bound --rebuild-mmq
python3 tools/q2-remote.py collect q2-decode-baseline-q2-r1
python3 tools/q2-remote.py ud-decode-baseline q2-decode-baseline-ud-r1 --rebuild-mmq
python3 tools/q2-remote.py collect q2-decode-baseline-ud-r1
python3 tools/analyze-q2-decode-baseline.py
python3 tools/plot-q2-decode-baseline.py
```

Existing labels refuse reuse. Choose a new cohort and update the fixed report
inputs for a new experiment; preserve every historical receipt. All source
and result paths are persistent under the project, not temporary directories.
The original four leases and shared registry retain their existing locations.
