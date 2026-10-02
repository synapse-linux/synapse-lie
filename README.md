<!-- SPDX-License-Identifier: MIT -->
# Synapse LIE — Q2 compatibility audit

This workstream targets **official Gufo with the original antirez Q2 GGUF**.
It does not use the antirez Qwen engine. The minimum acceptance requirement is
no PP or TG regression under matched conditions; Q4 follows Q2.

The source/layout audit and proposed format contract are complete. **Q2 runtime
support and its performance qualification are not implemented on this branch.**
The audited official Gufo cannot bind this file. The audited llama.cpp reference
also requires a different down-projection shape; no ready, independent Q2
reference for `.157` was established. See the concrete blockers before porting.

- [Audit and source pins](docs/ANTIREZ-Q2-AUDIT.md)
- [Format, binding and packing contract](docs/Q2-FORMAT-CONTRACT.md)
- [Correctness and no-regression protocol](docs/Q2-VALIDATION.md)
- [Machine-readable audited layout](config/antirez-q2-contract.json)
- [Progress and provenance](docs/PROGRESS.md)

`feature/antirez-compat-audit` starts at `develop` (`ce3ce59`, an empty tree).
The server worktree was not merged or copied. LIE checkpoint `c14ef26` supplies
the historical inventory/restart protocol; `83d178a` supplies the newer C17
engine/model-family/numerical-ABI contracts, read-only. This branch contains
audit artifacts, not a replacement server or benchmark executable.

Sources and receipts live persistently under this worktree's ignored `.deps/`
and `evidence/`; they are not in `/tmp`. No model payload, conversion, GPU build,
GPU run, deployment or DS4 mutation was performed. First-party work is MIT;
third-party sources retain their own licenses.
