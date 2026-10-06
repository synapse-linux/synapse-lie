#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile a private whole-row IQ2 producer against the unchanged retained provider."""
import argparse
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/q2-iq2-whole640-preparation'
INC = ROOT / 'experiments/q2-iq2-whole640-draft.inc'
spec = importlib.util.spec_from_file_location('prepare', ROOT / 'tools/prepare-q2-iq2-register-stage.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    global OUT, INC
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', default=OUT.name)
    parser.add_argument('--variant', choices=('register', 'lds'), default='register')
    args = parser.parse_args()
    if not re.fullmatch(r'q2-iq2-whole640-preparation(?:-v[0-9]+)?', args.label):
        raise ValueError('Invalid preparation label')
    OUT = ROOT / 'evidence' / args.label
    if args.variant == 'lds':
        INC = ROOT / 'experiments/q2-iq2-whole640-lds-draft.inc'
    parent_path = ROOT / 'config/q2-iq2-fixed-bounds-source.json'
    parent = json.loads(parent_path.read_text())['variants']['iq2-fixed-bounds']
    base = ROOT / parent['source']
    if prepare.inventory(base) != parent['files']:
        raise ValueError('Retained provider inventory differs')
    OUT.mkdir(exist_ok=False)
    (OUT / 'draft.inc').write_bytes(INC.read_bytes())
    probe = OUT / 'probe.hip.cpp'
    probe.write_text('// SPDX-License-Identifier: MIT\n'
                     '#include "../../' + parent['source'] + '/' + prepare.REL + '"\n'
                     'namespace gufo::models::qwen38_flash_next::rocm {\n'
                     '#include "draft.inc"\n'
                     '}\n')
    old_argv = json.loads((ROOT / 'evidence/q2-iq2-fixed-bounds-preparation/assembly-argv.json').read_text())
    argv = list(old_argv)
    argv[argv.index('-S') + 1] = str(probe.relative_to(ROOT))
    argv[argv.index('-o') + 1] = str((OUT / 'candidate.s').relative_to(ROOT))
    (OUT / 'assembly-argv.json').write_text(json.dumps(argv, indent=2) + '\n')
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with (OUT / 'assembly.stdout').open('x') as stdout, (OUT / 'assembly.stderr').open('x') as stderr:
        process = subprocess.run(argv, cwd=ROOT, stdout=stdout, stderr=stderr)
    record = dict(argv=argv, started_at=started,
                  finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  exit_code=process.returncode, gpu_run=False,
                  parent_manifest_sha256=sha(parent_path), parent_files=len(parent['files']),
                  draft_sha256=sha(INC), probe_sha256=sha(probe), variant=args.variant,
                  selected_live_rows='1..16 in existing 64-row tail descriptors',
                  matrix_dimensions=dict(logical_output=640, input=2560),
                  activation_stage_lds_bytes=2176,
                  total_declared_lds_bytes=52352 if args.variant == 'lds' else 11392,
                  wmma_accumulator_floats_per_thread=8 if args.variant == 'lds' else 80,
                  packed_value_floats_per_thread=20 if args.variant == 'lds' else 40,
                  global_F32_intermediate=False, output_inverse_scale='original whole640 dyadic scale',
                  production_selector=False, numerical_validation=False,
                  performance_measurement=False)
    if process.returncode == 0:
        record['assembly_sha256'] = sha(OUT / 'candidate.s')
    (OUT / 'assembly-command.json').write_text(json.dumps(record, indent=2) + '\n')
    if prepare.inventory(base) != parent['files']:
        raise ValueError('Retained provider changed during preparation')
    print(json.dumps(record))
    if process.returncode:
        print((OUT / 'assembly.stderr').read_text()[-5000:])
    raise SystemExit(process.returncode)


if __name__ == '__main__':
    main()
