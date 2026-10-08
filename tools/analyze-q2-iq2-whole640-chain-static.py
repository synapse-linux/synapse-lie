#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check new chain ISA against the retained parent and measured LDS donor."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prior', ROOT / 'tools/analyze-q2-iq2-whole640-wave16-static.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
isa = prior.prior.old.isa
instructions = prior.prior.old.instructions
sha = prior.sha


def main():
    manifest = ROOT / 'config/q2-iq2-whole640-chain-source.json'
    source = json.loads(manifest.read_text())['variants']['iq2-whole640-chain']
    provider = ROOT / source['source']
    assert {p.relative_to(provider).as_posix(): sha(p) for p in provider.rglob('*') if p.is_file()} == source['files']
    directory = ROOT / 'evidence/q2-iq2-whole640-chain-preparation'
    command = json.loads((directory / 'assembly-command.json').read_text())
    assert command['exit_code'] == 0 and '--offload-device-only' in command['argv']
    parent = ROOT / 'evidence/q2-iq2-fixed-bounds-preparation/candidate.s'
    candidate = directory / 'candidate.s'
    original, compiled = isa.parse(parent), isa.parse(candidate)
    old_text, new_text = parent.read_text(), candidate.read_text()
    assert len(original) == 164 and len(compiled) == 166 and set(original) < set(compiled)
    for symbol in original:
        assert instructions(old_text, symbol) == instructions(new_text, symbol), symbol
        assert original[symbol]['resources'] == compiled[symbol]['resources'], symbol
    donor = json.loads((ROOT / 'config/q2-iq2-whole640-wave16-static.json').read_text())['variants']['lds']
    donor_assembly = ROOT / donor['assembly']
    symbol = donor['symbol']
    assert sha(donor_assembly) == donor['assembly_sha256']
    assert instructions(donor_assembly.read_text(), symbol) == instructions(new_text, symbol)
    assert donor['resources'] == compiled[symbol]['resources']
    additions = {}
    for symbol in sorted(set(compiled) - set(original)):
        lines = [line for line in instructions(new_text, symbol).splitlines()
                 if re.match(r'^(?:[sv]_|ds_|global_|flat_|buffer_|scratch_|image_)', line)]
        additions[symbol] = dict(resources=compiled[symbol]['resources'], instructions=len(lines),
            scratch_instructions=sum('scratch_' in line for line in lines),
            comments=prior.prior.static.compiler_comments(new_text, symbol))
    report = dict(schema='synapse-lie.q2-iq2-whole640-chain-static.v1',
        source_manifest=str(manifest.relative_to(ROOT)), source_manifest_sha256=sha(manifest),
        provider_files=1034, original_kernels_instruction_operand_resource_exact=164,
        measured_LDS_kernel_instruction_operand_resource_exact=True,
        additions=additions, assembly=str(candidate.relative_to(ROOT)), assembly_sha256=sha(candidate),
        command_sha256=sha(directory / 'assembly-command.json'), GPU_run=False,
        performance_measurement=False, numerical_acceptance=False, goal_met=False)
    with (ROOT / 'config/q2-iq2-whole640-chain-static.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'additions'}))


if __name__ == '__main__':
    main()
