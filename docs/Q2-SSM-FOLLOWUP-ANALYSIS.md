<!-- SPDX-License-Identifier: MIT -->
# SSM follow-up result analysis

`tools/analyze-q2-ssm-followup.py` prepares component and original2048/tg128
model reports for the four sources in the [runtime patch](Q2-SSM-FOLLOWUP-RUNTIME.md).
No new component or model result exists yet. The first row-group campaign,
its88 fixtures/five manifests and window helper remain unchanged; the follow-up
runtime patch remains unapplied.

The analyzer requires a separately frozen one-candidate campaign plan. It
checks the fixed input identity,2048-token chunk,9216 context capacity,
128 generated tokens/127 timed decode calls, one warmup/three measurements,
15-second cooldowns, MTP off and no control reruns. New component/model modes
must match the selected source. Changing to a full curve, a different prompt
length or different timing counts is rejected.

Component analysis reuses the frozen SSM replay/oracle/timing checks. The
fixed-shape and fixed-bounds sources retain the original event names; compact-LDS
and alternating-slot sources use their own common event family. Reports preserve
the original event names and separate source identity. Each requires30 complete
output pairs,60 independent sampled FP64 checks and14 chronological timing rows.
Safe numerical exit1 retains every timing; missing writes, altered guards,
unexpected event families, incomplete timing or runtime exit2 are rejected.

Two resource records are additionally required for compact-LDS/alternating-slot
fixtures. Their register, local/shared memory and HIP block limits remain
theoretical launch metadata. A claim that they measure active occupancy is
rejected; no speedup follows from those records alone. The component timing
summary and whole-model measurement remain distinct.

The model analyzer checks collected artifacts, full source/fixture capsules,
binary/model identity, the host gate and the actual component evidence again.
A component report's `device_work_safe` flag alone is insufficient. It requires
window closure, then reads the saved fixed Q2, fixed UD and retained1580 model
evidence without executing those arms. Reports retain all samples, full-logit
comparisons and matched-history numerical differences. The CLI prints the
candidate and all three saved references, with both prefill and decode rates
and times. Point parity cannot promote independent quality or complete-curve,
concurrency or serving qualification.

Eleven focused test methods pass using synthetic component logs and a read-only
parse of the saved register-scatter model logs. They check all four source
identities, safe numerical rejection, damaged/missing writes, actual exits,
resource metadata, crossed event families, timing chronology, fixed protocol
changes and invalid model timings. Recomputed saved Q2/UD comparisons equal the
existing report exactly. These checks do not execute a GPU or a model and do not
qualify the future integration against actual follow-up device output.

After the first campaign completes, the follow-up launcher must be applied and
a new plan must bind its changed runtime files, source/fixture identities,
analysis tools and fresh window helper/release path. Runtime and result analysis
will then use the new candidate's own collected evidence. No admission, automatic
restart, control rerun or new performance claim is created by this preparation.

[Analyzer](../tools/analyze-q2-ssm-followup.py),
[focused tests](../tests/q2_ssm_followup_analysis_test.py),
[local preparation receipt](../config/q2-ssm-followup-analysis-preparation.json).
