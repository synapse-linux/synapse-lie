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
  --context 1048576 --rope-scaling yarn4 --prefill-chunk 256 \
  --kv-cache-ram-mb 0 --request-timeout-ms 86400000
```

The one-day timeout is an explicit experiment setting; the ordinary default
remains ten minutes. Allocation still reserves sequence state for configured
capacity. Begin with C1; increasing concurrency increases memory requirements.
This memory experiment explicitly disables RAM retention. Ordinary RAM prefix
retention remains enabled by default and SSD remains opt-in.

## Measure a physical prompt

`tokens.json` must contain real model-tokenizer IDs for the corpus being tested.
Its prompt length plus `--tg` must not exceed capacity. Repeated synthetic IDs
do not establish long-context quality.

```sh
build/release/synapse-lie-bench --suite core \
  --model /models/target-00001-of-00004.gguf --tokens-file tokens.json \
  --context 1048576 --rope-scaling yarn4 --users 1 --tg 128 \
  --chunk 256 --timeout-ms 86400000 --warmups 0 --repetitions 1 \
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
Short original-weight native/YaRN2/YaRN4 gates pass at capacity 4096; they
qualify profile integration without reaching extended physical positions.

The current provider's sparse WMMA attention path handles mask sizes through
256K. Larger masks use its existing generic causal-attention fallback;
1M performance is not established by adding the capacity option.
Model weights, active KV/index/recurrent state, scratch buffers, driver overhead,
RAM retention and the operating system all need memory. A larger GTT ceiling
permits addressing more RAM but does not create RAM. Record effective GTT,
available RAM and measured peaks for each original-weight run.

## GTT on the Point test host

After the explicitly authorized reboot on 2026-10-04, `.161` runs Linux
`7.1.5-76070105-generic` with 4 KiB pages, 123.44 GiB visible RAM and an
effective GTT ceiling of **112 GiB**. The verified boot argument is:

```text
ttm.pages_limit=29360128
```

