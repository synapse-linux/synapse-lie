<!-- SPDX-License-Identifier: MIT -->
# Vision development branch

`feature/vision` adds owned image inputs to the shared C17 core, Chat Completions,
Responses and the core benchmark client. The core contract is model-neutral.
The first real binding delegates image expansion, MRoPE, encoder execution and
model forward to the pinned Gufo Qwen3.8 Flash Next provider.

**Status:** CPU contract tests and HIP compilation/linking only. Original-weight
image understanding, memory fit and speed have not been qualified. GPU benchmarks
are postponed at the owner's request. MTP is developed on `feature/mtp`;
these two feature branches are not yet combined.

## Use

Build as described in the [build guide](../guides/BUILD.md). `LIE_VISION=ON` is the
default build option; `-DLIE_VISION=OFF` prevents image-job admission.

```sh
build/release/synapse-lie-server \
  --model /models/target-00001-of-00004.gguf \
  --model-vision /models/encoder.gguf \
  --model-id local-model --port 8000 --context 4096 --max-active 2 \
  --kv-cache-ram-mb 0
```

Create a request from a local PNG using standard shell tools:

```sh
image_base64=$(base64 -w0 image.png)
printf '{"model":"local-model","messages":[{"role":"user","content":[{"type":"text","text":"Describe this image."},{"type":"image_url","image_url":{"url":"data:image/png;base64,%s"}}]}],"max_tokens":128}' \
  "$image_base64" > request.json
curl http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' --data-binary @request.json
```

JPEG uses `data:image/jpeg;base64,`. Responses accepts the same inline data URL
in an `input_image` part's `image_url` string, next to `input_text` parts in the
user message. Both APIs support JSON and SSE. The first implementation accepts
`detail:auto` and `detail:high`; `detail:low`, remote URLs and file IDs are refused.
It does not fetch remote images or read paths supplied through HTTP.

For a direct core client with one image appended to a user prompt:

```sh
build/release/synapse-lie-bench --suite core \
  --model /models/target-00001-of-00004.gguf \
  --model-vision /models/encoder.gguf --image-file image.png \
  --prompt-file prompt.txt --context 4096 --chunk 2048 \
  --users 2 --tg 128 --repetitions 3 --kv-cache-ram-mb 0 \
  --output vision.jsonl --graphs vision-graphs
```

The benchmark records the encoded image hash, encoder path and expanded physical
token IDs. Image-bearing comparison inputs must match; token placeholders alone
cannot establish equal images. HTTP supports multiple image parts. These are
usage recipes, not a GPU run authorization on shared machines; follow
[coordination](../COORDINATION.md). Encoder and target must be compatible.

## Core and reactive behavior

`include/lie/vision.h` defines encoded PNG/JPEG spans, message placement and
versioned provider capabilities. `lie_core_request` ABI 3 includes images and
`lie_core_options.vision_model_path` configures admission. Submission deep-copies
encoded bytes and text. `text_offset` is a UTF-8 byte boundary; equal offsets
preserve image order. Input images belong to user messages.

Generic ceilings are 16 images, 8 MiB of encoded image bytes and 32 Mi pixels in
aggregate per request. Each provider may admit lower limits. HTTP additionally
limits the entire JSON body to 8 MiB, including base64 expansion. Header inspection
bounds admission; it is not a substitute for the provider's full PNG/JPEG decode.
The prepared prompt owns pixels, encoder identity and model-specific layout.
Context admission counts expanded physical tokens plus requested output before
creating/prefilling a sequence.

The existing device owner prepares/attaches the prompt; encoder work runs through
the provider's prefill path. Output credits, cancellation and lifetimes remain in
the common core, with no worker per image or HTTP-owned inference. CPU image
preparation and synchronous encoder calls are bounded but cannot be preempted.
Prefill time includes encoder work performed during prefill; CPU preparation is
included in client latency, not in executor-only prefill time. No speedup is
claimed from adding this input path.

## Cache and remaining gates

Current KVC state lacks the complete multimodal continuation state. Vision
therefore requires **explicit `--kv-cache-ram-mb 0` and no `--kv-disk-dir`**;
incompatible configurations are refused before loading a model. AR retains its
normal RAM-cache default. Text placeholders are never sufficient image identity.

Before integration: extend model-specific state and pixel/encoder/preprocessing
identity through the shared RAM/SSD lifecycle; qualify image/text histories,
physical positions, quality, cancellation, same-image reuse, different-image
refusal and restart on original weights. Account decoded pixels, embeddings,
encoder residency and temporary workspace on the target. Additional real model
families need their own image expansion/encoder bindings, not Qwen logic in core.

The numerical source remains official Gufo
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, with the existing LIE state-access
variant. No numerical kernels or DS4 project files were changed. Two synthetic
providers with different image limits and token expansion exercise the generic
contract; these fixtures are **NOT-INFERENCE**. See the
[validation receipt](validation/vision-2026-10-03.json).
