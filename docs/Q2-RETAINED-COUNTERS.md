<!-- SPDX-License-Identifier: MIT -->
# Retained Q2 hardware-counter preparation

The subsequent [GPU calibration](Q2-COUNTER-CALIBRATION.md) is complete.
It verifies the tested wave groups and rejects FETCH_SIZE after a roughly50%
read-count shortfall. This file preserves the preceding installation audit;
its then-proposed probe below is superseded by that measured result.

The retained model result remains **1585.308983 PP /25.16079073 TG**, from
`ssm-fixed-bounds` on the unchanged exact2048/tg128 benchmark. This audit reads
installed profiler files on .157 and official ROCm issue/PR evidence. It adds
no GPU measurement, benchmark sample, numerical change or model build. The
earlier1571 dispatch trace is used only for its saved device identity here.

The [machine-readable audit](../config/q2-retained-counter-capabilities.json)
binds five successful read-only collection commands, file/library hashes and
ten upstream API responses. The installed ROCm version is7.2.4. Its
`counter_defs.yaml` explicitly defines64 gfx1151 metrics:31 hardware counters
and33 derived expressions/constants. The hardware blocks are SQ18, GL2C10,
GRBM2 and TA1. A definition is not evidence of successful collection.

Relevant limits of the installed profiler are:

| Area | Static finding | Consequence for the next diagnosis |
| --- | --- | --- |
| Wave/instruction counts | Installed SDK test skips its positive SQ_WAVES assertion on gfx1151. | Check a known launch count, alone and alongside another counter, before using SQ-derived ratios. |
| SQ topology fix | SDK links external AQLProfile and imports the legacy agent-registration entry point. | The V2 harvested-WGP fix is not established by this installation audit. |
| Target topology | Saved agent reports Radeon8060S,40CUs,80SIMDs,wave32. | The published harvested-part failure is not proof of a failure on this target. |
| Read requests | FETCH_SIZE weights GL2C request sizes and divides by1024. | Interpret it as KiB; validate instance coverage before deriving bandwidth. |
| Detailed stalls | All26 newly named counters in PR10041 are absent. | Do not infer memory/VALU wait reasons from their nonexistent values. |

AMD's [GL2C correction](https://github.com/ROCm/rocm-systems/pull/3100), merged
March6,2026, changes the gfx11.5 instance count from4 to8. The unchanged YAML
formula cannot show whether that binary correction is present. Its
[SQ correction](https://github.com/ROCm/rocm-systems/pull/8229), merged
July22,2026, fixes topology aliasing and mixed-counter offsets on harvested
parts. The associated [issue](https://github.com/ROCm/rocm-systems/issues/3828)
is closed; it must not be presented as an unresolved defect proven on .157.
The [additional gfx11.5 metrics](https://github.com/ROCm/rocm-systems/pull/10041)
were merged August24,2026. Their absence is verified against installed
definitions, independently of package dates. No package, driver or profiler
definition is modified.

Next, admit one small owned calibration after the existing compact-LDS
release. Use deterministic complete output checks, an explicitly wave32
kernel with known thread count and ten dispatches. Collect SQ_WAVES_sum alone,
then with GRBM_COUNT, requiring the expected count on every dispatch. Check
FETCH_SIZE separately with known incompressible read traffic beyond32MiB,
recording instance dimensions and declaring tolerances before execution.
Cache effects and request-interface counts must remain distinct from physical
DRAM traffic. This is a proposed probe, not an implemented or admitted run.

Only validated counter groups may then diagnose the already saved1585 binary,
with its existing source, binary and runtime identities checked before reuse.
Counter collection can serialize dispatches; its durations never replace
unprofiled PP/TG or the fixedQ2/UD controls. If counters fail calibration,
retain the failure and use separate dispatch timing plus a controlled kernel
change. Do not compensate bad counts with an assumed factor of two or infer
that lower theoretical occupancy caused the measured model regression.

The .157 activity in this audit consists only of file reads and ELF inspection.
No GPU runtime is initialized, no lease is acquired and no source/model/cache
is changed. Five collection commands and the audit generator exit0; no C/C++
runtime, fixture or launcher changes, so no host suite is rerun. Raw inputs,
commands and actual exits remain under
`evidence/q2-retained-counter-preparation/`. The committed audit recipe can
verify the report with existing local PyYAML:

```sh
python3 tools/audit-q2-retained-counters.py --check
```

The [compressed antirez/ds4 cache](Q2-COMPRESSED-CACHE.md) remains a separate
completed capacity experiment. Its1576.007692 PP /24.32799080 TG result does
not replace the retained resident model. Full-curve parity remains open.
