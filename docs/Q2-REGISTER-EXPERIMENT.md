<!-- SPDX-License-Identifier: MIT -->
# Q2 integer scheduling experiment

Status: prepared; target GPU correctness and performance are pending the core
thread's explicit handover. No speedup or numerical pass is claimed yet.

The qualified original Q2 phase trace reports 320/860/1196 private bytes per
work item for down-projection tiles 32/48/64. These kernels account for
1382.876 ms of the measured 3364.126 ms prefill kernel total. UD's routed kernels
have no private allocation in the same diagnostic. Private size alone is not
executed spill traffic; this motivated an assembly inspection.

## Local static screening

Device-only compilation uses the installed AMD clang 22 toolchain and gfx1151
code generation, without executing a GPU program or loading weights. The flags
match the upstream MMQ target's optimization and language settings. The local
compiler is not a substitute for the target build. Its tile48/64 baseline
allocation differs slightly from the retained target profile (848/1204 versus
860/1196 bytes). Compare each candidate to its matching local baseline only.

| Q2 tile columns | Baseline private B/item | Token-tile barrier B/item | Bounded K loop B/item | Bounded K loop VGPRs |
| --- | ---: | ---: | ---: | ---: |
| 16 | 296 | 516 | 0 | 112 |
| 32 | 320 | 176 | 0 | 123 |
| 48 | 848 | 456 | 0 | 160 |
| 64 | 1204 | 0 | 0 | 187 |
| 80 | 2764 | 0 | 0 | 217 |

The baseline allocates 256 VGPRs for all these Q2 widths and contains static
scratch load/store instructions. The bounded K loop has no scratch instructions
for any of them. Instruction counts are static, not dynamic memory measurements.
The first barrier variant improves some widths but increases tile16 scratch;
it is retained in `experiments/q2-token-barrier.patch` for the experiment record
and is not in the active runtime. `config/q2-register-static.json` retains the
metadata, instruction counts and local command-receipt paths.

The active change adds `#pragma unroll 1` to the existing integer Q2 K loop,
restricted to RDNA3 WMMA. It preserves original Q2 weight bytes, Q8 activation
quantization, tile selection, persistent/temporary buffer sizes and explicit
arithmetic. This applies UD's bounded-register-lifetime principle; it does not
copy UD quantization semantics into Q2. The compiler may still change numerical
behavior, so exact output replay remains mandatory.

## Qualification sequence

`config/q2-register-protocol.json` declares the gates before execution:

1. Run focused CPU/sanitizer checks on `.157`, including resource-report fixtures.
2. Run the same extended operator harness against frozen original Q2 and the
   candidate: original IQ2/Q2 checks, all five Q2 tile widths, aligned64/ragged65
   rows, ordinary/small activations. Keep independent error limits at 0.002.
   All 44 saved F32 outputs must also match the original implementation exactly.
3. If operators pass, record marked 2K PP/TG phases. Compare token/logit replay
   exactly and inspect target resource metadata plus kernel durations.
4. A diagnostic gain must survive unprofiled C1 512/2048/8192 with three samples
   after warmup and an existing-UD control. Overall acceptance still requires
   no regression versus UD; an improvement over the slow Q2 baseline is partial.

Each remote build/GPU arm requires the coordinated window and all four leases.
No source, service or evidence owned by DS4 is changed. Rejected full-model WMMA
arithmetic remains separate in [Q2-DOWN-EXPERIMENT.md](Q2-DOWN-EXPERIMENT.md).
