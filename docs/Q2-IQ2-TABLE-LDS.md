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
