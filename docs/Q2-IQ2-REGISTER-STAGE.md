<!-- SPDX-License-Identifier: MIT -->
# IQ2 weights retained within their producer wave

This prepared candidate starts from retained1585.308983 PP /25.16079073 TG.
The fixed UD point remains1685.777092 PP /24.34174251 TG. No new model rate
is established here: device execution, numerical checks and the original
fixed2048/tg128 benchmark remain pending. The completed tail16 trial is
negative and is not part of this source.

The original IQ2 stage publishes decoded code bytes and rounded scales to
LDS, then reads them from the same wave32. Source ownership enumeration
confirms that none of these weight reads crosses waves. Activations do cross
waves, so their shared stage and both K-loop block barriers remain necessary.

The new private kernel gives the two half-waves the two K32 groups of the same
sixteen weight rows. It decodes the original table/sign bits into registers,
then exchanges the words between half-waves before the unchanged half FMA
and WMMA operations. This removes the8192-byte code plane and1024-byte scale
plane. The raw weight addresses as a set, activation addresses,128-token
tile,64 output rows, eight waves,64 accumulators per lane, descriptors and
number of dispatches remain fixed. It changes neither expert nor KV caching.

Only nonpacked IQ2 BN128 selects the new kernel. The initial shared-template
implementation also changed nine unrelated Q2 compiled bodies; its failed
scope audit and source remain preserved. The isolated v2 leaves the original
generic template intact and keeps the new numerical body in its own include.
All161 other production kernel bodies, operands and resources now match the
saved parent assembly. No parent executable or assembly was rebuilt.

| Compiled property | Saved parent | Isolated candidate |
| --- | ---: | ---: |
| LDS bytes per block |25728|16512|
| Next-free VGPR |150|142|
| Private scratch bytes per thread |0|0|
| Static instructions |2361|2355|
| Static block-barrier sites |18|18|
| Static WMMA instructions |32|32|
| Compiler occupancy field |9|10|

These are compiler observations. The occupancy field is not measured active
occupancy. Eighteen register-exchange instructions replace eight LDS shuffle
instructions and the weight-stage loads/stores; their runtime cost still
needs measurement. Fewer resources alone did not help the tail16 trial.
No throughput gain, GPU safety or numerical equivalence follows from this table.

The source audit accounts for256 unchanged weight-group fetches,1024
eight-byte publication groups and4096 consumer word reads per stage. It
checks which wave owns every read; it does not execute floating-point code.
The original scale rounding, K16 accumulation order and anchored F32 SwiGLU
epilogue are retained in source. Full GPU outputs and actual model results
must establish the compiled behavior, including zero/negative scales and tails.

## Next measured scope

The next fixture should compare the literal saved1585 kernel and this new
kernel on the existing captured layers0/3/22, plus full and unaffected-route
controls. Use the same mixed128/64 map for both arms; tail16 is excluded.
Include ragged output widths and token counts, three rotated weight sets,
guards and saved full outputs. Preserve performance after safe numerical
differences; stop only unsafe device work. The original model benchmark then
uses saved fixedQ2/UD and saved1585 references without reruns.

The runtime fixture, launcher binding and fresh coordinated .157 admission
are not prepared by this static result. No GPU job or reservation is active.
Q4 and full context curves stay deferred until fixed-point parity.

The same wave ownership exists in the active Q2-down stage and is the next
extension to examine after this experiment. That extension is not implemented.
It differs from the old half-wave decode trial, which kept its code/affine LDS
stage. The saved1571 trace attributes135.807810ms to IQ2 BN128 and161.558060ms
to Q2 down. These are older diagnostic costs, not fresh1585 measurements or
a prediction that the candidate will save those times.

[Isolated source](../config/q2-iq2-register-stage-source-v2.json),
[source and ISA audit](../config/q2-iq2-register-stage-static-v2.json),
[isolated patch](../experiments/q2-iq2-register-stage-v2.patch),
[generator](../tools/prepare-q2-iq2-register-stage-v2.py),
[initial source retained](../config/q2-iq2-register-stage-source.json),
[provenance](../third_party/gufo/LIE-Q2-IQ2-REGISTER-STAGE.md).

No public C17 model/state/metrics ABI changes. Official upstream source and
the experimental providers remain separate from LIE's owned scheduler and
resource policy. This experiment changes data movement inside inference;
it does not claim a reactive scheduling gain.
