#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the cumulative Q2 full-model experiment without summing micro gains."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('shared', ROOT / 'tools/analyze-q2-shared-overlap.py')
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)
require = shared.require


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def audit_capsule(path, fixtures):
    transport = json.loads((path / 'transport.json').read_text())
    collection = json.loads((path / 'collection.json').read_text())
    require(digest(path / 'source.tar.gz') == transport['capsule_sha256'], 'Source archive changed')
    require(digest(path / 'results.tar.gz') == collection['sha256'], 'Results archive changed')
    source = ROOT / transport['source_path']
    files = [p for p in source.rglob('*') if p.is_file()]
    with tarfile.open(path / 'source.tar.gz') as capsule:
        for local, member in [(ROOT / f, f) for f in fixtures] + [
                (p, 'source/' + str(p.relative_to(source))) for p in files]:
            require(hashlib.sha256(capsule.extractfile(member).read()).hexdigest() == digest(local),
                    'Frozen source differs: ' + member)
    temperatures = {}
    for line in (path / 'results/telemetry.jsonl').read_text().splitlines():
        sensors = json.loads(line)['thermal']
        require({s['device'] for s in sensors} == {'amdgpu', 'k10temp'}, 'Incomplete thermal coverage')
        for sensor in sensors:
            require(not sensor['over_limit'], 'Thermal limit exceeded')
            temperatures[sensor['device']] = max(temperatures.get(sensor['device'], -273),
                                                 sensor['temperature_mc'] / 1000)
    return dict(source_files_verified=len(files),
                source_capsule_sha256=transport['capsule_sha256'],
                archive_sha256=collection['sha256'],
                artifacts_verified=collection['verified_artifacts'],
                temperature_max_c=temperatures,
                fixtures_sha256={f: digest(ROOT / f) for f in fixtures})


def main():
    models, roots = {}, {}
    for name, label, variant in (
            ('reference', 'q2-combined-reference-r1', 'hc-up-chains'),
            ('retained', 'q2-combined-retained-model-r1', 'combined-retained'),
            ('scaled', 'q2-combined-scaled-model-r1', 'combined-scaled'),
            ('scaled_control', 'q2-combined-scaled-control-r1', 'scaled-input'),
            ('ud', 'q2-combined-ud-r1', 'qualified')):
        path = ROOT / 'evidence' / label
        root, row = shared.arm(path, variant)
        row['validation'] = audit_capsule(path, ['tests/q2_model.cpp', 'tests/q2_profile_markers.hip'])
        models[name], roots[name] = row, root
    replay = dict(retained_vs_reference=shared.compare(roots['reference'], roots['retained']),
                  scaled_vs_scaled_control=shared.compare(roots['scaled_control'], roots['scaled']),
                  scaled_vs_reference=shared.compare(roots['reference'], roots['scaled']))
    historical = ROOT / 'evidence/q2-scaled-input-candidate-r1'
    old_root, _ = shared.arm(historical, 'scaled-input')
    replay['scaled_vs_previous_scaled'] = shared.compare(old_root, roots['scaled'])
    changes = {name: {reference: {metric: 100 * (
        models[name]['measurements'][metric]['median'] /
        models[reference]['measurements'][metric]['median'] - 1)
        for metric in ('prefill_tok_s', 'decode_steps_s', 'prefill_s', 'decode_s')}
        for reference in ('reference', 'scaled_control', 'ud')}
        for name in ('retained', 'scaled', 'scaled_control')}
    report = dict(scope='Original-weight C1 pp2048/tg128, one warmup and three measured sessions, fan82 policy',
                  model=models, replay=replay, median_change_percent=changes,
                  exact_addition_replay=not replay['retained_vs_reference']['changed'] and
                                       not replay['scaled_vs_scaled_control']['changed'] and
                                       not replay['scaled_vs_previous_scaled']['changed'],
                  goal_met=False, promoted=False,
                  limits='Native single-chunk2K has no cross-chunk PLE overlap. Scaled operator/KL rejection remains; no long-context, HTTP or task-quality acceptance.')
    output = ROOT / 'config/q2-combined-results.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(median_change_percent=changes,
                         exact_addition_replay=report['exact_addition_replay'],
                         goal_met=False, promoted=False), indent=2))


if __name__ == '__main__':
    main()
