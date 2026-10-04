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
