# HTTP 256K capacity and real Pi tools on .157

The server now admits up to **262144 physical prompt plus reserved output tokens**,
8 MiB request bodies and 1024 messages. Actual original-weight requests and a
real Pi read/edit/read cycle passed. This does not establish 256K at eight
simultaneous sequences, independent model accuracy, cache reuse or complete
OpenAI platform coverage.

## Capacity qualification

`reactive-suite-r3`, server build `http256-r1`, source `9725832`, original read-only
Unsloth UD-Q4_K_XL, embedded pinned Gufo, context 262144, chunk 2048, max-active 1,
AR greedy, thinking/MTP off. `.157` CPU prerequisite: 20/20 debug and 20/20
ASan/UBSan. Three short JSON/SSE pairs also passed before the long cases.

| Request | Physical prompt | Actual output | Reserved output | HTTP body bytes | HTTP wall s | Executor PP s | Executor PP tok/s |
|---|---:|---:|---:|---:|---:|---:|---:|
| Chat JSON | 262075 | 1 | 32 | 1900013 | 189.857 | 189.570 | 1382.47 |
| Responses SSE | 262075 | 1 | 32 | 1900003 | 196.672 | Not exposed in terminal object | Not inferred |

Both returned exactly `READY`; Chat used 128 completed prefill calls. An oversized
physical prompt received `400 context_budget_exceeded` without another prefill
call. The 69-token gap to capacity is explicit; exact boundary/body/message
admission is covered separately by synthetic fixtures. This repeated-notes
prompt tests capacity, not long-context retrieval/reasoning quality. These are
single functional observations; CPU validation work overlapped part of the
Responses case, so they are not a controlled PP performance comparison.

The campaign later failed because Pi could not connect to LAN port 19879:
UFW's default-drop input chain did not permit that port. Model/server tests had
already passed. Both owned processes retired, KFD was empty and all four
unchanged lease files were free. No firewall setting was changed.

## Actual Pi acceptance on direct HTTP 8000

The operator selected port **8000**, already allowed by the firewall and free at
preflight. `reactive-suite-r4` reacquired the four leases, loaded the same server
binary and bound API `192.168.5.157:8000`, management `127.0.0.1:19880`.
The already installed **Pi 0.87.1** ran on client `.155`; model forward remained
entirely on the GPU `.157`. No tunnel, custom provider, package installation,
global Pi profile edit or permanent service was introduced.

A private Pi profile used standard `openai-completions`, thinking off, tools
`read,edit`, extensions/skills/templates/themes disabled. In a disposable private
directory Pi read `verification.txt`, changed only `status=pending` to
`status=verified`, read it again, and returned the previously unknown nonce.
Exact final bytes and the ordered successful three tool events were checked.
Four assistant turns ended toolUse/toolUse/toolUse/stop. Pi exit 0, client
wall **24.021 s**; prompt counts 4505/4607/4751/4853, output 54/87/54/27.
This proves a usable normal Pi tool cycle, not Pi operating at 256K history.

A collection-script race then read the SCP marker before upload completed,
raising JSONDecodeError. This was a harness defect after the independently
verified Pi success, not a successful overall campaign: `r4` remains FAILED.
Server exit 0, both owned helper/server PIDs absent, KFD empty and all four leases
free/unchanged. The following benchmark campaign uses fully staged input and no
transfer-polled marker; the Pi cycle is not unnecessarily repeated.

## Receipts and use

Versioned compact receipts:
[capacity](benchmarks/2026-10-01/http256/context-receipt.json) and
[Pi](benchmarks/2026-10-01/http256/pi-receipt.json).
Raw complete requests/responses/telemetry and failed attempts remain under
`evidence/reactive-suite-r3/`, `evidence/reactive-suite-r4/` and
`evidence/pi-http-r1/`. Collection manifests were SHA-256 verified before use.
The initial sandbox-denied Pi attempt and the subsequent network timeout are
preserved separately from the successful port-8000 attempt.

[SERVER-TOOLS.md](SERVER-TOOLS.md) gives the private Pi profile and supervised
server recipe. The profile points directly at `http://192.168.5.157:8000/v1`.
A completed qualification retires its server; it is not a permanent deployment.
Fresh use of the shared GPU still requires current coordinated admission.
