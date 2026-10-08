#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind the whole640 compiler drafts to the unchanged retained provider."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'prior_static', ROOT / 'tools/analyze-q2-ssm-row-group-compose-static.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = ROOT / 'config/q2-iq2-fixed-bounds-source.json'
    source = json.loads(manifest.read_text())['variants']['iq2-fixed-bounds']
    provider = ROOT / source['source']
    assert {p.relative_to(provider).as_posix(): sha(p) for p in provider.rglob('*')
            if p.is_file()} == source['files']
    parent = ROOT / 'evidence/q2-iq2-fixed-bounds-preparation/candidate.s'
    parent_text = parent.read_text()
    baseline = prior.old.isa.parse(parent)
    assert len(baseline) == 164
    variants = {}
    for name, version, draft in (
            ('register', 5, 'experiments/q2-iq2-whole640-draft.inc'),
            ('lds', 6, 'experiments/q2-iq2-whole640-lds-draft.inc')):
        directory = ROOT / f'evidence/q2-iq2-whole640-preparation-v{version}'
        command = json.loads((directory / 'assembly-command.json').read_text())
        assembly = directory / 'candidate.s'
        assert command['exit_code'] == 0 and not command['gpu_run']
        assert command['parent_manifest_sha256'] == sha(manifest)
        assert command['draft_sha256'] == sha(ROOT / draft) == sha(directory / 'draft.inc')
        assert command['assembly_sha256'] == sha(assembly)
        candidate = prior.old.isa.parse(assembly)
        text = assembly.read_text()
        assert set(baseline) < set(candidate) and len(candidate) == 165
        for symbol in baseline:
            assert prior.old.instructions(parent_text, symbol) == prior.old.instructions(text, symbol), symbol
            assert baseline[symbol]['resources'] == candidate[symbol]['resources'], symbol
        symbol = (set(candidate) - set(baseline)).pop()
        instructions = [line for line in prior.old.instructions(text, symbol).splitlines()
                        if re.match(r'^(?:[sv]_|ds_|global_|flat_|buffer_|scratch_|image_)', line)]
        variants[name] = dict(draft=draft, draft_sha256=sha(ROOT / draft),
            assembly=str(assembly.relative_to(ROOT)), assembly_sha256=sha(assembly),
            command=str((directory / 'assembly-command.json').relative_to(ROOT)),
            symbol=symbol, resources=candidate[symbol]['resources'],
            compiler_comments=prior.static.compiler_comments(text, symbol),
            instructions=len(instructions),
            scratch_instructions=sum('scratch_' in str(instruction) for instruction in instructions),
            original_kernels_exact=164)
    report = dict(schema='synapse-lie.q2-iq2-whole640-static.v1',
        source_manifest=str(manifest.relative_to(ROOT)), source_manifest_sha256=sha(manifest),
        retained_provider_files=1028, parent_assembly=str(parent.relative_to(ROOT)),
        parent_assembly_sha256=sha(parent), parent_recompiled=False, variants=variants,
        prompt_changed=False, production_selector=False, gpu_run=False,
        performance_measurement=False, numerical_acceptance=False, goal_met=False)
    path = ROOT / 'config/q2-iq2-whole640-static.json'
    with path.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(variants))


if __name__ == '__main__':
    main()
