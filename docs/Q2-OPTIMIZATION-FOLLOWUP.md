<!-- SPDX-License-Identifier: MIT -->
# Focused optimization queue after shared-Q8 component timing

The fixed model comparator remains exact2048, original direct-executor input
and timers: Q2 PP1443.672867 / UD1685.777092. PP/TG parity over the requested
curve remains the goal. No context-curve expansion is admitted while the fixed
point has a large gap. Marginal candidates remain retained for measured
composition rather than deleted.

The completed [shared-Q8 cycle](Q2-SHARED-Q8-PRODUCER.md) saves2.01–2.08% of
component time against both unchanged controls. Its independent GPU format
fixture still fails; all production reference/candidate buffers match. These
facts are separate from model throughput and independent quality acceptance.

| Priority | Mechanism | Current evidence and next boundary |
| --- | --- | --- |
| 1 | Independent Q8 format/store diagnosis | Replay the retained failed arrays with explicitly ordered initialization on the nonblocking oracle stream; preserve production source, FP32 arithmetic and existing gates. The possible default-stream memset race is not yet causally tested. |
| 2 | Specialized original-F16 HC-down staging | Explore bounded native-vector loads, wider K pieces and a direct epilogue while preserving original accumulation boundaries; compare the actual retained library consumer and preparation cost. Generic coalesced/tile probes already have negative or inconclusive results. |
| 3 | Eight-value IQ2 producer partition | Test weight-fetch/decode partition and compact codebook representation without repeating the earlier packed-sign WMMA probe or substituting BF16 arithmetic. Prefetch and mixed compact routing already exist. |
| 4 | Paired wide shared-Q8 gate/up | Input quantization is already shared; a paired kernel must improve the full gate/up/SwiGLU/down cycle, including register/resource effects. |
| Later, after point parity | Cross-query indexer-key reuse and distributed exact top-k | Current scoring reloads keys per query and selection uses one workgroup per query. Preserve dot reductions, rank and tie ordering. Selection is inactive at the fixed2048 point and cannot fix that point's deficit. |

The [retained diagnostic profile](Q2-SCALED-LIBRARY-PROFILE.md) attributes70.29%
of net extra prefill GPU time to preparation plus HC down. It describes that
measured composition, not a fresh current-provider trace. More scheduler
callbacks cannot remove this work. PLE read overlap, serving concurrency and
single-request kernel throughput keep distinct evidence.

The existing provider already compacts sparse attention tiles across mask
windows, shares activation quantization between shared-expert gate/up, and
limits predictor FFN work after draft KV catch-up. These are not missing
optimizations. Packed sparse layouts or changed softmax tile ordering require
their own numerical and full-cycle qualification.

The private read-only research snapshot, pinned source inventories and the
external positive/negative results are retained under local
`evidence/external-optimization-audit-20261004/`. No external code, dependency,
host setting or service was changed. Qualified whole-model control-binary
replay is implemented and CPU checked, but the owner now requests using
retained controls without rerunning them. Component controls already share
one binary. The [two new retained compositions](Q2-REAUDIT-COMPOSITION.md)
measure1451.924906 /1452.143206 PP without changing the fixed input/timers.
Row reuse remains model-exact; added norm reproduces the previous norm logits.
The fixed-point PP gap remains13.86%; the complete curve stays deferred.
