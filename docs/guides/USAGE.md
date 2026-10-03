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
publisher terms. Experimental [MTP](../development/MTP.md) and
[vision](../development/VISION.md) require compatible explicit predictor and
projector files. Their original-weight and combined GPU qualification is pending.

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

A Responses request (`store=false` keeps this example stateless):

```sh
curl --fail http://127.0.0.1:8000/v1/responses \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3.8-flash-next","input":"Write a short greeting.","store":false,"max_output_tokens":128,"temperature":0}'
```

Clients execute function tools and submit correlated tool results in the next
request. Tool-enabled SSE publishes a complete validated turn; function arguments
are not streamed incrementally. Thinking is disabled. Inline PNG/JPEG image
parts are available with explicit vision admission; see the
[vision guide](../development/VISION.md#use). The
[API reference](../reference/OPENAI-REACTIVE.md) lists supported fields and error behavior.

## MTP with images

Configure both sidecars to use MTP verification on image-bearing requests:

```sh
build/release/synapse-lie-server \
  --model /models/target-00001-of-00004.gguf \
  --model-mtp /models/predictor.gguf --mtp-draft-tokens 0 \
  --model-vision /models/projector.gguf \
  --model-id local-model --host 127.0.0.1 --port 8000 \
  --context 4096 --max-active 2
```

The HTTP image request is the same as in the [vision guide](../development/VISION.md#use).
RAM KV retention keeps its 4 GiB default; SSD remains opt-in through `--kv-disk-dir`
and its budgets. Reuse after restart requires the matching images again.
Changed images, placement, predictor, projector or draft policy cannot reuse
that state. Prefix restore starts with the new request's sampler.

The direct shared-core client accepts the same combination:

```sh
build/release/synapse-lie-bench --suite core \
  --model /models/target-00001-of-00004.gguf \
  --model-mtp /models/predictor.gguf --mtp-draft-tokens 0 \
  --model-vision /models/projector.gguf --image-file image.png \
  --prompt-file prompt.txt --context 4096 --chunk 2048 \
  --users 2 --tg 128 --repetitions 3 \
  --output mtp-vision.jsonl --graphs mtp-vision-graphs
```

These commands describe the integrated development path. Compatible complete
weights and coordinated GPU ownership are required for GPU qualification.
The current integration is covered by native fixtures and HIP build/link tests.

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

## KV cache in RAM and on disk

RAM retention uses a lazily allocated 4 GiB budget by default. Use
`--kv-cache-ram-mb 0` to disable it, or a larger value for more retained
checkpoints. This cache reuses matching prompts; it does not eliminate the
prefill of a new prompt.

To persist KV checkpoints on disk, add these options to the server command:

```sh
--kv-disk-dir /absolute/path/to/lie-cache \
--kv-disk-space-mb 16384 --kv-disk-staging-mb 8192
```

LIE creates the final private directory; its parent must already exist.
The directory holds LIE-owned checkpoints. Its quota limits retained disk usage;
the staging budget bounds in-flight state transfers. Keep enough staging space
for one checkpoint. RAM and SSD can be enabled independently. SSD persistence
is **off unless explicitly configured**. Experimental MTP follows the same
cache defaults when its provider admits complete predictor state; see the
[MTP guide](../development/MTP.md#cache-and-remaining-gates) for configuration
and qualification limits.

All `--kv-*` options configure inference state, never model weights. Budget
options ending in `-mb` use binary MiB (1,048,576 bytes). These names also apply
to `synapse-lie-bench --suite core`; the state suite accepts the disk options
and `--kv-disk-mode write|read`.

| Option | Purpose | Default |
| --- | --- | --- |
| `--kv-cache-ram-mb N` | Retained KV checkpoints in RAM; zero disables retention. | `4096` |
| `--kv-disk-dir PATH` | Private directory for persistent KV checkpoints. | Disabled |
| `--kv-disk-space-mb N` | Maximum retained KV disk space. | Required with directory |
| `--kv-disk-staging-mb N` | RAM budget for KV disk transfers. | Required with directory |
| `--kv-cache-min-tokens N` | Minimum reusable prefix length. | `512` |
| `--kv-cache-cold-max-tokens N` | Cold checkpoint capture threshold. | `30000` |
| `--kv-cache-continued-interval-tokens N` | Interval between continued checkpoints. | `10000` |
| `--kv-cache-boundary-trim-tokens N` | Tail tokens excluded from stable boundaries. | `32` |
| `--kv-cache-boundary-align-tokens N` | Alignment of stable boundaries. | `2048` |

The disk and boundary names follow [DS4's server options](https://github.com/antirez/ds4/blob/main/docs/SERVER.md#disk-kv-cache).
The RAM and staging budgets are LIE controls. Retention budgets do not limit the
live state required by active requests. The old `--prefix-cache-mib`,
`--prefix-ssd-*` and `--cache-*` spellings remain compatibility aliases.

Future persistence or streaming of **model weights** will use the separate
`--model-*` namespace. It is not implemented or enabled by any KV option.

The default `--kv-cache-policy ds4` captures reusable prompt checkpoints and applies
utility-based retention. `--kv-cache-policy legacy` selects the earlier capture
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
| No graph files. | Read the native report error and select a new output directory. Failed evidence is rejected; raw JSONL remains available. |

Run `synapse-lie-server --help` or `synapse-lie-bench --help` for the complete
option list. See [metrics](../reference/METRICS.md) for runtime diagnostics.

## Generation controls and stored responses

Chat accepts `n`, `stop`, `logit_bias`, `logprobs`, `top_logprobs`, and
`response_format`. Responses uses `text.format` for JSON/schema constraints and
`top_logprobs` for optional probability reporting. Strict functions use
`strict:true` in their definition. Unsupported schema features are errors.

```sh
curl http://127.0.0.1:8000/v1/responses \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3.8-flash-next","input":"Hello!","background":true}'

# Replace RESPONSE_ID with the id returned by the request.
curl http://127.0.0.1:8000/v1/responses/RESPONSE_ID
curl -X POST http://127.0.0.1:8000/v1/responses/RESPONSE_ID/cancel
curl -X DELETE http://127.0.0.1:8000/v1/responses/RESPONSE_ID
```

Continue a stored response by setting `previous_response_id` and supplying the
next input; supply current instructions explicitly. Retrieve normalized inputs
through `/v1/responses/RESPONSE_ID/input_items?limit=20&order=asc`. Pagination uses
`after` with the previous page's `last_id`. Stored Chat completions also support
GET/list, DELETE, metadata update and `/messages`. Filter completion lists with
`?model=MODEL&metadata%5Btask%5D=VALUE&limit=20`.

To reconnect to a response stream, supply the last received event number:

```sh
curl --no-buffer 'http://127.0.0.1:8000/v1/responses/RESPONSE_ID?stream=true&starting_after=12'
```

With `"truncation":"auto"`, LIE removes oldest complete conversation turns
until the prompt and requested output fit. System instructions and the latest
user turn remain. The default `"disabled"` policy returns a context error.

Records use RAM and expire after one hour by default. Configure their independent
bounds with `--response-store-ram-mb`, `--response-store-records` and
`--response-store-ttl-seconds`; these options do not control the KV cache. Use
`store:false` for repeated benchmarks. See the [API coverage and limits](../reference/OPENAI-REACTIVE.md).
