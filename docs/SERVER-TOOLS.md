# Native server tools and Pi with Unsloth

## What changed

Tool support belongs to the C17 server, not a Pi-specific extension. HTTP accepts
OpenAI function declarations, assistant calls and correlated tool results. C17
owns validation, response parsing, IDs, JSON/SSE and limits. The adapter translates
LIE-owned structured data into the **existing pinned Qwen template**; it does not
modify model weights or numerical kernels. Gufo remains a delegated engine.

Tools are **executed by the client**, with that client's permissions. Nothing in
the server spawns a shell, reads a requested tool path or loads tool code. Use a
trusted local client and loopback listeners; the dummy Pi key is not authentication.

## Verified now, and what remains

- `server-tools-final-cpu-r1`: 15 CPU suites with ASan/UBSan, including native JSON/SSE
  tool replies, history, typed arguments, whitespace, malformed/truncated output,
  refusals, nested nonfinite values, cancellation of buffered tool output,
  protocol-error counters, retirement and text-serving lifecycle tests.
- `server-tools-linked-r2`: new HIP-linked executable and 16 CPU suites, including
  translation into the actual Qwen formatter. Original `gufo-qwen-host-r2` archives
  stay unchanged. GPU visibility was masked; no weights or GPU forward were used.
- `server-tools-pi-cpu-r4`: installed Pi, **standard `openai-completions` provider**,
  actual built-in `read`, its file result returned to the server, final reply.
  Separate synthetic executor; no custom extension or global Pi changes.

The first Pi fixture (`server-tools-pi-cpu-r1`) failed: a 4096 context equals the
installed Pi SDK's 4096-token safety margin, forcing `max_tokens:1` before the
prompt estimate. Only `<` was generated, not a tool call. The failed trace is
retained. Server/client context now matches at **32768**; Pi itself is unchanged.

**Not yet verified:** Unsloth generating usable tool calls, a real read/edit/read
session, memory at 32768 context, updated serving behavior or matched performance.
The earlier original-model smoke/lifecycle/PP-TG records are historical evidence,
not tests of this new executable. A fresh [coordinated window](COORDINATION.md) is
required before the model run. No remote staging, deployment or permanent listener
was performed. The rejected client draft is archived, not active source.

## Exact functional limits

[HTTP.md](HTTP.md) is the wire contract. Requests are at most 1 MiB / 128 messages;
output is at most 4096 tokens, and **physical prompt plus requested output must fit
context**. No silent truncation, stochastic sampling, reasoning, vision, native
batching, MTP, prefix reuse or SSD session storage. Tool history is re-prefilled.
No constrained sampling/full JSON-Schema guarantee; `strict:true` is refused.

Tool-enabled responses buffer the complete turn after the SSE role header.
Only after successful parsing are content and structured calls emitted, then
`finish_reason:tool_calls`, optional usage and DONE. This is valid SSE, **not
incremental argument/text streaming on tool-enabled turns**. Ordinary requests
without tool declarations retain incremental text streaming/backpressure.

Malformed, ambiguous, disabled, unlisted, incomplete or budget-truncated calls
produce an error, not executable fragments or a text fallback. Raw Qwen framing
inside string arguments is not representable unambiguously and is refused.
Client-side full schema validation and tool safety policy are still necessary.
Protocol failures increment `llm.responses.tool_errors` separately from completed
generation; they do not poison an otherwise healthy numerical executor.

## Normal Pi configuration — separate from starting the server

The checked-in examples are:

- `config/pi-unsloth.models.json`: normal compatible endpoint, text-only Unsloth,
  context 32768, default output budget 2048 (server ceiling 4096).
- `config/pi-unsloth.settings.json`: only this provider/model, thinking off,
  no packages, auto compaction disabled for the initial session, no agent/provider
  retries. Provider timeout 330 seconds allows the server's 300-second deadline.

Create an **exclusive private profile**, never overwrite the user's Pi files:

```sh
# On the client, from the repository root. Choose a fresh profile path.
(
  set -eu
  PROFILE="$PWD/run/pi-unsloth-profile-r1"
  mkdir -p "$PWD/run"
  mkdir -m 700 "$PROFILE"               # refusal stops before either copy
  cp config/pi-unsloth.models.json "$PROFILE/models.json"
  cp config/pi-unsloth.settings.json "$PROFILE/settings.json"
  exec env PI_CODING_AGENT_DIR="$PROFILE" PI_OFFLINE=1 PI_TELEMETRY=0 \
    pi --provider synapse-lie --model qwen3.8-flash-next --thinking off \
       --no-extensions --no-skills --no-prompt-templates --no-themes
)
```

This starts **only Pi**, not inference. Its configured endpoint must already be
ready. `PI_OFFLINE` suppresses automatic catalog/version networking, not requests
to the configured local inference endpoint. Start a fresh session before limits
are exhausted; neither this profile nor the server silently compacts history.
Review all tool permissions before using Pi in a real project.

On the target, the new server's child command under an admitted supervisor is:

```sh
# AFTER current admission, verified staging and private HOME/cache setup.
# MODEL is the original read-only Unsloth first shard, not an antirez Q2 file.
build/server-tools-linked-r2/synapse-lie-server --model "$MODEL" \
  --context 32768 --prefill-chunk 2048 --max-active 1 \
  --host 127.0.0.1 --port 19879 \
  --management-host 127.0.0.1 --management-port 19880 \
  --request-timeout-ms 300000
```

The path above currently identifies a **local build**, not an installed .157
binary. Do not run an old text-only build under the new profile or expose the
unauthenticated service on the LAN. For a .155 client and .157 loopback server,
a foreground SSH tunnel may forward the chosen free client port to target
`127.0.0.1:19879`; update `baseUrl` if the local port differs. No tunnel was opened
by this change. End an admitted run by stopping only its supervised server and
waiting for retirement before releasing leases; stop Pi/the owned tunnel normally.

Next acceptance is one bounded real-Unsloth session in a disposable directory:
read an unpredictable file value, make a requested edit, read back the changed
file, and check tool events plus final contents. Stop at the first failure; no
fallback, unrelated optimization campaign or synthetic substitute for that verdict.
