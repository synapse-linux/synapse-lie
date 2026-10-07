#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the recovered original 130925-token Q2 trial against saved controls."""

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import statistics

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence/q2-decode-down-rows-native128-r2'
CONTROL = ROOT / 'evidence/q2-full-prefill128-final-r1/results'
spec = importlib.util.spec_from_file_location(
    'hc_native128', ROOT / 'tools/q2-decode-down-rows-native128-recovery-window.py')
window = importlib.util.module_from_spec(spec)
spec.loader.exec_module(window)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def telemetry(path):
    """Descriptive active samples, never a frequency-normalized benchmark."""
    clocks, busy, cpus, gpus = [], [], [], []
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    for row in rows:
        if 'sensors' in row:
            sensors = row['sensors']
            base = '/sys/class/drm/card1/device/'
            use = int(sensors[base + 'gpu_busy_percent'])
            clock = sensors[base + 'pp_dpm_sclk']
            gpu = next(t['temperature_mc'] for t in row['thermal']
                       if t['device'] == 'amdgpu')
            cpu = max(t['temperature_mc'] for t in row['thermal']
                      if t['device'] == 'k10temp')
        else:
            use, clock = int(row['gpu_busy']), row['gpu_clock']
            gpu, cpu = int(row['gpu_temp_mc']), row['cpu_temp_mc']
        cpus.append(cpu)
        gpus.append(gpu)
        if use >= 80:
            busy.append(use)
            clocks.append(int(re.search(r'(\d+)Mhz \*', clock).group(1)))
    return {'path': str(path.relative_to(ROOT)), 'sha256': sha(path),
            'sample_count': len(rows), 'gpu_busy_ge80_samples': len(clocks),
            'active_clock_mean_mhz': statistics.mean(clocks),
            'active_clock_median_mhz': statistics.median(clocks),
            'active_gpu_busy_mean_percent': statistics.mean(busy),
            'sampled_peak_cpu_mc': max(cpus), 'sampled_peak_gpu_mc': max(gpus)}


