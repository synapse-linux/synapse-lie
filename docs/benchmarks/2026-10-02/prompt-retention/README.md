<!-- SPDX-License-Identifier: MIT -->
# Prompt retention: CPU qualification and GPU protocol

See [the contract and declared GPU comparison](../../../CACHE-PROMPT-RETENTION.md).
[CPU receipt](cpu-receipt.json) binds source hashes, linked binaries, exact
commands/exits and thermals. [CPU archive](cpu-evidence.tar.gz) preserves all
17 command records, including four failed focused attempts, and the source
capsule. No model, cache payload or device inference is included.

Full sanitizer suite39/39; headless utility/compression/interchange-OFF10/10.
Both native and synthetic KVC retention tests exercise the same model-neutral
core. These are NOT-INFERENCE fixtures; the GPU comparison is a separate gate.