The upstream [AMDGPU initialization](https://raw.githubusercontent.com/torvalds/linux/master/drivers/gpu/drm/amd/amdgpu/amdgpu_ttm.c)
reads the TTM limit when creating its GTT manager. Writing the runtime TTM
parameter alone does not recreate that manager. Although Pop!_OS `kernelstub`
is installed, read-only `efibootmgr` and `bootctl` identify the active bootloader
as GRUB 2.12, EFI entry `0000` at `EFI/PopOS_disk2/grubx64.efi`. Its actual
kernel options match `/etc/default/grub`, not the kernelstub configuration.
Changing kernelstub alone would therefore target the wrong boot configuration.

The inspected `grub-mkconfig` sources `/etc/default/grub.d/*.cfg`. The prepared
isolated file `/etc/default/grub.d/99-synapse-lie-gtt.cfg` contains:

```sh
GRUB_CMDLINE_LINUX_DEFAULT="${GRUB_CMDLINE_LINUX_DEFAULT} ttm.pages_limit=29360128"
```

After backing up the original configuration, the maintenance action installs
only that new file, runs `sudo update-grub`, checks the generated normal boot
entry and schedules a reboot. The
[GRUB manual](https://www.gnu.org/software/grub/manual/grub/html_node/Simple-configuration.html)
describes these kernel arguments and configuration generation. After reboot,
verify `/proc/cmdline`, `/sys/module/ttm/parameters/pages_limit` and the AMD GPU's
`mem_info_gtt_total`: the expected values are 29,360,128 pages and
120,259,084,288 bytes. Rollback removes only this owned file, runs
`sudo update-grub` and schedules another reboot; recovery entries retain their
original arguments. The isolated GRUB file is installed; generated configuration
passes syntax and all five normal/recovery argument checks. Backups are collected.
The owner subsequently explicitly authorized reboot; a new boot ID and the
effective 120,259,084,288-byte GTT manager are verified. The earlier approval
rejection remains recorded as an action that did not execute.
[Boot receipt](../development/validation/gtt112-boot-capacity-2026-10-04.json).
Other hosts need their own boot and memory check.

Linux renumbered the filesystem device after reboot. Qualification may explicitly
bind the previous and current device numbers to the witnessed boot ID and
filesystem UUID. Model, predictor and projector receipts stay unchanged; path,
inode, length and both modification/change times must still match. Every window
checks exact current identities again at closure. This is an optional supervisor
control, not an inference or benchmark runtime dependency.

The corrected provider binds scratch allocation to the C17 prefill bound,
retaining space for admitted decode and MTP rows. For the current UD model,
C1 AR, PP chunk 256 and cache off, a 4K-capacity original-weight gate samples
a 78.33 GiB GTT peak, down from 79.55 GiB with the earlier fixed scratch.
Both chunk256 gates generate the same 32 output token IDs. The executor has
twelve full attention layers, each reserving F16 K/V, complete F32 raw index
history and F16 pooled index rows. A separate gate with capacity 524,288
samples 93.68 GiB GTT, against 93.65 GiB projected, and 18.65 GiB available RAM
remaining. It uses the same short PP1500/TG32 input and exact output IDs; it
does not reach physical extended positions. Allocation formulas and these
sampled baselines give the following budget:

| Total capacity | Active attention/index state | GTT peak | Evidence |
| ---: | ---: | ---: | --- |
| 262,144 | 7.69 GiB | 85.90 GiB | Estimated from the 4K baseline. |
| 524,288 | 15.38 GiB | 93.68 GiB | Measured capacity allocation with PP1500. |
| 1,048,576 | 30.75 GiB | 109.18 GiB | Measured capacity allocation with PP1500 after GTT112 boot. |

The earlier baselines projected only 1.82–3.15 GiB available RAM remaining;
host residency differs between windows. After reboot, the actual short capacity-1M
gate passes with 7.98 GiB minimum available RAM and the same 32 output IDs as the
512K gate. Its single cold PP1500 sample records 50.21 token/s, compared with
about 266 token/s in the smaller-capacity gates. This slowdown needs investigation;
short prompts do not establish physical 1M throughput or recall quality.

The separate physical C1 AR YaRN4 chunk256 run completes 1,048,448 prefill
tokens in 7,398.225 s (141.72 token/s), then stops naturally after 43 output
tokens. Its benchmark exits 0, while the required TG128 supervisor/controller
gate correctly fails with exit 1. Eleven artifacts and ownership closure verify;
minimum available RAM is 6.03 GiB and CPU/GPU/NVMe peaks are 78.625/79/66.85 C.
This is one stress sample using repeated tokenizer IDs, not recall quality or
matched performance. Do not use the partial output as a passing TG128 sample.

Every physical 1M window still needs fresh RAM/GTT admission. Host buffers and
an admitted operating-system margin must fit. MTP adds predictor and draft
state plus rollback, which this AR budget does not include.
The optional qualification supervisor accepts `memory_admission` with
`expected_peak_gtt_bytes` and `min_available_ram_bytes`; the prepared C1 AR
gate uses 117,234,307,072 predicted peak bytes and a 1 GiB available-RAM floor.
It refuses an unfit ceiling before stopping the router and checks the sampled
RAM budget during the owned run. This is an explicit campaign setting, not a
default engine reserve; sampled guards do not establish fit or guarantee that
every host allocation can be observed before memory exhaustion.
Compressed retained KV checkpoints do not replace active GPU attention state.
Smaller chunks trade prefill speed for memory: the single short chunk256 gate
records 266.94 prefill token/s and 10.52 decode token/s; the earlier chunk2048
gate records 460.44 and 10.53. These are functional one-sample measurements,
without warmup, rather than a replicated performance comparison. The ordinary
chunk2048 default is preserved. The
[memory receipt](../development/validation/context-memory-point-2026-10-04.json)
preserves both baselines, formulas and unmeasured limits; the
[GPU receipt](../development/validation/tool-context-point-gpu-2026-10-04.json)
binds collected measurements, exact outputs, temperatures and closure.
