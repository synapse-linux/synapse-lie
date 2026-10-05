#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare the narrower shared-down tiles with saved assembly, without a GPU run."""
import importlib.util
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('shared_static', ROOT/'tools/analyze-q2-shared-down-static.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
ssm, old, group = module.ssm, module.old, module.group


def main():
    manifest = ROOT/'config/q2-shared-down-n64-source.json'
    source = json.loads(manifest.read_text())['variants']['shared-down-n64']
    assert ssm.inventory(ROOT/source['source']) == source['files']
    for key, digest in source.items():
        if key.endswith('_sha256'):
            assert ssm.sha(ROOT/source[key[:-7]]) == digest, key
    saved = json.loads((ROOT/'config/q2-shared-down-static.json').read_text())['variants']['shared-down-fixed']
    before_path = ROOT/saved['candidate_assembly_path']
    assert ssm.sha(before_path) == saved['candidate_assembly_sha256']
    after_path = ROOT/'evidence/q2-shared-down-n64-preparation/candidate.s'
    before, after = before_path.read_text(), after_path.read_text()
    a, b = old.isa.parse(before_path), old.isa.parse(after_path)
    original = {s for s in a if 'SharedDownFixedKernel' not in s}
    assert len(a) == len(b) == 166 and len(original) == 164 and original <= b.keys()
    for symbol in original:
        assert old.instructions(before, symbol) == old.instructions(after, symbol), symbol
        assert a[symbol]['resources'] == b[symbol]['resources'], symbol
    new = {s: dict(**b[s], compiler_comments=group.static.compiler_comments(after, s))
           for s in b.keys()-original}
    assert len(new) == 2 and all('SharedDownFixedKernelILi256ELi64E' in s for s in new)
    parent = json.loads((ROOT/source['parent_manifest']).read_text())['variants']['down-register-scatter']
    with TemporaryDirectory(dir=ROOT/'evidence', prefix='shared-down-n64-reconstruct-') as directory:
        for name in source['changed_files']:
            target = Path(directory)/name
            target.parent.mkdir(parents=True, exist_ok=True)
            if name in parent['files']:
                target.write_bytes((ROOT/parent['source']/name).read_bytes())
        p = subprocess.run(['patch', '--batch', '-p1', '-i', str(ROOT/source['patch'])],
                           cwd=directory, text=True, capture_output=True)
        assert p.returncode == 0, p.stderr
        for name in source['changed_files']:
            assert ssm.sha(Path(directory)/name) == source['files'][name]
    commands = {label: json.loads((ROOT/'evidence/q2-shared-down-n64-preparation'/
                                   (label+'-command.json')).read_text())
                for label in ('generation', 'assembly', 'fixture-host', 'fixture-device')}
    assert all(c['exit_code'] == 0 for c in commands.values())
    report = dict(schema='synapse-lie.q2-shared-down-n64-static.v1',
                  source_manifest=str(manifest.relative_to(ROOT)), source_manifest_sha256=ssm.sha(manifest),
                  candidate_assembly_path=str(after_path.relative_to(ROOT)), candidate_assembly_sha256=ssm.sha(after_path),
                  prior_assembly_sha256=ssm.sha(before_path), provider_files_verified=1028,
                  original_kernels_instruction_operand_resource_exact=164, new_kernels=new,
                  complete_patch_reconstruction_exact=True, commands=commands,
                  scratch_free=all(k['resources']['private_segment_fixed_size'] == 0 for k in new.values()),
                  fixture_sha256=ssm.sha(ROOT/'tests/q2_shared_down_mirror.hip'),
                  runtime_wired=False, model_dispatch_changed=False, gpu_run=False,
                  numerical_acceptance=False, performance_gain=False, goal_met=False,
                  limits='Token tile64 changes register pressure and weight reuse. Static resources and '
                         'unchanged surrounding kernels do not establish speed or numerical correctness.')
    with (ROOT/'config/q2-shared-down-n64-static.json').open('x') as stream:
        json.dump(report, stream, indent=2); stream.write('\n')
    print(json.dumps(dict(original_kernels_exact=164, scratch_free=report['scratch_free'],
                         new_kernels={s: dict(resources=k['resources'], instructions=k['instructions'],
                             compiler_comments=k['compiler_comments']) for s,k in new.items()}, gpu_run=False)))


if __name__ == '__main__':
    main()
