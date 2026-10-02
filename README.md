<!-- SPDX-License-Identifier: MIT -->
# Synapse LIE — original Q2 support for official Gufo

This isolated workstream adds the original antirez Q2 GGUF to official Gufo
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, without the antirez Qwen engine.
The minimum acceptance requirement remains **no prefill or decode regression**.
The runtime patch is implemented. Parser/sanitizer, independent synthetic HIP
operators and original-model C1 screens run on `.157`. The latest isolated
[expert-kernel experiment](docs/Q2-EXPERT-STACK.md) reaches **1240.52 prefill
tok/s and 23.01 decode calls/s at 2K**, up 88.29% in prefill from the previous HC
checkpoint. **The performance requirement is not met:** the candidate still
trails historical UD by 26.36% in prefill and 5.37% in decode. Greedy tokens match
the Q2 reference, but logits differ. Do not promote this candidate yet.
The initial unoptimized screen was 48–66% slower in prefill and 16–17% in decode.
See the [complete results and plots](docs/Q2-RESULTS.md) and the now-qualified
[Q2/UD phase profiles](docs/Q2-PROFILING.md). The first WMMA down
[experiment](docs/Q2-DOWN-EXPERIMENT.md) improved PP by 34–64% but exceeded the
saved-logit limit and was rejected. The subsequent
[integer scheduling experiments](docs/Q2-REGISTER-EXPERIMENT.md) reduce static
register spills but fail exact operator replay. The original runtime is restored;
the subsequent owner-authorized [performance exploration](docs/Q2-PERFORMANCE-EXPLORATION.md)
measures +13–42% PP for bounded K and +1–28% for the barrier. Numerical work
and the overall no-regression target remain open.
The separate [F16 HC down experiment](docs/Q2-HC-EXPERIMENT.md) measures a
2.86x component speedup and about 12% higher model decode, with original weight
bytes. The fresh reference is thermally interrupted; the comparison is
incomplete and the candidate remains 5.7% below UD decode at 2K.
The subsequent [HC prefill WMMA experiment](docs/Q2-HC-PREFILL.md) completes both
matched model arms: PP rises from 608.8 to 658.8 tok/s (+8.22%), TG stays near 23.
All changed synthetic operator cases pass; greedy tokens match, but model logits
differ. The candidate still trails UD and remains isolated. The owner-approved
test ceiling is now 98 C inclusive, with lower exposed hardware limits retained.

The next [packed-activation experiment](docs/Q2-PACKED-ACTIVATIONS.md) moves
compensated input conversion into the IQ2 producer, using the same buffer bytes.
Source/static checks are complete; GPU correctness and performance are pending
the core campaign handover. It introduces no new measured speed claim.

- [Implementation and evidence](docs/Q2-IMPLEMENTATION.md)
- [Audit and source pins](docs/ANTIREZ-Q2-AUDIT.md)
- [Format and storage contract](docs/Q2-FORMAT-CONTRACT.md)
- [Correctness and performance protocol](docs/Q2-VALIDATION.md)
- [Progress](docs/PROGRESS.md) and [third-party provenance](third_party/README.md)

The reviewable change is `patches/gufo-q2.patch`. Given the exact official
archive recorded in `config/gufo-source.json`, reconstruct it with:

```sh
python3 tools/prepare-gufo.py .deps/gufo-f783fedb.tar.gz .deps/gufo-q2-reconstructed
```

The qualification capsule builds the pinned upstream HIP executor and tests;
it is not a replacement for the C17 LIE core or `synapse-lie-bench`. Run the
fixed remote checks with `tools/q2-remote.py`; GPU modes acquire all four known
nonblocking leases and refuse contention. Sources and evidence stay in persistent
project directories. Models are read-only; no conversion, deployment or publication.

Branch `feature/antirez-compat-audit` starts at empty `develop` (`ce3ce59`).
The server/cache branch is separate. Q4, MXFP4 predictor execution, HTTP
integration, concurrency qualification and long-context qualification remain
separate gates. The original Q2 predictor descriptor is understood with MTP off.
