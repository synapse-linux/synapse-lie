<!-- SPDX-License-Identifier: MIT -->
# Original-Q8 SSM wider K stages

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

Object, assembly and link pass locally. No GPU or model result is implied.
The separate .157 component window requires fresh coordination and admission;
it uses no model files, remote build or cleanup. Any model integration must
follow the [phase dispatch contract](Q2-PHASE-DISPATCH.md).

[Source and static binding](../config/q2-ssm-bk4-source.json).
