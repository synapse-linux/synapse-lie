# SPDX-License-Identifier: MIT
"""Bind the new counter fixture to its .157 host qualification before GPU use."""
import hashlib
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


previous = 'config/q2-counter-calibration-window-release.json'
previous_sha = 'd39fb71c9a2f8a7373069b58cc6fdf981af14b7a0201766f35b709e69e248c55'
assert sha(ROOT / previous) == previous_sha
prior = read(ROOT / 'config/q2-ssm-compact-lds-plan.json')
names = list(prior['fixtures']) + ['tests/q2_counter_calibration.hip',
        'tests/q2_counter_calibration_test.py', 'tools/q2_counter_calibration.py']
assert len(names) == len(set(names)) == 105
fixtures = {name: sha(ROOT / name) for name in names}
host_label = 'q2-counter-calibration-host-r2'
host = ROOT / 'evidence' / host_label
receipt = read(host / 'results/result.json')
assert receipt['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE'
assert len(receipt['commands']) == 6 and all(c['exit_code'] == 0 for c in receipt['commands'])
for name, metadata in receipt['artifacts'].items():
    assert sha(host / 'results' / name) == metadata['sha256']
for name in ('03.log', '06.log'):
    assert '100% tests passed out of 31' in (host / 'results' / name).read_text()
with tarfile.open(host / 'source.tar.gz') as archive:
    for name, digest in fixtures.items():
        assert hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest, name
audit = read(ROOT / 'config/q2-retained-counter-capabilities.json')
installed = [audit['launcher']]
installed += [{k: f[k] for k in ('path', 'sha256')} for f in audit['libraries']]
installed += [{k: f[k] for k in ('path', 'sha256')} for f in audit['installed_files']
              if f['path'].endswith('counter_defs.yaml')]
helper = 'tools/q2-counter-calibration-v2-window.py'
plan = dict(schema='synapse-lie.q2-counter-calibration-plan.v1',
    fixtures=fixtures, installed_files=installed,
    previous_release=previous, previous_release_sha256=previous_sha,
    window_helper=helper, window_helper_sha256=sha(ROOT / helper),
    host=host_label, host_test_counts=dict(debug=31, asan_ubsan=31),
    host_result_sha256=sha(host / 'results/result.json'),
    host_capsule_sha256=sha(host / 'source.tar.gz'),
    host_archive_sha256=sha(host / 'results.tar.gz'),
    gpu_label='q2-counter-calibration-r2', mode='counter-calibration',
    manifests={name: sha(ROOT / name) for name in (
        'config/q2-retained-counter-capabilities.json',
        'config/q2-ssm-fixed-bounds-model-results.json',
        'config/q2-fixed-prefill-reference.json',
        'tools/freeze-q2-counter-calibration-v2.py')},
    expected=dict(threads=16384, block_threads=256, wave_size=32, waves=512,
                  input_bytes=268435456, fetch_kib=262144,
                  fetch_relative_tolerance=0.05, repetitions_per_pass=10,
                  output_words=16384, guard_words=64),
    passes=[dict(name='waves', mode='waves', counters=['SQ_WAVES_sum']),
            dict(name='mixed', mode='waves', counters=['SQ_WAVES_sum', 'GRBM_COUNT']),
            dict(name='fetch', mode='read', counters=['FETCH_SIZE'])],
    numerical_contract='Complete unsigned32 output and guards must match on every repetition. Integer wrap is defined; no model arithmetic.',
    counter_contract='Every wave aggregate equals512, alone and co-collected. Every FETCH_SIZE lies within5% of262144KiB; retains all ten values. This qualifies only these controls/groups, not every counter or model.',
    scope='One synthetic fixture; no model or reference benchmark. Profiler timings are never headline throughput.',
    gpu_run=False, model_inference=False, controls_rerun=False, goal_met=False)
destination = ROOT / 'config/q2-counter-calibration-v2-plan.json'
with destination.open('x') as stream:
    json.dump(plan, stream, indent=2)
    stream.write('\n')
print(json.dumps(dict(plan=str(destination.relative_to(ROOT)), sha256=sha(destination), fixtures=len(fixtures), host_tests=62)))
