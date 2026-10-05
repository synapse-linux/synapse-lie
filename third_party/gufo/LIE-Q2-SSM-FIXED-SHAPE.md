<!-- SPDX-License-Identifier: MIT -->
# LIE fixed-shape SSM experiments

The sources derive from independently fetched official Gufo revision
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e` through the retained LIE Q2
register-scatter provider. Existing upstream licenses and notices remain.
No sibling workspace code or artifacts were imported.

The MIT first-party generators `tools/prepare-q2-ssm-fixed-shape.py` and
`tools/prepare-q2-ssm-fixed-bounds.py` preserve complete1027-file inventories
and separate patches against that retained provider. Only the existing dense
SSM template is specialized: fixed M/K propagation, followed by a separate
candidate removing row/K bounds already implied by the unchanged launcher.

Source manifests bind the parent, patches, literal control, fixture and oracle.
Assembly comparisons preserve161 other kernel instruction/operand/resource
bodies. The producer-fusion audit is source analysis only and adds no upstream
code. Compilation alone does not establish GPU correctness, throughput,
quality or full-model acceptance.

The subsequent fixed-M/K GPU campaign passes30 complete output pairs,
60 sampled FP64 checks and21 parent model files. Original-model prefill is
1582.845143 versus saved1580.226725, a nominal +0.165699%; both sources are
retained. The subsequent bounds experiment passes the same component checks
and both21-file saved-model comparisons, measuring1585.308983 PP, nominal
+0.155659% versus saved1582. Both sources remain. Producer fusion is unmeasured;
independent model task quality and full context/concurrency parity remain open.
[Bounds results](../../docs/Q2-SSM-FIXED-BOUNDS.md).

See [mechanisms and evidence](../../docs/Q2-SSM-FIXED-SHAPE.md).
