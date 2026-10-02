<!-- SPDX-License-Identifier: MIT -->
# Q2 correctness and performance gate

**Required outcome: no PP or TG regression.** Q2 comes first. Status is
`blocked_reference`; rates are null. This protocol does not authorize a GPU run.
All actual tests run on `.157` after current coordination/leases; no foreign
process, service, model, cache or qualified evidence may be changed.

## Comparators and preparation

1. Independently establish an immutable reference that can execute this **exact
   Q2 file** on `.157`. Record repository/commit, patch identity if any, compiler,
   build flags, HIP/driver/device, model stat/header/historical identity and
   physical prompt IDs. No audited candidate currently satisfies this gate.
   A candidate under development cannot certify itself as that reference.
2. Use official Gufo as the implementation foundation. Keep the selected Gufo
   base fixed during the comparison; a pin upgrade is a separate variable.
3. Freeze original UD-Q4_K_XL on the same Gufo base as the shared-code regression
   control. Compare this exact UD file/build before and after changes. Q2 need
   not numerically equal Q4, and a Q2-vs-UD speed table is not a same-file
   implementation-regression verdict. Publish that cross-format comparison
   separately to answer practical model-choice questions.
4. Record numerical thresholds before changing the candidate, using independent
   reference repeatability and operation error analysis. Thresholds are presently
   unset, not silently infinite. Preserve the frozen reference and all raw data.

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

Current numerical, operator, full-model, HTTP, concurrency and long-context
results for this new workstream: **not run**.
