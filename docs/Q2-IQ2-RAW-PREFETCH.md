<!-- SPDX-License-Identifier: MIT -->
# Deferred IQ2 expansion with raw prefetch

One new candidate starts from the saved compact IQ2 composition at
1498.799455 PP / 25.16866636 TG. It changes only IQ2 paired routed prefill.
Fetch retains the original eight-byte group and two-byte F16 header across
current-stage WMMA; unchanged codebook/sign expansion and scale conversion
move to LDS commit, before the existing barrier. Weight format, compact LDS
layout, tile geometry, routing, original F32 scale expression/F16 rounding,
packed F16 FMA, K16 WMMA order and SwiGLU remain unchanged. No new allocation,
device table, stream, public ABI, state or metrics contract is introduced.

The logical prefetched weight payload shrinks from 32 decoded high bytes plus
the half scale to one raw group plus its half header, 34 to 10 bytes. This is
not allocated register storage or a reduction of persistent model bytes.
Deferred codebook lookup may expose latency at commit; actual performance
must be measured.

Matched local production assembly changes eight IQ2 bodies and preserves the
other 149 exactly. Every changed body has zero private scratch and unchanged
LDS. Ordinary-output specializations show:

| Token tile | Parent / candidate instructions | Parent / candidate next-free VGPR | LDS bytes |
| ---: | ---: | ---: | ---: |
| 16 | 640 / 595 | 83 / 78 | 11392 |
| 48 | 1143 / 1095 | 94 / 88 | 15488 |
| 64 | 1366 / 1316 | 102 / 96 | 17536 |
| 128 | 2361 / 2311 | 148 / 142 | 25728 |

These are static counts. Moving expansion out of initial and loop fetch into
one commit body removes duplicated static load instructions; each dynamic
stage still decodes the same group. No bandwidth, occupancy or throughput gain
is inferred. The qualified parent assembly is reused without rebuilding it.

The new fixture compares 81 guarded complete outputs against a literal copy
of the compact parent. It includes ordinary/packed outputs, ragged token/row
edges, widths 16/48/64/128 and the existing mixed 128/64 map. Initialization,
poisoning, launch and readback use the same nonblocking stream. Three rotations
span 162201600 / 324403200 / 1297612800 weight bytes for 64/128/512 active
experts, above 32 MiB MALL. Forty-two alternating warmup/measured timings cover
fused IQ2 gate/up and SwiGLU only, excluding map construction and down projection.
They are not whole-model performance.

Saved exhaustive compact-format qualification is reused: format, decoder,
tables and half arithmetic are unchanged. New full outputs test the changed
producer lifecycle. Numeric failures preserve arrays and timings; guard/runtime
faults stop device work. The original-weight model follows any safe component
verdict, including a numerical or timing rejection.

The fixed comparison stays exact2048/tg128, 127 timed decode calls, capacity9216,
chunk2048, MTP off, one warmup plus three measurements, 15-second waits outside
timers. Saved Q2 1443.672867 / UD 1685.777092 and compact parent 1498.799455 PP
are reused without control or old component reruns. No context sweep,
dependency installation, tuning, cleanup or deployment is admitted.

Production/fixture device compilation and host syntax pass; 86 launch guards
pass locally. The first new-fixture format check fails on renamed line wrapping;
its whitespace-only correction passes without changing arithmetic tokens.
The shared formatter retains exit1 for nine byte-identical inherited files.
Both failures remain separate from numerical/performance evidence.

New `.157` host fixtures pass25/25 Debug and25/25 ASan/UBSan; six command exits are zero, seven artifacts and36 frozen fixture files verify. These fixtures access neither models nor GPU.

GPU component/model evidence is pending fresh coordinated admission. Static
preparation establishes neither original-weight quality nor Q2/UD parity.

[Frozen plan](../config/q2-iq2-raw-prefetch-plan.json),
[source inventory](../config/q2-iq2-raw-prefetch-source.json),
[static evidence](../config/q2-iq2-raw-prefetch-static.json),
[patch](../experiments/q2-iq2-raw-prefetch.patch),
[literal parent](../experiments/q2-iq2-raw-prefetch-control.inc),
[new fixture](../tests/q2_iq2_raw_prefetch.hip).
