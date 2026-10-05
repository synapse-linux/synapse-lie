#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify the new SSM specialization and unchanged saved parent assembly."""
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/q2-ssm-row128-preparation'


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


prior = module('analyze-q2-iq2-halfstage-static.py')
original = module('prepare-q2-q8-grouped.py')
sha = prior.sha


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    output = ROOT / 'config/q2-ssm-row128-static.json'
    require(not output.exists(), 'Refusing to overwrite static evidence')
    paths = dict(parent=ROOT / 'evidence/q2-iq2-halfbyte-preparation/perm-formatted.s',
                 candidate=OUT / 'candidate.s')
    p, c = (prior.parse(paths[key]) for key in ('parent', 'candidate'))
    removed, added = set(p) - set(c), set(c) - set(p)
    require(len(p) == len(c) == 157 and len(removed) == len(added) == 1, 'Kernel inventory changed')
    old, new = next(iter(removed)), next(iter(added))
    require('ILi256ELi128ELi2ELi8ELi1ELi1ELb0ELb1' in old and
            'ILi128ELi128ELi2ELi4ELi2ELi1ELb0ELb1' in new, 'Unexpected specialization change')
    require(all(p[s]['body_sha256'] == c[s]['body_sha256'] for s in set(p) & set(c)), 'Unrelated body changed')
    require(p[old]['resources']['group_segment_fixed_size'] == 49152 and
            c[new]['resources']['group_segment_fixed_size'] == 36864 and
            p[old]['resources']['private_segment_fixed_size'] == c[new]['resources']['private_segment_fixed_size'] == 0,
            'Changed LDS or private scratch contract')
    manifest_path = ROOT / 'config/q2-ssm-row128-source.json'
    source = json.loads(manifest_path.read_text())['variants']['ssm-row128']
    folder = ROOT / source['source']
    actual = {str(f.relative_to(folder)): sha(f) for f in folder.rglob('*') if f.is_file()}
    require(actual == source['files'] and len(actual) == 1025, 'Provider inventory changed')
    for key in ('parent_manifest', 'measured_parent', 'control_include', 'patch'):
        require(sha(ROOT / source[key]) == source[key + '_sha256'], 'Source binding changed')
    base = json.loads((ROOT / source['parent_manifest']).read_text())['variants']['iq2-halfbyte-perm']
    parent_text = (ROOT / base['source'] / 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp').read_text()
    control = (ROOT / source['control_include']).read_text()
    kernel = original.function(parent_text, 'template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,')
    require(kernel.replace('DenseF16GEMMKernel', 'DenseQ8GroupedControlKernel') in control, 'Literal control changed')
    for name in ('generation', 'assembly', 'fixture-device', 'fixture-host', 'guards', 'new-format'):
        require(json.loads((OUT / (name + '-command.json')).read_text())['exit_code'] == 0, 'Preparation check failed: ' + name)
    require('Ran 85 tests' in (OUT / 'guards-stderr.txt').read_text(), 'Missing scope guards')
    require(json.loads((OUT / 'shared-format-command.json').read_text())['exit_code'] == 1, 'Shared formatter exit lost')
    names = sorted(set(re.findall(r'^([^:\n]+):\d+:\d+: error:',
                                 (OUT / 'shared-format-stderr.txt').read_text(), re.M)))
    require(len(names) == 9 and all(actual[name] == base['files'][name] for name in names), 'Inherited format bytes changed')
    report = dict(schema='synapse-lie.q2-ssm-row128-static.v1', source_manifest_sha256=sha(manifest_path),
        source_files_verified=1025, literal_control_exact_to_parent=True, parent_assembly_reused_without_rebuild=True,
        kernel_count=157, unchanged_bodies=156, parent_ssm_symbol=old, candidate_ssm_symbol=new,
        parent=p[old], candidate=c[new], assemblies={k: dict(path=str(v.relative_to(ROOT)), sha256=sha(v)) for k, v in paths.items()},
        inherited_format_failures={name: actual[name] for name in names},
        commands=[json.loads(path.read_text()) for path in sorted(OUT.glob('*-command.json'))],
        local_wrapper_path_failure='The first shared-format invocation used a relative evidence wrapper from the provider cwd and exited2 before formatting; corrected absolute wrapper ran and preserved actual inherited exit1.',
        comparison_scope='Per-block static code; row-block grid doubles and activation reads are repeated. No dynamic instruction, occupancy or speedup claim.',
        gpu_run=False, model_inference=False, numerical_acceptance=False, promoted=False, goal_met=False)
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(unchanged_bodies=156, instructions=[p[old]['instructions'], c[new]['instructions']],
        next_free_vgpr=[p[old]['resources']['next_free_vgpr'], c[new]['resources']['next_free_vgpr']],
        lds_bytes=[49152, 36864], inherited_format_files=len(names), gpu_run=False)))


if __name__ == '__main__':
    main()
