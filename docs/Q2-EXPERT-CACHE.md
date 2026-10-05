<!-- SPDX-License-Identifier: MIT -->
# Bounded persistent IQ2/Q2_K expert cache

The owner requests a real expert-weight cache experiment after the negative
shared-Q8 mirror trials. This candidate starts from retained 1585.308983 PP /
25.16079073 TG and caches routed IQ2 gate/up plus Q2_K down operands. It is
not a shared-expert Q8 trial or a KV cache. DS4 supplies the design precedent
of bounded persistent converted weights; no DS4 project code is imported.

The cache keeps the exact half operands used by the retained prefill kernels,
in [expert][K16][output row][16 half values] layout. Every K16 accumulation,
SwiGLU, scaled activation, inverse scale, half down output and ordered HC
consumer remains. The cache kernels load these half fragments directly;
existing encoded kernels remain for uncached layers and scalar decode.

The budget is 32GiB with an 8GiB free-memory reserve. Layers 0/8/16/24/32/40
cache all512 experts, in complete gate/up/down groups. Expected auxiliary
allocation is 30199062528 bytes (28.125GiB payload plus73728 tail bytes), taking
resident model allocation from43156012544 to73355075072 bytes. All48 layers'
full mirrors would require225GiB payload alone. This experiment measures
six-layer coverage, not a full-model dequantized cache or demand-driven LRU.
Quota, free-memory or allocation exhaustion retains the original encoded route.
Conversion errors fail loading; the model owns all successful allocations and
publishes the cache only after synchronization. Model files remain unchanged.
Startup telemetry records admitted layers, bytes, budget and preparation time.

The first compilation fails on insufficient epilogue LDS and reordered include
dependencies. Its source/patch and exit1 remain. Revision2 preserves the LDS
correction before the include-order correction; revision3 compiles successfully.
All162 original kernel instruction/operand/resource bodies remain exact after
binding the added default-false template argument in symbols. Twelve new
kernels have zero scratch. Complete1029-file inventories and patches remain.

Fresh .157 host tests pass28 Debug and28 ASan/UBSan checks, including C17 quota,
reserve boundary, unsupported shape, exhaustion and null-output accounting.
The142 previous launch guards and eight new rejection/two acceptance checks
pass. Analyzer checks keep safe numeric failures timed and reject five unsafe
or scope-corrupted cases. Two staged capsules verify1029 provider files and98
fixtures; nine manifests and the window helper are frozen.

The component covers IQ2 gate/up widths16/48/64/128 with ragged15/17/129-token,
65-row edges; Q2 down float/half widths16/48/64 with129-row edges. Production
2048-token shapes use64 and512 active experts, ten routes/token, and three
weight rotations beyond32MiB. There are117 sampled-format records,216 complete
output comparisons (including post-timing replay), and56 timing samples. Each
arm has two warmups and five measured repetitions in alternating order.
Setup/conversion/readback/validation are outside projection timers. Independent
format checks use the upstream byte-magnitude table, parity signs and integer
binary32-to-binary16 rounding, not the GPU half-high-byte lookup helper.

Safe numerical or timing failure still proceeds to the original model test;
guard, missing-write and runtime errors stop device work. Only one new model
runs at the unchanged exact2048/tg128 point, capacity9216/chunk2048, greedy C1,
MTP off, one warmup plus three measured sessions,127 timed decode calls,15s
cooldown outside timers. Saved Q21443.672867, retained1585.308983 and
UD1685.777092 controls are reused without recompilation or execution.
No curve or Q4 run follows before point parity. Independent task quality and
whole-curve equality remain open. GPU results are pending fresh admission.

[Source](../config/q2-expert-cache-source-v3.json),
[static audit](../config/q2-expert-cache-static.json),
[plan](../config/q2-expert-cache-plan.json),
[staged capsules](../config/q2-expert-cache-staging.json),
[component fixture](../tests/q2_expert_cache.hip).
Actual commands and exit codes remain in evidence/q2-expert-cache-preparation/.
