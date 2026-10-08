<!-- SPDX-License-Identifier: MIT -->
# MMQ reuse in the retained Q2 executor

This read-only audit uses official Gufo independently fetched at
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e` and the retained LIE IQ2 raw-prefetch
provider. The [audit receipt](../config/q2-mmq-reuse-audit.json) records the
source identities and hashes. It does not import or change the other agent's
DS4 workspace, build, model, service or qualification evidence.

The retained Qwen `GatedExperts` fallback already passes both IQ2 gate/up
weights into `qfn_mmq_iq2_xxs_moe_raw`. Its `qfn_mmq_moe_impl` builds routing
once and quantizes activations once before launching both matrix operations.
Adding paired routing/quantization here would duplicate existing work.
The raw Q2 down entry also already separates logical input width640 from
stored weight width768; the existing quantizer supplies padded zero lanes.

The original fixed prefill point takes `MoeExperts`' IQ2 WMMA path instead:
hidden2560, expert intermediate640, stored down width768. It narrows token
activations once, executes paired IQ2 gate/up with the SwiGLU epilogue, packs
one scaled half plane and executes Q2 down. MMQ fallback improvements cannot
be credited to this point unless a new measured dispatch actually uses them.

Official DS4 has paired MMQ, token-bound maps, producer-Q8 consumption and
fused SwiGLU/down entries. The examined pair entries require K divisible by256;
the fused-down configuration also requires intermediate M divisible by256.
Qwen's logical intermediate640 is not a direct match. Its padded768 storage
does not authorize reading640-row activations with a768-row stride. Logical
tails, output-slot ordering, router weights and stream/scratch ownership need
explicit adaptation. Producer-Q8 and aligned-SoA variants also differ from the
current F16 WMMA activation arithmetic and original weight storage.

A useful next experiment must replace measured work in the active expert
chain, rather than claim the already present fallback reuse as a new gain.
Complete guarded outputs, ragged routing,640/768 tail coverage, preserved
failures and the original exact2048/tg128 model test remain required. Safe
numerical differences do not suppress performance measurement; independent
task quality remains separate. No new MMQ source port, GPU run, model
conversion or performance improvement is claimed by this audit.
