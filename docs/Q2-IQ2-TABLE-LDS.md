# IQ2 compact-table LDS reuse experiment

Derive from retained fixed-bound1587.893545 Q2, without the slower DPP trial.
Stage the existing2048-byte IEEE-half-high magnitude table and1024-byte sign
words once per workgroup. Mask sign bits at publication with exact integer
AND; every later lookup, four-lane owner, scale and rounded floating operation
is unchanged. One setup barrier occurs outside K. Original generic fallbacks
and scalar/decode remain. No expanded model weights or heap/stream changes.

This differs from the historical raw-integer magnitude-only LDS probe before
the compact half-high representation; it is a new composed provider. Preserve
that qualified historical evidence, do not rebuild/replay it.

Local gfx1151 assembly preserves162 original bodies. BN64 keeps104VGPR;
BN128 changes150→169. LDS17536/25728→20608/28800, zero spills, one extra setup
barrier. Static global64 loads10→4 include the new one-time table setup.
The higher BN128 register demand is charged in actual timings, not rejected
on source count alone. No GPU numerical/performance acceptance at preparation.

One new guarded component then one exact2048/tg128 original-model trial on
.157 only, unchanged capacity9216/chunk2048/C1/MTPoff and original timers.
Saved mixedQ2, stableSSM parent, retainedIQ2 parent and UD controls reused;
no control rebuild/rerun, no Q4 or full curve. Collect all artifacts and retire/
release/inform Core before local analysis. Safe finite numerical differences
preserve their exits/full buffers and still permit the model performance run.

The original-model trial completes with1562.063292 PP/25.16286660 TG,
-1.626699% PP against retained1587.893545. All113 guarded output pairs and
21/21 complete model files remain exact against both saved parents;9 internal
replays are exact. Keep fixed bounds as the experimental performance parent.

All13 primary commands exit0 and37 artifacts collect before release12:10:53UTC,
SHAf2eb2ccb.1472 IDs/1179 groups retired, KFD empty, original Core CPU/four GPU
leases and seven model stat tuples unchanged. Core informed before analysis;
no remote job/window/reservation/cleanup remains.

Complete operator time regresses11.995/20.298/12.219/11.994/14.268% for
uniform160/uniform512/captured0/3/22. All70 HIP elapsed timers are rawzero and
invalid; synchronized complete-operator wall measurements remain preserved.
Neither exactness nor fewer global loads establishes a model gain. This rules
out this compact AoS table placement as the default; it does not prove that
every shared-memory layout is slower, or identify measured bank conflicts.

The local table+DPP compiler probe preserves164 production bodies. Its BN128
still needs169VGPR and28800LDS bytes; BN64 changes104→100VGPR. The two private
bodies have1662/979 instructions. Standalone explicit instantiation is outside
the production anonymous namespace and has no provider/selector/runtime result.
It does not resolve the large-table-row register increase and receives no
GPU admission by this result. Prefer an independently bounded active-path
change over another table permutation at this stage.

| Session | PP tokens/s | PP seconds | TG calls/s | TG seconds |
| --- | ---: | ---: | ---: | ---: |
| Warmup | 1564.506236 | 1.309039205 | 25.14772986 | 5.050157637 |
| 1 | 1563.698155 | 1.309715685 | 25.14691436 | 5.050321410 |
| 2 | 1562.051828 | 1.311096062 | 25.16780028 | 5.046130317 |
| 3 | 1562.063292 | 1.311086440 | 25.16286660 | 5.047119710 |

[All20 model samples](figures/q2-iq2-table-lds-model.csv),
[graph](figures/q2-iq2-table-lds-model.png),
[all70 component timings](figures/q2-iq2-table-lds-component.csv).
