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
code. All three investigations remain local; no GPU correctness, throughput,
quality or full-model acceptance is inferred from compilation.

See [mechanisms and evidence](../../docs/Q2-SSM-FIXED-SHAPE.md).
