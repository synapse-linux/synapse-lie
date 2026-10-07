<!-- SPDX-License-Identifier: MIT -->
# Select optimizations by inference phase and operation

Use an optimization only for its qualified phase, shape, dtype and arithmetic
contract. Prefill, autoregressive decode and speculative verification are
distinct. Reuse the same model, session state, KV and stream; switching kernels
does not require loading another engine or duplicating weights.

A candidate that helps only one phase can remain enabled for that phase while
the other phase uses its retained implementation. Qualification should record
both rates independently; a prefill regression is not compensated by a decode
gain when both targets must be met. The final combined executable still needs
its own measurement because shared allocations, compilation or resource use
can affect an otherwise unchanged phase.

The retained isolated HC provider already applies this rule. Forward enters
PrefillPhase(mode == kPrefill); MatrixRows returns true during the entire
prefill body, even for a one-token final chunk. Scalar HC up/mix additionally
requires exactly one token and the original F16/F32 shapes and types.
Unqualified shapes keep their original path. Multirow verification is not
automatically eligible for a scalar-decode optimization.

The final logits head explicitly enters PrefillPhase(false). It can therefore
use the qualified single-row, no-injection HC operation after a prefill too.
This is a separate operation from the matrix body. Do not infer whole-request
phase from row count alone, and do not disable a qualified head optimization
merely because the request has a long prompt.

The new four-row Q2_K down candidate follows the same policy. Its executor
guard requires `!prefill_phase`, a non-tiled operation, one input token, ten
expert slots, one expert per slot, 2560 output rows, 768 stored / 640 logical
input columns and 512 experts. The entire prefill body keeps its prior branch,
including a final one-token chunk. Unsupported shapes and formats fall back.
Single-token speculative verification with the same operation geometry can
also take this path; this does not qualify multi-token verification or MTP as
a whole. No new weight or intermediate storage quantization is introduced.

The component reduces complete-operation latency by 6.96%, with small observed
rounding differences; full-model performance and task quality are separate
gates. All 922 common compiled GPU functions remain byte-identical to the
retained isolated HC binary. The new function matches the measured component.
[Dispatch patch](../experiments/q2-decode-down-rows-model.patch),
[component and model evaluation](Q2-DECODE-DOWN-ROWS.md).

The first recovered model trial runs at differing post-reboot power conditions
and records992.706649 PP /25.632191 TG. After the owner restores performance,
the unchanged executable reaches1337.972303 /26.101627, versus retained
HC1337.119965 /25.914406. All four replies match and performance120 W/fans
verify before/after. Preserve the small positive decode observation; eight
calls do not establish sustained TG128 or inherited task quality. Phase
dispatch cannot equalize host power conditions, and the large R2→R3 prefill
recovery must not be attributed to the decode-only kernel.

Compiler settings also need isolation: scalar HC resides in a separate HIP
translation unit. Its -g0 setting does not change the common backend's
RelWithDebInfo flags. The common numerical device instructions remain exact.
This addresses the earlier global compilation confound; a dispatch guard
alone could not prevent changes to unrelated compiled kernels.

The subsequent down/SiLU fusion is not selected in the retained provider:
its positive component result did not establish a gain in either measured
model phase. Preserve the experiment; phase dispatch cannot manufacture a
phase-specific gain where the model observation has not shown one.

The Q8/SSM BK4 experiment is a prefill component only. Its subsequent .157
measurement passes exact replay but increases complete-operation latency
47.66%, so it is not integrated. Future prefill candidates must restrict
dispatch to their qualified projection dimensions, weight types, phase and
tested row domain. Keep decode and unsupported tails on their retained paths.

[Source dispatch audit](../config/q2-hc-scalar-phase-dispatch-audit.json),
[isolated HC measurements](Q2-HC-SCALAR-UP-MIX.md),
[down/SiLU model result](Q2-HC-DOWN-SILU.md).

The owner now prioritizes new prefill experiments while retaining any useful
decode-only result independently. The planar Q8 component retains exact
vocabulary/SSM candidates (2.425%/0.344% less consumer time), but its attention
output and shared gated shapes regress. It is not a global kernel replacement
and has not established a model gain. Full-context V tiling is a rejected
prefill-only component; its numerical exactness does not justify dispatch.
[Per-shape Q8 results](Q2-DECODE-Q8-PLANAR.md),
[attention layout results](Q2-ATTENTION-V-TILES.md).

The four-key V candidate has a separate prefill-only integration. Its C17
contract and base-allocation check authorize reuse of inactive expert scratch
only for the measured full-row geometry/depth interval, with all deferred
expert flags clear. Consumers and subsequent producers stay on the original
stream. Decode and the real short tail retain their original paths, with no
extra persistent memory. The positive component is not a model-rate gain;
original-model validation follows separately.
[Guard and lifetime contract](../experiments/q2-attention-v-blocks-contract.h),
[integration evidence](Q2-ATTENTION-V-TILES.md).

The V-blocks integration now completes the original130925/8 model test:
1332.109243 PP / 26.037992 TG, below retained R3 in both observed rates.
Its four exact replies establish no performance benefit. Keep it private and
unpromoted; the retained prefill and decode provider stays selected. Positive
component results remain available for a different justified composition.
