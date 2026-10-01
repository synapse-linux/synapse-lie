# Replacement plan — use Unsloth now, measure before another Q2 port

## Rollback boundary

The owner rejected the Q2 porting effort and requested a restart. Active code,
recipes, optional builds and tests introduced after `4307486` are removed. This
includes the layout-inspection tooling for that effort. Runtime/server C17,
reactive lifecycle, metrics, original Unsloth/Gufo integration and C1 evidence
remain. No Git history, local evidence, qualified archive or model is erased.
The Q2 reports describe the withdrawn experiment, not available source/features.

## 1. Immediate delivery: Unsloth through Pi

Use the existing original-weight UD-Q4_K_XL executable, without Q2 modifications
or new numerical work. Make a separate local Pi profile, prove an actual tool
call/result/follow-up, and provide start/use/stop commands. No text-only demo
masquerading as a coding agent. Preserve the main Pi configuration and DS4.
The owner explicitly requires completing the server, not a Pi-specific protocol
bridge. Implement OpenAI tool messages/calls/results in the C17 server and use
the existing Qwen template inside the adapter, without numerical changes. Pi must
use ordinary compatible-endpoint configuration. Expose real limitations. Success
means a usable session and observed tool execution, not configuration alone.

## 2. Deferred Q2 restart: reference first

Independently acquire/pin an official implementation already supporting the exact
antirez Q2 artifact. Do not select Gufo by assumption, reuse the withdrawn patch,
or execute the sibling project's mutable binary. First establish real output,
full fresh PP and TG on that reference. If it cannot run, report the concrete
blocker before creating a new port. No source hashes beyond normal Git identity;
retain external artifact identity and raw measurements where needed.

## 3. Smallest integration, immediate comparison

Choose the smallest path behind LIE's existing C ABI that can use the proven
reference implementation. Keep delegation explicit; this does not fulfill the
owned C17 executor goal. First load/generate and compare at the reference's exact
physical IDs, weights, template, context 9216, chunk 2048, greedy/EOS/completion
semantics. Then PP targets 512/2048/8192 and TG up to 128, retaining warmups and all
samples. Test the same UD before/after if shared code changes. HTTP/TTFT is separate.

## 4. Stop/go before expanding

Declare the acceptable PP/TG comparison and observed variability before modifying
the candidate. No invented universal Q2=Q4 target. No promotion with an unexplained
performance loss; report it immediately and decide whether to discard the path or
run one bounded, diagnosed experiment. Do not substitute synthetic suite counts
for the model verdict or begin another open-ended adaptation campaign.

Only a working, compared integration unlocks broader format/quality/lifecycle
qualification and any T1/T2 ownership work. Q4, caches, SSD, MTP, batching and CUDA
are deferred, not silently canceled or implemented. Every GPU/load/heavy-I/O run
still needs current coordinated admission; a saved plan is not that authorization.
