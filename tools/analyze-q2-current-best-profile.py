#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind a saved-candidate trace to original2048 input and retained evidence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sqlite3
import statistics
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / name)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


hc = module('analyze-q2-hc-bk256.py')
profile = module('analyze-q2-profile.py')
resources = module('q2-resource-report.py')
require, sha, read = hc.require, hc.sha, hc.read


def stage(name):
    routed = re.search(r'(?:RoutedF16GEMMKernel|RoutedQ2HalfStorageKernel)<.*?WeightType\)(\d+),', name)
    if routed:
        require(routed[1] in ('10', '16'), 'Unexpected routed weight type')
        return 'routed_down_q2' if routed[1] == '10' else 'routed_gate_up_iq2'
    moe = re.search(r'mul_mat_vec_q_moe<.*?ggml_type\)(\d+),', name)
    if moe:
        require(moe[1] in ('10', '16'), 'Unexpected vector expert weight type')
        return 'routed_down_q2' if moe[1] == '10' else 'routed_gate_up_iq2'
    if 'HcDown' in name:
        return 'hc_down_f16'
    dense = re.search(r'DenseF16GEMMKernel<([^<>]+)>', name)
    if dense:
        args = [a.strip() for a in dense[1].split(',')]
        require(len(args) == 11 and args[9] in ('true', 'false'), 'Unknown dense contract')
        return 'hc_up_mix_f16' if args[9] == 'true' else 'dense_q8_f16_activations'
    if 'HcMixDeferredNormKernel' in name or 'HcUpF16VecKernel' in name:
        return 'hc_up_mix_f16'
    if 'HcCombine' in name or 'HcInject' in name or 'HcMixEpilogue' in name:
        return 'hc_norm_combine_inject'
    if any(x in name for x in ('WKQuantA8Blocked', 'W8A8Blocked', 'mul_mat_vec_q8<')):
        return 'dense_q8_quantized_activations'
    if any(x in name for x in ('Gdn', 'SsmConv')):
        return 'gdn_ssm'
    if any(x in name for x in ('Attention', 'Rope', 'StoreKv', 'SelectScore', 'SelectMark', 'PoolBlocks')):
        return 'attention_state'
    if any(x in name for x in ('Quantize', 'quantize_', 'Narrow', 'PackQ2ScaledRows')):
        return 'activation_packing'
    return 'other'


def geometry(database):
    with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True) as db:
        rows = db.execute('''SELECT ks.display_name,kd.start,kd.end,
            kd.grid_size_x,kd.grid_size_y,kd.grid_size_z,
            kd.workgroup_size_x,kd.workgroup_size_y,kd.workgroup_size_z
            FROM rocpd_kernel_dispatch kd
            JOIN rocpd_info_kernel_symbol ks ON ks.id=kd.kernel_id ORDER BY kd.start''').fetchall()
    begin = [r for r in rows if 'Q2ProfilePrefillBegin' in r[0]]
    end = [r for r in rows if 'Q2ProfilePrefillEnd' in r[0]]
    require(len(begin) == len(end) == 1, 'Missing unique PP marker')
    selected = [r for r in rows if begin[0][2] <= r[1] and r[2] <= end[0][1]
                and any(k in r[0] for k in ('RoutedF16GEMMKernel<', 'RoutedQ2HalfStorageKernel<'))]
    require(len(selected) == 144, 'Expected three expert dispatches per48 layers')
    layers = []
    for layer in range(48):
        wide, tail, down = selected[layer * 3:layer * 3 + 3]
        for row, weight, width, columns in ((wide, 16, 128, 10), (tail, 16, 64, 10),
                                           (down, 10, 48, 20)):
            require(f'WeightType){weight}, 128, {width}, 2,' in row[0] and
                    row[3:] == (columns * 256, row[4], 1, 256, 1, 1) and row[4] > 0,
                    'Routed geometry differs from frozen production launch')
        gate_slots = wide[4] * 128 + tail[4] * 64
        down_slots = down[4] * 48
        require(gate_slots >= 20480 and down_slots >= 20480, 'Insufficient routed capacity')
        layers.append(dict(layer=layer, iq2_128_tiles=wide[4], iq2_64_tiles=tail[4],
            q2_48_tiles=down[4], gate_reserved_slots=gate_slots, down_reserved_slots=down_slots,
            gate_actual_rows_fraction=20480 / gate_slots, down_actual_rows_fraction=20480 / down_slots,
            gate_ms=(wide[2]-wide[1]+tail[2]-tail[1])/1e6, down_ms=(down[2]-down[1])/1e6))
    return dict(layers=layers, actual_routes_per_layer=20480,
        median_q2_48_tiles=statistics.median(r['q2_48_tiles'] for r in layers),
        median_iq2_128_tiles=statistics.median(r['iq2_128_tiles'] for r in layers),
        median_iq2_64_tiles=statistics.median(r['iq2_64_tiles'] for r in layers),
        gate_aggregate_actual_rows_fraction=48*20480/sum(r['gate_reserved_slots'] for r in layers),
        down_aggregate_actual_rows_fraction=48*20480/sum(r['down_reserved_slots'] for r in layers),
        scope='Dispatch-map row capacity, not active-lane occupancy or per-expert histogram',
        per_expert_counts_available=False)


