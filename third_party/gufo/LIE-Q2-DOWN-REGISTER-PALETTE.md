<!-- SPDX-License-Identifier: MIT -->
# Isolated Q2 down register-palette trial

The [source manifest](../../config/q2-down-register-palette-source.json) pins
the1028-file candidate and retained `ssm-fixed-bounds` parent, both derived
from independently fetched official Gufo at
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`. Gufo MIT notices/license and
separate packed-format notices remain. No foreign DS4/CachyOS code or artifacts
are imported. The previous down-draft provenance remains applicable.

The [recipe](../../tools/prepare-q2-down-register-palette.py) copies that exact
parent, adds the private v3 register-palette body and changes only its BM128/BN48
selector. The [patch](../../experiments/q2-down-register-palette.patch), literal
parent control, donor include and generator hashes are bound in the manifest.
Weights, quantization, WMMA accumulation, inverse multiplication, output type,
public C17 contracts, scheduler, allocations and retained provider are unchanged.

[Static scope](../../config/q2-down-register-palette-static.json) establishes
161 other production bodies exact. The123-pair/70-timing fixture and matched
launch modes are prepared. Earlier host33+33 passes on `.157`; current phase
changes require fresh34+34. Failed SSH connects started no GPU work. No
runtime numerical, task quality or speed acceptance is claimed. See
[current status](../../docs/Q2-TARGET-PRIORITIES.md) for the outstanding gates.
