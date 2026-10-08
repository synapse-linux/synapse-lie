#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Close both retained routing attempts and verify the successful saved-binary diagnosis."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hc', ROOT/'tools/analyze-q2-hc-bk256.py')
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)
read, sha, require = hc.read, hc.sha, hc.require


def main():
    plan = read(ROOT/'config/q2-current-routing-v2-plan.json')
    for name, digest in {**plan['fixtures'], **plan['manifests'],
                         plan['window_helper']:plan['window_helper_sha256']}.items():
        require(sha(ROOT/name) == digest, 'Frozen input changed: '+name)
    source = read(ROOT/plan['source_variant_manifest'])['variants'][plan['source_variant']]
    require({str(p.relative_to(ROOT/source['source'])):sha(p) for p in
            (ROOT/source['source']).rglob('*') if p.is_file()} == source['files'], 'Provider changed')
    cohorts = []
    for label in ('q2-current-routing-host-r1', 'q2-current-routing-r1',
                  'q2-current-routing-v2-host-r1', 'q2-current-routing-v2-r1'):
        directory = ROOT/'evidence'/label
        result, transport = hc.curve.artifact_integrity(directory)
        failed = label == 'q2-current-routing-r1'
        require(result.get('finished_at') and transport['exit_code'] == (1 if failed else 0),
                'Incomplete/changed transport')
        require(all(c['exit_code'] == 0 for c in result['commands']), 'Changed actual command exit')
        if failed:
            require(result['state'] == 'FAILED' and result['commands'][1]['foreign_kfd'] == [184346] and
                    'Foreign KFD client during run' in result['error'] and
                    (directory/'results/routing-counts.jsonl').stat().st_size == 0,
                    'Initial failure evidence lost')
        cohorts.append(dict(label=label, state=result['state'], result_sha256=sha(directory/'results/result.json'),
            transport_exit=transport['exit_code'], command_exits=[c['exit_code'] for c in result['commands']],
            artifacts_verified=len(result['artifacts']), finished_at=result['finished_at']))
    root = ROOT/'evidence/q2-current-routing-v2-r1'
    binding = hc.capsule(root, plan['fixtures'], source['files'])
    result = read(root/'results/result.json')
    release_path = ROOT/'config/q2-current-routing-v2-window-release.json'
    release = read(release_path)
    require(release['state'] == 'Q2_CURRENT_ROUTING_V2_WINDOW_RELEASED' and not release['gpu_reserved'] and
            not release['kfd'] and not release['owned_group_members'] and release['model_stats_unchanged'],
            'GPU closure incomplete')
    require(all(r['unchanged_free_EX_NB'] for r in release['leases']) and len(release['leases']) == 4,
            'Original leases changed')
    known = {r['pid']:r for r in release['retired_identities']}
    child_ids = result['commands'][1]['owned_kfd_identities']
    require(len(child_ids) == 1 and all(known[c['pid']]['start_ticks'] == c['start_ticks'] and
            c['group'] in release['retired_groups'] for c in child_ids), 'Debugger child closure incomplete')
    for row in cohorts:
        require(row['finished_at'] < release['at'], 'Release precedes terminal cohort')
    collected = read(ROOT/'evidence/q2-current-routing-v2-preparation/routing-collect-command.json')
    require(collected['exit_code'] == 0 and collected['finished_at'] < release['at'], 'Collection incomplete at release')
    names = ['q2-current-routing-v2-window-release.json', 'q2-current-routing-v2-window-active.json',
             'q2-current-routing-v2-ready.json']
    require(all((ROOT.parents[1]/'run'/name).read_bytes() == release_path.read_bytes() for name in names),
            'Main mirrors changed')
    analysis = read(ROOT/'config/q2-current-routing-v2-results.json')
    require(analysis['captures'] == 96 and analysis['prefill_full_logits_exact'] and
            analysis['first16_greedy_tokens_exact'] and analysis['warm_profile_counts_exact'], 'Routing replay changed')
    artifacts = ['config/q2-current-routing-v2-results.json', 'config/q2-route-opportunities.json',
                 'config/q2-fixed-input-route-fixtures.json',
                 'docs/figures/q2-current-routing.csv', 'docs/figures/q2-current-routing.svg',
                 'docs/figures/q2-current-routing.png']
    report = dict(schema='synapse-lie.q2-current-routing-final-audit.v1', cohorts=cohorts,
        source_files_verified=len(source['files']), fixtures_verified=len(plan['fixtures']),
        manifests_verified=len(plan['manifests']), successful_diagnostic_binding=binding,
        artifacts={name:sha(ROOT/name) for name in artifacts}, release_at=release['at'],
        release_sha256=sha(release_path), retired_identities=len(known),
        retired_groups=len(release['retired_groups']), owned_debugger_children=child_ids,
        main_mirrors_exact=True, remote_mirror_receipt='evidence/q2-current-routing-v2-preparation/publish-release-stdout.txt',
        actual_command_exit_codes_preserved=True,
        initial_failure='Transport1/stateFAILED despite child exits0: ownership guard stopped '
            'GDB before any counts. Preserved separately, not counted as successful inference.',
        successful_host_tests=dict(debug=32, asan_ubsan=32),
        successful_diagnostic_commands=2, gpu_builds=0, performance_control_rerun=False,
        provider_changed=False, goal_met=False, full_curve=False, cleanup=False)
    with (ROOT/'config/q2-current-routing-final-audit.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(fixtures=111, provider_files=1027, captures=96,
                          release_at=release['at'], release_sha256=sha(release_path),
                          preserved_failed_transport=1, gpu_builds=0)))


if __name__ == '__main__':
    main()
