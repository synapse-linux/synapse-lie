#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind the width-relative tail map, unchanged kernels and captured route fixtures."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT/'evidence/q2-iq2-tail16-preparation'
spec = importlib.util.spec_from_file_location('prepare', ROOT/'tools/prepare-q2-iq2-tail16.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)
sha, inventory = prepare.sha, prepare.inventory


def main():
    manifest = ROOT/'config/q2-iq2-tail16-source-v2.json'
    source = json.loads(manifest.read_text())['variants']['iq2-tail16']
    parent = json.loads((ROOT/source['parent_manifest']).read_text())['variants']['ssm-fixed-bounds']
    for provider in (parent, source):
        assert inventory(ROOT/provider['source']) == provider['files']
    for key in ('parent_manifest', 'measured_parent', 'routing_audit', 'patch'):
        assert sha(ROOT/source[key]) == source[key+'_sha256']
    for name, digest in source['c17_map_files'].items():
        assert sha(ROOT/name) == digest
    for name, digest in source['unchanged_numerical_sources'].items():
        assert digest == parent['files'][name]
    assert len(source['files']) == 1029 and len(source['changed_files']) == 5
    with tempfile.TemporaryDirectory(dir=PREP, prefix='reconstruct-') as temporary:
        directory = Path(temporary)
        for name in source['changed_files']:
            if name in parent['files']:
                out = directory/name
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes((ROOT/parent['source']/name).read_bytes())
        result = subprocess.run(['patch', '--batch', '-p1', '-i', str(ROOT/source['patch'])],
                                cwd=directory, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert all(sha(directory/name) == source['files'][name] for name in source['changed_files'])
    fixtures = json.loads((ROOT/'config/q2-fixed-input-route-fixtures.json').read_text())
    generated = (ROOT/'experiments/q2_iq2_tail16_routes.inc').read_text()
    for layer in fixtures['layers']:
        begin = generated.index('kLayer'+str(layer['layer'])+'Counts[512] = {')
        payload = generated[begin:].split('{',1)[1].split('}',1)[0]
        counts = [int(v.strip()) for v in payload.split(',') if v.strip()]
        assert counts == layer['counts'] and len(counts) == 512 and sum(counts) == 20480
        routed = [(i % 2048, expert) for expert, count in enumerate(counts)
                  for i in range(sum(counts[:expert]), sum(counts[:expert])+count)]
        assert len(set(routed)) == len(routed) == 20480
        assert all(sum(token == n for token, _ in routed) == 10 for n in range(2048))
    commands = {name:json.loads((PREP/(name+'-command.json')).read_text())
                for name in ('generation', 'fixture-host', 'fixture-device')}
    assert all(c['exit_code'] == 0 for c in commands.values())
    report = dict(schema='synapse-lie.q2-iq2-tail16-static.v1',
        manifest_sha256=sha(manifest), provider_files=1029, changed_files=source['changed_files'],
        numerical_sources_unchanged=len(source['unchanged_numerical_sources']),
        source_patch_reconstruction_exact=True, descriptor_count_unchanged=True,
        captured_fixture_layers=[r['layer'] for r in fixtures['layers']],
        captured_fixture_identity_exact=True, synthetic_route_slots_unique=True,
        captured_source='config/q2-fixed-input-route-fixtures.json',
        captured_source_sha256=sha(ROOT/'config/q2-fixed-input-route-fixtures.json'),
        component='tests/q2_iq2_tail16.hip', component_sha256=sha(ROOT/'tests/q2_iq2_tail16.hip'),
        resource_reference='config/q2-route-opportunities.json',
        resource_reference_sha256=sha(ROOT/'config/q2-route-opportunities.json'),
        expected_output_pairs=96, expected_timing_samples=56,
        commands=commands, gpu_build=False, gpu_run=False, numerical_acceptance=False,
        model_measured=False, goal_met=False,
        limits='Source identity and row ownership do not prove GPU numerical equality or speed. '
            'Existing BN16 resource metadata is reused without rebuilding saved binaries. '
            'Actual component and original fixed2048/tg128 model remain required.')
    with (ROOT/'config/q2-iq2-tail16-static.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k:report[k] for k in ('provider_files','numerical_sources_unchanged',
        'captured_fixture_layers','expected_output_pairs','expected_timing_samples')}))


if __name__ == '__main__':
    main()
