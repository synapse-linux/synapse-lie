<!-- SPDX-License-Identifier: MIT -->
# Stage the existing IQ2 codebook for scalar decode

The retained scalar IQ2 gate/up dot reads the256-entry,2048-byte magnitude
codebook through global constant storage. Official Gufo's DeepSeek scalar
gate/up stages that table in LDS. This is a separate mechanism from the
already measured IQ2 prefill table experiments: the new draft targets the
Qwen single-token gated vector path, preserving its existing Q8_1 activation
format rather than importing DeepSeek's Q8_K arithmetic.

The generator extracts the exact retained MMVQ dot and two-row gated body.
The candidate loads the unchanged table cooperatively with64 threads, then
adds one uniform barrier before any early return. Gate and up remain in
separate32-thread waves. Weight bytes, parity/sign expansion, integer dots,
the rounded scale-product boundary, wave sum and SwiGLU expression remain.
Only the table-load address changes inside the dot. Model dispatch and
prefill are untouched; the current four-row Q2 down trial is independent.

Local gfx1151 object and assembly compilation use the saved native MMQ
compiler flags, with no GPU execution or control archive rebuild:

| Static property | Literal control | Codebook in LDS |
|---|---:|---:|
| Next-free VGPR |69|62|
| SGPR |24|24|
| LDS bytes |16|2064|
| Private scratch bytes |0|0|
| Instruction sites |381|418|
| Global-load sites |15|8|
| LDS-load sites |1|9|
| Workgroup-barrier sites |1|2|

These are compilation observations, not dynamic instruction counts, numerical
qualification or performance evidence. Initial staging and LDS bank conflicts
may outweigh the cheaper repeated reads. No speedup or model integration is
claimed. The next gate must measure the complete native quantizer plus gated
projection, rotate original-format expert weights beyond32MiB, compare every
output to the existing production archive and retain independent encoded-weight
checks and actual exits. Cover ragged rows, inactive IDs and tiny/zero inputs;
do not overwrite per-repetition failure evidence. A positive component would
still require a new original-input model measurement under verified power mode.

Provenance: independently fetched official Gufo pin
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, retained isolated-HC source
manifesteb12a478. The algorithm clue is in the pinned
`deepseek_v4_flash/kernels/rocm/detail/ds4_rocm_iq2_gate.hip.hpp`; no sibling
CachyOS/DS4 workspace source or artifact is imported. Existing Gufo/ggml
copyrights and MIT notices remain in `third_party/gufo/`.

[Generator](../tools/prepare-q2-iq2-decode-lds.py),
[derived kernel](../experiments/q2-iq2-decode-lds.inc),
[private launch entry](../experiments/q2-iq2-decode-lds.hip),
[source binding](../config/q2-iq2-decode-lds-source.json),
[static compilation](../config/q2-iq2-decode-lds-static.json).
