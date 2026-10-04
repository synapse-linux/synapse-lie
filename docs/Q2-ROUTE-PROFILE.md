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

[Source manifest](../config/q2-route-profile-source.json),
[bounded plan](../config/q2-route-profile-plan.json).
