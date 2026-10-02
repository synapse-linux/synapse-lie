<!-- SPDX-License-Identifier: MIT -->
# Synapse LIE — original Q2 support for official Gufo

This isolated workstream adds the original antirez Q2 GGUF to official Gufo
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, without the antirez Qwen engine.
The minimum acceptance requirement remains **no prefill or decode regression**.
The runtime patch is implemented. Parser/sanitizer, independent synthetic HIP
operators and the first original-model C1 screen pass on `.157`. **The performance
requirement is not met:** Q2 is 48–66% slower in prefill and 16–17% slower in
decode than existing UD-Q4 in this screen. Do not promote this candidate yet.
See the [complete results and plots](docs/Q2-RESULTS.md).

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
