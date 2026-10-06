# SPDX-License-Identifier: MIT
"""One owned synthetic calibration using the existing leased Q2 supervisor."""
import hashlib
import json
from pathlib import Path

PASSES = (
    ('waves', 'waves', ('SQ_WAVES_sum',), 'q2_counter_wave_probe'),
    ('mixed', 'waves', ('SQ_WAVES_sum', 'GRBM_COUNT'), 'q2_counter_wave_probe'),
    ('fetch', 'read', ('FETCH_SIZE',), 'q2_counter_read_probe'),
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(root, result, run, env, save):
    plan_path = root / 'config/q2-counter-calibration-plan.json'
    plan = json.loads(plan_path.read_text())
    for name, digest in plan['fixtures'].items():
        if sha(root / name) != digest:
            raise RuntimeError('Calibration source changed: ' + name)
    admission = json.loads((root.parent / 'q2-counter-calibration-window-admission.json').read_text())
    if (admission['previous_release_sha256'] != plan['previous_release_sha256'] or
            root.name not in admission['planned_labels'] or not admission['gpu_reserved']):
        raise RuntimeError('Calibration window not admitted')
    for item in plan['installed_files']:
        if sha(Path(item['path'])) != item['sha256']:
            raise RuntimeError('Installed profiler changed: ' + item['path'])
    result.update(calibration_plan_sha256=sha(plan_path), headline_eligible=False,
                  timed_scope='Synthetic counter calibration only; no model, benchmark or throughput result')
    build = root / 'build/counter-calibration'
    build.mkdir(parents=True)
    binary = build / 'q2-counter-calibration'
    run(['/opt/rocm/bin/hipcc', '-O3', '-std=c++17', '--offload-arch=gfx1151',
         '-mwavefrontsize32', str(root / 'tests/q2_counter_calibration.hip'), '-o', str(binary)], env, 180)
    result['binary_sha256'] = sha(binary)
    save()
    gpu_env = {k: v for k, v in env.items() if k not in ('HIP_VISIBLE_DEVICES', 'ROCR_VISIBLE_DEVICES')}
    for mode in ('waves', 'read'):
        run([str(binary), mode], gpu_env, 60)
    for label, mode, counters, kernel in PASSES:
        output = root / 'results' / label
        run(['/opt/rocm/bin/rocprofv3', '--pmc', *counters, '--kernel-trace',
             '--kernel-include-regex', '.*' + kernel + '.*',
             '--output-format', 'csv', 'json', '-d', str(output), '-o', 'probe',
             '--', str(binary), mode], gpu_env, 120)
    result['binary_sha256_after'] = sha(binary)
    if result['binary_sha256_after'] != result['binary_sha256']:
        raise RuntimeError('Calibration binary changed')
    save()
