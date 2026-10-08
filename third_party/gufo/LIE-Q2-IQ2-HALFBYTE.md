<!-- SPDX-License-Identifier: MIT -->
# LIE compact IQ2 half-byte experiment

The provider derives from official Gufo independently fetched at
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e` and the retained LIE MoE-deferred
composition. No source or artifact is imported from the sibling CachyOS
workspace or its DS4 build. Gufo and adapted ggml code retain the copyright
and MIT license notices in [NOTICE](NOTICE), [LICENSE](LICENSE) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

The generated 2 KiB table losslessly maps each magnitude byte of the pinned
`iq2xxs_grid` to the high byte of its exact F16 bits. Original table files and
all notices remain unchanged. Signed half bits are reconstructed by the new
first-party helper; scale rounding, half FMA, ordered WMMA and output arithmetic
remain the measured parent's contracts.

The MIT first-party generator, fixture and analyzers carry SPDX markers. The
fixture's numerical control is the literal retained parent kernel from
`experiments/q2-iq2-halfstage-control.inc`; no independently owned DS4 code is
copied. The source manifests bind the exact provider, original table, parent,
patch and CPU format-domain checks. Static/local checks and synthetic operator
replay do not establish original unquantized-model quality or Q2/UD parity.
