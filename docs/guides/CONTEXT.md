<!-- SPDX-License-Identifier: MIT -->
# Context configuration

The server and direct shared core accept a total capacity of 128 to 1,048,576
physical tokens. Prompt, image positions and reserved output must fit together.
The model's native geometry remains authoritative: increasing `--context` alone
does not change rotary frequencies or enable extended model context.

| `--rope-scaling` | Qwen3.8 Flash Next capacity | Use |
| --- | ---: | --- |
| `native` (default) | 262,144 | Native frequencies and existing qualified measurements. |
| `yarn2` | 524,288 | Explicit static scaling by two. |
| `yarn4` | 1,048,576 | Explicit static scaling by four. |

These capacities follow the model's declared 262,144-token native context.
Other model bindings must supply their actual rotary geometry and qualification.
The C17 plan uses beta-fast 32, beta-slow 1 and attention factor
`1 + 0.1 * log(factor)`. Attention and indexer kernels consume the same immutable
device frequency table. Image mRoPE coordinates remain physical coordinates.
The selected profile is fixed at model load and appears in `/v1/models` and
shared-core benchmark identity. RAM/SSD states cannot cross scaling profiles.

The [Qwen model card](https://huggingface.co/Qwen/Qwen3.8-Flash-Next#best-practices)
recommends YaRN for extended context. Static scaling can affect shorter-context
quality; native and scaled runs belong to separate numerical/quality cohorts.

## Run an extended-context server

Use the verified state-access GPU provider build from the [build guide](BUILD.md).
The pristine provider refuses non-native profiles. On a machine with sufficient
available GPU-addressable memory:

```sh
build/release/synapse-lie-server \
  --model /models/target-00001-of-00004.gguf --model-id local-model \
  --host 0.0.0.0 --port 8000 --max-active 1 \
  --context 1048576 --rope-scaling yarn4 --request-timeout-ms 86400000
```

The one-day timeout is an explicit experiment setting; the ordinary default
remains ten minutes. Allocation still reserves sequence state for configured
capacity. Begin with C1; increasing concurrency increases memory requirements.
RAM prefix retention remains enabled by default and SSD remains opt-in.

## Measure a physical prompt

`tokens.json` must contain real model-tokenizer IDs for the corpus being tested.
Its prompt length plus `--tg` must not exceed capacity. Repeated synthetic IDs
do not establish long-context quality.

```sh
build/release/synapse-lie-bench --suite core \
  --model /models/target-00001-of-00004.gguf --tokens-file tokens.json \
  --context 1048576 --rope-scaling yarn4 --users 1 --tg 128 \
  --timeout-ms 86400000 --warmups 0 --repetitions 1 \
  --kv-cache-ram-mb 0 --output run-1m.jsonl --graphs graphs-1m
```

The cache-off setting isolates fresh prefill for this measurement. Reports
preserve profile identity and refuse matched comparisons across profiles.
The canonical HTTP conversation curve is documented in the
[benchmark guide](BENCHMARKS.md#canonical-gufo-conversation-curve).

## Memory and qualification

CPU operator tests cover scaling frequencies through position 1,048,575.
A shared-core fixture prefills 1,048,575 physical tokens and emits one token;
neither test loads weights or proves GPU fit, throughput or recall quality.
Original-weight Strix Point measurements currently qualify native context
through near 256K. Extended-context GPU tests use fresh coordinated admissions.

The current provider's sparse WMMA attention path handles mask sizes through
256K. Larger masks use its existing generic causal-attention fallback;
1M performance is not established by adding the capacity option.
Model weights, active KV/index/recurrent state, scratch buffers, driver overhead,
RAM retention and the operating system all need memory. A larger GTT ceiling
permits addressing more RAM but does not create RAM. Record effective GTT,
available RAM and measured peaks for each original-weight run.

## GTT on the Point test host

Read-only inspection on `.161` reports Linux `7.1.5-76070105-generic`, 4 KiB
pages, `ttm.pages_limit=25165824` (96 GiB GTT), `amdgpu.gttsize=-1`, and
123.44 GiB visible RAM. A 112 GiB ceiling corresponds to the boot argument:

```text
ttm.pages_limit=29360128
```

The upstream [AMDGPU initialization](https://raw.githubusercontent.com/torvalds/linux/master/drivers/gpu/drm/amd/amdgpu/amdgpu_ttm.c)
reads the TTM limit when creating its GTT manager. Writing the runtime TTM
parameter alone does not recreate that manager. This host uses Pop!_OS
`kernelstub`; the prepared configuration action is
`sudo kernelstub -a "ttm.pages_limit=29360128"`, followed by a scheduled reboot
and verification of both the parameter and `mem_info_gtt_total`. Revert with
`sudo kernelstub -d "ttm.pages_limit=29360128"` and another scheduled reboot.
These actions have **not** been applied; they change the shared host and require
an explicit maintenance window under the coordination policy. No old boot
option needs removal on this inspected host. Other hosts need their own check.

For the current UD model, C1 AR, PP chunk 2,048 and cache off, a 4K-capacity
original-weight gate samples a 79.55 GiB GTT peak. The executor has twelve full
attention layers, each reserving F16 K/V, complete F32 raw index history and
F16 pooled index rows. Scaling those exact allocation formulas, including mask
and score scratch growth, gives the following **estimates**, not measured fit:

| Total context | Active attention/index state | Estimated GTT peak |
| ---: | ---: | ---: |
| 262,144 | 7.69 GiB | 87.12 GiB |
| 524,288 | 15.38 GiB | 94.94 GiB |
| 1,048,576 | 30.75 GiB | 110.60 GiB |

The 1M estimate leaves only about 0.72 GiB from the minimum available RAM
observed during that baseline. Raising GTT therefore needs a fresh RAM budget,
including host buffers and at least the admitted operating-system margin;
it is insufficient on its own. MTP adds its predictor, draft state and rollback.
Compressed retained KV checkpoints do not replace active GPU attention state.
A smaller prefill chunk may reduce scratch memory; measure its speed and peak
before selecting it for a 1M campaign. The
[memory receipt](../development/validation/context-memory-point-2026-10-04.json)
records the formulas, baseline and unmeasured limits.
