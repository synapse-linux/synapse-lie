<!-- SPDX-License-Identifier: MIT -->
# Original-Q8 SSM wider K stages

## Completed .157 component: no promotion

The complete projection/convolution operation slows from5406.401667 to
7983.260000 microseconds, +47.663094% median latency. All five measured pairs
regress. Keep the retained dispatch; no original-model run is justified.
All72 guarded outputs are byte-exact and144 independent FP64 checks pass,
maximum relative RMS1.06738397277e-5 against the unchanged0.002 limit.
The component exits0. All14 HIP event durations are zero/invalid; the result
uses completed host wall time. No reduced precision or model gain is claimed.

Runtime resources confirm170 versus220 registers,64KiB versus48KiB LDS,
and zero private scratch. HIP reports a theoretical maximum of one block
per multiprocessor for both variants. Fewer registers do not establish more
active blocks; the doubled output-row grid and activation traffic remain
costs, not a measured attribution of this slowdown.

CPU success/failure fixtures and preflight exit0 before admission13:34:38UTC.
The component finishes13:35:12.576400UTC, CPU/GPU peaks53.875/46C. All29
artifacts collect/hash before release13:36:14.127541UTC, SHA
4dc425921043fbf058b69265040f5fd77d213ea4c82a79ec08cea21efc961e11.
Latest registry matches;1973 identities/1579 groups retired, empty KFD,
five original leases free and seven model stats unchanged. Core receives
closure. No Q2 job, client, handle, lease, window, waiter or reservation remains.
No model access, remote build, dependency, service, tuning or cleanup occurs.

[All timings and checks](../config/q2-ssm-bk4-results.json),
[frozen plan](../config/q2-ssm-bk4-plan.json),
[auditor](../tools/analyze-q2-ssm-bk4.py).

The following records preparation; production dispatch was never changed.

This prefill-only component changes BM/BN/BK from256/128/2 to128/128/4,
with WM/WN4/2. K2560 uses20 staging iterations per block instead of40,
but output-row blocks double from64 to128 and activation loads are duplicated.
It preserves each output's K16 accumulation order, Q8-to-F16 rounding,
convolution, history and live raw-output mask. Prompt chunks stay2048.
There is no new quantization or precision boundary.

The local candidate uses170 VGPR,64KiB LDS and zero private scratch. The
fixture's original SSM kernel is byte-identical to retained native server
a4afb757 (220 VGPR/48KiB LDS). This static change is not a speedup claim.
The previous BM256 wave-balance and BM128/BK2 experiments remain rejected;
neither tested this K-stage geometry.

The unchanged complete-operator contract covers1024/1025/1057/2048/2049
rows,72 guarded exact comparisons and144 independent FP64 checks at the
original0.002 limit. Timed2048 calls rotate three Q8 matrices totaling
133693440 bytes. Two warmups and five alternating pairs measure completed
host wall time; retain raw HIP event validity separately. Finite numerical
failures do not suppress performance, and their exit codes and outputs survive.

Object, assembly and link pass locally. Those static checks alone imply no
GPU or model result. The separately admitted .157 result above rejects this
geometry; it uses no model files, remote build or cleanup. Future candidates
must follow the [phase dispatch contract](Q2-PHASE-DISPATCH.md).

[Source and static binding](../config/q2-ssm-bk4-source.json).
