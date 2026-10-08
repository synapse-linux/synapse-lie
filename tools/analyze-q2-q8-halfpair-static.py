#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind the new Q8 pair table, assemblies and inherited formatting failures."""
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/q2-q8-halfpair-preparation'
spec = importlib.util.spec_from_file_location('prior_static', ROOT / 'tools/analyze-q2-iq2-halfstage-static.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
sha = prior.sha


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    output = ROOT / 'config/q2-q8-halfpair-static.json'
    require(not output.exists(), 'Refusing to replace static evidence')
    paths = dict(parent=ROOT / 'evidence/q2-iq2-halfbyte-preparation/perm-formatted.s',
                 candidate=OUT / 'candidate.s')
    assemblies = {key: prior.parse(path) for key, path in paths.items()}
    parent, candidate = assemblies['parent'], assemblies['candidate']
    require(parent.keys() == candidate.keys() and len(parent) == 157, 'Kernel inventory changed')
    changed = [s for s in parent if parent[s]['body_sha256'] != candidate[s]['body_sha256']]
    require(len(changed) == 8 and all('DenseF16GEMMKernel' in s for s in changed),
            'Unrelated compiled body changed')
    for symbol in changed:
        require(candidate[symbol]['resources']['group_segment_fixed_size'] ==
                parent[symbol]['resources']['group_segment_fixed_size'] and
                candidate[symbol]['resources']['private_segment_fixed_size'] == 0 and
                candidate[symbol]['resources']['next_free_vgpr'] == parent[symbol]['resources']['next_free_vgpr'],
                'LDS/register/scratch change')
        require(candidate[symbol]['mnemonics'].get('v_pk_add_f16', 0) == 0 and
                candidate[symbol]['mnemonics'].get('v_pk_fma_f16', 0) ==
                parent[symbol]['mnemonics'].get('v_pk_fma_f16', 0), 'Half arithmetic contract changed')
    manifest_path = ROOT / 'config/q2-q8-halfpair-source.json'
    source = json.loads(manifest_path.read_text())['variants']['q8-halfpair']
    folder = ROOT / source['source']
    actual = {str(p.relative_to(folder)): sha(p) for p in folder.rglob('*') if p.is_file()}
    require(actual == source['files'] and len(actual) == 1026, 'Provider inventory changed')
    for key in ('parent_manifest', 'measured_parent', 'control_include', 'patch'):
        require(sha(ROOT / source[key]) == source[key + '_sha256'], 'Source reference changed: ' + key)
    base = json.loads((ROOT / source['parent_manifest']).read_text())['variants']['iq2-halfbyte-perm']
    spec = importlib.util.spec_from_file_location('q8_original', ROOT / 'tools/prepare-q2-q8-grouped.py')
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    parent_text = (ROOT / base['source'] / 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp').read_text()
    kernel = original.function(parent_text, 'template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,')
    control = (ROOT / source['control_include']).read_text()
    require(kernel.replace('DenseF16GEMMKernel', 'DenseQ8GroupedControlKernel') in control,
            'Literal numerical control differs from measured compact parent')
    commands = [json.loads(path.read_text()) for path in sorted(OUT.glob('*-command.json'))]
    failures = {path.name: json.loads(path.read_text()) for path in OUT.glob('*-command.json')
                if json.loads(path.read_text())['exit_code']}
    require(set(failures) == {'shared-format-command.json', 'new-format-command.json',
                             'static-analysis-command.json'} and
            all(row['exit_code'] == 1 for row in failures.values()), 'Unclassified command failure')
    require(failures['shared-format-command.json']['argv'] == ['python3', 'tools/ci/check-format.py'] and
            json.loads((OUT / 'new-format-fixed-command.json').read_text())['exit_code'] == 0,
            'Missing corrected explicit-style formatting check')
    names = sorted(set(re.findall(r'^([^:\n]+):\d+:\d+: error:',
                                 (OUT / 'shared-format-stderr.txt').read_text(), re.M)))
    require(len(names) == 7 and all(actual[name] == base['files'][name] for name in names),
            'Shared format failures are not the seven unchanged inherited files')
    require('Ran 84 tests' in (OUT / 'guards-stderr.txt').read_text(), 'Missing launch guards')
    report = dict(schema='synapse-lie.q2-q8-halfpair-static.v1',
                  source_manifest_sha256=sha(manifest_path), source_files_verified=1026,
                  parent_assembly_reused_without_rebuild=True, kernels_total=157, unchanged_bodies=149,
                  assemblies={key: dict(path=str(path.relative_to(ROOT)), sha256=sha(path))
                              for key, path in paths.items()},
                  q8_bodies={s: {key: assembly[s] for key, assembly in assemblies.items()} for s in changed},
                  literal_control_exact_to_parent=True, table_bytes=262144, integer_format_checks=131072,
                  inherited_format_failures={name: actual[name] for name in names}, commands=commands,
                  retained_failures=failures,
                  initial_new_format_failure='Dry-run omitted the explicit Gufo style used to format the fixture; corrected without changing fixture/provider bytes.',
                  initial_static_failure='First analysis correctly refused unclassified local format exit; final receipt explicitly retains the failed command and corrected check.',
                  gpu_run=False, model_inference=False, numerical_acceptance=False,
                  performance_gain=False, full_curve=False, promoted=False, goal_met=False)
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(changed_bodies=8, unchanged_bodies=149, inherited_format_files=7,
                         literal_control_exact=True, source_files=1026, static_counts_are_speedup=False)))


if __name__ == '__main__':
    main()
