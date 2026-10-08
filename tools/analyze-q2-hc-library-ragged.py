#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit ragged HC cycles, retaining numerical/position failures and all timings."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import statistics
import struct
import tarfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('original', ROOT/'tools/analyze-q2-original-baseline.py')
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)
require = original.require
SHAPES = (96, 97, 129, 502, 2042, 2047, 2048)
TIMED = (502, 2042, 2047, 2048)
FIXTURES = ('CMakeLists.txt', 'cmake/hip/CMakeLists.txt', 'tools/q2-remote.py',
            'tools/q2-runner.py', 'tools/q2_process.py', 'tools/q2_thermal.py',
            'tests/q2_remote_test.py', 'tests/q2_hc_library_ragged.cpp',
            'tests/q2_hc_sequence.cpp', 'tests/q2_hc_norm_half.cpp', 'tests/q2_hc_moe_fused.cpp')
# The measured component used c40f80f's component-only admission guards.
# Later model admission must not invalidate or silently replace that evidence.
COMPONENT_GUARDS = {
    'tools/q2-remote.py': 'e1dfa33c465a00c3301d3c1ebe89e316e0a8ffdcfe0dcbe7d0796ddb1add528e',
    'tests/q2_remote_test.py': '600952fda3124c40d567cadfd014b2837678f0979c6691aadfa6428952bde4fc',
}


