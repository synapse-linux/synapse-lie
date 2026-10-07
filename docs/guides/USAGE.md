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

For context above the model's native limit, select an explicit
[YaRN profile](CONTEXT.md). The configured ceiling is 1,048,576 tokens;
actual original-weight capacity depends on memory and GPU qualification.

## Directional steering

Experimental steering uses DS4-compatible layer-major `.f32` directions:

```sh
build/release/synapse-lie-server --model "$LIE_MODEL" --port 8000 \
  --dir-steering-file /path/to/directions.f32 \
  --dir-steering-ffn 1 --dir-steering-attn 0
```

Both scales are finite in [-100,100]. The flags set initial session defaults;
they do not change completed prompt/state. File defaults
are FFN 1 and attention 0; vector data has a 16 MiB admission budget. Use the same
file and initial scales after restart to reuse steered RAM/SSD prefixes. Omit the
file for ordinary inference. These controls also work in `--suite core` bench;
direct executor suites do not accept them. Initial and dynamic controls have host
tests; numerical GPU quality/performance qualification remains pending.

For an active request created with `store:true`, use its returned ID to submit a
live change. These `/steering` routes are LIE extensions to the two APIs:

```sh
LIE_REQUEST_ID=resp_ID_FROM_THE_RUNNING_REQUEST
curl --fail http://127.0.0.1:8000/v1/responses/$LIE_REQUEST_ID/steering \
  -H 'Content-Type: application/json' -d '{"ffn":-1,"attention":0.25}'
curl --fail http://127.0.0.1:8000/v1/responses/$LIE_REQUEST_ID/steering
```

For Chat Completions, use `/v1/chat/completions/CHAT_ID/steering`. With `n > 1`,
append the zero-based choice index, for example `/steering/1`; both GET and POST
then target that choice only. Omitting the index on a multi-choice request
returns **409**. Each choice has independent tickets, history and cache scope.
POST returns **202** with an admission `ticket`; GET reports `pending`,
`completed`, `last_result` and the last confirmed `policy`. Wait for
`completed == ticket` and status `0` before treating the change as applied.
`applied_position` is the retained physical boundary actually used. An already
selected call can finish first; this API does not promise the next output-token
index. A pending change or finished job returns **409**; an absent bank returns
**501** on POST. Both scales are required. Past state and sampled
corrections remain intact. Use a sufficiently long running request to exercise
the control before retirement.

To declare exact boundaries at creation, both APIs accept the LIE extension
`dir_steering_plan` with the same array as the native benchmark:

```json
{
  "dir_steering_plan": [
    {"position":0,"ffn":1,"attention":0},
    {"position":1024,"ffn":-1,"attention":0.25}
  ]
}
```

Positions count retained physical prompt/generated tokens. Supply 1–64 strictly
increasing integer positions and both finite scales in [-100,100]. The server
must have a direction bank. Each choice copies the plan and applies it through
the shared inference owner. The last position must precede the prepared prompt
length plus resolved output budget. GET `/steering` (or `/steering/{choice}`) returns the
declared plan, attempted/applied steps, actual positions and terminal status.
Early EOS can leave unapplied steps; inspect these results before treating the
plan as complete. A planned job refuses additional live changes. Plans also work
with `store:false`, but those requests have no retained control endpoint.

The native core bench also accepts `--dir-steering-plan FILE.json` for changes
at exact declared physical positions; see
[scheduled benchmarks](BENCHMARKS.md#scheduled-steering).
See [format and implementation](../development/STEERING.md).

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
request. Tool-enabled SSE publishes provisional starts and argument fragments;
clients execute only after successful final validation. See the
[agent and tool guide](AGENT-CLIENTS.md). Thinking is disabled. Inline PNG/JPEG image
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
| `--context 262144` | Maximum tokens per sequence, including prompt and reserved output; application range: 128–1,048,576; the model/profile sets the actual limit. |
| `--rope-scaling native` | Explicit rotary profile: `native`, `yarn2` or `yarn4`; see [context configuration](CONTEXT.md). |
| `--max-active 1` | Active sequences; set 2–8 to allow GPU decode batches when multiple requests are ready. |
| `--prefill-chunk 2048` | Maximum new prompt tokens per completed prefill call; range 1–32,768. |
| `--prefill-capacity N` | Scratch capacity reserved at model load; range 1–32,768, at least the initial chunk. Defaults to the initial chunk. |
| `--request-timeout-ms 600000` | Request deadline, in milliseconds; allow enough time for long prompts. |

The shared engine exposes `lie_core_set_prefill_chunk()` to change the chunk
while READY, within the reserved capacity. For HTTP, reserve room at startup,
for example `--prefill-chunk 2048 --prefill-capacity 32768`, then use the
management listener (default loopback port 19880):

```sh
curl http://127.0.0.1:19880/actuator/llm/prefill
curl http://127.0.0.1:19880/actuator/llm/prefill \
  -H 'Content-Type: application/json' -d '{"prefill_chunk":16384}'
```

The response reports `prefill_chunk`, `prefill_capacity`, `revision` and
`applies_to: "new_requests"`. A change affects subsequent admissions; active and
queued requests keep their original chunk. An unchanged value keeps its revision.
Exceeding the reserved capacity returns 409 without changing configuration.
This control is available only on the management port. Capacity cannot grow
without recreating the engine. Larger reservations increase provider scratch;
larger chunks can delay cancellation and other ready requests. The provider and
context bound actual calls; a larger chunk alone establishes no speedup.

Omitting `max_tokens`/`max_completion_tokens` in Chat or `max_output_tokens` in
Responses, or passing null, selects an automatic budget: remaining physical
context after the complete prompt/template, up to the advertised 4,096-token
engine output ceiling. Explicit positive limits are preserved; a prompt plus
explicit output that exceeds context is rejected instead of silently capped.
An explicit zero is invalid HTTP input. Natural EOS and stop strings still end
generation early. The resolved limit is available in Chat's
`lie_timings.output_token_limit` and the completed Responses object's
`max_output_tokens`, including stored replay. `/v1/models` and individual model
details advertise the configured `context_length` and `max_output_tokens`.

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

Both APIs accept the LIE sampling extensions `top_k` (integer 0..2147483647)
and `min_p` (number 0..1). Zero disables that filter. Null, strings, booleans and
out-of-range values are errors. Defaults remain `temperature:0`, `top_p:1`,
`top_k:0`, `min_p:0`; requesting the DS4 sampling profile is explicit:

```sh
curl http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3.8-flash-next","messages":[{"role":"user","content":"Hello!"}],"temperature":1,"top_p":1,"top_k":0,"min_p":0.05,"seed":123,"max_tokens":128}'
```

Responses uses the same candidate filters and retains supplied values in stored
response objects. Top-k limits candidate count; min-p drops candidates below
its fraction of the highest retained probability. These controls use the shared
core; original-weight qualification of this new client exposure is pending.

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
