# Private Q2 host-compatibility variant

This is a **transitional Gufo extension**, not a replacement LIE model executor.
`host-edits.json` is the authoritative exact-byte edit recipe for six files at
Gufo `f783fedb9bea2ec7de941f6da4e02f4a4596b29e`. First-party edits/tooling are MIT;
Gufo and its component licenses/notices remain unchanged and are copied with the
pinned source by `tools/q2_port.py`. See `../../third_party/README.md`.

No source is taken from the sibling DS4/CachyOS project. The source for existing
IQ2/Q2 storage facts and future numerical helpers is the independently acquired
Gufo tree; MXFP4 geometry was independently cross-checked against official
antirez upstream. The absent mRoPE section rule uses architectural facts from
the explicitly pinned official Qwen configuration, under its separate retained
Qwen Community License 1.0, not model-forward code.

The generated tree lives only in a fresh `build/<label>/source`; pristine `.deps`
and qualified builds are never patched. Hashes, refusal behavior and source
scope are tested. Recipe and source receipts state `runtime_link_allowed=false`.
The old runtime verifier must refuse this variant, and its device upload also
contains a pre-allocation Q2 refusal. Do not disable those safeguards to imply
that host acceptance implements a GPU route.

`hip-edits.json` now layers six further exact changes plus `q2_plan.h`,
`q2_routed.h` and `q2_routed.hip` over that host variant. The private candidate
implements vector/tiled/grouped IQ2/Q2 dispatch, direct quantized padding and
reserved scratch. It compiles with the MMQ target's flags and passes the initial
64 synthetic GPU cases. **Full-format/model qualification remains open and
production model admission is refused**. Host-recipe changes in this
increment are formatting only. The original Gufo arithmetic helpers are reused;
this is not an autonomous numerical engine.

[Host proof](../../docs/Q2-COMPATIBILITY.md) · [HIP implementation, tests and gates](../../docs/Q2-HIP.md).
