# Native server tools and Pi with Unsloth

> Historical technical record. See [current usage](../guides/USAGE.md) and
> [benchmark tables and graphs](../benchmarks/README.md). Results below retain
> their original build, protocol and limitations.

## What changed

Tool support belongs to the C17 server, not a Pi-specific extension. HTTP accepts
OpenAI function declarations, assistant calls and correlated tool results. C17
owns validation, response parsing, IDs, JSON/SSE and limits. The adapter translates
LIE-owned structured data into the **existing pinned Qwen template**; it does not
modify model weights or numerical kernels. Gufo remains a delegated engine.

Tools are **executed by the client**, with that client's permissions. Nothing in
the server spawns a shell, reads a requested tool path or loads tool code. The explicit development profile uses the operator-selected LAN listener
192.168.5.157:8000; the dummy Pi key is not authentication. Management stays
on loopback.

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

The earlier synthetic Pi fixture failure remains historical evidence. The current
profile advertises 262144 total context, 8 MiB requests and a 2048 output budget.
Original-weight Chat JSON and Responses SSE now pass at 262075 prompt tokens.
Installed Pi 0.87.1 has completed the real read/edit/read cycle over direct LAN
HTTP on `.157:8000`: four model turns, three successful tools, exact file/nonce
verification, 24.02 seconds. No custom Pi provider extension or dependency install.
The 19879 attempt failed at the firewall before inference; its evidence is kept.
See [HTTP 256K and Pi qualification](HTTP-256K-PI.md) for scope and receipts.

## Exact functional limits

[HTTP.md](../reference/HTTP.md) is the wire contract. Requests are at most 8 MiB / 1024 messages;
output is at most 4096 tokens, and **physical prompt plus requested output must fit
context**. No silent truncation. Per-sequence sampling and native AR decode batching are
implemented; reasoning, vision, MTP, prefix reuse and SSD session storage are not. Tool history is re-prefilled.
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
  context 262144, default output budget 2048 (server ceiling 4096).
- `config/pi-unsloth.settings.json`: only this provider/model, thinking off,
  no packages, auto compaction disabled for the initial session, no agent/provider
  retries. Provider timeout 630 seconds allows the server's 600-second deadline.

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
build/http256-r1/synapse-lie-server --model "$MODEL" \
  --context 262144 --prefill-chunk 2048 --max-active 1 \
  --host 192.168.5.157 --port 8000 \
  --management-host 127.0.0.1 --management-port 19880 \
  --request-timeout-ms 600000
```

The command is a supervised child recipe, not a permanent deployment. The
qualified server binary and run manifest are retained under LIE-owned `.157`
`run/reactive-suite-r4/http/`; a new model run still requires fresh lease admission.
Pi connects directly to `http://192.168.5.157:8000/v1`; no tunnel is needed.
Port 8000 was already allowed by the existing firewall, which was not modified.
End a run by stopping only its supervised server and waiting for retirement
before releasing leases. No permanent listener is promised by a completed test.