def audit_component_capsule(path):
    result = original.audit.audit_capsule(path, [n for n in FIXTURES if n not in COMPONENT_GUARDS])
    with tarfile.open(path/'source.tar.gz') as capsule:
        for name, frozen in COMPONENT_GUARDS.items():
            digest = hashlib.sha256(capsule.extractfile(name).read()).hexdigest()
            require(digest in (frozen, original.audit.digest(ROOT/name)), 'Unknown component guard')
            result['fixtures_sha256'][name] = digest
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--host', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.directory/'results'
    receipt = json.loads((root/'result.json').read_text())
    transport = json.loads((args.directory/'transport.json').read_text())
    exits = [r['exit_code'] for r in receipt['commands']]
    require(receipt['mode'] == 'hc-library-ragged-bench' and not receipt['model_access'], 'Wrong scope')
    require(exits in ([0,0,0], [0,0,1]) and transport['exit_code'] == exits[-1], 'Incomplete run')
    require(transport['source_variant'] == 'hc-library-ragged', 'Wrong source')
    require(receipt['binary_sha256'] == receipt['binary_sha256_after'], 'Binary changed')
    require('finished_at' in receipt, 'Unfinished runner')
    require(receipt['locks'] == receipt['postflight_locks'] and
            [(r['device'],r['inode']) for r in receipt['locks']] ==
            [(52,3232146),(52,3206482),(52,3228451),(55,45067)], 'Lease mismatch')
    require(not receipt['preflight_kfd'] and not receipt['postflight_kfd'], 'Unretired KFD')
    for r in [receipt, *receipt['commands']]:
        require(not any(r.get(k) for k in ('thermal_stop','postflight_error','timeout',
                    'foreign_kfd','lingering_descendants')), 'Runtime failure')
    original.verify_artifacts(args.directory, receipt)
    host = json.loads((args.host/'results/result.json').read_text())
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and not host['model_access'] and
            [c['exit_code'] for c in host['commands']] == [0]*6, 'Host cohort incomplete')
    require(json.loads((args.host/'transport.json').read_text())['exit_code'] == 0, 'Host transport failed')
    original.verify_artifacts(args.host, host)
    for name in ('03.log','06.log'):
        require('100% tests passed out of 17' in (args.host/'results'/name).read_text(), 'Missing host tests')
    with tarfile.open(args.directory/'source.tar.gz') as candidate, tarfile.open(args.host/'source.tar.gz') as control:
        for name in FIXTURES:
            require(candidate.extractfile(name).read() == control.extractfile(name).read(), 'Host fixture differs')
    validation = dict(component=audit_component_capsule(args.directory),
                      host=audit_component_capsule(args.host))
    manifest = json.loads((ROOT/'config/q2-hc-library-ragged-source.json').read_text())
    source = ROOT/manifest['candidate']
    require({str(p.relative_to(source)):original.audit.digest(p) for p in source.rglob('*') if p.is_file()} ==
            manifest['source_file_hashes'], 'Prepared source differs')
    log = (root/'03.log').read_text()
    events = [json.loads(line) for line in log.splitlines() if line.startswith('{')]
    unsupported = sorted({e['tokens'] for e in events if e.get('event') == 'ragged_unsupported'})
    require(set(unsupported) <= set(SHAPES), 'Unknown unsupported shape')
    # Refusal is visible and cannot be treated as a successful complete campaign.
    supported = set(SHAPES)-set(unsupported)
    expected_labels = {f'ragged-n{n}-p{p}-moe{moe}-{arm}'
                       for n,p in [*((n,0) for n in SHAPES),(2042,1)] if n in supported
                       for moe in (0,1) for arm in ('native','library')}
    expected_labels |= {f'ragged-bench-n{n}-moe{moe}-rep{rep}' for n in TIMED if n in supported
                        for moe in (0,1) for rep in range(5)}
    comparisons = [e for e in events if e.get('event') == 'hc_sequence_replay']
    require(len(comparisons) == len(expected_labels) and
            {e['label'] for e in comparisons} == expected_labels, 'Missing/duplicate comparisons')
    norms = [e for e in events if e.get('event') == 'hc_sequence_norm_oracle']
    require(len(norms) == len(expected_labels)-10*len(set(TIMED)&supported), 'Missing norm oracles')
    for e in comparisons:
        require(all(e[k] is True for k in ('res_exact','norm_exact','half_exact','scalar_half_exact')),
                'Producer changed')
        for prefix in ('res','norm','half'):
            require(e[f'reference_{prefix}_sha256'] == e[f'paired_{prefix}_sha256'], 'Producer hash mismatch')
        require(all(math.isfinite(e[k]) and e[k] >= 0 for k in ('down_rrms','down_peak_scaled')),
                'Invalid FP64 metric')
        require(type(e['pass']) is bool and type(e['down_exact']) is bool, 'Missing verdict')
        require(e['down_exact'] == (e['reference_down_sha256'] == e['paired_down_sha256']),
                'Full down comparison differs')
        norm_pass = True
        if not e['label'].startswith('ragged-bench-'):
            index = next(i for i,row in enumerate(events) if row is e)
            require(index > 0 and events[index-1]['event'] == 'hc_sequence_norm_oracle', 'Missing paired oracle')
            norm_pass = events[index-1]['pass']
        require(e['pass'] == (e['down_exact'] and e['down_rrms'] <= 2e-5 and
                              e['down_peak_scaled'] <= 2e-5 and norm_pass), 'Numerical verdict differs')
    for e in norms:
        require(all(math.isfinite(e[k]) and e[k] >= 0 for k in
                    ('res_rrms','norm_rrms','res_peak_scaled','norm_peak_scaled')), 'Invalid norm oracle')
        require(e['pass'] == all(e[k] <= 2e-5 for k in
                    ('res_rrms','norm_rrms','res_peak_scaled','norm_peak_scaled')), 'Norm verdict differs')
    names = set()
    for e in comparisons:
        m = re.fullmatch(r'(ragged-n(\d+)-p\d+-moe[01])-library',e['label'])
        if not m:
            continue
        for arm,key in [('native','reference_down_sha256'),('library','paired_down_sha256')]:
            name = m[1]+'-'+arm+'.f32';names.add(name)
            raw = (root/name).read_bytes()
            require(len(raw) == int(m[2])*320*4 and hashlib.sha256(raw).hexdigest() == e[key],
                    'Down output differs')
            require(all(math.isfinite(v[0]) for v in struct.iter_unpack('<f',raw)), 'Nonfinite output')
    position = [e for e in events if e.get('event') == 'ragged_position']
    expected_positions = {(n,lib) for n in (97,2042,2047,2048) if n in supported for lib in (False,True)}
    require(len(position) == len(expected_positions) and
            {(e['tokens'],e['library']) for e in position} == expected_positions, 'Missing position probe')
    for e in position:
        n = e['tokens']; arm = 'library' if e['library'] else 'native'
        name = f'ragged-repeat-n{n}-{arm}.f32';names.add(name)
        raw = (root/name).read_bytes()
        require(len(raw) == n*320*4 and hashlib.sha256(raw).hexdigest() == e['sha256'], 'Position bytes differ')
        row_size = 320*4
        changed = sum(raw[i*row_size:(i+1)*row_size] != raw[:row_size] for i in range(1,n))
        require(changed == e['changed_rows'], 'Position verdict differs')
        require(all(math.isfinite(v[0]) for v in struct.iter_unpack('<f',raw)), 'Nonfinite repeated output')
    require(names == {p.name for p in root.glob('*.f32')}, 'Unexpected output inventory')
    samples = [e for e in events if e.get('event') == 'ragged_microbench']
    expected_samples = {(n,moe,rep,lib) for n in TIMED if n in supported
                        for moe in (False,True) for rep in range(5) for lib in (False,True)}
    require(len(samples) == len(expected_samples) and
            {(e['tokens'],e['moe'],e['rep'],e['library']) for e in samples} == expected_samples,
            'Incomplete timings')
    require([(e['tokens'],e['moe'],e['rep'],e['library']) for e in samples] ==
            [(n,moe,rep,bool((rep+arm)%2)) for n in TIMED if n in supported
             for moe in (False,True) for rep in range(5) for arm in range(2)], 'Timing order differs')
    medians = {}
    for e in samples:
        require(e['iterations'] == 16 and e['weight_bytes'] == 104857600 and
                e['allocation'] == (int(e['library']) ^ (e['rep'] % 2)) and
                math.isfinite(e['microseconds_per_iteration']) and e['microseconds_per_iteration'] > 0,
                'Changed timing scope')
    for n in TIMED:
        if n not in supported:
            continue
        for moe in (False,True):
            row = {arm:statistics.median(e['microseconds_per_iteration'] for e in samples
                   if (e['tokens'],e['moe'],e['library']) == (n,moe,lib))
                   for arm,lib in [('native',False),('library',True)]}
            row['time_change_percent'] = 100*(row['library']/row['native']-1)
            medians[f'n{n}-moe{int(moe)}'] = row
    passed = not unsupported and all(e['pass'] for e in comparisons+norms) and all(e['changed_rows'] == 0 for e in position)
    require([e for e in events if e.get('event') == 'ragged_complete'] ==
            [dict(event='ragged_complete',numerical_pass=passed,model_inference=False)], 'Completion differs')
    require(exits[-1] == (0 if passed else 1), 'Exit does not retain numerical failure')
    require(receipt['state'] == ('SYNTHETIC_HC_MICROBENCH_COMPLETE_NOT_MODEL_THROUGHPUT'
                                if passed else 'FAILED'), 'Runner verdict differs')
    report = dict(scope='Synthetic same-process HC ragged norm/narrow/down cycles, no model inference',
        validation=validation, command_exits=exits, unsupported_shapes=unsupported,
        comparisons=comparisons, independent_norms=norms, repeated_row_positions=position,
        samples=samples, median_us=medians, numerical_pass=passed, promoted=False, goal_met=False,
        limits='Both paths retain the same original producer. Library arithmetic and position drift remain explicit failures. n2048 is an existing library shape; its native comparison is not a new model gain. No decode or full-model improvement established.')
    args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(numerical_pass=passed,unsupported_shapes=unsupported,median_us=medians)))
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
