<!-- SPDX-License-Identifier: MIT -->
# Retained Q2 under the original 0–128K native protocol

**Stopped after owner scope correction.** The request was to display available
results; launching another continuation curve was an assistant error. The owner
also clarified that a tail of approximately2048 tokens does not measure the
complete long prefill dominated by full2048-token chunks. Seven continuation
points through64K and the aborted128K prefix are preserved without a full-prefill
or parity claim. Client and supervisor exit1; server exit0; nine artifacts
collected before release16:59:59UTC/b9c8f3f1. No replay of this plan is scheduled.
[Disposition](../config/q2-curve128-disposition.json).

The subsequent explicit owner instruction requests the latest optimized Q2 on
[complete saved prefill inputs](Q2-FULL-PREFILL128.md). This is a new scoped run,
with unchanged messages and naturally final residual chunks, not a restart of
the excluded continuation curve.

The owner requests this complete curve while fixed-point parity remains the
optimization priority. Compare one new retained Q2 run against both saved Q2
controls and saved UD from the native-row campaign. UD128K prefill is1280.583
token/s; the invalid266240-capacity campaign does not replace it.

The frozen native C client remains b598e4c / binary87d856cf. Depths are
0,4096,8192,12288,16384,32768,65536,131072; capacity133760; prose seed1;
approximately2048 new tokens;128 completed decode calls; one warmup and one
accepted sample per depth. There is no prompt padding or token substitution.
Prefill measures the new continuation after a prepared prefix. Prefix setup,
cache capture/restore, TTFT and end-to-end duration are separate recorded phases.

The unchanged server r2 binary9993fdce and retained1028-file IQ2-fixed-bounds
provider are reused. The old r2 run rejected capacity266240 before inference;
that failure is preserved and is not a successful model qualification. At the
original133760 capacity, the C17 upper-limit/help edits are inactive. This binary
has no later Gufo engine headroom patch. Numerical qualification remains tied
to the retained fixed-point model, not to the failed r2 context request.

Server settings match the historical curve: chunk2048, C1 greedy AR, RAM prefix
checkpoint budget16GiB, finish capture enabled, SSD/MTP/vision/thinking off.
No service deployment, model conversion, dependency installation, tuning or
remote cleanup. Both server and benchmark binary identities are checked before
and after the run. Historical controls are reused without recompiling or rerunning.

New versus archived controls is not a contemporaneous paired experiment. One
sample per depth does not establish statistical significance. Request, completion
and physical-count histories must be checked before interpreting differences.
Whole-curve parity and independent quality remain open until their gates pass.

The final .157 host gate passes38 Debug and38 ASan/UBSan checks, six zero
command exits and seven collected artifacts. The [frozen plan](../config/q2-curve128-plan.json)
binds230 fixture hashes and requires fresh GPU admission. This historical plan is now retired; see the disposition above.
