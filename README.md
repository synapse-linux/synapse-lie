<!-- SPDX-License-Identifier: MIT -->
# Synapse LIE — original Q2 support for official Gufo

This isolated workstream adds the original antirez Q2 GGUF to official Gufo
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, without the antirez Qwen engine.
The minimum acceptance requirement remains **no prefill or decode regression**.
The runtime patch is implemented. Parser/sanitizer, independent synthetic HIP
operators and original-model C1 screens run on `.157`. The latest isolated
[HC up vector experiment](docs/Q2-HC-UP-VECTOR.md) reaches **1287.12 prefill
tokens/s and 23.21 decode steps/s at 2K**, with byte-exact synthetic buffers,
saved model logits and tokens against the retained packed Q2 reference.
**The performance requirement is not met:** the fresh same-window UD control
reaches 1682.77 PP/24.30 TG; Q2 trails by 23.51% and 4.47%. Earlier checkpoint
drift from qualified Q2 remains unresolved. This is an experimental checkpoint,
not a promotion to the qualified runtime patch.
The prior [expert-kernel experiment](docs/Q2-EXPERT-STACK.md) produced the main
prefill gain: 1240.52 tok/s, up 88.29% over the previous HC checkpoint.
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

The packed activation move passes 30 independent GPU operator cases, 32 exact
packing/down/chain checks and 42 saved-model comparisons against fresh/retained
Q2 references. Fresh UD also replays all 21 retained model buffers exactly.
[Complete samples and graph](docs/Q2-PACKED-ACTIVATIONS.md#fresh-complete-model-performance)
include prefill/decode rates and durations. The current baseline profile points
to remaining HC projection/epilogue and activation-conversion costs.

The [raw-F16 HC up/mix fusion](docs/Q2-HC-UP-FUSION.md) passes seven GPU cases
and 19 byte-exact complete buffers. It removes the intermediate gate write/read
and emits the existing half input in the producer. Prefill improves 2.91% over
the fresh packed checkpoint; decode is unchanged. The subsequent
[scalar HC up vector kernel](docs/Q2-HC-UP-VECTOR.md) speeds up its isolated
component 15.22% and the full-model decode 1.16% without model-logit drift.

Separate [HC down prefetch variants](docs/Q2-HC-PREFETCH.md) retain exact
synthetic outputs but are 0.44% and 7.35% slower in the rotating-weight GPU
microbenchmark. Neither is promoted.

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
