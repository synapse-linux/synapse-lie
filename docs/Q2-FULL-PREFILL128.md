<!-- SPDX-License-Identifier: MIT -->
# Complete prefill through128K on the latest retained Q2

The owner explicitly requests the entire prefill on the latest optimized
version, without invented token variations. Use the retained IQ2-fixed-bounds
provider1028 files, server9993fdce and native C synapse-lie-bench87d856cf.
The fixed benchmark reference remains unchanged; no numerical source, GPU
binary, model, scheduler, ABI or cache-policy change is introduced here.

The [input manifest](../config/q2-full-prefill128-inputs.json) binds exact saved
request bodies from the historical native-row Q2-before log. Eleven requests
replay the three original calibration/warmup inputs and eight complete-prefix
requests, retaining both8K attempts. No new prompt generation, padding,
truncation, token substitution or calibration is performed. Prefix requests
contain4088,8138,8177,12242,16317,32711,65440,130925 physical tokens.
Every prefix must report zero cached tokens and ceil(tokens/2048) prefill calls.
The128K input is63 full2048-token chunks plus1901 final tokens,64 calls total.

The existing native client's `--suite http --requests` facility replays these
bodies once. It uses SSE plus include_usage, while old prefix requests used
nonstream JSON; model messages, generation settings and expected physical
counts are unchanged. Compare the existing completed-executor prefill duration
only; keep HTTP wall and output time separate. Prefix output budget stays at
its original8, so it is not a128-token decode benchmark. Server capacity133760,
chunk2048, C1,16GiB prefix budget and original capture policy are unchanged;
measurements with any prefix reuse fail validation.

Saved UD and both historical Q2 controls provide references for those exact
messages and token counts. Historical variation, request ordering and transport
differences prevent a claim of isolated causality or statistical significance.
The earlier continuation-only curve was stopped and does not become a valid
whole-prefill result. No control rebuild/rerun, Q4, conversion, tuning, dependency
installation or remote cleanup is scheduled. Collect and release before analysis.

The initial whole-prefill replay completes through32K, then stops at CPU98.125C
against the configured inclusive98C limit during64K. Primary command exits are
0,0,0,-15; supervisor1. All nine artifacts collect before release17:15:45UTC /
46c4bae9. Completed short prefixes remain observations;64K and128K are incomplete.

Recovery selects only the exact saved64K and128K prefix requests. Each runs in
its own model session after the three original preparation inputs, with CPU<=60C
before launch. Cooling and model initialization stay outside prefill timers;
there are no pauses between2048-token chunks. The98C limit is unchanged. Already
completed short prefixes and archived controls are not rerun. This changes
request scheduling/initial thermal state, not tokens, numerical kernels, model,
server context, prefill chunk size or the completed-executor timer.
