#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind the compact Q8 fixture and audit unaffected device bodies without execution."""
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'q2-decode-q8-compact'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bodies(path):
    result = {}
    for name, body in re.findall(r'^([^\s:]+):\s*;[^\n]*\n(.*?)^\s*\.section\s+\.rodata',
                                path.read_text(), re.M | re.S):
        lines = [line.split(';')[0].strip() for line in body.splitlines()]
        result[name] = '\n'.join(re.sub(r'\.LBB\d+_', '.LBB_', line) for line in lines if line)
    return result


def main():
    out = ROOT / ('evidence/' + PREFIX + '-preparation')
    base = ROOT / 'evidence/q2-decode-q8-rows4-preparation/candidate.s'
    candidate = out / 'candidate.s'
    original, changed = bodies(base), bodies(candidate)
    names = [n for n in original if ('mul_mat_vec_q8I' in n or 'mul_mat_q8_decode_batch' in n)]
    assert len(names) == 28 and all(original[n] == changed[n] for n in names)
    common = [n for n in original if 'rows4' not in n]
    assert all(n in changed and original[n] == changed[n] for n in common)
    kernels = []
    for name in changed:
        if 'mul_mat_vec_q8_compact' not in name:
            continue
        match = re.search(r'\.amdhsa_kernel ' + re.escape(name) + r'\n(.*?)\.end_amdhsa_kernel',
                          candidate.read_text(), re.S)
        resources = dict(re.findall(r'\.(amdhsa_\w+)\s+(\S+)', match.group(1)))
        assert resources['amdhsa_private_segment_fixed_size'] == '0'
        assert resources['amdhsa_group_segment_fixed_size'] == '0'
        instructions = [line.split()[0] for line in changed[name].splitlines() if not line.startswith('.')]
        kernels.append(dict(symbol=name, resources=resources, static_instructions=len(instructions),
            ds_bpermute=sum(t.startswith('ds_bpermute') for t in instructions),
            dpp_adds=sum(t == 'v_add_f32_dpp' for t in instructions),
            note='Whole body includes a separate tail; these are not dynamic instructions per row.'))
    control = ROOT / 'experiments/q2-decode-q8-control.inc'
    report = dict(schema='synapse-lie.' + PREFIX + '-static.v1',
        source_manifest_sha256=sha(ROOT / ('config/' + PREFIX + '-source.json')),
        assembly=str(candidate.relative_to(ROOT)), assembly_sha256=sha(candidate),
        reference_assembly=str(base.relative_to(ROOT)), reference_assembly_sha256=sha(base),
        all_q8_original_bodies_exact=names, all_unaffected_device_bodies_exact=len(common),
        candidate_kernels=kernels, control_include=str(control.relative_to(ROOT)),
        control_sha256=sha(control), GPU_run=False)
    with (ROOT / ('config/' + PREFIX + '-static.json')).open('x') as stream:
        json.dump(report, stream, indent=2); stream.write('\n')
    print(json.dumps(dict(unaffected_device_bodies=len(common), original_q8_bodies=len(names),
                          candidate_kernels=kernels)))
    argv = json.loads((ROOT / 'evidence/q2-decode-q8-rows4-preparation/fixture-v2-command.json').read_text())['argv']
    argv[-1] = str(ROOT / 'tests/q2_decode_q8_compact.hip')
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with (out / 'fixture.stdout').open('x') as stdout, (out / 'fixture.stderr').open('x') as stderr:
        result = subprocess.run(argv, stdout=stdout, stderr=stderr)
    bindings = {name: sha(ROOT / name) for name in (
        'tests/q2_decode_q8_compact.hip', 'experiments/q2-decode-q8-control.inc',
        'experiments/' + PREFIX + '.inc')}
    receipt = out / 'fixture-command.json'
    with receipt.open('x') as stream:
        json.dump(dict(argv=argv, started_at=started,
            finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            exit_code=result.returncode, bindings=bindings), stream, indent=2); stream.write('\n')
    if result.returncode:
        return result.returncode
    report = dict(schema='synapse-lie.' + PREFIX + '-fixture.v1', bindings=bindings,
        compile_receipt=str(receipt.relative_to(ROOT)), compile_receipt_sha256=sha(receipt),
        cases=8, timing_cases=4, pair_records=2038, oracle_records=4076, timing_records=56,
        independent_formula='FP64 encoded Q8_0 dot Q8_1, optional gated SiLU, limit2e-5',
        allocation='Production hipMalloc; rotating weights above48MiB; distinct outputs for at least64 calls per timed sample',
        quantizer_tested=False, actual_model_dispatch_tested=False,
        all_timed_outputs_checked_before_reuse=True, controls_rebuilt_or_rerun=False)
    with (ROOT / ('config/' + PREFIX + '-fixture.json')).open('x') as stream:
        json.dump(report, stream, indent=2); stream.write('\n')
    print('Fixture syntax:0; no GPU execution')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
