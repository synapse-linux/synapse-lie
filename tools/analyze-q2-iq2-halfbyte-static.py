#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind compact IQ2 assemblies and distinguish inherited format failures."""
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/q2-iq2-halfbyte-preparation'
spec = importlib.util.spec_from_file_location('prior_static', ROOT / 'tools/analyze-q2-iq2-halfstage-static.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
sha = prior.sha


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    output = ROOT / 'config/q2-iq2-halfbyte-static.json'
    require(not output.exists(), 'Refusing to overwrite static evidence')
    parent_path = ROOT / 'config/q2-hc-moe-deferred-source.json'
    parent_source = json.loads(parent_path.read_text())['variants']['hc-moe-deferred']
    paths = {'parent': ROOT / 'evidence/q2-iq2-halfstage-preparation/parent.s',
             **{key: OUT / (key + '.s') for key in ('perm', 'shift', 'perm-formatted')}}
    assemblies = {key: prior.parse(path) for key, path in paths.items()}
    parent = assemblies['parent']
    affected = [s for s in parent if 'RoutedF16GEMMKernel' in s and 'WeightTypeE16' in s]
    require(len(parent) == 157 and len(affected) == 8, 'Saved parent kernel inventory changed')
    for key, candidate in assemblies.items():
        require(candidate.keys() == parent.keys(), 'Kernel inventory changed: ' + key)
        if key == 'parent':
            continue
        changed = [s for s in parent if candidate[s]['body_sha256'] != parent[s]['body_sha256']]
        require(sorted(changed) == sorted(affected), 'Unrelated compiled body changed: ' + key)
        for symbol in affected:
            require(candidate[symbol]['resources']['group_segment_fixed_size'] ==
                    parent[symbol]['resources']['group_segment_fixed_size'] and
                    candidate[symbol]['resources']['private_segment_fixed_size'] == 0,
                    'LDS size or scratch changed: ' + key)
            require(candidate[symbol]['mnemonics'].get('v_pk_add_f16', 0) == 0 and
                    candidate[symbol]['mnemonics'].get('v_pk_fma_f16', 0) ==
                    parent[symbol]['mnemonics'].get('v_pk_fma_f16', 0), 'Half arithmetic count changed')
            if key == 'perm-formatted':
                bn = int(re.search(r'WeightTypeE16ELi128ELi(\d+)ELi2', symbol)[1])
                require(candidate[symbol] == assemblies['perm'][symbol],
                        'Filename-aware include formatting changed generated kernel')
                require(candidate[symbol]['instructions'] < parent[symbol]['instructions'],
                        'Selected candidate adds instructions')
                require(candidate[symbol]['resources']['next_free_vgpr'] ==
                        parent[symbol]['resources']['next_free_vgpr'] + (1 if bn == 16 else 0),
                        'Selected candidate register change differs')
    sources = {}
    format_failures = {}
    commands = json.loads((OUT / 'generation-commands.json').read_text())
    for key in ('perm', 'shift', 'perm-formatted'):
        path = ROOT / 'config' / ('q2-iq2-halfbyte-' + key + '-source.json')
        data = json.loads(path.read_text())
        variant = next(iter(data['variants'].values()))
        folder = ROOT / variant['source']
        actual = {str(p.relative_to(folder)): sha(p) for p in folder.rglob('*') if p.is_file()}
        require(actual == variant['files'] and len(actual) == 1025, 'Provider inventory changed')
        require(sha(ROOT / variant['patch']) == variant['patch_sha256'] and
                variant['parent_manifest_sha256'] == sha(parent_path), 'Provider reference changed')
        sources[key] = dict(manifest=str(path.relative_to(ROOT)), manifest_sha256=sha(path),
                            files_verified=len(actual), scalar_format_checks=variant['scalar_format_checks'],
                            packed_format_checks=variant['packed_format_checks'])
        rows = json.loads((OUT / (key + '-commands.json')).read_text())
        commands.extend(rows)
        failed = [row for row in rows if row['exit_code'] != 0]
        require(len(failed) == 1 and failed[0]['exit_code'] == 1 and 'format' in failed[0]['name'],
                'Unclassified compiler or formatter exit')
        log = OUT / (key + '-format-stderr.txt' if key != 'perm-formatted'
                     else 'perm-formatted-shared-format-stderr.txt')
        names = sorted(set(re.findall(r'^([^:\n]+):\d+:\d+: error:', log.read_text(), re.M)))
        inherited = [name for name in names if actual[name] == parent_source['files'][name]]
        changed_files = [name for name in names if name not in inherited]
        require(len(inherited) == 7 and changed_files ==
                ([] if key == 'perm-formatted' else variant['changed_files']),
                'Formatting failures differ from inherited source or corrected include ordering')
        format_failures[key] = dict(command=failed[0], log_sha256=sha(log),
                                   unchanged_parent_files={name: actual[name] for name in inherited},
                                   new_file_initial_include_ordering=changed_files)
    fixture_commands = json.loads((OUT / 'fixture-commands.json').read_text())
    final_guard_commands = json.loads((OUT / 'guards-final-commands.json').read_text())
    require(all(row['exit_code'] == 0 for row in fixture_commands + final_guard_commands),
            'Fixture syntax or final scope guard failed')
    require('Ran 83 tests' in (OUT / 'guards-final-stderr.txt').read_text(), 'Missing final guards')
    commands += fixture_commands + final_guard_commands
    report = dict(schema='synapse-lie.q2-iq2-halfbyte-static.v1', sources=sources,
                  assemblies={key: dict(path=str(path.relative_to(ROOT)), sha256=sha(path))
                              for key, path in paths.items()},
                  parent_assembly_reused_without_rebuild=True, kernels_total=157, unrelated_bodies_exact=149,
                  iq2_bodies={s: {key: assembly[s] for key, assembly in assemblies.items()} for s in affected},
                  commands=commands, formatting_failures=format_failures,
                  initial_guard_failure=json.loads((OUT / 'guards-commands.json').read_text()),
                  initial_guard_failure_reason='New component absent from parser mode choices; corrected before staging or SSH.',
                  selected_source_variant='iq2-halfbyte-perm', selected_source_manifest=sources['perm-formatted']['manifest'],
                  shift_source_retained_without_gpu_run=True, production_abi_or_stage_layout_changed=False,
                  gpu_run=False, original_model_inference=False, numerical_acceptance=False,
                  performance_gain=False, goal_met=False)
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(unrelated_bodies_exact=149, iq2_bodies_changed=8,
                         selected_source='iq2-halfbyte-perm', static_counts_are_performance=False,
                         inherited_formatter_failures=7, final_scope_guards=83)))


if __name__ == '__main__':
    main()
