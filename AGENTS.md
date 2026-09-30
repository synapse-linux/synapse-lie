# Synapse LIE development

The parent Synapse workspace policy applies. First-party source is MIT; keep
SPDX markers. Use Git Flow (`feature/*` from `develop`); no implicit publication.

- Own this repository only. DS4 is owned by the other agent. No changes to its
  source, build, service, cache, profiles, model files or qualified evidence.
- Do not import project code/artifacts from the sibling CachyOS workspace.
  Official upstream Gufo source is fetched independently at the recorded pin.
  Read-only historical DS4 qualification data is reference evidence, not code.
- Core/network/scheduling/resource accounting/metrics are C17. Isolate C++/HIP
  behind `include/lie/executor.h`; no CPU model-forward substitution.
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
