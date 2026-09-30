# Development configuration (current CLI, no config-file loader)

Run from the project root, on the editing host, with separate API and management:

```sh
build/debug/synapse-lie-server \
  --host 127.0.0.1 --port 19879 \
  --management-host 127.0.0.1 --management-port 19880
```

There is intentionally no `--model` option in the current server. Adding one
requires a linked/qualified executor, admission budgets and a device-owner
worker, not merely reporting the path in `/v1/models`.

Future private paths (not created or populated by current server):

- model input: read-only paths in `models-157.inventory.json`;
- LIE cache: `$HOME/.local/state/synapse-lie/sessions` (never a DS4 cache);
- build/results: this repository's `build/` and `evidence/`;
- isolated Gufo reference listener: `127.0.0.1:19881`, only under agreed lease.

Budget planning must measure actual shared RAM, model state, workspace, MTP and
I/O. There is no invented fixed 32GiB model reserve and no implicit global
power/driver/governor modification. A failed admission is not an OOM/fit proof.
