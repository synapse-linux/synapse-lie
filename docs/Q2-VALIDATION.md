<!-- SPDX-License-Identifier: MIT -->
# Q2 correctness and performance gate

**Required outcome: no PP or TG regression.** Q2 comes first. The user approved starting the minimal port with independent operator
oracles and the existing UD control, replacing the earlier requirement for a
fully runnable independent Q2 model engine before implementation. The missing
exact-file model comparator remains an explicit qualification limitation.
This protocol alone does not authorize a GPU run.
All actual tests run on `.157` after current coordination/leases; no foreign
process, service, model, cache or qualified evidence may be changed.

## Comparators and preparation

The owner-confirmed short-prefill reference is **1443.672867 token/s Q2**
against **1685.777092 token/s UD**, from the retained exact-2048 counting
replay. [Frozen identity and samples](../config/q2-fixed-prefill-reference.json)
bind the input, tester, provider and measurements. Keep that record visible;
fresh controls supplement it and never replace it silently. The mixed-map
provider produced that Q2 value; freezing its result does not promote that
provider across other workloads.

Claims of improvement over this reference require the same physical prompt,
context/chunk, timer boundaries, output/step counts and declared warmup policy.
Compare repeated identical inputs, retain every observation and report control
drift. Different prose prompts, even near 2048 tokens, remain a separate
diagnostic. A median across different prompts is descriptive, not repeated
measurement of the fixed input and not evidence of its improvement. The
latest paired-norm run has not tested that fixed-reference improvement.
Full canonical short/long-context, PP/TG, latency, concurrency, resource and
quality requirements remain in force; this fixed point does not replace them.

**Owner's expansion gate:** do not start another context curve until Q2
matches UD on this fixed comparison under the repeatability and no-regression
rules below. Preserve the 1443.672867 Q2 / 1685.777092 UD record; a lower fresh
control or an unrelated component gain cannot lower the target. Small gains
or a cumulative checkpoint alone do not authorize expansion. While this gap
remains, limit performance work to relevant component comparisons with retained
controls and the same fixed model point. Reuse existing evidence; no unrelated
model workloads or baseline-free exploratory sweeps. Required correctness
checks remain applicable to each actual change. After fixed-point parity,
progress to the full short/long-context curve without changing its acceptance
criteria.

1. Use independent scalar operator formulas for IQ2_XXS/Q2_K and exact F16
   widening, with thresholds frozen before GPU execution. Initial thresholds:
   relative RMS error <= 0.002 and maximum absolute error / maximum reference
   magnitude <= 0.002. The IQ2 codebook is format data from the pinned source;
   reference unpacking and accumulation are independent of the GPU implementation.
2. Keep official Gufo base `f783fedb` fixed. A pin upgrade is a separate variable.
3. Freeze original UD-Q4_K_XL on that base as the shared-code regression control.
   Compare identical UD files, physical prompts and settings before/after the
   patch. Q2 need not numerically equal Q4. Cross-format speed comparison is
   separate from same-file implementation regression.
4. Record exact file stat/header/historical identity, binary/source hashes,
   compiler/runtime and physical token IDs. A full independent Q2 teacher is
   still unavailable; semantic smoke and finite frontiers do not replace it.

## CPU and operator gates

After implementation, run focused parser/binder/metrics CTest and ASan/UBSan
fixtures on `.157` with GPU visibility disabled. Fixtures cover MXFP4 storage
recognition even with MTP off, exact role types, both widths, malformed/missing
padding metadata, overflow, truncation, row/expert bounds and mixed formats.
These fixtures never execute a CPU model forward.

Separately admitted GPU operators must cover IQ2_XXS gate/up, Q2_K down, paired
and fused paths against independently evaluated small tensors, plus existing
UD routes. Exercise one token, batch boundaries and a partial PP chunk; use
expert 0 and 511, multiple selected experts and odd tile tails. Check finite
values **before** any sanitization. Include nonzero encoded weights in the padded
region with zero activations, and reuse scratch with previous nonzero contents.
Verify raw-versus-packed equivalence and peak allocations if packing is added.
Operator compilation/success is not full-model correctness or performance.

## Initial full-model lane

