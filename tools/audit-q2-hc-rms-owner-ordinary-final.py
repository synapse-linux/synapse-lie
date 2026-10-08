#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit a collected, released single-model retry against its fixed evidence."""
import csv
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hc', ROOT / 'tools/analyze-q2-hc-bk256.py')
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)
require, sha, read = hc.require, hc.sha, hc.read


def main():
    prefix = 'q2-hc-rms-owner-ordinary'
    output = ROOT / ('config/' + prefix + '-final-audit.json')
    require(not output.exists(), 'Preserve existing audit')
    plan_path = ROOT / ('config/' + prefix + '-plan.json')
    plan = read(plan_path)
    frozen = {**plan['fixtures'], **plan['manifests']}
    for name, digest in frozen.items():
        require(sha(ROOT / name) == digest, 'Frozen identity differs: ' + name)
    report_path = ROOT / ('config/' + prefix + '-model-results.json')
    report = read(report_path)
    require(report['plan_sha256'] == sha(plan_path) and not report['controls_rerun'] and
            not report['component_rerun'] and report['original_tester_unchanged'],
            'Model-only protocol differs')
    release_path = ROOT / plan['release_path']
    release = read(release_path)
    require(report['release_sha256'] == sha(release_path) and
            release['state'] == 'Q2_HC_RMS_OWNER_ORDINARY_WINDOW_RELEASED' and
            not release['gpu_reserved'] and not release['kfd'] and
            not release['owned_group_members'] and release['model_stats_unchanged'],
            'Window closure differs')
    require(all(row['unchanged_free_EX_NB'] for row in release['leases']) and
            release['core_cpu_lease'] == plan['core_cpu_lease'], 'Original lease witness differs')
    for suffix in ('window-release', 'window-active', 'ready'):
        require(sha(ROOT.parents[1] / 'run' / (prefix + '-' + suffix + '.json')) ==
                sha(release_path), 'Canonical main mirror differs')
    provider = read(ROOT / plan['source_variant_manifest'])['variants']['hc-rms-owner-ordinary']
    source = ROOT / provider['source']
    inventory = {str(p.relative_to(source)): sha(p) for p in source.rglob('*') if p.is_file()}
    require(inventory == provider['files'] and len(inventory) == 1028, 'Provider inventory differs')
    artifact_count = 0
    exits = []
    for label in (plan['host'], plan['arms'][0]['label']):
        cohort = ROOT / 'evidence' / label
        receipt = hc.curve.artifacts(cohort)
        artifact_count += len(receipt['artifacts'])
        exits.extend(c['exit_code'] for c in receipt['commands'])
        hc.capsule(cohort, frozen, provider['files'] if label == plan['arms'][0]['label'] else None)
    require(exits == [0] * 10 and artifact_count == 33, 'Qualified commands or collection differs')
    failures = []
    for row in plan['retired_cpu_cohorts']:
        directory = ROOT / 'evidence' / row['label']
        receipt, transport = hc.curve.artifact_integrity(directory)
        require(sha(directory / 'results/result.json') == row['result_sha256'] and
                receipt['state'] == 'FAILED' and transport['exit_code'] == 1 and
                [c['exit_code'] for c in receipt['commands']] == [0, 0, 8],
                'Historical CPU failure lost')
        failures.append(dict(label=row['label'], command_exits=[0, 0, 8],
                             artifacts=len(receipt['artifacts'])))
        artifact_count += len(receipt['artifacts'])
    require(len(failures) == 2, 'Preserved failure inventory differs')
    require(report['within_arm_exact'] and report['checks']['best_parent']['changed_files'] == [] and
            len(report['replay']['best_parent']['files']) == 21 and
            report['checks']['best_parent']['max_matched_history_kl'] == 0,
            'Exact parent replay differs')
    fixed = read(ROOT / 'config/q2-fixed-prefill-reference.json')
    for key, saved in (('fixed_q2', 'mixed'), ('fixed_ud', 'ud')):
        require(report['references'][key]['measurements'] == fixed['arms'][saved]['measurements'],
                'Fixed reference differs')
    prep = ROOT / 'evidence' / (prefix + '-runtime-preparation')
    commands = {label: read(prep / (label + '-command.json')) for label in
                ('core-handover', 'host-r3', 'collect-host-r3', 'freeze', 'transfer',
                 'admission', 'publish-admission', 'model', 'collect-model', 'release',
                 'publish-release', 'analysis', 'plot')}
    require(all(row['exit_code'] == 0 for row in commands.values()), 'Successful command receipt differs')
    require(commands['analysis']['started_at'] > commands['publish-release']['finished_at'],
            'Analysis preceded collected release')
    graph = ROOT / 'docs/figures' / (prefix + '-model')
    with graph.with_suffix('.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    require(len(rows) == 16 and sum(row['historical'] == 'False' for row in rows) == 4,
            'Full sample export differs')
    result = dict(schema='synapse-lie.q2-hc-rms-owner-ordinary-final-audit.v1',
                  plan_sha256=sha(plan_path), model_result_sha256=sha(report_path),
                  release_sha256=sha(release_path), qualified_command_exits=exits,
                  command_receipts={name: dict(exit_code=row['exit_code'],
                      sha256=sha(prep / (name + '-command.json'))) for name, row in commands.items()},
                  preserved_CPU_failures=failures, verified_artifacts=artifact_count,
                  frozen_files=len(frozen), provider_files=1028, exact_parent_files=21,
                  samples_exported=16, retired_identities=len(release['retired_identities']),
                  retired_groups=len(release['retired_groups']), controls_rerun=False,
                  component_rerun=False, performance_default='ssm-fixed-bounds',
                  robust_model_speedup=False, independent_quality=False, goal_met=False,
                  report_tool_sha256=sha(ROOT / 'tools/analyze-q2-hc-rms-owner-ordinary-model.py'),
                  graph_hashes={suffix: sha(graph.with_suffix(suffix)) for suffix in ('.csv', '.svg', '.png')})
    hc.write(output, result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
