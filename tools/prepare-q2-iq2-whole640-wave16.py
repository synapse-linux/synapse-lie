#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile only the new sixteen-wave whole640 draft; do not run the GPU."""
import argparse
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/q2-iq2-whole640-wave16-preparation'
INC = ROOT / 'experiments/q2-iq2-whole640-wave16-draft.inc'
spec = importlib.util.spec_from_file_location('prepare', ROOT / 'tools/prepare-q2-iq2-register-stage.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    global OUT, INC
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant', choices=('register', 'lds'), default='register')
    args = parser.parse_args()
    if args.variant == 'lds':
        OUT = ROOT / 'evidence/q2-iq2-whole640-wave16-lds-preparation'
        INC = ROOT / 'experiments/q2-iq2-whole640-wave16-lds-draft.inc'
    manifest = ROOT / 'config/q2-iq2-fixed-bounds-source.json'
    source = json.loads(manifest.read_text())['variants']['iq2-fixed-bounds']
    base = ROOT / source['source']
    assert prepare.inventory(base) == source['files']
    OUT.mkdir(exist_ok=False)
    commands = [('format', ['clang-format', '-i', '--style=file:' + str(base / '.clang-format'), str(INC)]),
                ('format-check', ['clang-format', '--dry-run', '--Werror',
                                  '--style=file:' + str(base / '.clang-format'), str(INC)])]
    for label, argv in commands:
        with (OUT / (label + '.stdout')).open('x') as stdout, (OUT / (label + '.stderr')).open('x') as stderr:
            result = subprocess.run(argv, stdout=stdout, stderr=stderr)
        (OUT / (label + '-command.json')).write_text(json.dumps(dict(argv=argv, exit_code=result.returncode)) + '\n')
        if result.returncode:
            raise SystemExit(result.returncode)
    (OUT / 'draft.inc').write_bytes(INC.read_bytes())
    probe = OUT / 'probe.hip.cpp'
    probe.write_text('// SPDX-License-Identifier: MIT\n#include "../../' + source['source'] + '/' + prepare.REL + '"\n'
                     'namespace gufo::models::qwen38_flash_next::rocm {\n#include "draft.inc"\n}\n')
    argv = json.loads((ROOT / 'evidence/q2-iq2-fixed-bounds-preparation/assembly-argv.json').read_text())
    argv[argv.index('-S') + 1] = str(probe.relative_to(ROOT))
    argv[argv.index('-o') + 1] = str((OUT / 'candidate.s').relative_to(ROOT))
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with (OUT / 'assembly.stdout').open('x') as stdout, (OUT / 'assembly.stderr').open('x') as stderr:
        result = subprocess.run(argv, cwd=ROOT, stdout=stdout, stderr=stderr)
    record = dict(argv=argv, exit_code=result.returncode, started_at=started,
        finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source_manifest_sha256=sha(manifest), draft_sha256=sha(INC),
        probe_sha256=sha(probe), threads=512, waves=16, groups=5,
        variant=args.variant,
        accumulator_floats_per_thread=8 if args.variant == 'lds' else 40,
        retained_packing_floats_per_thread=20,
        declared_LDS_bytes=61568 if args.variant == 'lds' else 20608, parent_provider_files=1028,
        numerical_validation=False, GPU_run=False, model_inference=False,
        production_selector=False, performance_measurement=False)
    if result.returncode == 0:
        record['assembly_sha256'] = sha(OUT / 'candidate.s')
    (OUT / 'assembly-command.json').write_text(json.dumps(record, indent=2) + '\n')
    assert prepare.inventory(base) == source['files']
    print(json.dumps(record))
    if result.returncode:
        print((OUT / 'assembly.stderr').read_text()[-4000:])
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