def main():
    destination = ROOT/'config/q2-current-best-profile-results.json'
    require(not destination.exists(), 'Refusing to overwrite trace evidence')
    plan_path = ROOT/'config/q2-current-best-profile-plan.json'
    plan = read(plan_path)
    for name, digest in {**plan['fixtures'], **plan['frozen_manifests']}.items():
        require(sha(ROOT/name) == digest, 'Frozen local identity changed: '+name)
    require(sha(ROOT/plan['window_helper']) == plan['window_helper_sha256'], 'Corrected helper changed')
    require(not plan['headline_eligible'] and not plan['run_controls'] and plan['build_commands'] == 0,
            'Diagnostic-only scope changed')
    host_path = ROOT/'evidence/q2-current-best-profile-host-r1'
    host = hc.curve.artifacts(host_path)
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and
            len(host['commands']) == 6 and not host['model_access'] and not host['locks'], 'Host scope changed')
    for name in ('03.log', '06.log'):
        require('100% tests passed out of 27' in (host_path/'results'/name).read_text(), 'Host tests incomplete')
    arm = plan['arms'][0]
    path = ROOT/'evidence'/arm['label']
    result = hc.curve.artifacts(path)
    transport = read(path/'transport.json')
    require(result['state'] == 'DIAGNOSTIC_PROFILE_COMPLETE_NOT_WALL_BENCHMARK' and
            result['mode'] == transport['mode'] == arm['mode'] and result['headline_eligible'] is False and
            transport['source_variant'] == arm['variant'] and not transport['rebuild_mmq'] and
            not transport['detached'] and len(result['commands']) == 5 and result['model_access'],
            'Diagnostic execution differs')
    require(result['commands'][0]['argv'][0] == 'ldd' and
            Path(result['commands'][1]['argv'][0]).name == 'rocprofv3' and
            result['commands'][1]['argv'][-1] == 'profile' and
            all(c['argv'][0] != 'cmake' for c in result['commands']), 'Unexpected build/workload')
    require(result['binary_sha256'] == result['binary_sha256_after'] and
            result['models_before'] == result['models_after'] and
            result['locks'] == result['postflight_locks'] and len(result['locks']) == 4 and
            not result['preflight_kfd'] and not result['postflight_kfd'], 'Runtime ownership changed')
    binding = read(ROOT/'config/q2-current-best-profile-binary.json')['controls']['q2-half-consumer-eight-model-r1']
    saved_path = ROOT/'evidence/q2-half-consumer-eight-model-r1'
    saved = hc.curve.artifacts(saved_path)
    require(sha(saved_path/'results/result.json') == binding['receipt_sha256'] and
            result['binary_sha256'] == saved['binary_sha256_after'] == binding['binary_sha256'] and
            result['runtime_libraries'] == saved['runtime_libraries'] == binding['libraries'], 'Saved binary/lib changed')
    require(result['models_before'] == saved['models_after'] and result['locks'] == saved['locks'],
            'Original model stat or lease identities changed')
    require(result['qualified_binary_replay']['historical_library_hashes_available'] and
            result['qualified_binary_replay']['build_commands'] == 0, 'Saved replay metadata incomplete')
    source = read(ROOT/'config/q2-half-consumer-eight-source.json')['variants'][arm['variant']]['files']
    capsules = dict(host=hc.capsule(host_path, plan['fixtures']),
                    trace=hc.capsule(path, plan['fixtures'], source))
    hc.capsule(saved_path, {'experiments/counting-baseline/q2_model.cpp': binding['fixture_sha256'],
                           'tests/q2_profile_markers.hip': binding['markers_sha256']}, source)
    for folder in (host_path, path):
        with tarfile.open(folder/'source.tar.gz') as archive:
            for name, digest in plan['frozen_manifests'].items():
                require(hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest,
                        'Capsule manifest differs: '+name)
    directory = path/'results'
    require(sha(directory/'profile2048-input.i32') == plan['input_sha256'] ==
            sha(saved_path/'results/pp2048-input.i32') and
            (directory/'profile2048-input.i32').stat().st_size == 8192, 'Original2048 input changed')
    events = [json.loads(line) for line in (directory/'02.log').read_text().splitlines()
              if line.startswith('{"event"')]
    samples = [e for e in events if e['event'] == 'sample']
    require([e['label'] for e in samples] == ['arithmetic', 'counting', 'warm2048', 'profile2048'] and
            any(e['event'] == 'complete' and e['semantic_smoke'] and e['finite_frontiers'] for e in events),
            'Incomplete diagnostic replay')
    loaded = next(e for e in events if e['event'] == 'loaded')
    require(loaded['max_context'] == 9216 and loaded['prefill_chunk'] == 2048 and not loaded['mtp'],
            'Model context configuration changed')
    for sample in samples[2:]:
        require(sample['prompt_tokens'] == 2048 and sample['output_tokens'] == 16 and
                sample['decode_steps'] == 15 and not sample['eos'], 'Diagnostic shape changed')
    replay = []
    for prefix in ('warm2048', 'profile2048'):
        require((directory/f'{prefix}-0-prefill.f32').read_bytes() ==
                (saved_path/'results/pp2048-0-prefill.f32').read_bytes(), 'Saved prefill logits differ')
        require((directory/f'{prefix}-0-output.u32').read_bytes() ==
                (saved_path/'results/pp2048-0-output.u32').read_bytes()[:64], 'Saved greedy prefix differs')
        replay.append(dict(prefix=prefix, prefill_logits_exact=True, first16_tokens_exact=True))
    require((directory/'warm2048-0-last.f32').read_bytes() ==
            (directory/'profile2048-0-last.f32').read_bytes(), 'Within-trace last logits differ')
    database = directory/'profile/q2_results.db'
    raw = profile.analyze(database)
    resource = resources.report(database)
    require(raw == read(directory/'profile-phases.json') and
            resource == read(directory/'profile-resources.json'), 'Trace recomputation differs')
    phases = {}
    for phase, data in raw['phases'].items():
        groups = {}
        for row in data['kernels']:
            entry = groups.setdefault(stage(row['kernel']), dict(calls=0, total_ns=0))
            entry['calls'] += row['calls']
            entry['total_ns'] += row['total_ns']
        require(sum(g['total_ns'] for g in groups.values()) == data['kernel_sum_ns'], 'Lost grouped time')
        phases[phase] = dict(**data, gpu_busy_fraction=data['gpu_busy_union_ns']/data['kernel_span_ns'],
            stages=[dict(stage=s, **v, kernel_time_percent=100*v['total_ns']/data['kernel_sum_ns'])
                    for s, v in sorted(groups.items(), key=lambda pair: pair[1]['total_ns'], reverse=True)],
            resources=resource['phases'][phase])
    release = read(ROOT/'config/q2-current-best-profile-window-release.json')
    require(release['state'] == 'Q2_CURRENT_BEST_PROFILE_WINDOW_RELEASED' and not release['kfd'] and
            not release['gpu_reserved'] and release['model_stats_unchanged'], 'Window still open')
    telemetry = [json.loads(line) for line in (directory/'telemetry.jsonl').read_text().splitlines()]
    maxima = {device: max(row['temperature_mc'] for t in telemetry for row in t['thermal']
                          if row['device'] == device) for device in ('k10temp', 'amdgpu')}
    report = dict(schema='synapse-lie.q2-current-best-profile.v1', plan_sha256=sha(plan_path), capsules=capsules,
        command_exits=[0]*5, build_commands=0, artifacts_verified=len(result['artifacts']),
        binary_sha256=result['binary_sha256'], qualified_receipt_sha256=binding['receipt_sha256'],
        source_files_verified=len(source), historical_and_current_library_hashes_verified=51,
        historical_library_hashes_available=result['qualified_binary_replay']['historical_library_hashes_available'],
        input_sha256=plan['input_sha256'], loaded=loaded, diagnostic_samples=samples,
        replay=replay, within_trace_last_logits_exact=True, phases=phases, routing=geometry(database),
        thermal_max_mc=maxima, release_sha256=sha(ROOT/'config/q2-current-best-profile-window-release.json'),
        saved_unprofiled_best=read(ROOT/'config/q2-half-consumer-eight-model-results.json')['model']['measurements'],
        headline_eligible=False, independent_quality_qualification=False, full_curve=False, goal_met=False)
    with destination.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    for phase, data in phases.items():
        print(phase, 'busy_fraction', data['gpu_busy_fraction'])
        for row in data['stages']:
            print(row['stage'], round(row['total_ns']/1e6, 3), round(row['kernel_time_percent'], 3))
    print('routing', json.dumps({k:v for k,v in report['routing'].items() if k != 'layers'}))


if __name__ == '__main__':
    main()
