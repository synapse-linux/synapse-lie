<!-- SPDX-License-Identifier: MIT -->
# IQ2 whole640 integrated expert chain

This experiment derives from the independently fetched official Gufo commit
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e` and LIE's retained
`iq2-fixed-bounds` provider. Existing Gufo and numerical dependency notices
remain applicable. No sibling CachyOS or DS4 artifact is imported.

The LIE C17 partition wrapper reuses the qualified `q2_iq2_tail16` algorithm
and converts only its final span back to the original64-row descriptor units.
The fused device include is byte-identical to the measured sixteen-wave LDS
draft. Selective packing derives from the provider's original dyadic row
packing, retaining scale and rounding. The unchanged down consumer receives
the original slot layout. First-party additions retain MIT/SPDX markers.

The source manifest records all1034 provider file hashes, the complete patch,
generator and donor identities. Static qualification proves164 unchanged
parent device bodies and the unchanged measured donor ISA/resources. These
checks do not establish inference speed or independent numerical quality.

See [the source manifest](../../config/q2-iq2-whole640-chain-source.json),
[static evidence](../../config/q2-iq2-whole640-chain-static.json), and
[the integration contract](../../docs/Q2-IQ2-WHOLE640.md).
