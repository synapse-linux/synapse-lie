# Synapse LIE development

The parent Synapse workspace policy applies. First-party source is MIT; keep
SPDX markers. Use Git Flow (`feature/*` from `develop`); no implicit publication.

- Own this repository only. DS4 is owned by the other agent. No changes to its
  source, build, service, cache, profiles, model files or qualified evidence.
- Do not import project code/artifacts from the sibling CachyOS workspace.
  Official upstream Gufo source is fetched independently at the recorded pin.
  Read-only historical DS4 qualification data is reference evidence, not code.
- Implement an autonomous LIE backend, not a Gufo proxy or in-process wrapper.
  LIE owns loading/binding, model execution, sessions, memory, batching and state.
  Do not delegate whole-model work to Gufo Model/Session/Executor/DeviceModel.
  `docs/BACKEND.md` supersedes the earlier embedded-adapter plan.
- Core/network/model execution/scheduling/resource accounting/metrics are C17.
  Selectively port useful Gufo numerical kernels/helpers, retaining provenance
  and licenses, behind a narrow C numerical/device ABI; no CPU model forward.
  The existing `include/lie/executor.h` and `adapters/gufo.cpp` are reference-only
  experiments, not the production backend ABI or an integration shortcut.
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
