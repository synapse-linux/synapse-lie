#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Serial CPU verification of a private Q2 host variant. No HIP/model access."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import sys

import q2_port

ROOT = q2_port.ROOT


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    label = sys.argv[1] if len(sys.argv) == 2 else ''
    if not re.fullmatch(r'[a-z0-9-]{1,64}', label):
        raise SystemExit('Usage: verify-q2-host.py EXCLUSIVE-LABEL')
    if os.environ.get('SSH_CONNECTION'):
        raise SystemExit('Q2 host verification is editing-host-only')
    out = ROOT / 'evidence' / label
    out.mkdir()
    build = ROOT / 'build' / label
    build.mkdir()
    paths = ['tools/q2_port.py', 'tools/verify-q2-host.py', 'adapters/gufo-q2/host-edits.json',
             'cmake/q2-host/CMakeLists.txt', 'tests/test_q2_host.cpp', 'tests/q2_header_bind.cpp',
             'tests/test_q2_port.py',
             'third_party/gufo-source.json']
    before = {p: sha(ROOT / p) for p in paths}
    r = {'state': 'RUNNING', 'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'scope': 'synthetic host storage/binding and source-integrity tests, NOT-INFERENCE',
         'gpu_execution': False, 'hip_linked': False, 'real_model_access': False,
         'runtime_link_allowed': False, 'inputs_before': before, 'commands': []}
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    env = dict(os.environ, HIP_VISIBLE_DEVICES='-1', ROCR_VISIBLE_DEVICES='-1', LC_ALL='C',
               ASAN_OPTIONS='detect_leaks=1:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1')
    def save():
        (out / 'result.json').write_text(json.dumps(r, indent=2) + '\n')
    def run(argv, expected=0):
        i = len(r['commands'])
        row = {'argv': list(map(str, argv)), 'expected_exit_code': expected, 'log': f'{i:02}.log'}
        r['commands'].append(row); save()
        with (out / row['log']).open('xb') as log:
            p = subprocess.Popen(row['argv'], cwd=ROOT, env=env, stdout=log,
                                 stderr=subprocess.STDOUT, start_new_session=True)
            try:
                p.wait(timeout=120)
            except BaseException:
                row['interrupted_or_timed_out'] = True
                try:
                    os.killpg(p.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    p.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL); p.wait()
                row['exit_code'] = p.returncode; save()
                raise
        row['exit_code'] = p.returncode; save()
        if p.returncode != expected:
            raise RuntimeError('Q2 host command failed: ' + str(i))
    save()
    try:
        r['source'] = q2_port.prepare(ROOT / '.deps/gufo-f783fedb', build / 'source')
        save()
        run([sys.executable, '-B', 'tests/test_q2_port.py'])
        for name, compiler, flags in [('gcc', 'g++', []), ('clang', 'clang++', []),
                                      ('sanitize', 'g++', ['-DLIE_SANITIZERS=ON'])]:
            target = build / name
            run(['cmake', '-S', ROOT / 'cmake/q2-host', '-B', target, '-G', 'Ninja',
                 '-DCMAKE_BUILD_TYPE=Debug', '-DCMAKE_CXX_COMPILER=' + compiler,
                 '-DGUFO_SOURCE=' + str(build / 'source'), *flags])
            run(['cmake', '--build', target, '-j1'])
            run(['ctest', '--test-dir', target, '--output-on-failure', '-V'])
        # The normal production linker must not accept this experimental source.
        run([sys.executable, '-B', 'tools/check-gufo-build.py', build / 'source',
             ROOT / 'build/gufo-qwen-host-r2'], expected=1)
        if 'sources and archives must stay inside this repository' not in (out / r['commands'][-1]['log']).read_text():
            raise RuntimeError('production source refusal did not match the expected guard')
        r['source_unchanged'] = all(sha(build / 'source' / p) == h for p, h in r['source']['files'].items())
        pristine = json.loads((ROOT / 'third_party/gufo-source.json').read_text())
        r['pristine_unchanged'] = all(sha(ROOT / '.deps/gufo-f783fedb' / p) == h for p, h in pristine['files'].items())
        r['inputs_unchanged'] = before == {p: sha(ROOT / p) for p in paths}
        if not all(r[k] for k in ('source_unchanged', 'pristine_unchanged', 'inputs_unchanged')):
            raise RuntimeError('source changed during Q2 host verification')
        r['binaries'] = {name + '/' + binary: sha(build / name / binary)
                         for name in ('gcc', 'clang', 'sanitize')
                         for binary in ('test-q2-host', 'q2-header-bind')}
        r['state'] = 'Q2_HOST_STORAGE_BINDING_PASS_NOT_GPU_COMPATIBILITY'
    except BaseException as e:
        r['state'], r['error'] = 'FAILED', repr(e)
        raise
    finally:
        r['finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat(); save()
    print(json.dumps({k: v for k, v in r.items() if k not in ('source', 'commands')}, indent=2))


if __name__ == '__main__':
    main()
