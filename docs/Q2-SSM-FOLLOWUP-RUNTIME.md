<!-- SPDX-License-Identifier: MIT -->
# Runtime wiring for the SSM follow-ups

All four follow-ups now have component/model evidence. Compact LDS completes
at1555.078658 PP, losing1.906904% against retained1585 despite exact outputs.
Host30+30 is reused with102 byte-identical fixtures; seven new commands exit0
and30 new artifacts verify. Its .157 window is released. Keep fixed-bounds
1585.308983/25.16079073; no control or full curve is rerun.
[Compact-LDS results](Q2-SSM-COMPACT-LDS.md).
The pending statements below record earlier campaign states.

Fixed bounds now completes at1585.308983 PP, nominal +0.155659% against
saved fixed-M/K1582.845143. Both21-file parent comparisons are exact. The90
unchanged fixtures again permit explicitly reusing qualified host27+27; only
the new component/model run. Compact LDS remains unmeasured. All three
completed follow-up windows are released.
[Fixed-bounds results](Q2-SSM-FIXED-BOUNDS.md),
[fixed-M/K results](Q2-SSM-FIXED-SHAPE.md).

The patch is applied at checkpoint `c75e03e`, after the original row-group
campaign completed. Six applicable integrated tests,142 existing launcher
tests and11 analyzer tests pass against the applied files. A separate90-fixture,
ten-manifest pingpong plan passes27 Debug and27 ASan/UBSan host checks. Its
component completes with exact outputs but12.434211% longer cycle time; the
model measures1554.624652 PP,1.620152% below saved1580. The window is released.
At that closure the other three prepared variants remained unmeasured;
fixed-M/K is subsequently completed above. [Pingpong evidence](Q2-SSM-PINGPONG.md).

The following section records the original unapplied preparation; its receipts
are preserved unchanged and are superseded for runtime state by the
[applied receipt](../config/q2-ssm-followup-runtime-applied.json).

## Original preparation record

Four existing numerical candidates now have a locally verified, unapplied
launcher patch. The first row-group campaign remains frozen: its88 fixtures,
five manifests and window helper are unchanged. The current production launcher
does not yet accept the new variants. No remote command, build, model execution
or GPU test was started by this preparation.

| Source variant | Component mode | Fixture |
| --- | --- | --- |
| `ssm-fixed-shape` | `ssm-fixed-shape-check` | Original SSM30-pair/60-FP64/14-timing fixture |
| `ssm-fixed-bounds` | `ssm-fixed-bounds-check` | Same original fixture |
| `ssm-compact-lds` | `ssm-compact-lds-check` | Same numerical coverage plus two HIP resource-limit records |
| `ssm-pingpong` | `ssm-pingpong-check` | Same compact-LDS fixture, independently bound source |

Each source also gets its matching `q2-counting-<variant>` original2048/tg128
model mode with mandatory full candidate MMQ build. Crossed providers, unrelated
benchmark modes, detached execution and native curves are refused. Existing
leases, thermal enforcement, supervision, artifact collection and safe
numerical-failure handling remain in the existing runner. No separate runtime
execution path is introduced. Collection allows the same8GiB diagnostic output
as the original SSM fixture.

The launcher validates the source manifest, literal parent control, fixture,
oracle, inherited parent/patch bindings and all1027 provider files. Compact-LDS
and ping-pong retain their common `ssm_compact_lds_*` event names; candidate
identity comes from the separate source manifest and run receipt. Resource-limit
records describe theoretical limits, not measured active GPU occupancy.

Local validation passes seven new test methods, including all four providers,
crossed-mode cases and corrupted fixture/parent/kernel rejection, plus the142
existing launcher tests against the prepared copy. The patch passes
`git apply --check`. Eight complete source capsules, one component and one model
per variant, reach an intercepted first SSH call. No subprocess is executed by
the staging test; each capsule verifies1027 source files and eight additional
fixture/launcher/manifest bindings. These are archive checks, not GPU tests.

The patch is intentionally not applied until the frozen row-group campaign has
completed and released its window. Applying it later still requires a new frozen
campaign plan, result analysis bound to each candidate and fresh coordinated
admission. Existing saved Q2/UD/1580 model results are reused, not rebuilt or
rerun. Safe numerical rejection still retains performance evidence; memory
safety/runtime failures stop dependent device work. Q4 and full-curve sweeps
remain deferred until the fixed-point gap is closed.

Measured Q2 remains1580.226725 prefill tokens/s and25.10411864 decode calls/s;
fixed UD remains1685.777092/24.34174251. Required additional prefill improvement
is6.6794445%. No SSM candidate has a GPU/model result yet, and numerical/task
quality and complete-curve parity remain open.

[Prepared patch](../experiments/q2-ssm-followup-runtime.patch),
[source and fixture bindings](../config/q2-ssm-followup-runtime-source.json),
[eight capsule receipts](../config/q2-ssm-followup-runtime-staging.json),
[final preparation audit](../config/q2-ssm-followup-runtime-preparation.json).
