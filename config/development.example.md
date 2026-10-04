<!-- SPDX-License-Identifier: MIT -->
# Development configuration

Configuration is supplied through CLI options. LIE has no configuration-file
loader. See the [usage guide](../docs/guides/USAGE.md) for model startup, HTTP
requests, Pi, concurrency and RAM/SSD settings.

For a management-only development instance, without a model:

```sh
build/debug/synapse-lie-server \
  --host 127.0.0.1 --port 8000 \
  --management-host 127.0.0.1 --management-port 19880
```

Readiness remains 503 until a real provider and model are available. CPU fixture
executors are confined to test binaries.

The included [Pi models](pi-unsloth.models.json) and
[Pi settings](pi-unsloth.settings.json) are templates for a separate client
profile. Set the server address and context capacity as described in the guide.