| Parameter | Required value |
|---|---|
| Host / concurrency | `.157`, one admitted device owner, C1 |
| Model | Original antirez Q2, same file on both arms |
| PP targets | 512 / 2048 / 8192 physical tokens; record actual IDs/counts |
| Context / chunk | 9216 / 2048 |
| Generation | Greedy, thinking disabled, at most 128 emitted tokens; honor EOS |
| MTP / vision / prefix / SSD state | Disabled |
| Initial warmup | One retained warmup per arm and profile |
| Measurement | Three complete rounds, profile order ascending / descending / ascending |
| Paired arm order | Reference-candidate / candidate-reference / reference-candidate |

Generate/validate physical prompts once using the model tokenizer/template,
then feed the same IDs to both direct executor arms. A nearby token count is
reported as its actual count. Reset the complete hybrid inference state before
every fresh PP; a reused process or warm PLE pages do not authorize prefix reuse.
Record PLE/page-cache conditions and startup/load time separately. Do not flush
the machine-wide page cache or tune the system.

Collect synchronized executor wall time, not enqueue or kernel-only time:

- PP: newly completed physical prompt tokens divided by completed PP seconds.
  Include activation padding, gather/quantization, synchronization and PLE reads.
- TG: emitted output tokens and decode wall seconds, with counted/timed step and
  EOS semantics identical on both arms. Explicitly record whether any terminal
  EOS call is timed. Retain time series so long-context decode can be inspected.
- End-to-end direct-request latency, load/packing time, host/device peak memory,
  I/O and relevant thermal/power/clock telemetry. No implicit zero for unknowns.

Retain full finite logits at the PP frontier and selected decode frontiers,
generated token IDs, state position and stop cause. Compare numerical error and
greedy behavior under predeclared thresholds. Diagnose the first divergence;
do not loosen the oracle afterward or benchmark differing token trajectories
as if they were matched. Early EOS remains visible and may require a separately
declared matched teacher-forced lane, not fabricated 128-token output.

## No-regression verdict

Evaluate **each prompt length, PP and TG separately**. No average can hide a
slower profile; a TG gain cannot compensate for PP loss. Preserve every sample,
warmup, failure, exit code and arm order; report min/median/max and paired ratios
`candidate / reference`. Rates and verdicts remain absent/blocked until valid.

The target ratio is at least **1.0**, with no preapproved 5% regression allowance.
Reference-only repetitions establish run noise before candidate changes.
Three measured pairs are an initial screen, not an automatic statistical
non-regression certificate. Any observed loss is reported. Systematic loss
outside measured reference variability fails; overlapping/noisy evidence is
inconclusive, not pass. A confidence interval used for a formal zero-margin
non-regression claim must have its lower bound at least 1.0, with method and
sample count declared before collection. Do not claim exact equality from a
failure to detect a difference.

An unexplained loss stops expansion. One bounded, diagnosed experiment can
follow under the inherited restart policy; do not launch open-ended tuning.
Acceptance requires correct output, valid memory/lifecycle behavior, and all
relevant PP/TG/control gates, not just a parser that loads the file.

## After the first gate

Re-run the unchanged UD control through shared code, including existing C2/4/8
dispatch when touched. Qualify Q2 C2/4/8 before advertising native batching;
serial loops do not establish it. Run the HTTP worker separately with identical
inputs/settings, completed `lie_timings`, client TTFT and delivery latency.
Direct ABI timings do not prove the reactive HTTP path has no regression.

Then extend fresh Q2 PP/TG to 32K, 64K, 128K and the admitted native-context
frontier, preserving output capacity and physical counts. Use the same protocol
on each arm. 1M, prefix cache, MTP and Q4 have separate capability/quality gates.
Plot all samples and separate PP/TG panels with context on the x-axis, reference
and candidate shown explicitly; do not plot blocked values as zero throughput.

Current receipts and their exact scope are in [the implementation report](Q2-IMPLEMENTATION.md).

The first C1 screen uses a single fresh process per arm, one warmup plus three
measurements per profile. It is deliberately reported as an initial screen,
not the interleaved paired-arm protocol or a formal zero-margin acceptance
certificate. Each sample creates a new full hybrid session, preserving only
model residency and the bounded upstream PLE row cache. Model output terminates
on EOS. PP includes synchronous full-logit transfer per chunk; TG times decode
forward plus finite-frontier scan and greedy selection, excluding saved-file
I/O and text rendering. The first output token comes from PP; `decode_steps`
counts subsequent executed forward calls, including a terminal EOS-producing
call when present. Rates are named `decode_steps_s`, not silently relabeled
emitted-output throughput. Input IDs and complete PP/final logit frontiers are
retained for matched UD validation.
