#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Local CPU-only verification with actual subprocess return codes and source hashes."""
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


def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()


def inputs():
    result = {}
    for p in ROOT.rglob('*'):
        if p.relative_to(ROOT).parts[0] in {'.git', '.deps', 'build', 'evidence', 'run'}: continue
        if p.is_file() and '__pycache__' not in p.parts:
            if p.is_symlink(): raise ValueError('source symlink')
            result[str(p.relative_to(ROOT))] = sha(p)
    return result


def main():
    label = sys.argv[1] if len(sys.argv) == 2 else ''
    if not re.fullmatch(r'[a-z0-9-]{1,64}', label): raise SystemExit('Usage: tools/verify.py EXCLUSIVE-LABEL')
    out = ROOT / 'evidence' / label; out.mkdir()
    before = inputs()
    (out / 'inputs-before.json').write_text(json.dumps(before, indent=2) + '\n')
    result = {'state': 'RUNNING', 'hardware_inference': False, 'commands': [], 'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    def save(): (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    def run(argv, env=None):
        index=len(result['commands'])
        entry={'argv':argv,'start':datetime.datetime.now(datetime.timezone.utc).isoformat(),'log':f'{index:02}.log'}
        with (out/f'{index:02}.log').open('xb') as log:
            proc=subprocess.Popen(argv,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            entry['pid']=proc.pid; result['commands'].append(entry); save()
            try: code=proc.wait(timeout=120)
            except subprocess.TimeoutExpired:
                entry['timeout']=True
                try: os.killpg(proc.pid,signal.SIGTERM)
                except ProcessLookupError: pass
                try: code=proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    try: os.killpg(proc.pid,signal.SIGKILL)
                    except ProcessLookupError: pass
                    code=proc.wait()
        entry['exit_code']=code; entry['end']=datetime.datetime.now(datetime.timezone.utc).isoformat(); save()
        if code or entry.get('timeout'): raise RuntimeError(f'command {index} exit {code}')
    save()
    try:
        base=ROOT/'build'/label; base.mkdir()
        for name, options in [('debug', ['-DCMAKE_C_COMPILER=gcc']), ('clang', ['-DCMAKE_C_COMPILER=clang']), ('sanitize', ['-DCMAKE_C_COMPILER=gcc','-DLIE_SANITIZERS=ON'])]:
            build = str(base/name)
            run(['cmake', '-S', str(ROOT), '-B', build, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Debug',
                 '-DLIE_GUFO_RUNTIME=OFF','-DLIE_BUILD_ID='+label+'-'+name,*options])
            run(['cmake', '--build', build, '-j2'])
            env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1')
            run(['ctest', '--test-dir', build, '--output-on-failure', '-V'], env)
        source = ROOT / '.deps/gufo-f783fedb'
        manifest = json.loads((ROOT / 'third_party/gufo-source.json').read_text())
        for path, expected in manifest['files'].items():
            p = source / path
            if not p.is_file() or p.is_symlink() or sha(p) != expected: raise RuntimeError('Gufo source drift: ' + path)
        result['gufo_regular_files_verified'] = len(manifest['files'])
        build = str(base/'adapter-check')
        run(['cmake', '-S', str(ROOT), '-B', build, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Debug', '-DLIE_GUFO_HEADER_CHECK=ON'])
        run(['cmake', '--build', build, '--target', 'lie_gufo_header_check', '-j2'])
        run(['git', 'diff', '--check'])
        run(['git', 'diff', '--cached', '--check'])
        result['promtool_available'] = bool(__import__('shutil').which('promtool'))
        result['inputs_unchanged'] = before == inputs()
        if not result['inputs_unchanged']: raise RuntimeError('source changed during verification')
        result['binaries'] = {str(p.relative_to(ROOT)):sha(p) for directory in ('debug','clang','sanitize')
                              for name in ('synapse-lie-server','synapse-lie-monitor','test-flow','test-metrics','test-prometheus','test-executor-abi','test-chat','test-worker','test-worker-timings','test-synthetic-server','test-synthetic-bench')
                              if (p := base / directory / name).is_file()}
        result['transitional_adapter_permitted'] = True
        result['inference_adapter_linked'] = False
        result['autonomous_inference_backend_implemented'] = False
        result['reactive_pure_inference_measured'] = False
        result['synthetic_executor_only'] = True
        result['http_flow_worker_integrated'] = True
        result['state'] = 'CPU_RUNTIME_HTTP_SSE_SYNTHETIC_PASS_GUFO_HEADER_CHECK_ONLY_NO_MODEL_EXECUTION'
    except Exception as ex:
        result['state'] = 'FAILED'; result['error'] = repr(ex); raise
    finally:
        result['finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat(); save()
    print(json.dumps({k:v for k,v in result.items() if k not in ('commands','binaries')}, indent=2))


if __name__ == '__main__': main()
