# Development configuration (current CLI, no config-file loader)

Run from the project root, on the editing host, with separate API and management:

```sh
build/debug/synapse-lie-server \
  --host 127.0.0.1 --port 19879 \
  --management-host 127.0.0.1 --management-port 19880
```

This default build/start has no loaded model. The opt-in HIP build now accepts
`--model FIRST-SHARD.gguf`, `--model-id ID`, `--context N` (128–32768, default 4096),
`--prefill-chunk N` (1–2048), `--max-active 1|2` (default 1), and
`--request-timeout-ms N` (100–1800000, default 120000). `--build-info` opens no model.
Model loading occurs on the single owner worker; merely setting a path does not
publish a model or readiness. Failed/unconfigured models remain unavailable.

Actual model startup requires the shared lease and a fresh target preflight;
use private HOME/XDG_CACHE_HOME/runtime directories and the original read-only
weights. No GPU execution is yet qualified. Two active slots mean interleaved
single-row execution, not native batching or measured memory capacity. No
synthetic provider is selectable in the production binary.

Future private paths (not created or populated by current server):

- model input: read-only paths in `models-157.inventory.json`;
- LIE cache: `$HOME/.local/state/synapse-lie/sessions` (never a DS4 cache);
- build/results: this repository's `build/` and `evidence/`;
- isolated Gufo reference listener: `127.0.0.1:19881`, only under agreed lease.

Budget planning must measure actual shared RAM, model state, workspace, MTP and
I/O. There is no invented fixed 32GiB model reserve and no implicit global
power/driver/governor modification. A failed admission is not an OOM/fit proof.
