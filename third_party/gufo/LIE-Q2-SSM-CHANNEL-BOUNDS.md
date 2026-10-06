<!-- SPDX-License-Identifier: MIT -->
# Local Q2 SSM channel partition

The provider derives from independently fetched Gufo commit
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e` through the retained local Q2
`ssm-fixed-bounds` composition. Its parent source manifest SHA256 is
`dd1e671a1bb521b51fb0df6989b926052d3145c835a9e86e29ffdcd7bd4d060a`.
All upstream licenses and notices remain. No sibling workspace code, other
agent's DS4 project, model conversion or Antirez Qwen executor is imported.

The MIT local patch replaces two SSM channel predicates by their block-uniform
equivalent and asserts the exact divisibility of the channel boundary. The
generator enumerates the output ownership proof; the static audit compares
against saved parent assembly. This is local preparation only, without GPU
or model performance qualification. No public ABI, state, scheduling or
metrics contract changes.

[Patch](../../experiments/q2-ssm-channel-bounds.patch),
[source identities](../../config/q2-ssm-channel-bounds-source.json),
[scope and pending measurements](../../docs/Q2-SSM-CHANNEL-BOUNDS.md).
