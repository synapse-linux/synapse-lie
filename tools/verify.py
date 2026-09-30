#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Local CPU-only verification with actual subprocess return codes and source hashes."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
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
        index = len(result['commands']); start = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with (out / f'{index:02}.log').open('wb') as log:
            proc = subprocess.run(argv, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=120)
        result['commands'].append({'argv':argv, 'start':start, 'exit_code':proc.returncode, 'log':f'{index:02}.log'})
        save()
        if proc.returncode: raise RuntimeError(f'command {index} exit {proc.returncode}')
    save()
    try:
        for name, options in [('debug', []), ('clang', ['-DCMAKE_C_COMPILER=clang']), ('sanitize', ['-DLIE_SANITIZERS=ON'])]:
            build = str(ROOT / 'build' / name)
            run(['cmake', '-S', str(ROOT), '-B', build, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Debug', *options])
            run(['cmake', '--build', build, '-j2'])
            env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1')
            run(['ctest', '--test-dir', build, '--output-on-failure', '-V'], env)
        source = ROOT / '.deps/gufo-f783fedb'
        manifest = json.loads((ROOT / 'third_party/gufo-source.json').read_text())
        for path, expected in manifest['files'].items():
            p = source / path
            if not p.is_file() or p.is_symlink() or sha(p) != expected: raise RuntimeError('Gufo source drift: ' + path)
        result['gufo_regular_files_verified'] = len(manifest['files'])
        build = str(ROOT / 'build/adapter-check')
        run(['cmake', '-S', str(ROOT), '-B', build, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Debug', '-DLIE_GUFO_HEADER_CHECK=ON'])
        run(['cmake', '--build', build, '--target', 'lie_gufo_header_check', '-j2'])
        run(['git', 'diff', '--check'])
        run(['git', 'diff', '--cached', '--check'])
        result['promtool_available'] = bool(__import__('shutil').which('promtool'))
        result['inputs_unchanged'] = before == inputs()
        if not result['inputs_unchanged']: raise RuntimeError('source changed during verification')
        result['binaries'] = {str(p.relative_to(ROOT)):sha(p) for directory in ('debug','clang','sanitize')
                              for name in ('synapse-lie-server','synapse-lie-monitor','test-flow','test-metrics','test-prometheus','test-executor-abi')
                              if (p := ROOT / 'build' / directory / name).is_file()}
        result['state'] = 'CPU_CONTROL_PLANE_AND_REACTIVE_FLOW_PASS_ADAPTER_COMPILED_NOT_LINKED_NOT_INFERENCE'
    except Exception as ex:
        result['state'] = 'FAILED'; result['error'] = repr(ex); raise
    finally:
        result['finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat(); save()
    print(json.dumps({k:v for k,v in result.items() if k not in ('commands','binaries')}, indent=2))


if __name__ == '__main__': main()
