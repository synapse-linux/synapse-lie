<!-- SPDX-License-Identifier: MIT -->
# Compressed Q2 cache provenance

The numerical provider retains independently fetched official Gufo
f783fedb9bea2ec7de941f6da4e02f4a4596b29e and the measured ssm-fixed-bounds
composition. Original licenses and attribution remain. The new C17 slot/LRU
policy and HIP adapter integration are first-party MIT code.

The reference mechanism is independently fetched official antirez/ds4
0aaea5a238fb41a35106a551e73c8409dfb751ac, specifically protected selected
experts, compressed slot storage, LRU eviction and completion before reuse in
`cuda_stream_selected_cache_begin_load` and the ROCm streaming runtime.
No source or artifact from the other agent's DS4 workspace is imported. No
Antirez Qwen executor is substituted for Gufo. Reference file identities and
the original MIT license hash are recorded in
[the reference manifest](../../config/q2-compressed-cache-reference.json).

Numerical template bodies and wrappers are adapted from the retained Gufo
provider under its existing MIT notices. Only weight address resolution changes
in the added specializations. Original source and unsuccessful/earlier
experiments remain independently reconstructible from full inventories/patches.

[Mechanism and qualification](../../docs/Q2-COMPRESSED-CACHE.md).
