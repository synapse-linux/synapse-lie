#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build a provenance-bound upstream Gufo gfx1150 control without GPU access."""

import datetime
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

WORK = Path('/work')
SOURCE_ROOT = Path('/source')
UPSTREAM = SOURCE_ROOT/'.deps/gufo-f783fedb'
WMMA = Path('/wmma')
PIN = 'f783fedb9bea2ec7de941f6da4e02f4a4596b29e'
WMMA_INVENTORY_SHA = '76691eaf997ced3f6ff2f9f028f94c92a47c95fefeaaa3b3031ff5e378459654'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_source():
    manifest = json.loads((SOURCE_ROOT/'third_party/gufo-source.json').read_text())
    if manifest['commit'] != PIN:
        raise RuntimeError('Official Gufo pin mismatch')
    names = set(manifest['files'])
    if {str(path.relative_to(UPSTREAM)) for path in UPSTREAM.rglob('*')
        if path.is_file()} != names:
        raise RuntimeError('Official Gufo source inventory incomplete')
    for name, digest in manifest['files'].items():
        path = UPSTREAM/name
        if path.is_symlink() or sha(path) != digest:
            raise RuntimeError('Official Gufo source drift: '+name)
    return sha(SOURCE_ROOT/'third_party/gufo-source.json'), len(names)


def verify_wmma():
    inventory = WMMA/'FILES.sha256'
    if sha(inventory) != WMMA_INVENTORY_SHA:
        raise RuntimeError('rocWMMA source inventory drift')
    names = set()
    for line in inventory.read_text().splitlines():
        digest, name = line.split('  ./', 1)
        path = WMMA/name
        if path.is_symlink() or sha(path) != digest:
            raise RuntimeError('rocWMMA header drift: '+name)
        names.add(name)
    if {str(path.relative_to(WMMA)) for path in WMMA.rglob('*')
        if path.is_file()} != names | {'FILES.sha256'}:
        raise RuntimeError('rocWMMA source inventory incomplete')
    header = (WMMA/'include/rocwmma/internal/rocwmma-version.hpp').read_text()
    if not all(re.search(r'#define ROCWMMA_VERSION_'+key+r'\s+'+value+r'\b', header)
               for key, value in (('MAJOR', '2'), ('MINOR', '2'), ('PATCH', '0'))):
        raise RuntimeError('rocWMMA generated version mismatch')
    return len(names)


def port_source():
    target = WORK/'gufo-port-source'
    if target.exists():
        raise RuntimeError('Exclusive Gufo port source already exists')
    shutil.copytree(UPSTREAM, target)
    cmake = target/'CMakeLists.txt'
    old = cmake.read_text()
    predicate = 'if (ENGINE_ENABLE_HIP AND NOT CMAKE_HIP_ARCHITECTURES STREQUAL "gfx1151")'
    replacement = 'if (ENGINE_ENABLE_HIP AND NOT CMAKE_HIP_ARCHITECTURES MATCHES "^gfx115[01]$")'
    if old.count(predicate) != 1:
        raise RuntimeError('Upstream architecture gate changed')
    new = old.replace(predicate, replacement)
    cmake.write_text(new)
    diff = ''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                        fromfile='upstream/CMakeLists.txt',
                                        tofile='point-port/CMakeLists.txt'))
    (WORK/'gufo-gfx1150-port.patch').write_text(diff)
    return target, {'upstream_cmake_sha256': sha(UPSTREAM/'CMakeLists.txt'),
                    'ported_cmake_sha256': sha(cmake),
                    'patch_sha256': sha(WORK/'gufo-gfx1150-port.patch'),
                    'patch': diff}


def main():
    if os.environ.get('LIE_POINT_GUIFO_BUILD_WINDOW') != 'admitted' or Path('/dev/kfd').exists():
        raise SystemExit('Fresh leased device-free Point build window required')
    result = {'schema': 'synapse-lie.point-gufo-port-build.v1', 'state': 'RUNNING',
              'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'upstream_pin': PIN, 'target': 'gfx1150', 'commands': [],
              'gpu_device_available': False, 'installation': False, 'exit_code': 1}
    receipt = WORK/'gufo-build-result.json'

    def save():
        receipt.write_text(json.dumps(result, indent=2)+'\n')

    def run(name, argv, timeout):
        row = {'stage': name, 'argv': argv}
        result['commands'].append(row)
        save()
        with (WORK/f'gufo-{name}.stdout.log').open('xb') as stdout, \
             (WORK/f'gufo-{name}.stderr.log').open('xb') as stderr:
            try:
                child = subprocess.run(argv, stdout=stdout, stderr=stderr,
                                       timeout=timeout, cwd=WORK)
                row['exit_code'] = child.returncode
            except subprocess.TimeoutExpired:
                row['timeout_seconds'] = timeout
                row['exit_code'] = 124
            row['ended_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            save()
            if row['exit_code']:
                raise RuntimeError(name+' exited '+str(row['exit_code']))

    try:
        result['upstream_manifest_sha256'], result['upstream_files_verified'] = verify_source()
        result['rocwmma_files_verified'] = verify_wmma()
        source, result['port'] = port_source()
        build = WORK/'gufo-build'
        if build.exists():
            raise RuntimeError('Exclusive Gufo build directory already exists')
        run('configure', ['cmake', '-S', str(source), '-B', str(build), '-G', 'Ninja',
                          '-DCMAKE_BUILD_TYPE=RelWithDebInfo', '-DBUILD_TESTING=OFF',
                          '-DGUFO_BUILD_TOOLS=OFF', '-DENGINE_ENABLE_HIP=ON',
                          '-DCMAKE_HIP_ARCHITECTURES=gfx1150',
                          '-DCMAKE_CXX_FLAGS=-include chrono',
                          '-DCMAKE_HIP_FLAGS=-include chrono',
                          '-DCMAKE_EXE_LINKER_FLAGS=-no-pie',
                          '-DGUFO_REVISION='+PIN,
                          '-DROCWMMA_INCLUDE_DIR=/wmma/include'], 900)
        run('link', ['cmake', '--build', str(build), '--target', 'gufo',
                     '--parallel', '2'], 6300)
        binary = build/'gufo'
        if not binary.is_file():
            raise RuntimeError('Official Gufo server binary missing')
        result['binary_sha256'] = sha(binary)
        result['binary_bytes'] = binary.stat().st_size
        result['state'] = 'BUILT_NOT_GPU_TESTED'
        result['exit_code'] = 0
    except BaseException as error:
        result['state'] = 'FAILED'
        result['error'] = repr(error)
    finally:
        result['ended_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save()
    print(json.dumps({'state': result['state'], 'exit_code': result['exit_code'],
                      'error': result.get('error'), 'binary_sha256': result.get('binary_sha256')}))
    return result['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
