<!-- SPDX-License-Identifier: MIT -->

# BF16 row-sized reader trial

The [native diagnostic](Q2-LONG-PROFILE.md) identifies45–70ms late-chunk CPU
gaps before the20MiB PLE upload. The retained reader requests an aligned
4096/8192-byte window even when the encoded BF16/160 row is only320 bytes.
The [earlier I/O investigation](Q2-PLE-ANALYSIS.md) established that compressed
Q2 extents already use buffered I/O underneath the direct-I/O descriptor.
This new candidate selects a private buffered descriptor for BF16/160 and
uses the existing exact-row offset/length reader. Other shapes and formats
retain their prior direct mode and fallback.

Only `src/models/qwen38_flash_next/ngram.cpp` differs from the retained
1028-file provider;1027 files remain exact. The encoded row cache, workers,
hashing, ordering, dequantization and numerical kernels are unchanged. This
does permit reclaimable file-cache residency. It does not reserve another
copy of the model, change model files or evict existing pages. Any measured
memory/I/O change must accompany the performance result.

The new host fixture wraps `pread` to verify320-byte requests and a descriptor
without `O_DIRECT`, exact BF16 conversion, duplicate/warm-cache behavior,
interrupted reads and EOF without an output overwrite. Existing upstream
reader tests also run against the exact candidate translation unit. On .157,
`q2-ple-row-bytes-host-r1` passes42/42 Debug and42/42 ASan/UBSan tests, with
six command exits0. Seven collected artifacts hash-verify. These are host
checks, not model performance or GPU qualification.

[Source manifest](../config/q2-ple-row-bytes-source.json) binds the independently
fetched Gufo parent, generator, patch and exact host fixture. Source remains
durable under `.deps/gufo-q2-ple-row-bytes-run`; remote capsules remain under
the project `run/` tree. No source or qualified evidence is cleaned up.

[Plan](../config/q2-ple-row-bytes-plan.json) `56c1948c` binds332 fixtures for
one new candidate build. The qualified MMQ archive and native
`synapse-lie-bench` executable are reused. The nine original serialized
requests retain all preparations, both original8K observations and the
complete32711-token prefill. Capacity133760, chunks2048, C1 AR, MTP off and
zero prefix hits remain mandatory. The original saved unprofiled control
and replies are the comparison; the intervening instrumented profile is not.

Model performance is pending. A32K trial cannot establish128K target
acceptance or sustained TG128 performance. No qualified control is rebuilt or
rerun, and no longer curve runs until the new candidate has useful evidence.
