#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit a collected, released component and one model trial against its fixed evidence."""
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
    prefix = 'q2-hc-inject-raw-q8'
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
            release['state'] == 'Q2_HC_INJECT_RAW_Q8_WINDOW_RELEASED' and
            not release['gpu_reserved'] and not release['kfd'] and
            not release['owned_group_members'] and release['model_stats_unchanged'],
            'Window closure differs')
    require(all(row['unchanged_free_EX_NB'] for row in release['leases']) and
            release['core_cpu_lease'] == plan['core_cpu_lease'], 'Original lease witness differs')
    for suffix in ('window-release', 'window-active', 'ready'):
        require(sha(ROOT.parents[1] / 'run' / (prefix + '-' + suffix + '.json')) ==
                sha(release_path), 'Canonical main mirror differs')
    provider = read(ROOT / plan['source_variant_manifest'])['variants']['hc-inject-raw-q8']
    source = ROOT / provider['source']
    inventory = {str(p.relative_to(source)): sha(p) for p in source.rglob('*') if p.is_file()}
    require(inventory == provider['files'] and len(inventory) == 1030, 'Provider inventory differs')
    artifact_count = 0
    exits = []
    for label in (plan['host'], plan['arms'][0]['label']):
        cohort = ROOT / 'evidence' / label
        receipt = hc.curve.artifacts(cohort)
        artifact_count += len(receipt['artifacts'])
        exits.extend(c['exit_code'] for c in receipt['commands'])
        hc.capsule(cohort, frozen, provider['files'] if label != plan['host'] else None)
    require(exits == [0] * 10 and artifact_count == 33, 'Qualified commands or collection differs')
    component_path = ROOT / plan['component_qualification']
    component = read(component_path)
    require(component['device_work_safe'] and not component['numerical_exact'] and
            len(component['output_records']) == 200 and component['command_exits'] == [0, 0, 1],
            'Saved component finite differences changed')
    hc.curve.artifact_integrity(ROOT / 'evidence' / component['label'])
    require(report['within_arm_exact'] and len(report['replay']['best_parent']['files']) == 21,
            'Deterministic replay or complete comparison missing')
    fixed = read(ROOT / 'config/q2-fixed-prefill-reference.json')
    for key, saved in (('fixed_q2', 'mixed'), ('fixed_ud', 'ud')):
        require(report['references'][key]['measurements'] == fixed['arms'][saved]['measurements'],
                'Fixed reference differs')
    prep = ROOT / 'evidence' / (prefix + '-preparation')
    successful = ('generation', 'assembly', 'static', 'fresh-handover', 'host', 'collect-host', 'freeze', 'transfer-window',
                  'admission', 'publish-admission', 'model',
                  'collect-model', 'release', 'publish-release', 'model-analysis', 'plot')
    commands = {label: read(prep / (label + '-command.json')) for label in successful}
    require(all(row['exit_code'] == 0 for row in commands.values()), 'Successful command receipt differs')
    require(commands['model-analysis']['started_at'] > commands['publish-release']['finished_at'],
            'Analysis preceded collected release')
    graph = ROOT / 'docs/figures' / (prefix + '-model')
    with graph.with_suffix('.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    require(len(rows) == 20 and sum(row['historical'] == 'False' for row in rows) == 4,
            'Full sample export differs')
    result = dict(schema='synapse-lie.q2-hc-inject-raw-q8-final-audit.v1',
                  plan_sha256=sha(plan_path), model_result_sha256=sha(report_path),
                  release_sha256=sha(release_path), qualified_command_exits=exits,
                  command_receipts={name: dict(exit_code=row['exit_code'],
                      sha256=sha(prep / (name + '-command.json'))) for name, row in commands.items()},
                  component_result_sha256=sha(component_path), component_output_records=200, component_recorded_exits=component['command_exits'],
                  component_rerun_required=False,
                  verified_artifacts=artifact_count,
                  frozen_files=len(frozen), provider_files=1030, compared_parent_files=21, changed_parent_files=report['checks']['best_parent']['changed_files'],
                  samples_exported=20, retired_identities=len(release['retired_identities']),
                  retired_groups=len(release['retired_groups']), controls_rerun=False,
                  component_rerun=False, performance_default=report['source_variant'] if report['candidate_median_change_percent']['best_parent']['prefill_tok_s'] > 0 else 'iq2-fixed-bounds',
                  robust_model_speedup=False, independent_quality=False, goal_met=False,
                  report_tool_sha256=sha(ROOT / 'tools/analyze-q2-hc-inject-raw-q8-model.py'),
                  graph_hashes={suffix: sha(graph.with_suffix(suffix)) for suffix in ('.csv', '.svg', '.png')})
    hc.write(output, result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
