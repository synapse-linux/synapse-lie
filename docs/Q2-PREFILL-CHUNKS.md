<!-- SPDX-License-Identifier: MIT -->

# Original-input prefill chunk experiment

The owner requested 4096- and 8192-token prefill calls across the saved cold
curve through the original 130925-token prompt. The retained default is 2048.
No request is padded, truncated or regenerated. The 2055-token preparation
request remains a preparation request; it is not the separate fixed2048/tg128
benchmark. All eight saved prefix cases, including both original 8K attempts,
remain in the corpus.

The private runtime and provider are prepared by
`tools/prepare-q2-prefill-chunks.py`. The retained 333-file runtime and R3
provider remain unchanged. The adapter propagates a bounded chunk capacity
to the provider instead of leaving its internal capacity fixed at 2048.
Buffer allocations already scale with that capacity. The extension preserves
the mixed IQ2 expert map, full-chunk deferred normalization, compact expert
down storage and HC down projection at the newly selected shapes. Other
partial shapes keep their original fallback. No weight precision changes.

The candidate builds locally with the retained RelWithDebInfo configuration
and unchanged MMQ archive. All 923 device functions are byte-identical to R3.
This proves code identity, not numerical equivalence across different chunk
partitions or a performance gain. New host contract fixtures exercise actual
C17 chunk/tail dispatch, deferred-buffer identity and independent expert-map
coverage through8192. All nine focused runtime checks pass on .157, including
Debug and ASan/UBSan. This is synthetic host-contract evidence, not inference.
Changed-file formatting passes; the shared upstream formatting check still
fails on unchanged inherited files, with its actual exit1 preserved.

One new2048 curve is the matched control for4096/8192 in the same executable:
there is no complete curve for the latest R3 provider to reuse as that control.
Historical UD and earlier Q2 measurements are retained, not rebuilt.
Every arm reports actual PP/TG counters, output differences and zero prefix
reuse. The existing `synapse-lie-bench` client and original input corpus remain
hash-bound. A chunk win is not automatically a decode win.

The subsequent owner instruction requests an IOMMU A/B first. That comparison
uses the already-qualified R3 executable and original chunk2048; the larger
chunk candidate is prepared, but no GPU curve has run yet.
