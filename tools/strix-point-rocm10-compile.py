#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile the pinned gfx1150 slice in the isolated Fedora/ROCm 10 image.

The outer .161 campaign owns the lease, service restoration and thermal guard.
This child has no GPU device nodes or network and records each compiler exit.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LIBRARY_LABEL = 'rocm10-point-libraries-r1'
LINK_LABEL = 'rocm10-point-linked-r1'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    if os.environ.get('LIE_ROCM10_BUILD_WINDOW') != 'admitted':
        raise SystemExit('An admitted one-shot build window is required')
    if Path('/dev/kfd').exists():
        raise SystemExit('Compiler container must not receive GPU devices')
    if not (ROOT/'.deps/gufo-f783fedb').is_dir():
        raise SystemExit('Pinned independent Gufo source is missing')
    output = ROOT/'evidence'/'rocm10-point-compile-r1'
    output.mkdir(parents=True, exist_ok=False)
    record = {'schema': 'synapse-lie.point-rocm10-compile.v1',
              'scope': 'gfx1150 device-code compilation, no GPU execution',
              'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'rocm_version': subprocess.run(['/opt/rocm/bin/hipcc', '--version'],
                                            capture_output=True, text=True).stdout,
              'source_manifest_sha256': sha(ROOT/'third_party/gufo-source.json'),
              'commands': [], 'exit_code': 1}

    def save():
        (output/'result.json').write_text(json.dumps(record, indent=2)+'\n')

    def run(name, argv):
        row = {'name': name, 'argv': argv,
               'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
        record['commands'].append(row)
        save()
        with (output/(name+'.log')).open('wb') as log:
            proc = subprocess.run(argv, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        row['exit_code'] = proc.returncode
        row['ended_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save()
        if proc.returncode:
            raise RuntimeError(f'{name} failed with exit {proc.returncode}')

    try:
        # Both arms use the same canonical recipe and complete private layouts.
        # The historical Python helper builds only the old state-access slice.
        run('libraries', ['cmake', '-DLABEL='+LIBRARY_LABEL,
                          '-DLIE_HIP_ARCHITECTURE=gfx1150',
                          '-DLIE_GUFO_STATE_ACCESS=ON', '-DLIE_DS4_RUNTIME_CACHE=ON',
                          '-DLIE_C17_SAMPLING=ON', '-DLIE_ATTENTION_DISPATCH_STATS=ON',
                          '-P', 'cmake/provider/Build.cmake'])
        reference_label = LIBRARY_LABEL + '-reference'
        run('reference-libraries', ['cmake', '-DLABEL='+reference_label,
                                  '-DLIE_HIP_ARCHITECTURE=gfx1150',
                                  '-DLIE_GUFO_STATE_ACCESS=ON', '-DLIE_DS4_RUNTIME_CACHE=ON',
                                  '-DLIE_C17_SAMPLING=OFF', '-DLIE_ATTENTION_DISPATCH_STATS=ON',
                                  '-P', 'cmake/provider/Build.cmake'])
        run('configure', ['cmake', '-S', '.', '-B', 'build/'+LINK_LABEL, '-G', 'Ninja',
                          '-DCMAKE_BUILD_TYPE=Release', '-DLIE_GUFO_RUNTIME=ON',
                          '-DLIE_GUFO_STATE_ACCESS=ON', '-DLIE_DS4_RUNTIME_CACHE=ON',
                          '-DLIE_ATTENTION_DISPATCH_STATS=ON', '-DLIE_HIP_ARCHITECTURE=gfx1150',
                          '-DLIE_BUILD_ID='+LINK_LABEL,
                          '-DGUFO_SOURCE='+str(ROOT/'.deps'/('gufo-state-access-'+LIBRARY_LABEL)),
                          '-DGUFO_BUILD='+str(ROOT/'build'/LIBRARY_LABEL),
                          '-DGUFO_REFERENCE_BUILD='+str(ROOT/'build'/reference_label)])
        run('link', ['cmake', '--build', 'build/'+LINK_LABEL, '--parallel', '1',
                     '--target', 'synapse-lie-server', 'synapse-lie-bench',
                     'synapse-lie-bench-gufo-reference', 'lie-hip-probe'])
        binaries = ('synapse-lie-server', 'synapse-lie-bench',
                    'synapse-lie-bench-gufo-reference', 'lie-hip-probe')
        record['binaries'] = {name: sha(ROOT/'build'/LINK_LABEL/name) for name in binaries}
        record['state'] = 'BUILT_NOT_GPU_TESTED'
        record['exit_code'] = 0
    except BaseException as error:
        record['state'] = 'FAILED'
        record['error'] = repr(error)
        raise
    finally:
        record['ended_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save()
    print(json.dumps({'state': record['state'], 'binaries': record['binaries']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
