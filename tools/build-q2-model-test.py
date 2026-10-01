#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Serial local build of the first Q2 model test. NEVER launches GPU/model work."""
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
import q2_model_source as source
ROOT = source.ROOT

def git(*args): return subprocess.check_output(['git', *args], cwd=ROOT)
def snapshot():
    parts = [git('diff', '--binary', 'HEAD')]
    for name in git('ls-files', '--others', '--exclude-standard', '-z').decode().split('\0'):
        if name:
            p = subprocess.run(['git', 'diff', '--no-index', '--binary', '/dev/null', name],
                               cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if p.returncode not in (0, 1): raise RuntimeError('cannot record new source diff')
            parts.append(p.stdout)
    return b''.join(parts)
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def main():
    label = sys.argv[1] if len(sys.argv) == 2 else ''
    if not re.fullmatch('[a-z0-9-]{1,64}', label) or os.environ.get('SSH_CONNECTION'):
        raise SystemExit('Usage: build-q2-model-test.py EXCLUSIVE-LABEL (editing host only)')
    build, out = ROOT/'build'/label, ROOT/'evidence'/label
    for p in (build, out):
        if any(x.is_symlink() for x in [p, *p.parents]): raise ValueError('symlink output path')
        p.mkdir()
    before = snapshot()
    (out/'source.patch').write_bytes(before)
    r = {'state': 'BUILDING', 'started_at': now(), 'source_commit': git('rev-parse','HEAD').decode().strip(),
         'source_diff': 'source.patch', 'gpu_execution': False, 'model_access': False,
         'runtime_link_allowed': False, 'test_link_only': True, 'commands': []}
    env = {k:v for k,v in os.environ.items() if not k.startswith(('HIP_', 'HSA_', 'ROCR_', 'CUDA_', 'GUFO_', 'DS4_'))
           and k not in ('LD_PRELOAD','LD_LIBRARY_PATH','CC','CXX','CFLAGS','CXXFLAGS','HIPFLAGS',
                         'HIPCC_COMPILE_FLAGS_APPEND','HIPCC_LINK_FLAGS_APPEND')}
    env.update(HIP_VISIBLE_DEVICES='-1', ROCR_VISIBLE_DEVICES='-1', CUDA_VISIBLE_DEVICES='-1', LC_ALL='C')
    resource.setrlimit(resource.RLIMIT_CORE, (0,0))
    def save(): (out/'result.json').write_text(json.dumps(r, indent=2)+'\n')
    def run(argv, timeout=900):
        row={'argv':list(map(str,argv)), 'log':f'{len(r["commands"]):02}.log'}
        r['commands'].append(row); save()
        with (out/row['log']).open('xb') as log:
            p=subprocess.Popen(row['argv'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try: p.wait(timeout=timeout)
            except BaseException:
                row['interrupted_or_timeout']=True
                try: os.killpg(p.pid,signal.SIGTERM)
                except ProcessLookupError: pass
                try: p.wait(timeout=20)
                except subprocess.TimeoutExpired: os.killpg(p.pid,signal.SIGKILL); p.wait()
                raise
            finally: row['exit_code']=p.returncode; save()
        if p.returncode: raise RuntimeError('build/check failed: '+row['log'])
    save()
    try:
        r['source']=source.prepare(build/'source'); save()
        for name in source.TARGETS:
            run(['clang-format','-i',build/'source'/name])
        run(['cmake','-S',ROOT/'cmake/q2-model','-B',build/'hip','-G','Ninja',
             '-DCMAKE_BUILD_TYPE=RelWithDebInfo','-DCMAKE_HIP_ARCHITECTURES=gfx1151',
             '-DCMAKE_CXX_FLAGS=-include chrono','-DCMAKE_HIP_FLAGS=-include chrono',
             '-DGUFO_SOURCE='+str(build/'source'),'-DLIE_BUILD_ID='+label])
        run(['cmake','--build',build/'hip','-j1'])
        run([build/'hip/test-q2-model-memory'],20)
        run([build/'hip/q2-model-header-plan',ROOT/'evidence/q2-header-readonly-r1/q2.header',
             '147207127040','11025376'],30)
        run([build/'hip/q2-model-first-test','--build-info'],20)
        if before != snapshot(): raise RuntimeError('source diff changed during build')
        with (build/'hip/q2-model-first-test').open('rb') as f:
            r['test_binary_sha256']=hashlib.file_digest(f,'sha256').hexdigest()
        r['state']='Q2_FIRST_MODEL_TEST_BUILT_HOST_PLAN_PASS_GPU_NOT_RUN'
    except BaseException as error:
        r['state'],r['error']='FAILED',repr(error)
        raise
    finally: r['finished_at']=now(); save()
    print(json.dumps({k:v for k,v in r.items() if k!='commands'},indent=2))
if __name__=='__main__': main()
