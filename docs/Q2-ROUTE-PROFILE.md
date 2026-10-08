<!-- SPDX-License-Identifier: MIT -->
# Canonical expert routing before mixed-tile experiments

The completed PLE comparison establishes no stable additional model gain, while
Q2 prefill remains below UD at every canonical depth. The next isolated diagnostic
records the actual expert-count distributions that select IQ2 gate/up geometry.
The acceptance target remains both PP and TG across the complete 0–128K curve.

The pinned DeepSeek port partitions expert work into a large-tile span and a
small-tail span. Qwen already compacts active experts and chooses one 64/128-row
gate/up width for the entire layer. Mixed widths might reduce weight decoding
or resource reservation, but two launches also cost time. The existing WMMA loop
already skips wholly empty 16-row fragments through `live_tok_tiles`; reserved
padding is therefore **not** a count of unnecessary executed matrix operations.
The paired epilogue still iterates over every compile-time fragment, including
shared stores and barriers for empty fragments. That is a separate possible
optimization; neither mechanism has a measured model benefit yet.

`tools/prepare-q2-route-profile.py` starts from the measured ordered-IQ2 provider.
Only host `executor.cpp` changes, and one diagnostic header is added. All 1019
other parent files, including device kernels and the original PLE reader, are
exact. Sources stay in `.deps/gufo-q2-curve-route-profile`. The observations use
the counts already downloaded by `RouteHints` after its existing event wait;
they add no GPU transfer, synchronization primitive or routing decision.

Every completed Forward records its ID, monotonic interval, prefill/decode mode,
token frontier and expected/observed layer counts. Each prefill layer records
the complete per-expert counts and actual gate/down tile width/count. The
analyzer checks assignment conservation, individual count bounds, original
selector decisions, contiguous layer/Forward identities and alignment with the
complete accepted HTTP request. The raw log retains preparation-prefix shapes
as well as measured new-turn shapes. A distinct build/client/runner identity
marks the entire run diagnostic; headline curve analysis rejects it.

The output compares the existing map's reserved fragments with hypothetical
128/64 mixed maps, retaining live fragments, tile counts, launch spans and count
bands. It does not convert geometry into a speedup estimate. All 20 complete
Q2 request/output histories must replay against the retained ordered control.
Earlier model numerical and task-quality failures remain independent gates.

The new host fixture exercises actual logger output, a skewed distribution and
a small-bucket control. Parser tests reject failed Forward completion, missing
layers, wrong count conservation, selector mismatch, reordered IDs, invalid
timing and incomplete HTTP attribution. The planned `.157` cohort runs the
complete 20-test Debug and ASan/UBSan suites before one full canonical diagnostic
curve. Static syntax or fixture success is not model performance evidence.

Fresh admission at 2026-10-04T04:10:27.186037 UTC verifies the previous canonical
release is still latest, 39 processes and 26 groups are retired, KFD is empty,
four original lease identities are free, and five model stat identities match.
The host cohort then passes **20/20 Debug and 20/20 ASan/UBSan**, all six commands
exit zero and seven artifacts verify. The model profile subsequently completes with the
same verified logger/harness. Core has requested the next window; no subsequent
Q2 component run is included in this admission.

[Host results](../config/q2-route-profile-host-results.json),
[admission receipt](../config/q2-route-profile-window-admission.json).

[Source manifest](../config/q2-route-profile-source.json),
[bounded plan](../config/q2-route-profile-plan.json).

## Completed canonical observations — 2026-10-04

All eight depths complete. The strict analyzer accepts **1385 Forward spans**
and **7248 layer-count observations**; all 20 complete requests, outputs, finish
reasons and physical work counts replay exactly against the unchanged ordered
control. This remains an instrumented diagnostic, with no new throughput claim.

The accepted continuation requests contain 432 observed prefill layers. Of these,
384 belong to the large calls where gate/up selects 64 or 128 rows; the other 48
belong to the 9-token second call at 64K. The table below evaluates mixed maps only
on those 384 eligible layers. The complete report retains the small tail too.

| Prefix target | Layers using 64 / 128 | Live 16-row fragments | Reserved 16-row fragments | Empty epilogue fragments % | Hypothetical mixed reservation reduction % | Hypothetical tile-count reduction % |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 2 / 46 | 69122 | 140648 | 50.855 | 29.441 | 1.417 |
| 4096 | 3 / 45 | 68787 | 135932 | 49.396 | 28.279 | 2.281 |
| 8192 | 3 / 45 | 68892 | 135440 | 49.135 | 28.045 | 2.265 |
| 12288 | 3 / 45 | 68709 | 133900 | 48.686 | 27.821 | 2.348 |
| 16384 | 3 / 45 | 68988 | 137428 | 49.801 | 28.562 | 2.202 |
| 32768 | 3 / 45 | 68498 | 136604 | 49.857 | 28.532 | 2.259 |
| 65536 | 5 / 43 | 69168 | 135432 | 48.928 | 27.302 | 3.673 |
| 131072 | 6 / 42 | 69055 | 134380 | 48.612 | 26.766 | 4.383 |

The current epilogue visits 48.612–50.855% wholly empty fragments on these calls.
A direct uniform guard can skip their shared stores and two barriers while
retaining the existing map and kernel geometry. The separately prepared
[live-epilogue candidate](Q2-IQ2-LIVE-EPILOGUE.md) addresses exactly that work.
This percentage describes epilogue fragment visits, not total inference time.
The matrix loop already skips the corresponding WMMA operations.

A hypothetical 128/64 map reduces reserved fragment capacity by 26.766–29.441%,
but total tile descriptors by only 1.417–4.383%, and adds a second launch for
layers containing both widths. It may improve resource use on small buckets;
geometry alone cannot establish net elapsed-time benefit. Selected real layers
are retained in the next component plan: active weight extents are 274.56–321.87 MB,
well above 32 MiB MALL, with source counts and their diagnostic-log SHA preserved.
The component will use synthetic weights/activations with those count vectors;
these are not captured model activation values.

The same inspection finds unconditional zero activation stores for empty token
fragments in `commit_stage`, repeated across K stages. Their slots currently
remain valid whenever `chunk < kActChunks`, even when the entire fragment is
outside the expert bucket. This is an additional isolated candidate to assess:
only whole 16-row fragments that the WMMA loop never reads may be omitted.
It is not included in the prepared epilogue patch or its static evidence.

[Complete routing report](../config/q2-route-profile-results.json),
[eligible-layer geometry](../config/q2-route-geometry.json),
[geometry CSV](figures/q2-route-profile/geometry.csv),
[representative real count vectors](../config/q2-iq2-live-epilogue-plan.json).

Verified release at **2026-10-04T04:21:50.647379+00:00** confirms 15 owned process
identities and 11 groups retired, empty KFD, four unchanged original leases free
and five model stat identities unchanged. All 11 command exits are zero and 37
artifacts verify. Remote/main receipts and the shared registry record release;
no Q2 job, waiter or restart remains. Core owns the next admission opportunity.
Outgoing MCP transport fails; the persistent handover records remain available.
[Release receipt](../config/q2-route-profile-window-release.json).
