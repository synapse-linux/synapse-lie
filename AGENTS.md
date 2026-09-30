# Synapse LIE development

The parent Synapse workspace policy applies. First-party source is MIT; keep
SPDX markers. Use Git Flow (`feature/*` from `develop`); no implicit publication.

- Own this repository only. DS4 is owned by the other agent. No changes to its
  source, build, service, cache, profiles, model files or qualified evidence.
- Do not import project code/artifacts from the sibling CachyOS workspace.
  Official upstream Gufo source is fetched independently at the recorded pin.
  Read-only historical DS4 qualification data is reference evidence, not code.
- Target an autonomous LIE backend. An explicit opt-in in-process Gufo adapter
  is permitted for the initial working slice, then refactored against the other
  requirements and new developments. Do not call delegation reimplementation.
  Keep upstream types inside the adapter; LIE owns the contracts, reactive
  scheduling/resource policy and observability. `docs/BACKEND.md` defines the
  stages, replacement acceptance gates and eventual ownership of model/state.
- Core/network/scheduling/resource accounting/metrics and the eventual owned
  model executor are C17. C++/HIP is allowed inside the transitional engine and
  selected numerical ports, with provenance/licenses; no CPU model forward.
  `include/lie/executor.h` and `adapters/gufo.cpp` are compile-checked only today;
  permission to evolve/link them is not evidence of working inference.
- Investigate reactive scheduling inside pure inference as a separate measured
  hypothesis (docs/INFERENCE-REACTIVE.md). C1 PP/TG gains, concurrency gains and
  serving responsiveness are distinct; more callbacks/threads imply no speedup.
- No GPU run, heavyweight model hash, model conversion or remote GPU build until
  the coordinated ownership/lease protocol in `docs/COORDINATION.md` is satisfied.
  No foreign process termination, deployment, dependency installation or tuning.
- Keep CPU fixtures visibly separate from inference; never claim object
  compilation, health endpoints or an empty model list are real model serving.
- Run focused CTest and ASan/UBSan for changes to lifetimes, parsers or metrics.
  Tests use private ephemeral loopback ports and own only their child processes.
- Maintain README, `docs/PROGRESS.md`, ABI/state/metrics contracts and provenance.
  Preserve failures and actual command exit codes under local `evidence/`.
- CLI text is deterministic US English; data/protocols are locale-neutral.
  The web page is a development en_US fallback, not a localized release GUI.