def main():
    plan_path = ROOT / 'config/q2-decode-down-rows-native128-recovery-plan.json'
    plan = read(plan_path)
    build = read(EVIDENCE / 'native-build.json')
    require(build['build_type'] == build['saved_build_type'] == 'RelWithDebInfo' and
            build['common_function_size_changes'] == 0 and
            build['common_function_resource_changes'] == 0 and
            build['server_sha256'] == plan['candidate_server']['sha256'],
            'Matching build contract differs')
    require(sha(EVIDENCE / 'plan.json') == sha(plan_path), 'Frozen plan differs')
    require(sha(ROOT / 'tools/q2-decode-down-rows-native128-recovery-window.py') ==
            plan['runner_sha256'], 'Measured validator differs')
    artifacts = read(EVIDENCE / 'artifact-hashes.json')
    for name, digest in artifacts.items():
        require(sha(EVIDENCE / name) == digest, 'Collected artifact differs: ' + name)
    for name, digest in plan['staged_sha256'].items():
        require(sha(EVIDENCE / name) == digest, 'Staged artifact differs: ' + name)
    for name, digest in plan['saved_reference_sha256'].items():
        require(sha(ROOT / name) == digest, 'Saved reference differs: ' + name)
    result, release = read(EVIDENCE / 'results/native-result.json'), read(EVIDENCE / 'release.json')
    require(result['state'] == 'COMPLETE' and len(result['arms']) == 1 and
            result['plan_sha256'] == sha(plan_path), 'Native result incomplete')
    require(release['pair_result_sha256'] == sha(EVIDENCE / 'results/native-result.json') and
            release['plan_sha256'] == sha(plan_path) and release['pair_state'] == 'COMPLETE' and
            release['kfd_empty'] and release['original_model_stats_unchanged'] and
            release['original_leases_free'] and not release['gpu_reserved'], 'Closure differs')
    require(release['boot_id'] == plan['boot_id'], 'Release boot differs')
    for label in ('cpu-test', 'verify', 'run'):
        require(read(EVIDENCE / (label + '-command.json'))['exit_code'] == 0,
                'Command failed: ' + label)
    children = read(EVIDENCE / 'results/00-down-rows.children.json')
    require(children['server_exit_code'] == 0 and children['client_exit_code'] == 0,
            'Native child exit differs')
    cases = [json.loads(line) for line in (EVIDENCE / 'requests.jsonl').read_text().splitlines()]
    new = window.validate_output(EVIDENCE / 'results/00-down-rows.jsonl', cases)
    old = window.validate_output(CONTROL / 'full-prefill.jsonl', cases)
    require(result['arms'][0]['outputs'] == json.loads(json.dumps(new['outputs'])),
            'Persisted native output differs')
    require(sha(EVIDENCE / 'requests.jsonl') == sha(CONTROL / 'full-prefill.requests.jsonl'),
            'Saved request sequence differs')
    report = {'schema': 'synapse-lie.q2-decode-down-rows-native128-results.v1',
              'boot_id': plan['boot_id'],
              'recovery_after_owner_reported_power_outage': True,
              'interrupted_predecessor_sha256': plan['interrupted_predecessor_sha256'],
              'source_commit': plan['source_commit'], 'plan_sha256': sha(plan_path),
              'server_sha256': plan['candidate_server']['sha256'],
              'build_manifest_sha256': sha(EVIDENCE / 'native-build.json'),
              'client_sha256': plan['client']['sha256'],
              'request_sha256': plan['requests']['sha256'],
              'tokens': 130925, 'prefill_calls': 64, 'full_chunks': 63, 'tail_tokens': 1901,
              'cached_tokens': 0, 'output_tokens': 8, 'decode_calls': 8,
              'all_four_outputs_exact': old['outputs'] == new['outputs'],
              'new': {k: new[k] for k in ('prefill_ms', 'prefill_tps', 'decode_ms', 'decode_tps')},
              'saved_unprofiled': {
                  'path': str((CONTROL / 'full-prefill.jsonl').relative_to(ROOT)),
                  'sha256': sha(CONTROL / 'full-prefill.jsonl'),
                  **{k: old[k] for k in ('prefill_ms', 'prefill_tps', 'decode_ms', 'decode_tps')}},
              'prefill_change_percent': 100 * (new['prefill_tps'] / old['prefill_tps'] - 1),
              'decode_change_percent': 100 * (new['decode_tps'] / old['decode_tps'] - 1),
              'target_prefill_ms': 130925000 / 1500,
              'new_prefill_excess_ms': new['prefill_ms'] - 130925000 / 1500,
              'new_decode_ms_per_call': new['decode_ms'] / 8,
              'target_decode_ms_per_call': 1000 / 30,
              'new_telemetry': telemetry(EVIDENCE / 'results/00-down-rows.telemetry.jsonl'),
              'saved_telemetry': telemetry(CONTROL / 'telemetry.jsonl'),
              'server_exit_code': children['server_exit_code'],
              'client_exit_code': children['client_exit_code'], 'artifact_count': len(artifacts),
              'release_at': release['at'], 'release_sha256': sha(EVIDENCE / 'release.json'),
              'retired_identities': len(release['retired_identities']),
              'retired_groups': len(release['retired_groups']),
              'controls_rebuilt_or_rerun': False, 'candidate_rebuilt_for_depth': False, 'candidate_common_flags_match_control': True, 'new_file_compile_options': '-std=gnu++17;-fPIC;-DGGML_HIP_NO_VMM;-Wno-unused-value',
              'build_modes_match': True, 'build_type': 'RelWithDebInfo',
              'new_precision_reduction': False, 'sustained_tg128_measured': False,
              'independent_parent_quality_qualified': False, 'goal_met': False,
              'limits': ['One new observation after a power outage against historical unprofiled controls; host restart/page-cache state is not normalized.',
                         'Eight native output calls are not sustained TG128.',
                         'Exact replies do not settle component rounding differences or inherited task quality.',
                         'Active clock/busy samples describe correlation, not causality.',
                         'Neither clocks nor cache capture correct the measured prefill rate.']}
    previous_path = ROOT / 'config/q2-hc-scalar-native128-isolated-results.json'
    previous = read(previous_path)
    require(previous['request_sha256'] == report['request_sha256'] and
            previous['client_sha256'] == report['client_sha256'],
            'Previous isolated measurement scope differs')
    report['saved_isolated_up_mix'] = {
        'path': str(previous_path.relative_to(ROOT)), 'sha256': sha(previous_path),
        **previous['new']}
    report['incremental_prefill_change_percent'] = 100 * (
        new['prefill_tps'] / previous['new']['prefill_tps'] - 1)
    report['incremental_decode_change_percent'] = 100 * (
        new['decode_tps'] / previous['new']['decode_tps'] - 1)
    diagnostic_path = ROOT / 'config/q2-post-reboot-apu-observation.json'
    diagnostic = read(diagnostic_path)
    for key in ('raw', 'command', 'last_saved_live_apu'):
        item = diagnostic[key]
        require(sha(ROOT / item['path']) == item['sha256'],
                'APU observation source differs: ' + key)
    require(diagnostic['boot_id'] == plan['boot_id'] and
            diagnostic['remote_read_only'] and diagnostic['observed_after_r2'] and
            diagnostic['fan_curves_unchanged'] and diagnostic['stored_config_unchanged'],
            'Post-run APU observation differs')
    report['power_observation'] = {
        'path': str(diagnostic_path.relative_to(ROOT)), 'sha256': sha(diagnostic_path),
        'observed_after_r2': True, 'current_apu': diagnostic['current_apu'],
        'last_saved_live_apu': diagnostic['last_saved_live_apu'],
        'fan_curves_unchanged': True, 'during_run_mode_sampled': False}
    report['runtime_conditions_match_saved_controls'] = False
    report['candidate_promoted'] = False
    report['retained_telemetry'] = telemetry(ROOT / previous['new_telemetry']['path'])
    report['limits'].insert(0, 'Post-run APU is balanced/85 W versus the last saved live performance/120 W state; power conditions differ, so throughput deltas do not isolate the candidate.')
    report['limits'].insert(1, 'The APU mode is not sampled during either benchmark. Historical GPU clocks and power support the discrepancy, without quantifying its causal effect.')
    output = ROOT / 'config/q2-decode-down-rows-native128-recovery-results.json'
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
