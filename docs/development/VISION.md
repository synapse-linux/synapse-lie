<!-- SPDX-License-Identifier: MIT -->
# Vision development

`feature/vision` adds owned image inputs to the shared C17 core, Chat Completions,
Responses and the core benchmark client. The core contract is model-neutral.
The first real binding delegates image expansion, MRoPE, encoder execution and
model forward to the pinned Gufo Qwen3.8 Flash Next provider.

**Status:** original-weight functional checks pass on `.157` with the mixed
Q8/F16 projector and C17 upload decoder: image color semantics, image-scoped RAM
reuse, combined MTP state and SSD restore in a new process. The
[GPU receipt](validation/vision-mtp-gpu-2026-10-03.json) records the tested
checkpoint (`bec0955`), scope and retained failures. The newer sampler/vision
integration awaits GPU retesting. Independent quality, allocation-exact memory fit and
performance qualification remain open. [Joint configuration](../guides/USAGE.md#mtp-with-images)
uses the same core, reactive output flow and RAM/SSD state.

The separate [Strix Point direct-core gates](../benchmarks/models/qwen3.8-flash-next/strix-point/README.md#direct-reactive-core-and-q8-vision-gates)
now pass on `.161` with the copied original Q8 projector, once in AR and once
with Q8 MTP. They use the same 224×224 PNG, expand to identical 92 physical
tokens and produce identical 13 output IDs; MTP accepts 8 drafts. The Point
benchmark records token IDs rather than decoded text, so this result verifies
the image execution path and AR/MTP parity, not color recognition quality.
Its one-sample prefill/decode values are observations, not a speed claim.

## Use

Build as described in the [build guide](../guides/BUILD.md). `LIE_VISION=ON` is the
default build option; `-DLIE_VISION=OFF` prevents image-job admission.

The Qwen binding accepts BF16 dense projector weights, or F16/Q8_0 with
`LIE_VISION_WEIGHT_DECODE=ON` (default). Small normalization/bias/patch tensors
remain F32. This option must match in the provider and application builds;
`OFF` retains BF16-only admission. Model dimensions and preprocessing still
must match the target; a file named `mmproj` is not sufficient.

```sh
build/release/synapse-lie-server \
  --model /models/target-00001-of-00004.gguf \
  --model-vision /models/encoder.gguf \
  --model-id local-model --port 8000 --context 4096 --max-active 2
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
  --users 2 --tg 128 --repetitions 3 \
  --output vision.jsonl --graphs vision-graphs
```

The benchmark records the encoded image hash, encoder path and expanded physical
token IDs. Image-bearing comparison inputs must match; token placeholders alone
cannot establish equal images. HTTP supports multiple image parts. These are
usage recipes, not a GPU run authorization on shared machines; follow
[coordination](../COORDINATION.md). Encoder and target must be compatible.

## Core and reactive behavior

`lie/weight_decode.h` is a separate model-neutral C17 buffer contract, ABI 1.
It decodes little-endian F16 or GGML Q8_0 blocks into caller-owned BF16 codes,
with nearest/even rounding, bounded lengths and no allocation. Invalid lengths,
overlap, nonfinite values or insufficient capacity fail before any output write.
It has no model-forward, file, GPU, HTTP or scheduling dependency and is reusable
by other executors. It does not recover weights lost during quantization.

The transitional vision adapter decodes one tensor at a time during the first
image upload and waits for that upload before releasing its staging buffer.
The projector remains BF16 on the GPU and uses the existing pinned kernels;
later requests reuse those resident weights. Disk model files remain unchanged.
Device residency is larger than the quantized file; host staging is bounded by
one dense tensor. GPU resource and performance qualification must measure these
costs separately from prompt preparation, image encoding and decode throughput.

`include/lie/vision.h` defines encoded PNG/JPEG spans, message placement and
versioned provider capabilities. `lie_core_request` ABI 5 includes images and
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

The C state codec now retains the DS4 MRoPE delta and physical position rows,
and requires an exact comparison with independently prepared expected positions
before restore admission. Noncanonical states cannot enter the ordinary text-only
path. Fixtures reject changed rows, reserved/negative lanes, truncated input and
overlapping capture spans, and retain the complete position payload across SSD
restart. Typed auxiliary storage is shared with other model features.

RAM retention now uses its normal 4 GiB default for a complete-state vision
provider. Only SSD persistence is opt-in. Configure `--kv-disk-dir`,
`--kv-disk-space-mb` and `--kv-disk-staging-mb` as in the
[cache guide](../reference/SSD-PREFIX.md). An incomplete provider refuses READY
when either cache is enabled; explicitly setting RAM to zero permits uncached
vision. There is no implicit downgrade.

The model-neutral `LIE_STATE_CACHE_SCOPE` component binds the entire prepared
image prompt. Qwen obtains its SHA-256 from decoded/resized pixels, ordered grid
placements, the preprocessing version and the actual encoder identity. Tokens
remain a separate key. RAM lookup, deduplication, retention/protection and SSD
filenames/index/restart all compare this scope. A changed image with identical
physical tokens produces a miss before device mutation. Text-prefix suffix
retokenization is disabled for image jobs, since it cannot rebuild image input.

Full-prompt scope is deliberately conservative: changing a future image also
prevents reuse of an earlier prefix. This version does not persist pixels or
encoder embeddings. After restart, the client must supply the matching images;
the prepared prompt remains owned by its destination sequence. The binding
validates every saved position against that prompt and restores the device MRoPE
layout before publishing a usable frontier. Generated rows use the same prepared
layout and delta. Numerical uploads complete on the existing device owner,
with the destination's fresh sampler/RNG. No request thread is added.

The RAM representation is `[unchanged DS4 tensor payload][8-byte LIESCP1
marker][32-byte semantic scope]`. On SSD the unchanged client trailer precedes
that typed auxiliary extension and the existing authenticated table/footer.
All bytes are charged. Plain AR files and their names remain byte-compatible.
KVC state stays raw, as required by DS4; aligned synthetic scoped state also
bypasses optional packing so its scope remains available without expansion.

Native ASan/UBSan/LeakSanitizer checks pass **30/30**, including two model
fixtures, equal-token/different-image and placement misses, RAM hits, process
restart for both KVC and aligned storage, MRoPE/scope rejection and Chat/Responses
JSON/SSE reuse. An independently materialized source variant builds and the HIP
server/bench link. These are NOT-INFERENCE checks. See the
[cache validation receipt](validation/vision-cache-2026-10-03.json).

The original-weight follow-up passes **20 combined HTTP assertions**, including
equal-length red/blue prompts, changed-image cache misses and exact same-image
reuse. RAM and new-process SSD continuations preserve the full logits frontier,
confirmed tokens and MTP counters. Greedy MTP also matches a fresh forced-AR
control from the same provider. These checks use 256-pixel color fixtures and
one prompt family; they do not establish general image understanding.

Remaining gates are independent vision quality, image/text histories, image
in-flight cancellation and fault behavior, allocation-exact resource fit and
matched performance. Account decoded pixels, embeddings, BF16 encoder residency
and workspace separately. The pinned encoder already reports a BF16-reference
quality discrepancy in its [pinned upstream evaluation](https://github.com/gufo-org/gufo/blob/f783fedb9bea2ec7de941f6da4e02f4a4596b29e/docs/models/qwen3.8-flash-next/QUALITY.md); passing color fixtures
does not resolve it. Additional real models need their own image bindings.
No fresh-prefill or reactive speedup is claimed.

The GPU numerical source remains official Gufo
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, with the existing LIE state-access
variant plus the exact vision-upload edits. No GPU kernels or DS4 project files
were changed. The C17 decoder passes every finite F16 value and **16,252,928**
Q8 scale/value combinations against the independently acquired pinned Gufo
decoder and encoder rounding boundary. The native sanitizer suite passes
**44/44**. The [host validation receipt](validation/vision-weight-decode-2026-10-03.json)
binds source/provider identities and actual command exits. These checks are
**NOT-INFERENCE**. Two synthetic
providers with different image limits and token expansion exercise the generic
contract; these fixtures are **NOT-INFERENCE**. See the
[validation receipt](validation/vision-2026-10-03.json).
The subsequent state-codec checks are recorded separately in the
[state validation receipt](validation/vision-state-2026-10-03.json).

Combined integration validation is recorded in the
[source-bound receipt](validation/mtp-vision-integration-2026-10-03.json).
