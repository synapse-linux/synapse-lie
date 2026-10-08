<!-- SPDX-License-Identifier: MIT -->
# One-shot Q4 comparison

The owner requests one Q4 comparison to check whether the retained Q2 work
also improves common Q8/shared-expert paths. This campaign is not added to
subsequent Q2 checks.

The model is the original Antirez `Qwen3.8-Flash-Next-Q4.gguf` on .157, not
the separately qualified Unsloth UD model. The same model is run with the
immutable original fixed-Q2 reference binary and the retained IQ2 raw-prefetch
binary. Their original Q2 prefill results are 1443.672867 and 1505.152258
token/s; those values are identities, not predictions for Q4.

The unchanged direct-executor tester uses the fixed counting input, physical
2048 tokens, 128 outputs/127 timed decode calls, capacity9216, chunk2048,
one warmup and three measurements per binary, 15-second pauses outside
timers, C1, greedy, MTP off. Compilation, model loading and evidence copies
are excluded from PP/TG. No binary is rebuilt and no original evidence is
modified. All full inputs, logits and token arrays will be retained.

IQ2 and Q2 expert routes are conditional; their gains cannot be assumed to
transfer to Q4. This comparison measures the cumulative applicable changes,
not the causal contribution of an individual Q8 kernel. Independent model
quality and the complete context curve remain separate qualifications.

[Frozen plan](../config/q4-oneshot-plan.json),
[source identities](../config/q4-oneshot-sources.json),
[host guards](../config/q4-oneshot-host-results.json).
The new runner uses the existing qualified process/thermal supervision.
Nineteen new host guards pass; existing25 Debug/25 ASan/UBSan evidence is
reused because no engine source, C ABI, allocation or timer changes.

Preparation has no GPU admission. The fresh core handover confirms no
.157 job/build/eval/client/lease/waiter/reservation/restart/interleaving.
The helper must freshly admit from release4d34e1e before either model run.
No dependency installation, tuning, conversion, heavyweight model hash,
deployment or remote cleanup is included.

The original-model attempt exits1 before Upload/Forward: `missing GGUF array qwen4exp.rope.dimension_sections`. No performance sample exists. [Failure](../config/q4-oneshot-failure.json) preserves the actual exit and error; [release](../config/q4-oneshot-window-release.json) proves closure at06:09:10 UTC. [Owner deferral](../config/q4-oneshot-deferral.json) supersedes the briefly proposed UD followup: no UD comparison is started, and no automatic repetition remains.
