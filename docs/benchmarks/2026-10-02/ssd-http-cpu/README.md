<!-- SPDX-License-Identifier: MIT -->
# SSD HTTP functional qualification — NOT-INFERENCE

[Protocol and usage](../../../SSD-HTTP-PROTOCOL.md).

The [receipt](receipt.json) binds source hashes, commands, exits and the final
HTTP scheduling witness. The [small evidence archive](evidence.tar.gz) preserves
all nine build/test records under their original local `evidence/` paths.
R1..R4 are development checks; R5 is the final four-suite ASan/UBSan run with
leak detection and halt-on-error, all exit0. Final test peak on the editing
`.155` host: CPU75.625 C, GPU54 C; inference devices were masked.

Two actual synthetic-server processes exercise persistence. The reader completes
20 measured requests in two repetitions, then overlap/recovery/slow-client
checks. Final counters: 23 completed, 2 cancelled, 0 failed; no active, queued,
blocked or pending work and no retained SSD staging. No original model forward,
GPU performance, active-KV compression or DS4-policy parity is established.
