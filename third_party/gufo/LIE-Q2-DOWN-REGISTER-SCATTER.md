<!-- SPDX-License-Identifier: MIT -->
# LIE Q2 register-scatter experiment

The source is independently derived from official Gufo commit
f783fedb9bea2ec7de941f6da4e02f4a4596b29e and the retained LIE scaled-wave-pack
provider. The full1027-file inventories and reconstructible patches are in
config/q2-down-register-scatter-source.json and
config/q2-down-register-scatter-pair-source.json.

Only the half-output routed-Q2 epilogue changes. The first-party branch replaces
the aligned LDS transpose with exchanges of already-rounded half words between
wave lanes. Existing matrix arithmetic, encoded weights, fallback and upstream
attribution remain. The retained first-party half-wave decoder provides an
existing compiler-builtin example; no sibling DS4/CachyOS sources or binaries
are copied. First-party generator, fixture, analyzer and additions use MIT SPDX.

Only local static/mapping/fixture-syntax evidence exists at preparation. No
GPU numerical/performance, model quality, full-curve parity or promotion follows
from source reconstruction or compiled resource metadata.

Subsequent .157 qualification records705 exact full down pairs,93 exact
consumers, and21 exact saved-parent numerical files. The original2048/tg128
model measures1580.226725 PP /25.10411864 TG, while the isolated down/combine
component is0.883903% slower. Both outcomes are retained in
`config/q2-down-register-scatter-final-audit.json`; inherited independent
task quality and full-curve parity remain open. Source inventories above are
unchanged. There is no deployment or production promotion.
