<!-- SPDX-License-Identifier: MIT -->
# .157 fan curve and thermal guard

On 2026-10-03 the owner clarifies that 98 C is the CPU limit and explicitly
requests maximum fan speed at 82 C, with earlier levels adjusted accordingly.
This authorizes the fan-only host change below, preserving clocks, power
limits, model code and benchmark scoring.

The host identifies as Bosgame BeyondMax Series, board AXB35-02. The already
installed `axb35-tools 1.0.2-1` and `ec_su_axb35` driver expose three fans.
The [upstream driver interface](https://github.com/cmetz/ec-su_axb35-linux#devices)
defines levels 1–5 as 20/40/60/80/100 percent with rising/falling thresholds.
All three fans now use:

| Level | Requested speed | Rising temperature | Falling temperature |
| --- | --- | --- | --- |
| 1 | 20% | 40 C | 35 C |
| 2 | 40% | 50 C | 45 C |
| 3 | 60% | 60 C | 55 C |
| 4 | 80% | 70 C | 65 C |
| 5 | 100% | 82 C | 78 C |

Previously, rising thresholds were 60,70,83,95,97 C and falling thresholds
50,60,80,94,96 C. The lower falling thresholds provide hysteresis.
The existing driver raises the level when its EC CPU temperature reaches the
next rising threshold; it steps one level per controller update. This operation
does not qualify a sustained 82 C load or measure throughput improvement.

## Persistent configuration

The configuration remains `/etc/axb35-config.json`. Its three curve pairs
are updated; other fields are preserved. A backup of the complete original,
the effective unit before modification and before/after hardware readings
reside in persistent remote `run/q2-fan-curve-82-r1/` and local `evidence/`.
The [receipt](../config/q2-fan-curve-82.json) records command exits and hashes.

The installed manual says `axb35-ctl apply` loads the JSON. Read-only inspection
of this installed binary instead shows its apply path opening/closing the file,
then calling a routine that formats the fixed 60,70,83,95,97 / 50,60,80,94,96
curves. The original enabled service runs that command. Saving JSON alone would
therefore not implement the requested startup behavior.

A drop-in at
`/etc/systemd/system/axb35-fan-control.service.d/90-configured-fan-curves.conf`
replaces only ExecStart with the installed
`/usr/local/sbin/synapse-axb35-fan-curves` helper and the existing JSON path.
The helper source is [axb35-fan-curves.py](../tools/axb35-fan-curves.py).
It validates all three curves before writing and calls existing `axb35-ctl`
for ramp-down, ramp-up and curve mode. It ignores APU and fixed level fields.
It currently accepts only three curve-mode fans, matching this configuration.
The existing board check, module-load step and oneshot service are retained;
no new background daemon is installed.

The service is restarted successfully and remains enabled. Hardware readback
confirms all six curves and three modes. At EC temperature 49 C, fan speeds
are 1407/1427/423 RPM, each at level 1. Live APU remains performance/120 W.
The stored APU field remains its original balanced value and is not applied
by the fan-only helper. No reboot is performed or claimed.

After the owner's reported power outage on2026-10-07, all three fan modes and
curve pairs survive unchanged, as does the stored config hash. Read-only APU
observation instead reports balanced/85 W. The earlier fan-only operation
did not persist the independently selected live performance/120 W mode.
The recovered Q2 trial therefore has a power-condition confound; a separate
runtime-only restoration plan was prepared under the repository's no-tuning
rule. The owner subsequently restores performance; read-only verification
confirms120 W and retained curves. The agent makes no APU write.
[Observation](../config/q2-post-reboot-apu-observation.json),
[plan](../config/q2-post-reboot-apu-restore-plan.json).

The operation acquires all four original leases nonblocking, verifies empty
KFD and releases them on completion. The shared registry records
`fan_curve_update`. Fresh performance pairs must run both Q2 and UD under this
same cooling policy; older results retain their historical thermal conditions.

## Measurement guard correction

`q2_thermal.py` now applies the inclusive 98000 mC owner threshold only to
`k10temp`. A lower or equal exposed CPU max/crit remains a strict threshold.
GPU temperature remains mandatory and validated; its lowest positive exposed
max/crit is strict. This host exposes only amdgpu edge temperature, with no
max/crit, so GPU telemetry explicitly records `limit_mc: null` and
`limit_source: no_exposed_gpu_threshold`. No CPU threshold is reused for it.
The hardware's thermal policies are not rewritten.

The former shared 98 C software policy caused the preserved Core-19 stop at
GPU 99 C / CPU 96.5 C. That is a historical policy stop, not proof of hardware
failure. It is not relabeled as a completed task campaign.

On `.157`, `q2-narrow-thermal-host-r1` passes 15/15 Debug and ASan/UBSan checks;
`q2-fan-curve-host-r1` adds fan validation and passes 16/16 in both profiles.
All 14 host artifacts are collected/hash verified. Fixtures cover CPU/GPU
threshold separation, exposed thresholds, missing/malformed sensors, complete
fan validation, hysteresis and fan-only command scope. These are CPU checks,
separate from the applied fan readback and pending GPU work.
