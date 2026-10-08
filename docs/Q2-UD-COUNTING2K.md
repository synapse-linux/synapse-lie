<!-- SPDX-License-Identifier: MIT -->

# Native Q2 and UD comparison at 2048 tokens

Owner-requested UD model check on .157 using the same retained `synapse-lie-bench`
executable as the saved Q2 arm. No standalone Gufo application and no Q2 rerun.
Physical input: 2048 identical counting-chat token IDs, one 2048-token prefill call
from an empty sequence, allocated capacity 133760, C1 reactive greedy AR, MTP off.
Each model has one warmup and three measured repetitions, with no pause between them.
PP times the whole input; TG times 128 completed calls and emits 128 tokens.
Model load, tokenization and sequence allocation are outside these phase timestamps.
IOMMU remains enabled. These sequential model runs are not interleaved repetitions.

| Model | Repetition | Prefill (token/s) | Full prefill (s) | Decode (token/s) | Decode (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Q2 | 1 | 1572.629602 | 1.302277407 | 27.485388 | 4.657019980 |
| Q2 | 2 | 1569.828941 | 1.304600741 | 27.550565 | 4.646002778 |
| Q2 | 3 | 1572.143839 | 1.302679786 | 27.553658 | 4.645481222 |
| UD-Q4_K_XL | 1 | 1654.914448 | 1.237526207 | 25.923047 | 4.937691173 |
| UD-Q4_K_XL | 2 | 1657.625292 | 1.235502384 | 25.932564 | 4.935878994 |
| UD-Q4_K_XL | 3 | 1650.724881 | 1.240667069 | 25.933379 | 4.935723889 |

All warmups and measured values: [CSV](figures/q2-ud-counting2k.csv).

| Model | Prefill median (token/s) | Decode median (token/s) |
| --- | ---: | ---: |
| Q2 | 1572.143839 | 27.550565 |
| UD-Q4_K_XL | 1654.914448 | 25.932564 |

Observed UD minus Q2: +5.2648% PP; -5.8728% TG.
All eight 128-token continuations identical: True.
This single counting task does not establish general model quality or numerical equivalence.
UD uses the current embedded provider and its UD loader/kernel dispatch; this result
does not claim an unmodified upstream Gufo executable. Only the 2K point was run.

## Historical Q2 difference remains open

The saved best fixed-2K prefill observation remains 1587.893545 token/s.
The later scalar-HC executable already measured 1571.380247 on 7 October.
That historical comparison also changed Release versus RelWithDebInfo compilation,
so it does not isolate a scalar-kernel regression. The current same-capacity 9216
native observation is 1574.899595; the 133760-capacity arm above is 1572.143839.
These are observed differences of -12.993950 and -15.749706 token/s from the saved best.
The 1542.547201 observation belongs to the full 8192-token prompt, not the 2048-token point;
subtracting it from 1587.893545 gives -45.346344 while changing input length.
The historical harness also pauses 15 seconds between samples and times 127 decode
forwards. Neither the historical best nor the lower observations are discarded,
but no causal attribution or directly comparable historical TG delta is established.
[Earlier HC evidence and compilation correction](Q2-HC-SCALAR-UP-MIX.md),
[current Q2 full-prefill samples](Q2-COUNTING-FULL-PREFILL.md).

## Closure

UD run/child exit 0. Release: `4bbc66e0439fa2c36fd14a7e317ba6b5d4a0ed1dfac939fb6e6285a513a48f01` at 2026-10-08T00:39:59.629518+00:00.
Strong closure at 2026-10-08T00:40:07.739080+00:00 verifies empty KFD, five free original leases,
65 retired identities/groups and unchanged model stats.
No model mutation, remote build, cleanup, service change, tuning or reboot occurs.
