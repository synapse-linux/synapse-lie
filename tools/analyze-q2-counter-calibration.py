# SPDX-License-Identifier: MIT
"""Cross-check complete outputs and CSV/JSON counter records; never run a model."""
import csv
import hashlib
import json
import math
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def artifacts(label, fixtures):
    root = ROOT / 'evidence' / label
    receipt = read(root / 'results/result.json')
    collection = read(root / 'collection.json')
    assert sha(root / 'results.tar.gz') == collection['sha256']
    with tarfile.open(root / 'results.tar.gz') as archive:
        assert archive.extractfile('results/result.json').read() == (root / 'results/result.json').read_bytes()
        for name, info in receipt['artifacts'].items():
            data = (root / 'results' / name).read_bytes()
            assert len(data) == info['bytes']
            assert hashlib.sha256(data).hexdigest() == info['sha256']
            assert archive.extractfile('results/' + name).read() == data
    transport = read(root / 'transport.json')
    assert transport['exit_code'] == 0
    assert sha(root / 'source.tar.gz') == transport['capsule_sha256']
    with tarfile.open(root / 'source.tar.gz') as archive:
        for name, digest in fixtures.items():
            assert hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest, name
    return receipt


def main():
    plan_path = ROOT / 'config/q2-counter-calibration-v2-plan.json'
    plan = read(plan_path)
    assert sha(ROOT / plan['window_helper']) == plan['window_helper_sha256']
    for name, digest in {**plan['fixtures'], **plan['manifests']}.items():
        assert sha(ROOT / name) == digest, name
    host = artifacts(plan['host'], plan['fixtures'])
    assert host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE'
    assert sha(ROOT / 'evidence' / plan['host'] / 'results/result.json') == plan['host_result_sha256']
    assert sha(ROOT / 'evidence' / plan['host'] / 'source.tar.gz') == plan['host_capsule_sha256']
    assert sha(ROOT / 'evidence' / plan['host'] / 'results.tar.gz') == plan['host_archive_sha256']
    for name in ('03.log', '06.log'):
        assert '100% tests passed out of 31' in (ROOT / 'evidence' / plan['host'] / 'results' / name).read_text()
    receipt = artifacts(plan['gpu_label'], plan['fixtures'])
    assert receipt['state'] == 'SYNTHETIC_COUNTER_COLLECTION_COMPLETE_NOT_MODEL_INFERENCE'
    assert receipt['calibration_plan_sha256'] == sha(plan_path)
    assert not receipt['model_access'] and not receipt['headline_eligible']
    assert receipt['binary_sha256'] == receipt['binary_sha256_after']
    for cohort in (host, receipt):
        assert len(cohort['commands']) == 6 and all(c['exit_code'] == 0 for c in cohort['commands'])
    root = ROOT / 'evidence' / plan['gpu_label'] / 'results'
    complete_checks = []
    for index, mode in enumerate(('waves', 'read', 'waves', 'waves', 'read'), 2):
        records = [json.loads(line) for line in (root / f'{index:02d}.log').read_text().splitlines()
                   if line.startswith('{"event":')]
        geometry = [r for r in records if r['event'] == 'geometry']
        checks = [r for r in records if r['event'] == 'check']
        assert len(geometry) == 1 and geometry[0]['expected_waves'] == 512
        assert geometry[0]['threads'] == 16384 and geometry[0]['block_threads'] == 256
        # The fixture's legacy label records HIP multiProcessorCount (20),
        # whereas rocprofiler agent.cu_count below reports 40. They are not
        # interchangeable hardware fields and do not set the expected waves.
        assert geometry[0]['compute_units'] == 20 and geometry[0]['mode'] == mode
        assert geometry[0]['input_bytes'] == (268435456 if mode == 'read' else 0)
        assert [c['rep'] for c in checks] == list(range(10))
        assert all(c['exact'] and c['mode'] == mode and c['output_words'] == 16384 and c['guard_words'] == 64
                   for c in checks)
        complete_checks.append(dict(log=f'{index:02d}.log', mode=mode, checks=len(checks), geometry=geometry[0]))
    passes = []
    for specification in plan['passes']:
        name = specification['name']
        path = root / name / 'probe_counter_collection.csv'
        rows = list(csv.DictReader(path.open()))
        assert len(rows) == 10 * len(specification['counters'])
        expected_kernel = 'q2_counter_read_probe' if name == 'fetch' else 'q2_counter_wave_probe'
        csv_values = {}
        for row in rows:
            key = (int(row['Dispatch_Id']), row['Counter_Name'])
            assert key not in csv_values
            assert row['Kernel_Name'] == expected_kernel
            assert int(row['Grid_Size']) == 16384 and int(row['Workgroup_Size']) == 256
            value = float(row['Counter_Value'])
            assert math.isfinite(value)
            csv_values[key] = value
        assert set(csv_values) == {(i, counter) for i in range(1, 11) for counter in specification['counters']}
        exported = read(root / name / 'probe_results.json')['rocprofiler-sdk-tool']
        assert len(exported) == 1
        data = exported[0]
        agents = [a for a in data['agents'] if a['name'] == 'gfx1151']
        assert len(agents) == 1 and agents[0]['cu_count'] == 40 and agents[0]['wave_front_size'] == 32
        counters = {c['id']['handle']: c for c in data['counters']}
        kernels = {k['kernel_id']: k for k in data['kernel_symbols']}
        json_values = {}
        for dispatch in data['callback_records']['counter_collection']:
            info = dispatch['dispatch_data']['dispatch_info']
            assert kernels[info['kernel_id']]['formatted_kernel_name'] == expected_kernel
            assert info['grid_size'] == dict(x=16384, y=1, z=1)
            assert info['workgroup_size'] == dict(x=256, y=1, z=1)
            for record in dispatch['records']:
                counter = counters[record['counter_id']['handle']]['name']
                key = (info['dispatch_id'], counter)
                assert key not in json_values
                json_values[key] = record['value']
        assert csv_values == json_values
        values = {counter: [csv_values[(i, counter)] for i in range(1, 11)]
                  for counter in specification['counters']}
        if name == 'fetch':
            ratios = [v / plan['expected']['fetch_kib'] for v in values['FETCH_SIZE']]
            qualified = all(abs(r - 1) <= plan['expected']['fetch_relative_tolerance'] for r in ratios)
        else:
            ratios = None
            qualified = all(v == 512 for v in values['SQ_WAVES_sum'])
            if name == 'mixed': qualified &= all(v > 0 for v in values['GRBM_COUNT'])
        passes.append(dict(name=name, counters=values, qualified=qualified,
                           payload_ratios=ratios, csv_json_exact=True,
                           csv_sha256=sha(path), json_sha256=sha(root / name / 'probe_results.json')))
    release_path = ROOT / 'config/q2-counter-calibration-v2-window-release.json'
    release = read(release_path)
    assert not release['gpu_reserved'] and not release['kfd'] and release['model_stats_unchanged']
    assert not release['owned_group_members'] and not release['model_inference']
    assert plan['gpu_label'] in [c['label'] for c in release['cohorts']]
    for name in ('q2-counter-calibration-v2-window-release.json',
                 'q2-counter-calibration-v2-window-active.json', 'q2-counter-calibration-v2-ready.json'):
        assert (ROOT.parents[1] / 'run' / name).read_bytes() == release_path.read_bytes()
    thermal = {}
    for line in (root / 'telemetry.jsonl').read_text().splitlines():
        for sensor in json.loads(line)['thermal']:
            thermal[sensor['device']] = max(thermal.get(sensor['device'], 0), sensor['temperature_mc'])
    report = dict(schema='synapse-lie.q2-counter-calibration-results.v1',
        state='CALIBRATION_COMPLETE_WITH_PER_GROUP_VERDICTS',
        plan_sha256=sha(plan_path), analyzer_sha256=sha(Path(__file__)),
        label=plan['gpu_label'], finished_at=receipt['finished_at'],
        host_tests=plan['host_test_counts'],
        primary_command_exits=[c['exit_code'] for cohort in (host, receipt) for c in cohort['commands']],
        artifacts_verified=len(host['artifacts']) + len(receipt['artifacts']),
        fixture_files_verified=len(plan['fixtures']),
        gpu_topology=dict(hip_multiProcessorCount=20, rocprofiler_cu_count=40,
                          fixture_field_label='compute_units',
                          note='Saved fixture label means the HIP API field; do not substitute it for rocprofiler CU count.'),
        binary_sha256=receipt['binary_sha256'], complete_checks=complete_checks,
        complete_check_count=sum(c['checks'] for c in complete_checks), passes=passes,
        thermal_max_mc=thermal, release_at=release['at'], release_sha256=sha(release_path),
        retained=read(ROOT / 'config/q2-retained-counter-capabilities.json')['retained'],
        disposition='Use only the groups that passed their declared control. FETCH_SIZE is ineligible for bandwidth diagnosis; never multiply it by two as an assumed correction.',
        limits='Known synthetic wave32 kernels on one40-CU gfx1151 device. This does not qualify other counters, derived occupancy, model traffic or DRAM bandwidth. JSON exposes derived scalar counts, not the underlying GL2C instance coverage. No model inference or throughput measurement is added.',
        model_inference=False, controls_rerun=False, throughput_change_claimed=False,
        goal_met=False)
    destination = ROOT / 'config/q2-counter-calibration-results.json'
    with destination.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(report=str(destination.relative_to(ROOT)), checks=report['complete_check_count'],
                          passes=passes, thermal_max_mc=thermal, release_sha256=sha(release_path))))


if __name__ == '__main__':
    main()
