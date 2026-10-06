#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind four compiler probes and reclassify saved diagnostic traces, without GPU work."""
import csv
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


prior = module('analyze-q2-ssm-row-group-compose-static.py')
classify = module('analyze-q2-scaled-library-profile.py')
sha = prior.ssm.sha


def comments(text, symbol):
    end = text.index('\n\t.end_amdhsa_kernel', text.index(symbol + ':'))
    start = text.index('; Kernel info:', end)
    # The private probe can be the last body: no following text section exists.
    stop = text.find('\n\t.section\t.text', start)
    section = text[start:stop if stop != -1 else None]
    return {field: int(re.search(r';\s*' + field + r':\s*(\d+)', section)[1])
            for field in ('NumVgprs', 'TotalNumSgprs', 'NumVGPRsForWavesPerEU', 'Occupancy')}


def category(name):
    if 'HcDownBk256Kernel' in name:
        return 'hc_down_projection'
    if 'HcMixDeferredNormKernel' in name or 'HcUpF16VecKernel' in name:
        return 'hc_up_projection'
    if 'HcInjectDeferredNormKernel' in name:
        return 'hc_mix_epilogues'
    if 'RoutedQ2HalfStorageKernel' in name:
        return 'routed_down'
    return classify.category(name, set())


def main():
    manifest = ROOT / 'config/q2-iq2-fixed-bounds-source.json'
    source = json.loads(manifest.read_text())['variants']['iq2-fixed-bounds']
    assert prior.ssm.inventory(ROOT / source['source']) == source['files']
    parent = ROOT / 'evidence/q2-iq2-fixed-bounds-preparation/candidate.s'
    original = prior.old.isa.parse(parent)
    before = parent.read_text()
    assert len(original) == 164
    variants = {}
    for name, additional in (('ssm-resident', 1), ('ssm-resident-fence', 1),
                             ('hc-up-short-chain', 2), ('hc-up-short-chain-phased', 2)):
        path = ROOT / ('evidence/q2-' + name + '-preparation/candidate.s')
        command = json.loads(path.with_name('assembly-command.json').read_text())
        assert command['exit_code'] == 0 and command['assembly_sha256'] == sha(path)
        assert sha(ROOT / command['draft']) == command['draft_sha256']
        assert command['parent_manifest_sha256'] == sha(manifest)
        after = path.read_text()
        parsed = prior.old.isa.parse(path)
        assert set(original) <= set(parsed) and len(parsed) == 164 + additional
        for symbol in original:
            assert prior.old.instructions(before, symbol) == prior.old.instructions(after, symbol), symbol
            assert original[symbol]['resources'] == parsed[symbol]['resources'], symbol
        kernels = []
        for symbol in sorted(set(parsed) - set(original)):
            instructions = prior.old.instructions(after, symbol).splitlines()
            kernels.append(dict(symbol=symbol, resources=parsed[symbol]['resources'],
                compiler_comments=comments(after, symbol),
                static_instructions=sum(bool(re.match(r'^(?:[sv]_|ds_|global_|flat_|buffer_|scratch_|image_)', v))
                                        for v in instructions)))
        variants[name] = dict(draft=command['draft'], draft_sha256=command['draft_sha256'],
            assembly_path=str(path.relative_to(ROOT)), assembly_sha256=sha(path),
            command_sha256=sha(path.with_name('assembly-command.json')),
            original_kernels_exact=164, added_kernels=kernels)
    selected = variants['hc-up-short-chain-phased']
    assert all(k['resources']['private_segment_fixed_size'] == 0 for k in selected['added_kernels'])
    assert all(k['resources']['private_segment_fixed_size'] > 0
               for k in variants['hc-up-short-chain']['added_kernels'])
    fixture = ROOT / 'tests/q2_hc_up_short_chain.hip'
    compiled = ROOT / 'evidence/q2-hc-up-short-chain-fixture-preparation/compile-command.json'
    assert json.loads(compiled.read_text())['exit_code'] == 0
    report = dict(schema='synapse-lie.q2-hc-up-short-chain-static.v1',
        source_manifest_sha256=sha(manifest), retained_files=1028,
        parent_assembly_sha256=sha(parent), parent_recompiled=False, variants=variants,
        fixture=str(fixture.relative_to(ROOT)), fixture_sha256=sha(fixture),
        fixture_compile_receipt_sha256=sha(compiled),
        selected='hc-up-short-chain-phased', selected_paths=['ordinary', 'deferred-normalization'],
        deliberately_changed_FP32_reduction=True, original_F16_operands=True,
        device_allocations_in_provider=0, model_selector=False, GPU_run=False,
        numerical_acceptance=False, performance_measurement=False, goal_met=False)
    destination = ROOT / 'config/q2-hc-up-short-chain-static.json'
    with destination.open('x') as stream:
        json.dump(report, stream, indent=2); stream.write('\n')

    qpath = ROOT / 'config/q2-current-best-profile-results.json'
    upath = ROOT / 'config/q2-scaled-library-profile-results.json'
    q, u = [json.loads(p.read_text()) for p in (qpath, upath)]
    paths = {'q2_saved1571': ROOT / 'evidence/q2-current-best-profile-r1',
             'ud_historical': ROOT / u['arms']['ud']['path']}
    groups, bindings = {}, {}
    for arm, path in paths.items():
        receipt = json.loads((path / 'results/result.json').read_text())
        assert all(c['exit_code'] == 0 for c in receipt['commands'])
        assert sha(path / 'results/profile2048-input.i32') == q['input_sha256']
        rawpath = path / 'results/profile-phases.json'
        data = json.loads(rawpath.read_text())['phases']['prefill']
        for name in ('profile-phases.json', 'profile/q2_results.db', 'profile2048-input.i32'):
            meta = receipt['artifacts'][name]
            assert sha(path / 'results' / name) == meta['sha256']
            assert (path / 'results' / name).stat().st_size == meta['bytes']
        grouped = {}
        for kernel in data['kernels']:
            group = grouped.setdefault(category(kernel['kernel']), dict(ns=0, calls=0))
            group['ns'] += kernel['total_ns']; group['calls'] += kernel['calls']
        assert sum(v['ns'] for v in grouped.values()) == data['kernel_sum_ns']
        assert sum(v['calls'] for v in grouped.values()) == data['dispatches']
        groups[arm] = grouped
        bindings[arm] = dict(path=str(path.relative_to(ROOT)), receipt_sha256=sha(path / 'results/result.json'),
            phase_sha256=sha(rawpath), input_sha256=q['input_sha256'],
            binary_sha256=receipt['binary_sha256'], finished_at=receipt['finished_at'],
            kernel_sum_ns=data['kernel_sum_ns'])
    names = set().union(*groups.values())
    rows = []
    for name in names:
        a, b = [groups[key].get(name, dict(ns=0,calls=0)) for key in ('q2_saved1571','ud_historical')]
        rows.append(dict(group=name,q2_ns=a['ns'],ud_ns=b['ns'],q2_calls=a['calls'],ud_calls=b['calls'],delta_ns=a['ns']-b['ns']))
    rows.sort(key=lambda r:-r['delta_ns'])
    gap = dict(schema='synapse-lie.q2-hc-focus-reassessment.v1', bindings=bindings, rows=rows,
        previous_reports={str(p.relative_to(ROOT)):sha(p) for p in (qpath,upath)},
        scope='Offline reclassification of saved noncontemporaneous diagnostic traces. Q2 is1571, not current1587. '
              'Matched exact2048 input, but not a new performance benchmark or causal decomposition of the fixed74.889ms gap. '
              'Generic half dense calls are not automatically HC-up; deferred up and half expert-down are explicit. '
              'Different Q2/UD formats and dispatch counts remain visible.',
        new_GPU_run=False, headline_comparison_changed=False, goal_met=False)
    out = ROOT / 'config/q2-hc-focus-reassessment.json'
    with out.open('x') as stream: json.dump(gap,stream,indent=2);stream.write('\n')
    with (ROOT / 'docs/figures/q2-hc-focus-reassessment.csv').open('x') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    print(json.dumps(dict(variants={k:v['added_kernels'] for k,v in variants.items()},profile_groups=rows)))


if __name__ == '__main__':
    main()
