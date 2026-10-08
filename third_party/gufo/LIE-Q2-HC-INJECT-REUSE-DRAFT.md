<!-- SPDX-License-Identifier: MIT -->

Qualification update 2026-10-06: the private draft completes42 component cases
on `.157`; all guards are safe,140/200 outputs exact and60 injection outputs
differ by at most4.768e−7 absolute. Original retained ISA orders the first two
products y,x, whereas the explicit draft uses x,y. Complete-cycle wall medians
show+0.225%/−0.211%/+0.602% time for raw/raw-Q8/deferred; all HIP timings are
invalid zero. This is component evidence, not production adoption, full-model
harmlessness or borrowed-scratch qualification. All1027 retained parent files
remain unchanged. [Full results](../../docs/Q2-HC-INJECTION-REUSE-RESULTS.md).
# HC injection input-reuse compiler probes

The [v3 draft](../../config/q2-hc-inject-reuse-draft-v3.json) adds a LIE-owned
coefficient staging mechanism:4096 exact F32 bytes in the unused tail of the
existing24576-byte projection LDS, after its last K-loop barrier and before
the first existing gate-publication barrier. No allocation or barrier is added.
[Recipe](../../tools/prepare-q2-hc-inject-reuse-draft-v3.py) reconstructs this
isolated include from v2. The [new static audit](../../config/q2-hc-inject-reuse-draft-static-v3.json)
keeps all162 production bodies exact, checks10240 coefficient address vectors
and reports raw/deferred instructions5234→4761/5610→5148. A preserved exit1
comes from comparing the defining symbol of the renamed private reducer;
the additive corrected auditor excludes only that header line and verifies all
remaining operands/resources. No production source, executor or GPU program
is changed/run by these static probes. [Scope and next qualification](../../docs/Q2-HC-INJECTION-REUSE-DRAFT.md).

The raw and deferred numerical bodies derive from this repository's independently
fetched official Gufo lineage at `f783fedb9bea2ec7de941f6da4e02f4a4596b29e`,
through retained `ssm-fixed-bounds`. Gufo's MIT notices/license are retained.
No sibling CachyOS or foreign DS4 source, artifact, cache or model is imported.

[Initial manifest](../../config/q2-hc-inject-reuse-draft.json) and
[v2 manifest](../../config/q2-hc-inject-reuse-draft-v2.json) pin the complete
parent inventory, original numerical includes, generated probe and recipes.
The initial source is retained uncompiled; v2 excludes two duplicate dispatchers.
[Initial recipe](../../tools/prepare-q2-hc-inject-reuse-draft.py) and
[v2 correction](../../tools/prepare-q2-hc-inject-reuse-draft-v2.py) reconstruct
the includes without modifying the parent provider.

LIE changes reuse each already-loaded normalized float4 for the four ordered
injection dot products and emit a compact F32 dot workspace. The new reducer
retains the original reduction sequence and output layout. Proposed `down_e`
borrowing is not integrated into the executor. Core C17 contracts, resource
policy, scheduling, model state and qualified binaries remain unchanged.

The [static audit](../../config/q2-hc-inject-reuse-draft-static.json) verifies
162 parent production bodies exact and three additional private kernels.
Compilation/symbolic coverage provide no GPU safety, numerical equivalence,
task quality, inference measurement or performance acceptance. Full rotated
producer/consumer timing and complete replay on `.157` are required. All
experiments are retained under the user's instruction, including rejected ones.
