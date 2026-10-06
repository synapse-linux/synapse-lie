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
GPU qualification and model performance are pending; no goal acceptance.
