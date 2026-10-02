#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build pinned upstream libraries on the editing host; never runs GPU code.
Remote use requires the separate agreed DS4 lease/supervisor. No installation.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PIN = 'f783fedb9bea2ec7de941f6da4e02f4a4596b29e'

def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()

def main():
    if len(sys.argv)<2 or not re.fullmatch(r'[a-z0-9-]{1,48}',sys.argv[1]) or sys.argv[2:] not in ([],['--qwen-only'],['--qwen-only','--state-access'],['--qwen-only','--state-access','--ds4-state']):
        raise SystemExit('Usage: tools/build-gufo.py EXCLUSIVE-LABEL [--qwen-only [--state-access [--ds4-state]]] (local compile only)')
    subset = '--qwen-only' in sys.argv
    state_access = '--state-access' in sys.argv
    kvc = '--ds4-state' in sys.argv
    if os.environ.get('SSH_CONNECTION'):
        raise SystemExit('Remote GPU build requires the agreed lease runner; this helper is local-only')
    label = sys.argv[1]
    out = ROOT / 'evidence' / label; out.mkdir()
    build = ROOT / 'build' / label; build.mkdir()
    home = build / 'private-home'; home.mkdir()
    temp = build / 'tmp'; temp.mkdir()
    source = ROOT / '.deps/gufo-f783fedb'
    manifest = json.loads((ROOT / 'third_party/gufo-source.json').read_text())
    source_files=manifest['files']
    result = {'state':'RUNNING', 'source_pin':PIN, 'pid':os.getpid(), 'commands':[],
              'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'gpu_execution':False, 'installation':False, 'build':str(build),
              'scope':'lie-qwen-only-source-subset' if subset else 'upstream-cmake',
              'build_script_sha256':sha(Path(__file__)),
              'subset_cmake_sha256':sha(ROOT/'cmake/gufo-runtime/CMakeLists.txt') if subset else None}
    if state_access:
        result['source_variant']='lie-state-access-v1'
        result['state_access_edits_sha256']=sha(ROOT/'adapters/gufo-state/access-edits.json')
        if kvc:
            result['source_variant']='lie-ds4-state-v1'
            result['kvc_edits_sha256']=sha(ROOT/'adapters/gufo-state/kvc-edits.json')
    def save(): (out / 'result.json').write_text(json.dumps(result, indent=2)+'\n')
    def verify():
        for name,h in source_files.items():
            p=source/name
            if p.is_symlink() or not p.is_file() or sha(p)!=h: raise RuntimeError('source drift: '+name)
    env = {k:v for k,v in os.environ.items() if not k.startswith(('GUFO_', 'DS4_')) and k not in
           ('LD_PRELOAD','LD_LIBRARY_PATH','CC','CXX','CFLAGS','CXXFLAGS','HIPFLAGS','HIPCC_COMPILE_FLAGS_APPEND','HIPCC_LINK_FLAGS_APPEND')}
    env.update(HOME=str(home), XDG_CACHE_HOME=str(home/'cache'), TMPDIR=str(temp), LC_ALL='C')
    def run(argv):
        row={'argv':argv,'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
        index=len(result['commands']); result['commands'].append(row); save()
        with (out/f'{index:02}.log').open('wb') as log:
            p=subprocess.Popen(argv, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            row['pid']=p.pid; save()
            try: code=p.wait(timeout=5400)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid,signal.SIGTERM)
                try: p.wait(timeout=20)
                except subprocess.TimeoutExpired: os.killpg(p.pid,signal.SIGKILL); p.wait()
                row['exit_code']=p.returncode; row['timeout']=True; save(); raise
        row['exit_code']=code; row['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat(); save()
        if code: raise RuntimeError(f'command {index} exit {code}')
    save()
    try:
        if state_access:
            from gufo_state_source import materialize
            source,source_files=materialize(ROOT,label,kvc)
            result['source']=str(source);result['variant_files']=source_files;save()
        verify()
        run(['cmake','--version']); run(['c++','--version']); run(['/opt/rocm/bin/hipcc','--version'])
        run(['cmake','-S',str(ROOT/'cmake/gufo-runtime' if subset else source),'-B',str(build),'-G','Ninja',
             '-DGUFO_SOURCE='+str(source),
             '-DCMAKE_BUILD_TYPE=RelWithDebInfo','-DBUILD_TESTING=OFF','-DGUFO_BUILD_TOOLS=OFF',
             '-DENGINE_ENABLE_HIP=ON','-DCMAKE_HIP_ARCHITECTURES=gfx1151',
             '-DCMAKE_CXX_FLAGS=-include chrono','-DCMAKE_HIP_FLAGS=-include chrono',
             '-DGUFO_REVISION='+PIN])
        run(['cmake','--build',str(build),'--target','gufo_qwen38_flash_next','--parallel','1'])
        verify()
        libs=['libgufo_core.a','src/models/qwen38_flash_next/libgufo_qwen38_flash_next.a',
              'src/models/qwen38_flash_next/libgufo_qwen38_flash_next_mmq.a']
        result['libraries']={n:sha(build/n) for n in libs}
        result['source_manifest_sha256']=sha(ROOT/'third_party/gufo-source.json')
        result['cmake_cache_sha256']=sha(build/'CMakeCache.txt')
        result['state']='LIBRARIES_BUILT_NOT_EXECUTED_NOT_INFERENCE_QUALIFIED'
        (build/'BUILD-RECEIPT.json').write_text(json.dumps(result,indent=2)+'\n')
    except Exception as ex:
        result['state']='FAILED';result['error']=repr(ex);raise
    finally:
        result['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
    print(result['state'])

if __name__=='__main__': main()
