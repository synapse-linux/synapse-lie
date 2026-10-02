<!-- SPDX-License-Identifier: MIT -->
# Using LIE

[Documentation](../README.md) · [Build](BUILD.md) · [Benchmarks](BENCHMARKS.md)

## Model files

The tested model is `unsloth/Qwen3.8-Flash-Next-GGUF`, revision
`38bb39ee97821de2c9009abb7e93950eec396e66`, quantization **UD-Q4_K_XL**.
Download the four GGUF shards from the
[model directory](https://huggingface.co/unsloth/Qwen3.8-Flash-Next-GGUF/tree/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL)
and keep them together. Pass `Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf`
to LIE; the loader discovers the other shards. Model weights have their own
publisher terms. MTP sidecars and vision projectors are not used by this branch.

## Start the server

After the GPU build, set the path to your first shard:

```sh
LIE_MODEL=/path/to/Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf
build/release/synapse-lie-server \
  --model "$LIE_MODEL" --model-id qwen3.8-flash-next \
  --host 127.0.0.1 --port 8000 --context 262144 --max-active 1
```

Use `--host 0.0.0.0` for access from another machine. Clients then connect to
`http://SERVER-IP:8000/v1`; no tunnel is required. The server has no built-in
authentication or TLS, so expose it only on a trusted network or through an
appropriately configured proxy.

Check readiness and list models:

```sh
curl --fail http://127.0.0.1:19880/actuator/health/readiness
curl --fail http://127.0.0.1:8000/v1/models
```

The management endpoint listens on loopback, port 19880, separately from the
inference API. Its development dashboard is at `http://127.0.0.1:19880/monitor`.
Stop the foreground server with Ctrl+C.

## Chat, streaming and Responses

A non-streaming Chat Completions request:

```sh
curl --fail http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3.8-flash-next","messages":[{"role":"user","content":"Explain what a KV cache does."}],"max_tokens":256,"temperature":0}'
```

For streaming, set `stream` to `true` and disable curl's output buffering:

```sh
curl --fail --no-buffer http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3.8-flash-next","messages":[{"role":"user","content":"Write a short greeting."}],"max_tokens":128,"temperature":0,"stream":true}'
```

A stateless Responses request:

```sh
curl --fail http://127.0.0.1:8000/v1/responses \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3.8-flash-next","input":"Write a short greeting.","max_output_tokens":128,"temperature":0}'
```

Clients execute function tools and submit correlated tool results in the next
request. Tool-enabled SSE publishes a complete validated turn; function arguments
are not streamed incrementally. The current API is text-only, with thinking
disabled. It implements Chat Completions and stateless Responses, rather than
all OpenAI services. See the [API reference](../reference/OPENAI-REACTIVE.md)
for supported fields and error behavior.

## Context and concurrency

| Option | Meaning |
| --- | --- |
| `--context 262144` | Maximum tokens per sequence, including prompt and reserved output; valid range: 128–262,144. |
| `--max-active 1` | Active sequences; set 2–8 to allow GPU decode batches when multiple requests are ready. |
| `--prefill-chunk 2048` | Maximum prompt tokens handled in one prefill dispatch. |
| `--request-timeout-ms 600000` | Request deadline, in milliseconds; allow enough time for long prompts. |

The maximum requested output is 4,096 tokens. The model's chat template also
consumes context, so a 262,144-token capacity does not admit a user message of
that length plus output. Each active sequence needs its own runtime state;
higher concurrency and larger contexts increase memory requirements.
`--max-active` controls sequences, not the number of inference worker threads.

## RAM and SSD cache

RAM retention uses a lazily allocated 4 GiB budget by default. Use
`--prefix-cache-mib 0` to disable it, or a larger value for more retained
checkpoints. This cache reuses matching prompts; it does not eliminate the
prefill of a new prompt.

To enable SSD persistence, add the following options to the server command:

```sh
--prefix-ssd-dir /absolute/path/to/lie-cache \
--prefix-ssd-quota-mib 16384 --prefix-ssd-staging-mib 8192
```

LIE creates the final private directory; its parent must already exist.
The directory holds LIE-owned checkpoints. Its quota limits retained disk usage;
the staging budget bounds in-flight state transfers. Keep enough staging space
for one checkpoint. RAM and SSD can be enabled independently. SSD persistence
is **off unless explicitly configured**.

The default `--cache-policy ds4` captures reusable prompt checkpoints and applies
utility-based retention. `--cache-policy legacy` selects the earlier capture
schedule. The DS4 runtime payload is retained in RAM and written to SSD with a
LIE identity/integrity extension. This is not an extra high-ratio compression
codec, and importing arbitrary DS4 checkpoints is not yet qualified.

## Connect Pi

LIE accepts Pi's normal OpenAI provider over HTTP. Create a separate profile;
choose a new directory name if this one already exists:

```sh
mkdir -p run
mkdir -m 700 run/pi-profile
cp config/pi-unsloth.models.json run/pi-profile/models.json
cp config/pi-unsloth.settings.json run/pi-profile/settings.json
```

Edit `baseUrl` in `run/pi-profile/models.json` to
`http://SERVER-IP:8000/v1`. Set `contextWindow` to the server's configured
context. The included `apiKey` is a client placeholder, not server-side
access control. Start Pi with its installed executable:

```sh
env PI_CODING_AGENT_DIR="$PWD/run/pi-profile" PI_OFFLINE=1 PI_TELEMETRY=0 \
  pi --provider synapse-lie --model qwen3.8-flash-next --thinking off \
  --no-extensions --no-skills --no-prompt-templates --no-themes
```

Pi 0.87.1 completed a real read/edit/read tool round trip against the GPU server
on `192.168.5.157:8000`. This profile requires no Pi-specific server interface.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Readiness 503 or empty model list. | The model is still loading, no model was configured, or the build has no HIP provider. Read the server log. |
| Context-limit error. | Reduce the prompt or requested output, or raise `--context` within the supported limit. |
| No RAM cache hit. | The input must match a retained prefix; inspect the cache budget and eviction metrics. |
| No SSD checkpoint. | Check the absolute directory, quota and staging budget. Oversized states can be skipped. |
| No graph files. | Graph export requires Python and Matplotlib; the raw JSONL result remains available. |

Run `synapse-lie-server --help` or `synapse-lie-bench --help` for the complete
option list. See [metrics](../reference/METRICS.md) for runtime diagnostics.
