# Shared reactive C core — first extraction

The subsequent [original-weight GPU regression](CORE-GPU-RESULT.md) passes the
first extraction gate through C8 and 131072-token fresh prefill. The CPU-only
receipt below records the earlier implementation checkpoint, not the later run.

Receipt date: 2026-10-02. Source base: `2ba01ed`, with the exact tested source
inventory retained in local `evidence/reactive-cpu-r7/source.json`.
Source capsule SHA-256: `300e889cabca97d18c3a6d5543c6c4d39b48b71ec719fee451abebcf2c0dc8aa`.
All compilation and execution in this increment ran on **192.168.5.157**, in
persistent LIE-owned `run/reactive-cpu-r7`, with GPU visibility masked.

## Implemented boundary

`lie_core` is a C17 static library, not an HTTP server or a second provider.
It owns asynchronous model open/stop, copied normalized messages/tools or raw
text/physical tokens, bounded admission, sequence configuration/prefill/decode,
ready-row batching, cancellation, demand, job snapshots and retirement.
Provider implementations still supply the existing executor ABI; Gufo retains
its numerical Model/Session/tokenizer/sampler ownership.

`lie_runtime` contains Chat/Responses parsing, tool-output interpretation and wire
formatting. `worker_http.c` bridges the legacy HTTP request into the neutral core
and frees the parsed request after successful admission. No JSON object, socket
or SSE option is stored in a core job. Tool schema strings are copied model data.
The core builds and links with a fixture provider without json-c, libuv, llhttp,
libcurl or an HTTP executable. Its current OS primitives are pthreads/eventfd.

`--suite core` in `synapse-lie-bench` is an actual direct client of this lifecycle,
not a renamed executor benchmark. It supports raw UTF-8 or exact physical-token
replay, C1 through C8, repetitions/warmups, first confirmed token and total client
latency, per-job completed prefill/decode durations and common-window throughput.
It exports JSONL witnesses and optional SVG/PNG/CSV/JSON. It rejects failed or
incomplete evidence for aggregation. Existing low-level executor and HTTP suite
labels and numerical scope remain distinct. See [usage](BENCHMARKING.md#direct-shared-core-suite).

## Preserved reactive semantics

One device-owner thread selects ready rows. Eight initial output credits per
job and eight bounded token loans limit run-ahead; releasing a loan and returning
credit permits more work. A blocked row does not block a peer with credit.
Multiple ready rows use the existing native decode dispatcher; C1 dispatches
without waiting for a batch. Prefill uses bounded completed chunks, and submitted
provider calls remain synchronous. Cancellation is a protected latch and safe
retirement, not kernel preemption. Thread count and provider numerical execution
were not tuned.

The new input copy executes during submission, outside the scheduler gate, after
reserving an admission slot. This adds allocation/copy cost to HTTP admission;
its net effect is now covered by the matched HTTP/core [GPU run](CORE-GPU-RESULT.md),
although input-copy time is not isolated as a separate metric. Input arena storage
is capped at 32 MiB per job. Prompt/output witnesses stay alive until the final
consumer reference and must be released by the client. No allocation-exact
resource accounting or reusable KV cache is implied by retaining token IDs.

## Verification

| Configuration | Result | CTest wall time |
|---|---|---:|
| Headless `LIE_CORE_ONLY=ON`, protocol package discovery disabled | 1/1 passed | 0.05 s |
| Full Debug, `LIE_GUFO_RUNTIME=OFF` | 23/23 passed | 26.54 s |
| Full Debug with ASan/UBSan | 23/23 passed | 28.09 s |

All nine configure/build/test commands returned 0; builds used `-j2` and
`-Wall -Wextra -Wpedantic -Werror`. Headless CMake reports the intentionally unused
PkgConfig-disable variable because that branch returns before dependency lookup.
`result.json`, all command logs, archive hash verification, source inventory and
the exact private runner are retained under local `evidence/reactive-cpu-r7/`.
The two active project threads coordinated a CPU window; no GPU job or model
read was launched for this receipt.

Headless fixtures check caller mutation after submit (including nested tool
arguments/schema strings), physical token witnesses, invalid input and vocabulary
refusal before sequence mutation, stopped demand, peer progress, native batch
selection and cancellation with a pinned output loan. Existing HTTP tests cover
Chat/Responses, tools, 256K admission, errors, timing, disconnect and shutdown.
The six core benchmark checks pass in each full configuration, including raw text,
physical replay, EOS, failed evidence, exclusive output, corrupted report rejection
and actual graph export. These are CPU fixtures, visibly **NOT-INFERENCE**.

Pi/node were not available through the runner's installed-tool discovery, so no
new Pi client check ran. Previous Pi/GPU receipts remain historical and are not
reassigned to this binary. No original-weight HIP link, numerical/performance,
GPU failure, TSan or independent review qualification is claimed here.

## Next acceptance and roadmap

1. **Completed:** coordinated supervisor core input identity/manifest binding,
   with source-bound CPU/sanitizer checks (`reactive-cpu-r9`).
2. **Completed for this slice:** unchanged-provider GPU comparison across HTTP,
   direct core and executor, C1/2/4/8 and 8192/131072 fresh tokens. See the
   [full result and remaining limits](CORE-GPU-RESULT.md). Numerical ownership,
   256K requalification and 1M execution are not covered by this gate.
3. Complete neutral engine semantic events as clients need them: tool-frame
   interpretation is still in the protocol library; scoring/logit operations are
   not yet a core capability. Future chat/eval must not duplicate model semantics.
4. Add C-owned RAM prefix policy and complete hybrid capture/restore through this
   core, then explicit opt-in SSD persistence with separate quotas and bounded I/O.
   Token witnesses do not restore attention/recurrent state.
5. Add MTP verified bursts and vision inputs under the same demand/resource rules;
   progressively replace delegated numerical/model responsibilities with qualified
   C contracts. One-million-token execution remains a separate capacity/RoPE/quality
   gate. The Q2 compatibility work proceeds independently on its own feature branch.

No cache, MTP, vision, extra CPU thread pool, platform provider or new performance
gain is introduced by this extraction. No upstream source/model, DS4 artifact,
service configuration or published branch was changed.
