<!-- SPDX-License-Identifier: MIT -->
# C17 dense sampling extraction

The first model-executor extraction on `feature/c17-sampling` replaces dense
token selection and random draws with `src/sampling.c`, shared through
`include/lie/sampling.h`. HTTP and the direct benchmark keep their existing
core/worker path. The numerical model forward remains the transitional Gufo
provider; this does not complete the autonomous C executor.

Original-weight continuation on `.157` now passes the AR HTTP controls and
fifteen C17/C++ output/usage/logprob comparisons. MTP prefix continuation also
passes complete-logit replay after correcting separately admitted predictor
geometry. [Functional evidence](validation/c17-gpu-functional-2026-10-03.json)
records the failures and limits. Matched performance is a separate campaign;
ordinary greedy can retain GPU argmax and does not isolate C dense-filter cost.

## Ownership and behavior

The C library owns finite greedy argmax, token-ID tie ordering, repetition /
frequency / presence arithmetic, dense bias, bounded top-k selection, top-p,
min-p, softmax normalization and xorshift64* draws. Filters retain the pinned
order and rounding: penalties/bias, temperature, top-k, top-p, min-p. The
ordinary greedy path needs no workspace. The unfiltered path retains vocabulary
order; ranked paths retain descending logits and ascending token IDs for ties.
Large top-p rows use the same 256-candidate first pass and full-selection fallback
as the pinned control, including its 1024-entry threshold.

The contract is model-neutral C17 ABI 1. Logits, already-compiled grammar masks,
sorted penalty counts, bias and RNG are borrowed from the caller. A growth
callback supplies bounded scratch storage and preserves live entries. The C
module creates no threads, performs no device call, allocates no memory itself
and retains no input pointer. Failed builds publish a zero result count;
invalid draws leave RNG unchanged. The caller owns workspace cleanup.

`adapters/gufo_sampling.hpp` translates the provider's controls and containers.
Gufo still owns history/generated-count maintenance, cloning/deferred draws,
entropy acquisition, grammar compilation/masking and compact speculative
distributions/residual construction. Their random draws and dense target
distributions use C. Reporting logits still use the provider transform before
the existing C probability normalizer. These remaining dependencies must be
extracted in later slices; the sampler as a whole is not yet autonomous C.
Existing eligible GPU argmax shortcuts remain delegated and preserved.

Reactive readiness, per-row credits, cancellation, native batching and MTP
verification are unchanged. There is still one device-owner worker. The C
selection call is synchronous; it does not add an asynchronous GPU forward or
establish a throughput improvement.

## Build selection and observability

`LIE_C17_SAMPLING=ON` is the default for the verified state-access provider.
An explicit OFF build retains the legacy provider selection. Use the same
selection in the provider build and the linked application; verification refuses
an incompatible receipt. Acquire the pin once using the
[build guide](../guides/BUILD.md#gpu-inference-build), then use unused labels:

```sh
cmake -DLABEL=qwen-c17 -DLIE_C17_SAMPLING=ON -P cmake/provider/Build.cmake
cmake -S . -B build/release -DLIE_GUFO_RUNTIME=ON \
  -DLIE_GUFO_STATE_ACCESS=ON -DLIE_C17_SAMPLING=ON \
  -DGUFO_SOURCE="$PWD/.deps/gufo-state-access-qwen-c17" \
  -DGUFO_BUILD="$PWD/build/qwen-c17"
cmake --build build/release -j1
```

Repeat with unused labels and OFF in both commands for the explicit fallback.
No new HTTP field or runtime switch is required. `dense_sampling` in server
build information, actuator and benchmark identity reports `lie-c17-dense`,
`gufo`, `none` or `synthetic-test-fixture`. Overall backend ownership remains
`delegated` while the Gufo model/session executor is required.

The direct Gufo reference executable resolves a separately compiled legacy
sampler before the provider archive, with the same verified layouts. Its
`dense_sampling` value is `gufo`; comparing LIE to a control that also used the
new C selector would not isolate this extraction.

## Verification and remaining gates

The standalone C fixture checks mathematical normalization, tie ordering,
penalty/bias order, masks, minimum retention, large flat top-p rows, RNG goldens,
categorical frequencies and workspace refusal. It works in a headless C build.

The separate host-only reference project independently verifies the official
Gufo pin, then tests the pristine sampler, C17 variant and OFF variant. It runs
upstream sampling, grammar and MTP-policy fixtures, complete distribution /
draw / residual / RNG witnesses for 1200 cases, another 1200 biased cases
against the same-layout legacy variant, and twelve complete 248320-entry rows.
These are synthetic operator/contract checks, **not original-weight inference**.

The final native, headless and host-reference suites pass **43/43**, **18/18**
and **14/14** tests with ASan/UBSan/LeakSanitizer. HIP compilation/linking and
the metadata/symbol audit also pass; they perform no model execution. The
[source-bound receipt](validation/c17-sampling-2026-10-03.json) records exact
source/provider identities, witness hashes, failures, exits and temperatures.

```sh
cmake -S tests/sampling -B build/sampling-host -DLIE_SANITIZERS=ON
cmake --build build/sampling-host -j1
env HIP_VISIBLE_DEVICES=-1 ROCR_VISIBLE_DEVICES=-1 CUDA_VISIBLE_DEVICES=-1 \
  ctest --test-dir build/sampling-host --output-on-failure -j1
```

Reference checks need a C++20 compiler and ICU; the C sampler itself needs C17
and libm. The normal build/test path does not need Python. Shared-hardware GPU
qualification remains subject to [coordination](../COORDINATION.md).

Next gates: original-weight AR and MTP/vision continuation under new controls,
cache equivalence, matched C1/C2..8, sampling overhead, host scratch peaks and
HTTP responsiveness on `.157`. Then extract request-owned sampler state and
compact speculative distributions, followed by tokenizer, loading/binding and
layer control. GPU-kernel replacement has its separate C++ removal gate.

## Provenance

The C numerical algorithm is an attributed port of official Gufo
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, acquired independently in this
worktree. `dense-sampling-edits.json` records exact conditional integration
replacements; the build receipt binds that manifest, the C source/header, glue,
provider source inventory, compile selection and archive hashes. No DS4 project
code, sibling checkout artifact, model conversion or weight payload is imported.
Retain [Gufo's MIT notice](../../third_party/gufo-NOTICE) and
[license](../../third_party/gufo-LICENSE) with the port.
