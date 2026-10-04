<!-- SPDX-License-Identifier: MIT -->
# Complete prompt retention under cache pressure

The DS4 progressive schedule previously left an uncached prompt tail and allowed
a generated checkpoint to evict the last prefix usable by the same input. At
128K/4 GiB the earlier native-format campaign repeated 102400 prefill tokens.
That [negative result](../archive/CACHE-DS4-GPU.md) remains historical evidence.

The shared C17 core now also captures the completed prompt before decode, subject
to the existing minimum and byte budgets. An exact hit performs no new capture.
Generated, retirement and shutdown captures preserve the longest cached prefix
usable by the original request. If both records cannot fit, optional retention of
the generated record is skipped before evicting the prompt. With sufficient
space both remain available for growing conversations. This is a LIE serving
policy addition; it does not change the DS4 payload, upstream utility formula,
precision, numerical kernels or available compression.

Protection is local to each capture, not a permanent pin. A different request can
replace the entry. If the complete prompt is too large, the longest retained
waypoint remains the fallback. Matching uses physical tokens and the original
request's visibility-key kind; generated raw keys need not have that same kind.
RAM accounting includes metadata, and refusal occurs before the new host-state
allocation. Other jobs retain their normal eligibility and output-credit rules.

The optional SSD worker applies the same rule independently of RAM, using its
identity-bound token-prefix index and context/chunk compatibility. Both logical
and allocated file bytes count; an old replacement remains charged until atomic
publication. Quota refusal counts as `ssd.skipped`, not an I/O error. Capture and
staging of a candidate may already have occurred before the worker rejects its
write, so this is not a claim of zero generated-capture cost with SSD enabled.
No provider call or model-specific geometry enters that worker. RAM remains on
by default, SSD opt-in, with one device owner and one optional I/O thread.

The additive `lie_store_write_prompt` API accepts the original prompt length and
key flags separately from captured metadata. Existing `write`/`write_ex` retain
their unprotected behavior; core clients receive the new policy through the
same `lie_core` contract. No public structure, executor ABI or KVC wire version
changes. `--cache-policy legacy` retains the previous aligned capture schedule.

## Functional qualification

`cache-prompt-retention-native` and `cache-prompt-retention-kvc` use a tiny,
deliberately synthetic provider: complete unaligned prompts, single-record RAM
pressure, oversized-prompt fallback, generated-state reuse with ample space,
replacement by unrelated requests, visibility isolation, independent-process
SSD restart and RAM promotion. Bounded opaque trailers exercise SSD quota pressure
without large tensors. Existing reactive SSD fixtures still verify peer progress
and cancellation while I/O is held. These are NOT-INFERENCE checks, not a second
real model-family binding or GPU performance evidence.

Full ASan/UBSan/LeakSanitizer: **39/39**. Headless utility/compression/interchange
OFF: **10/10**, with the progressive policy still enabled to exercise LRU.
Both server and benchmark link against the unchanged HIP provider in a new
private build. [Source/binary-bound CPU receipt](../benchmarks/2026-10-02/prompt-retention/cpu-receipt.json)
preserves all commands, four failed focused attempts and their corrections.
Sampled local CPU peak across preparation was81.125 C; no GPU/model work ran.

## Declared GPU comparison

Next campaign: `.157`, original Qwen3.8 Flash Next UD-Q4_K_XL, the unchanged
complete-history KVC provider, chunk2048, TG128, one warmup and three measured
cohorts. Pair legacy and repaired DS4 policy at 8192/C4/context16384 and
131072/C1/context262144, both with4 GiB RAM. Require every warm prompt to be
fully reused and all output IDs to match its paired control. Report first-cohort
PP, warm TG/TTFT/capture/restore, complete-cohort throughput and retained bytes.
Any matched median slowdown above5% remains explicit; fixed order and three
cohorts do not establish statistical significance or a reactive speedup.

Separately run an8192/C1 SSD producer and restarted reader with RAM disabled,
512 MiB quota and staging. Both must retain the complete input despite final
captures, with exact output IDs and zero warm executed-prefill tokens. Record
load/identity-hash startup, SSD read/write and device restore separately. Compare
quota/evictions/skips and drain the writer before inspecting durable state.

Source/binary/CPU receipts are frozen before launch. Q2/Point handover and fresh
four-lease admission remain mandatory for each arm. The established CPU/GPU
thermal observation and independent1Hz observer remain unchanged. Verify all
owned processes and observer retired, model stats unchanged, KFD empty and four
unchanged/free leases before releasing the window. No GPU result is yet claimed
for this repair; previous reports retain their own source identities.
