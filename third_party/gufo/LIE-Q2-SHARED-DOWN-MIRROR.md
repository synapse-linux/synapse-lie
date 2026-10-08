<!-- SPDX-License-Identifier: MIT -->
# LIE shared-down mirror and fixed-shape experiment

The isolated HIP templates derive from independently fetched official Gufo at
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, through LIE's retained
register-scatter provider. Gufo's MIT license and notices remain. No source or
artifact is imported from the sibling workspace or another DS4 checkout.

`tools/prepare-q2-shared-down-mirror.py` retains the original production kernel
and adds a component-only copy with raw-half weight loading and the original
Q8 single-chain accumulation order. It reuses the exact LIE GPU converter from
`experiments/q2_q8_mirror_kernels.inc`; both source and assembly are checked
against the previously qualified conversion, without rerunning that experiment.

`tools/prepare-q2-shared-down-fixed.py` adds Q8 and F16 specializations with the
guarded M2560/K640 dimensions and complete-row epilogue. Two separate durable
providers, inventories and complete patches preserve the initial experiment.
The new first-party fixture reuses MIT buffer helpers and the independent
integer binary16 product from `tests/q2_q8_mirror.hip`, then adds the new shape,
four-arm replay, sampled FP64 checks and rotating-weight timings.

No model lifetime, C ABI, executor dispatch, runtime default or dependency is
changed. Source inspection and local compilation are not GPU correctness or
performance evidence. See [scope and evidence](../../docs/Q2-SHARED-DOWN-MIRROR.md).
