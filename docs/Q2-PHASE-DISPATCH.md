<!-- SPDX-License-Identifier: MIT -->
# Select optimizations by inference phase and operation

Use an optimization only for its qualified phase, shape, dtype and arithmetic
contract. Prefill, autoregressive decode and speculative verification are
distinct. Reuse the same model, session state, KV and stream; switching kernels
does not require loading another engine or duplicating weights.

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
