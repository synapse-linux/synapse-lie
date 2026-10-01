#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Serial editing-host-only HIP candidate build. Never executes GPU/model work."""
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
import q2_hip_port

ROOT = q2_hip_port.ROOT

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def main():
    label = sys.argv[1] if len(sys.argv) == 2 else ''
    if not re.fullmatch(r'[a-z0-9-]{1,64}', label) or os.environ.get('SSH_CONNECTION'):
        raise SystemExit('Usage: build-q2-hip.py EXCLUSIVE-LABEL (editing host only)')
    out, build = ROOT / 'evidence' / label, ROOT / 'build' / label
    for p in (out, build):
        if any(x.is_symlink() for x in [p, *p.parents]):
            raise SystemExit('symlink build/evidence path')
        p.mkdir()
    inputs = ['tools/build-q2-hip.py', 'tools/q2_port.py', 'tools/q2_hip_port.py',
              'cmake/q2-hip/CMakeLists.txt', 'cmake/gufo-runtime/CMakeLists.txt',
              'tests/q2_route_probe.cpp', 'tests/q2_operator_probe.cpp', 'tests/test_q2_plan.c',
              'third_party/gufo-source.json']
    inputs += [str(p.relative_to(ROOT)) for p in sorted((ROOT / 'adapters/gufo-q2').iterdir())
               if p.is_file()]
    before = {p: sha(ROOT / p) for p in inputs}
    r = {'state': 'RUNNING', 'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'gpu_execution': False, 'model_access': False, 'runtime_link_allowed': False,
         'inputs_before': before, 'commands': []}
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('HIP_', 'HSA_', 'ROCR_', 'CUDA_', 'GUFO_', 'DS4_'))
           and k not in ('LD_PRELOAD', 'LD_LIBRARY_PATH', 'CC', 'CXX', 'CFLAGS',
                         'CXXFLAGS', 'HIPFLAGS', 'HIPCC_COMPILE_FLAGS_APPEND',
                         'HIPCC_LINK_FLAGS_APPEND')}
    env.update(HIP_VISIBLE_DEVICES='-1', ROCR_VISIBLE_DEVICES='-1', LC_ALL='C')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    def save(): (out / 'result.json').write_text(json.dumps(r, indent=2) + '\n')
    def run(argv, timeout=600):
        i = len(r['commands']); row = {'argv': list(map(str, argv)), 'log': f'{i:02}.log'}
        r['commands'].append(row); save()
        with (out / row['log']).open('xb') as f:
            p = subprocess.Popen(row['argv'], cwd=ROOT, env=env, stdout=f,
                                 stderr=subprocess.STDOUT, start_new_session=True)
            try: p.wait(timeout=timeout)
            except BaseException:
                row['interrupted_or_timed_out'] = True
                try: os.killpg(p.pid, signal.SIGTERM)
                except ProcessLookupError: pass
                try: p.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL); p.wait()
                row['exit_code'] = p.returncode; save(); raise
        row['exit_code'] = p.returncode; save()
        if p.returncode: raise RuntimeError('Q2 candidate build/check failed: ' + str(i))
    save()
    try:
        r['source'] = q2_hip_port.prepare(build / 'source'); save()
        run(['/opt/rocm/llvm/bin/clang++', '--version'])
        run(['clang-format', '--version'])
        run([sys.executable, '-B', build / 'source/tools/ci/check-format.py'], timeout=120)
        run(['cmake', '-S', ROOT / 'cmake/q2-hip', '-B', build / 'hip', '-G', 'Ninja',
             '-DCMAKE_BUILD_TYPE=RelWithDebInfo', '-DCMAKE_HIP_ARCHITECTURES=gfx1151',
             '-DCMAKE_CXX_FLAGS=-include chrono', '-DCMAKE_HIP_FLAGS=-include chrono',
             '-DGUFO_SOURCE=' + str(build / 'source')])
        run(['cmake', '--build', build / 'hip', '-j1'], timeout=900)
        run([build / 'hip/q2-route-probe', '--contract-only'], timeout=20)
        run([build / 'hip/q2-operator-probe', '--cpu-oracle'], timeout=20)
        r['source_unchanged'] = all(sha(build / 'source' / p) == h
                                     for p, h in r['source']['files'].items())
        manifest = json.loads((ROOT / 'third_party/gufo-source.json').read_text())
        r['pristine_unchanged'] = all(sha(ROOT / '.deps/gufo-f783fedb' / p) == h
                                       for p, h in manifest['files'].items())
        r['inputs_unchanged'] = before == {p: sha(ROOT / p) for p in inputs}
        if not all(r[k] for k in ('source_unchanged', 'pristine_unchanged', 'inputs_unchanged')):
            raise RuntimeError('source drift during HIP candidate build')
        r['artifacts'] = {str(p.relative_to(build)): sha(p)
                          for p in sorted((build / 'hip').rglob('*.a'))}
        for binary in ('q2-route-probe', 'q2-operator-probe'):
            r['artifacts']['hip/' + binary] = sha(build / 'hip' / binary)
        r['operator_gpu_cases_run'] = False
        r['scalar_fixture_goldens_pass'] = True
        r['state'] = 'Q2_HIP_BUILD_HOST_REFUSALS_PASS_NOT_GPU_OR_MODEL_QUALIFICATION'
    except BaseException as e:
        r['state'], r['error'] = 'FAILED', repr(e); raise
    finally:
        r['finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat(); save()
    print(json.dumps({k: v for k, v in r.items() if k not in ('source', 'commands')}, indent=2))

if __name__ == '__main__': main()
