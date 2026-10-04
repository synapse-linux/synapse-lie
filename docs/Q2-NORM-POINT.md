<!-- SPDX-License-Identifier: MIT -->
# One canonical model point for the paired HC norm

The [ragged component](Q2-NORM-RAGGED.md) selects a focused model comparison,
not another full context curve. The candidate only extends paired F32/F16
norm production to the already supported HC library row interval. Ordered
IQ2 decode, all arithmetic kernels and original PLE remain unchanged.

The frozen native C `synapse-lie-bench` now receives `--depths 0` and three
measured repetitions after one warmup. The existing prose generator changes
the text by repetition, exactly as the native benchmark already implements;
each Q2 arm must preserve the complete corresponding request/reply/count
history. Repetition zero is the original canonical depth-zero workload.
There is no counting-prompt substitution or deep-prefix construction.

All other settings remain: pp2048/tg128, AR greedy, thinking/MTP/vision/SSD
off, capacity133760, chunk2048, C1, HTTP port8000, RAM prefix budget16GiB,
and completed-executor-call PP/TG timers. Client wall/TTFT and cache work
remain separate. The source-pinned C client and 333-file server are unchanged;
the existing native-client Debug/ASan conformance is reused after inventory
verification. Three samples address the earlier large observed variation.

[Frozen four-arm plan](../config/q2-norm-point-plan.json): unchanged ordered
Q2, paired-norm Q2, unchanged ordered Q2 again, then pristine UD. Retain all
samples and both controls. A useful change must preserve request/output/count
history and improve against both controls; initial warming is not a patch
gain. A focused win still does not establish full-curve parity or independent
quality. The component's shared numerical failures remain open.

The candidate model mode requires `--native-curve --point-only --rebuild-mmq`;
it cannot silently launch a full sweep or use the older Python request driver.
Build identity and complete provider inventory are checked. The host wrapper
checks on `.157` pass 22/22 Debug and 22/22 ASan/UBSan, with six zero command
exits and seven verified artifacts. [Host receipt](../config/q2-norm-point-host-results.json).
GPU admission and actual model results remain separate from preparation.
