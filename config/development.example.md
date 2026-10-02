# Development configuration (current CLI, no config-file loader)

Run from the project root, on the editing host, with separate API and management:

```sh
build/debug/synapse-lie-server \
  --host 127.0.0.1 --port 19879 \
  --management-host 127.0.0.1 --management-port 19880
```

This default build/start has no loaded model. The opt-in HIP build now accepts
`--model FIRST-SHARD.gguf`, `--model-id ID`, `--context N` (128–262144, default 4096),
`--prefill-chunk N` (1–2048), `--max-active 1..8` (default 1), and
`--request-timeout-ms N` (100–1800000, default 600000). `--build-info` opens no model.
Model loading occurs on the single owner worker; merely setting a path does not
publish a model or readiness. Failed/unconfigured models remain unavailable.

The separate [ordinary Pi model profile](pi-unsloth.models.json) expects the
native OpenAI tool API and **`--context 262144`**, not the default 4096. It is not
a custom provider extension or a global Pi installation. See
[setup, limits and current test scope](../docs/SERVER-TOOLS.md).

Actual model startup requires the shared lease and a fresh target preflight;
use private HOME/XDG_CACHE_HOME/runtime directories and the original read-only
weights. Scoped original-weight smoke/C1/lifecycle runs are recorded, not full
numerical/hardware qualification. Multiple ready active slots can use native AR decode batches. Context capacity
262144 is qualified at one active sequence, not eight simultaneous full contexts. No
synthetic provider is selectable in the production binary.

RAM prefix reuse is enabled by default with a lazy 4 GiB budget;
`--prefix-cache-mib 0` disables RAM retention explicitly. Optional SSD persistence
is implemented with three explicit options:

```text
--prefix-ssd-dir /absolute/private/lie-prefix-directory
--prefix-ssd-quota-mib 16384
--prefix-ssd-staging-mib 4096
```

SSD is **off by default**, independent of RAM. It creates only the named final
private directory; parents must already exist. Disabled persistence performs no
store I/O and never silently spills to disk. This implementation has synthetic
CPU evidence; original-weight SSD qualification is pending. See
[SSD-PREFIX.md](../docs/SSD-PREFIX.md) for identity, resource and lifecycle limits.
Model inputs stay read-only, build/results stay under LIE, and a store must never
point at another engine's cache. No directory or persistent service is installed
by this example.

Budget planning must measure actual shared RAM, model state, workspace, MTP and
I/O. There is no invented fixed 32GiB model reserve and no implicit global
power/driver/governor modification. A failed admission is not an OOM/fit proof.
