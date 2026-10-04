#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bounded .161 inventory, CPU fixtures or linked no-model checks. No GPU/service operations."""
import argparse
import base64
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SSH = ['ssh', '-F', '/dev/null', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', 'pop@192.168.5.161']
FILES = ('tools/strix-point-inventory.py', 'tools/thermal-run.py', 'tools/gufo_build_policy.py',
         'tests/test_gufo_target.py', 'tests/test_gufo_arch.c', 'adapters/gufo_arch.h',
         'tests/test_gufo_device.cpp', 'tests/hip_stub/hip/hip_runtime_api.h',
         'adapters/gufo_device.cpp', 'include/lie/executor.h')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('inventory', 'cpu-tests', 'core-tests', 'runtime-check', 'probe-check', 'probe-tests'))
    parser.add_argument('label')
    parser.add_argument('--bundle',type=Path,default=Path('build/point-runtime-bundle'))
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z0-9-]{1,48}', args.label):
        parser.error('Invalid exclusive evidence label')
    out = ROOT/'evidence'/args.label
    out.mkdir(parents=True, exist_ok=False)
    source = {name: (ROOT/name).read_bytes() for name in FILES}
    if args.action == 'probe-tests':
        for name in ('tools/hip-probe.c', 'tests/hip_probe_stub.c', 'tests/test_hip_probe.py',
                     'tests/hip_stub/rocblas/rocblas.h'):
            source[name] = (ROOT/name).read_bytes()
    if args.action in ('runtime-check', 'probe-check'):
        bundle=(ROOT/args.bundle).resolve()
        if not bundle.is_relative_to((ROOT/'build').resolve()):
            parser.error('Runtime bundle must be inside this worktree build directory')
        binaries = ('lie-hip-probe',) if args.action == 'probe-check' else ('synapse-lie-server','synapse-lie-bench','synapse-lie-bench-gufo-reference')
        for name in binaries:
            source['runtime/bin/'+name]=(bundle/name).read_bytes()
        for name in ('libllhttp.so.9.3','libdrm.so.2','libdrm_amdgpu.so.1','libpng16.so.16','libjpeg.so.8'):
            source['runtime/lib/'+name]=(Path('/usr/lib')/name).read_bytes()
        source['runtime/strip-receipt.json']=(bundle/'receipt.json').read_bytes()
        for row in json.loads(source['runtime/strip-receipt.json']):
            name=Path(row['argv'][-1]).name
            if row['exit_code'] or row['stripped_sha256']!=hashlib.sha256(source['runtime/bin/'+name]).hexdigest():
                raise ValueError('Runtime bundle differs from the strip receipt')
        source['runtime/system-packages.txt']=subprocess.check_output(['pacman','-Q','llhttp','libdrm','libpng','libjpeg-turbo'])
    if args.action == 'core-tests':
        for directory in ('src', 'include', 'tests'):
            for path in sorted((ROOT/directory).rglob('*')):
                if path.is_file() and path.suffix in ('.c', '.h', '.py'):
                    source[str(path.relative_to(ROOT))] = path.read_bytes()
        for name in ('CMakeLists.txt', 'cmake/hip-target.cmake'):
            source[name] = (ROOT/name).read_bytes()
    receipt = {'action': args.action, 'host': 'pop@192.168.5.161',
               'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'source_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in source.items()},
               'scope': 'No GPU, model payload, service mutation, package installation or remote GPU build'}
    runner=Path(__file__).read_bytes()
    receipt['runner_sha256']=hashlib.sha256(runner).hexdigest()
    (out/'runner.py').write_bytes(runner)
    if args.action == 'inventory':
        program = source['tools/strix-point-inventory.py'].decode()
    else:
        encoded = {name: base64.b64encode(data).decode() for name, data in source.items()}
        # Constant remote prefix and validated exclusive label; no arbitrary command input.
        program = '''import base64,json,os,pathlib,subprocess,sys
base=pathlib.Path('/home/pop/workspace/synapse-lie')
base.mkdir(parents=True,exist_ok=True)
if base.resolve()!=base or base.stat().st_uid!=os.getuid():
    raise SystemExit('Unsafe project staging directory')
'''
        program += 'root=base/'+repr(args.label)+'\nroot.mkdir()\nos.chdir(root)\nfiles='+repr(encoded)+'\n'
        program += 'action='+repr(args.action)+'\n'
        program += '''for name,data in files.items():
    path=root/name
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as output: output.write(base64.b64decode(data))
    if name.startswith('runtime/bin/'): path.chmod(0o700)
commands=[
 ('build-arch',['cc','-std=c17','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer','-Iadapters','tests/test_gufo_arch.c','-o','test-gufo-arch']),
 ('build-device',['c++','-std=c++17','-D_POSIX_C_SOURCE=200809L','-DLIE_HIP_ARCHITECTURE="gfx1150"','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer','-Itests/hip_stub','-Iinclude','-Iadapters','tests/test_gufo_device.cpp','adapters/gufo_device.cpp','-o','test-gufo-device']),
 ('test-arch',['./test-gufo-arch']), ('test-device',['./test-gufo-device']),
 ('test-receipt',['python3','-B','tests/test_gufo_target.py'])]
prefix=[]
if action in ('core-tests','runtime-check','probe-check','probe-tests'):
    commands=[('configure',['cmake','-S','.','-B','build','-G','Ninja','-DLIE_CORE_ONLY=ON','-DLIE_SANITIZERS=ON','-DLIE_HIP_ARCHITECTURE=gfx1150','-DCMAKE_BUILD_TYPE=Debug']),
              ('build',['cmake','--build','build','-j1']),
              ('test',['ctest','--test-dir','build','--output-on-failure','-V'])]
    # Existing Synapse builder derived from official binary packages. No install,
    # source/artifact import from another project, network, or device passthrough.
    prefix=['docker','run','--rm','--network','none','--read-only','--cap-drop','ALL',
            '--security-opt','no-new-privileges','--user',str(os.getuid())+':'+str(os.getgid()),
            '--pids-limit','128','--cpus','2','--memory','2g','--tmpfs','/tmp:rw,nosuid,size=64m',
            '--mount','type=bind,src='+str(root)+',dst=/work','--workdir','/work',
            '--mount','type=bind,src=/sys,dst=/sys,readonly',
            '--env','ASAN_OPTIONS=detect_leaks=1:halt_on_error=1','--env','UBSAN_OPTIONS=halt_on_error=1',
            '--entrypoint','/usr/bin/python3','sha256:29e3b2b4b984ddb2614068271b2967bdc941664690468390c907508b5da8c2ac']
    if action in ('runtime-check','probe-check'):
        # Reuse the existing target runtime read-only. Five official system DSOs
        # are private test artifacts; no package or service environment is changed.
        prefix[-1:-1]=['--mount','type=bind,src=/home/pop/.local/opt/rocm-7.2-root/opt/rocm-7.2.0,dst=/opt/rocm,readonly',
                       '--env','LD_LIBRARY_PATH=/work/runtime/lib:/opt/rocm/lib']
        commands=[('server-help',['./runtime/bin/synapse-lie-server','--help']),
                  ('bench-info',['./runtime/bin/synapse-lie-bench','--build-info']),
                  ('reference-info',['./runtime/bin/synapse-lie-bench-gufo-reference','--build-info'])]
        if action=='probe-check':
            commands=[('probe-help',['./runtime/bin/lie-hip-probe','--help'])]
    if action=='probe-tests':
        flags=['-D_POSIX_C_SOURCE=200809L','-DLIE_HIP_PROBE_SYNTHETIC=1','-DLIE_BUILD_ID="synthetic-probe"','-DLIE_HIP_ARCHITECTURE="gfx1150"',
               '-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',
               '-Itests/hip_stub','-Iinclude','-Iadapters']
        commands=[('compile-probe',['cc','-std=c17']+flags+['-c','tools/hip-probe.c','-o','probe.o']),
                  ('compile-stubs',['cc','-std=c17']+flags+['-c','tests/hip_probe_stub.c','-o','stub.o']),
                  ('link-fixture',['c++','-std=c++17']+flags+['adapters/gufo_device.cpp','probe.o','stub.o','-ljson-c','-lm','-o','test-hip-probe-fixture']),
                  ('test-probe',['python3','-B','tests/test_hip_probe.py','./test-hip-probe-fixture'])]
os.environ.update(ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
rows=[]
for label,command in commands:
    runner=prefix+['-B'] if prefix else ['python3','-B']
    run=subprocess.run(runner+['tools/thermal-run.py','--timeout','45','--output','evidence/'+label,'--']+command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    rows.append({'step':label,'exit_code':run.returncode,'guard_stdout':run.stdout})
    if run.returncode: break
artifacts={str(path.relative_to(root)):path.read_text() for path in sorted((root/'evidence').rglob('*')) if path.is_file()}
result={'scope':'LINKED_NO_MODEL_NOT_INFERENCE' if action in ('runtime-check','probe-check') else 'SYNTHETIC_CPU_NOT_INFERENCE','remote_root':str(root),'commands':rows,'artifacts':artifacts}
(root/'RESULT.json').write_text(json.dumps(result,indent=2)+'\\n')
print(json.dumps(result))
sys.exit(0 if len(rows)==len(commands) and all(r['exit_code']==0 for r in rows) else 1)
'''
    argv = SSH + ['python3 -']
    receipt['argv'] = argv
    receipt['remote_program_sha256']=hashlib.sha256(program.encode()).hexdigest()
    (out/'plan.json').write_text(json.dumps(receipt, indent=2)+'\n')
    try:
        run = subprocess.run(argv, input=program, text=True, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, timeout=300)
        (out/'stdout.log').write_text(run.stdout)
        (out/'stderr.log').write_text(run.stderr)
        receipt['exit_code'] = run.returncode
        if run.stdout:
            try:
                data = json.loads(run.stdout)
                (out/'remote-result.json').write_text(json.dumps(data, indent=2)+'\n')
                brief={k:v for k,v in data.items() if k not in ('artifacts', 'memory', 'topology', 'models', 'sensors')}
                if 'commands' in brief:
                    brief['commands']=[{'step':r['step'],'exit_code':r['exit_code']} for r in brief['commands']]
                print(json.dumps(brief))
            except json.JSONDecodeError:
                receipt['invalid_json'] = True
    except subprocess.TimeoutExpired as error:
        receipt.update(exit_code=124, error='SSH timeout; remote completion unconfirmed')
        for name, data in (('stdout.log', error.stdout), ('stderr.log', error.stderr)):
            (out/name).write_bytes(data or b'')
    (out/'result.json').write_text(json.dumps(receipt, indent=2)+'\n')
    raise SystemExit(receipt['exit_code'])

if __name__ == '__main__':
    main()
