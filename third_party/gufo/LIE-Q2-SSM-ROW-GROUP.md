<!-- SPDX-License-Identifier: MIT -->
# LIE fused SSM row-group experiment

Official Gufo was independently fetched at
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`. This first-party experiment derives
from the retained LIE scaled-wave-pack provider and preserves its1027-file
inventory except for two substitutions in `kernels.hip.cpp`.

The existing generic four-row tile mapping is selected only for the fused SSM
projection, retaining its shape guards, arithmetic, convolution boundaries and
storage. The local patch and manifest preserve attribution and MIT licensing.
No other agent's DS4 source/build/evidence or sibling CachyOS artifact is used.

The test-only control is the literal saved dense template and SSM wrapper with
renamed symbols. The fixture derives from the retained LIE SSM row128 fixture;
an independent sampled FP64 synthetic operator is added. Source identities,
assembly comparison, unchanged existing campaign hashes and actual local
command exits are bound by `config/q2-ssm-row-group-preparation.json`.

Local preparation establishes no GPU numerical, model-quality or performance
acceptance. Runtime source integration remains separate from this experiment.
