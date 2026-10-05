<!-- SPDX-License-Identifier: MIT -->
# Q8 integer-half pair experiment provenance

The task-owned compact IQ2 provider is the parent. Its source identity is
`config/q2-iq2-halfbyte-perm-formatted-source.json`, measured by
`config/q2-iq2-halfbyte-model-results.json`. It derives from independently
fetched official Gufo `f783fedb9bea2ec7de941f6da4e02f4a4596b29e`.

`tools/prepare-q2-q8-halfpair.py` generates all signed-int8 pair encodings using
exact IEEE binary16 integer representations. The256KiB table contains no model
weights or imported project data. The MIT delta adds that generated table and
uses it in the Q8-weight branch of `DenseF16GEMMKernel`, preserving the existing
scale half bits, packed FMA, ordered K16 products and output layout.

The existing test-only `experiments/q2-q8-grouped-control.inc` supplies a literal
parent numerical control. Static comparison verifies its dense kernel matches
the measured compact parent before a new component is admitted. Its earlier
qualification artifacts remain unchanged; no old cohort is rerun.

New source/table, patch, parent, measured parent and control hashes are recorded
in `config/q2-q8-halfpair-source.json`. Original upstream source notices,
licenses and codebook bytes remain unchanged. No code/artifact from the sibling
CachyOS workspace or the other agent's DS4 project is imported. CPU format and
syntax checks supply no original-weight inference or independent model quality.
