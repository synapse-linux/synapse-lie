<!-- SPDX-License-Identifier: MIT -->
# Omit unread IQ2 activation-stage stores

The isolated candidate masks activation LDS slots once before the K loop.
It omits repeated zero stores for entire 16-row fragments that the existing
matrix loop never reads. Partial live fragments retain their zero padding.
Weight conversion, accumulation, barriers, epilogue, routing, tile geometry,
down projection and the original PLE reader remain unchanged.

This differs from the completed [empty-epilogue experiment](Q2-IQ2-LIVE-EPILOGUE.md),
which omitted stores and barriers after the matrix loop. The candidate was
prepared earlier but has no prior runtime transport in retained evidence.
It also excludes the scale-reuse and scaled-row-input patches whose model
comparisons did not establish a uniform gain.

[Source and provenance](../config/q2-iq2-live-stage-source.json),
[patch](../experiments/q2-iq2-live-stage.patch),
[static device accounting](../config/q2-iq2-live-stage-static.json).
Recorded canonical routing has 48.61–50.85% wholly unread fragments; skipping
their zero stores removes a calculated 49.74–54.57 GiB of logical LDS traffic
across a large prefill call. This is not DRAM traffic or a measured time saving.
[Accounting and tail exclusions](../config/q2-iq2-live-stage-traffic.json).

The [three-arm plan](../config/q2-live-stage-plan.json) measures unchanged
reference, stage masking and unchanged reference again. It reuses the complete
narrowing/compaction/IQ2 gate-up/SwiGLU fixture with four recorded short/128K
routing histograms and a full-tile control. Operands are synthetic, rotating
active weights exceed 32 MiB, and timing units are microseconds per cycle.
There are two warmups, five samples of eight calls, 51 independent FP64 checks
and 102 retained output arrays per arm. Numerical limits and failure exits
remain unchanged. This is not attention at 128K or a model token-rate test.

All sixteen measured harness/fixture files are byte-identical to the retained
`.157` `q2-native-row-host-r1` source capsule, whose Debug and ASan/UBSan suites
passed 22/22. The existing qualification is reused, avoiding another unchanged
CPU run. [Reuse receipt](../config/q2-live-stage-host-reuse.json).

Advance only if all independent checks and output bytes pass, and the four
recorded-routing medians improve against both controls by more than the larger
of 1% or twice the observed reference drift. The full-tile overhead must stay
within that same allowance. This selects further profiling, not automatic
model admission or promotion. Full canonical Q2/UD parity and independent
model quality remain required; neither is established by a component gain.

GPU admission and actual component results remain pending. No model run or
additional source composition belongs to this component window.
