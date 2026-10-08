# IQ2 quad DPP commit experiment

This private variant composes the retained fixed-bound Q2 provider with exact
integer broadcasts inside each four-lane group. The original group/header
prefetch, scale owner, sign/code tables, compact LDS byte ownership, F16 rounded
products, K16 WMMA order and SwiGLU remain unchanged. Only guarded unpacked
640x2560 paired IQ2 BN64/128 uses the private body; generic fallbacks remain.

Local gfx1151 assembly preserves162 original bodies and replaces the two
fixed-bound bodies. Eight ds_bpermute operations become eight DPP bit extracts;
VGPR104/150 become100/146, LDS17536/25728 and zero spills remain. Static code
is not inference, numerical acceptance or performance evidence.

The fixture compares every source bit, four owners and all256 lanes with an
independent host integer expectation, then113 whole guarded operator output
pairs including token tails and captured routing. Complete operator timings
rotate three weight copies beyond MALL; raw HIP timers and synchronized wall
measurements are preserved separately. Safe finite numerical differences still
permit the single original-model performance trial, as requested by the owner.

The model comparison remains exact2048 input/128 output,127 timed decode calls,
9216 capacity,2048 chunk,C1 greedy,MTP off,one warmup/three measurements,15second
pauses outside timers. Saved mixedQ2 1443.672867 and UD1685.777092 references,
stable1585.308983 parent and retained1587.893545 parent are reused without
rebuilding or rerunning. No Q4 or full curve. Collect all artifacts, retire all
owned processes/groups, release the window and inform Core before analysis.

Primary instruction semantics: [LLVM DPP modifiers](https://llvm.org/docs/AMDGPUModifierSyntax.html)
and [Clang AMDGPU builtin](https://clang.llvm.org/docs/AMDGPUBuiltinReference.html#builtin-amdgcn-update-dpp).
GPU qualification and original-model result follow; the target remains unmet.

The original-model trial completes with1582.042649 PP/25.16711939 TG:
-0.368469% PP versus retained1587.893545. Its113 operator comparisons and
71,680 independently expected integer transports are exact;21/21 full model
files match both saved parents,9 repeat checks exact. All13 primary commands
exit0;39 artifacts collected before release11:57:35UTC/df016d3a,1456 identities/
1166 groups retired, original leases/model stats unchanged. Core informed
before analysis. No remote job/window/reservation remains.

The operator itself saves0.964/2.935/1.249/1.090/1.203% time for uniform160,
uniform512 and captured0/3/22, but that does not imply original-model gain.
All70 HIP timers are rawzero/invalid; synchronized complete-operator wall
measurements are valid and retained. Keep the fixed-bound parent1587.893545;
DPP remains a private exact alternative, not a default or goal acceptance.

| Session | PP tokens/s | PP seconds | TG calls/s | TG seconds |
| --- | ---: | ---: | ---: | ---: |
| Warmup | 1580.951128 | 1.295422713 | 25.14914947 | 5.049872567 |
| 1 | 1582.042649 | 1.294528944 | 25.16672732 | 5.046345453 |
| 2 | 1580.706020 | 1.295623585 | 25.16711939 | 5.046266838 |
| 3 | 1582.138007 | 1.294450921 | 25.17276565 | 5.045134959 |

[All20 model samples](figures/q2-iq2-dpp-commit-model.csv),
[graph](figures/q2-iq2-dpp-commit-model.png),
[all70 component timings](figures/q2-iq2-dpp-commit-component.csv).
