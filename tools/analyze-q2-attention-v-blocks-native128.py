#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare the new prefill value-block model trial with frozen original128K evidence."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence/q2-attention-v-blocks-native128-r1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def main():
    window = module('v_blocks_window', 'tools/q2-attention-v-blocks-native128-window.py')
    helper = module('prior_audit', 'tools/analyze-q2-decode-down-rows-native128-performance.py')
    plan_path = ROOT / 'config/q2-attention-v-blocks-native128-plan.json'
    plan = read(plan_path)
    require(sha(EVIDENCE/'plan.json') == sha(plan_path), 'Frozen plan differs')
    require(sha(ROOT/'tools/q2-attention-v-blocks-native128-window.py') == plan['runner_sha256'],
            'Measured validator differs')
    artifacts = read(EVIDENCE/'artifact-hashes.json')
    for name, digest in artifacts.items():
        require(sha(EVIDENCE/name) == digest, 'Collected artifact differs: ' + name)
    for name, digest in plan['staged_sha256'].items():
        require(sha(EVIDENCE/name) == digest, 'Staged artifact differs: ' + name)
    for name, digest in plan['saved_reference_sha256'].items():
        require(sha(ROOT/name) == digest, 'Saved reference differs: ' + name)
    for name in ('cpu-test', 'verify', 'admit', 'run', 'release'):
        require(read(EVIDENCE/(name+'-command.json'))['exit_code'] == 0,
                'Command failed: ' + name)
    build = read(EVIDENCE/'native-build.json')
    require(build['build_type'] == build['saved_build_type'] == 'RelWithDebInfo' and
            build['common_device_functions'] == build['byte_exact_device_functions'] == 923 and
            build['server_sha256'] == sha(EVIDENCE/'synapse-lie-server') ==
            plan['candidate_server']['sha256'], 'Binary/build contract differs')
    release = read(EVIDENCE/'release.json')
    result = read(EVIDENCE/'results/native-result.json')
    closure = read(EVIDENCE/'release-registry-check.json')
    require(result['state'] == release['pair_state'] == 'COMPLETE' and
            result['plan_sha256'] == release['plan_sha256'] == sha(plan_path) and
            release['pair_result_sha256'] == sha(EVIDENCE/'results/native-result.json') and
            release['boot_id'] == plan['boot_id'] and
            all(release[k] for k in ('kfd_empty','original_model_stats_unchanged','original_leases_free')) and
            not release['gpu_reserved'] and closure['registry_matches'] and
            closure['release_sha256'] == sha(EVIDENCE/'release.json'), 'Closure differs')
    collection = read(EVIDENCE/'local-collection-check.json')
    require(collection['all_sha256_verified'] and collection['at'] < release['at'],
            'Collection did not precede release')
    children = read(EVIDENCE/'results/00-v-blocks.children.json')
    require(children['server_exit_code'] == children['client_exit_code'] == 0, 'Child failed')
    cases = [json.loads(line) for line in (EVIDENCE/'requests.jsonl').read_text().splitlines()]
    paths = {
        'original': ROOT/'evidence/q2-full-prefill128-final-r1/results/full-prefill.jsonl',
        'down_rows': ROOT/'evidence/q2-decode-down-rows-native128-r3/results/00-down-rows.jsonl',
        'v_blocks': EVIDENCE/'results/00-v-blocks.jsonl'}
    samples = {key:window.validate_output(path,cases) for key,path in paths.items()}
    hc = read(ROOT/'config/q2-hc-scalar-native128-isolated-results.json')['new']
    rates = {key:{k:v for k,v in s.items() if k != 'outputs'} for key,s in samples.items()}
    rates['isolated_hc'] = hc
    new, old = rates['v_blocks'], rates['down_rows']
    exact = samples['v_blocks']['outputs'] == samples['down_rows']['outputs'] == samples['original']['outputs']
    require(json.loads(json.dumps(samples['v_blocks']['outputs'])) == result['arms'][0]['outputs'],
            'Persisted outputs differ')
    for phase in ('before', 'after'):
        window.validate_power(read(EVIDENCE/('results/power-'+phase+'.json')))
    report = dict(schema='synapse-lie.q2-attention-v-blocks-native128-results.v1',
        source_commit=plan['source_commit'], plan_sha256=sha(plan_path),
        server_sha256=plan['candidate_server']['sha256'],
        client_sha256=plan['client']['sha256'], request_sha256=plan['requests']['sha256'],
        tokens=130925, prefill_calls=64, full_chunks=63, tail_tokens=1901,
        output_tokens=8, decode_calls=8, cached_tokens=0,
        all_four_outputs_exact=exact, rates=rates,
        prefill_change_vs_down_rows_percent=100*(new['prefill_tps']/old['prefill_tps']-1),
        decode_change_vs_down_rows_percent=100*(new['decode_tps']/old['decode_tps']-1),
        new_telemetry=helper.telemetry(EVIDENCE/'results/00-v-blocks.telemetry.jsonl'),
        saved_telemetry=helper.telemetry(paths['down_rows'].with_suffix('.telemetry.jsonl')),
        power_mode_verified_before_after=True, controls_rebuilt_or_rerun=False,
        new_precision_reduction=False, sustained_tg128_measured=False,
        independent_parent_quality_qualified=False, model_promoted=False, goal_met=False,
        artifact_count=len(artifacts), release_at=release['at'],
        release_sha256=sha(EVIDENCE/'release.json'),
        decision=('Retain the new prefill observation for phase-specific composition; original reference remains visible.' if new['prefill_tps'] > old['prefill_tps'] and exact else 'No verified positive prefill model result; retain down-rows and preserve the component evidence.'),
        prefill_only_implementation=True, additional_allocated_bytes=0,
        decode_device_functions_unchanged=True,
        limits=['One new original130925/8 observation; saved references were not rerun.',
                'Eight AR calls do not establish sustained TG128 or task quality.',
                'Decode source/device kernels are unchanged; observed TG variation is not a new decode-kernel improvement.'])
    out=ROOT/'config/q2-attention-v-blocks-native128-results.json'
    out.write_text(json.dumps(report,indent=2)+'\n')
    labels={'original':'Original saved Q2','isolated_hc':'Isolated HC','down_rows':'Retained Q2 down rows','v_blocks':'Prefill V blocks candidate'}
    with (ROOT/'docs/figures/q2-attention-v-blocks-native128.csv').open('w') as stream:
        writer=csv.writer(stream, lineterminator='\n');writer.writerow(['variant','prefill_tps','decode_tps','prefill_ms','decode_ms'])
        for key,label in labels.items():
            row=rates[key];writer.writerow([label,*[row[k] for k in ('prefill_tps','decode_tps','prefill_ms','decode_ms')]])
    print(json.dumps({k:v for k,v in report.items() if k not in ('rates','new_telemetry','saved_telemetry','limits')}))


if __name__ == '__main__':
    main()
