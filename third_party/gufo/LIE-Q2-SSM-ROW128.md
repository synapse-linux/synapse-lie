<!-- SPDX-License-Identifier: MIT -->
# SSM row128 candidate provenance

The isolated provider is prepared from LIE's saved compact IQ2 provider,
independently derived from official Gufo pin
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`. The1025-file inventory and measured
parent bindings are in `config/q2-ssm-row128-source.json`. Only
`src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp` changes: the fused
SSM specialization uses128 output rows per block and explicitly sizes its
unchanged32-token epilogue scratch. There is no new weight representation,
table, conversion, allocation or arithmetic formula.

The MIT first-party delta is in `experiments/q2-ssm-row128.patch`; original
Gufo notices/licenses remain unchanged. The literal retained parent kernel
in `experiments/q2-q8-grouped-control.inc` is reused inside the new test binary
as a numerical control, not a rebuilt qualified model/cohort. New fixture,
generator, scoped launch changes, analyzers and documentation carry MIT markers.

No project code/artifact is imported from the sibling CachyOS workspace. DS4
source, build, service, cache, profile, model and qualified evidence are not
modified. Persistent source directories and frozen fixtures permit independent
reproduction; CPU/static evidence is separate from GPU/model qualification.
