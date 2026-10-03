#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""One-shot leased simplified benchmark supervisor. No builds, downloads, tuning or retries.
Requires a fresh operator-authorized manifest and private, unused run directory.
Shares only read-only utility functions with the retained original-model runner.
"""
import fcntl
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import resource
import re
import runpy
import signal
import stat
import statistics
import subprocess
import sys
import threading
import time

H = runpy.run_path(str(Path(__file__).with_name('smoke-model.py')))
now, sha, ticks = (H[x] for x in ('now', 'sha', 'ticks'))


def read_power_settings(paths):
    observed = {}
    for p in paths:
        try:
            observed[str(p)] = {'value': p.read_text().strip(), 'error': None}
        except OSError as ex:
            # Optional telemetry, not an admission control. Never invent a value.
            observed[str(p)] = {'value': None, 'error': {'type': type(ex).__name__, 'errno': ex.errno}}
    return observed


REPORT = runpy.run_path(str(Path(__file__).with_name("bench-report.py")))
BENCH_PASS = 'SIMPLIFIED_BENCHMARK_PASS_NOT_INDEPENDENT_QUALIFICATION'
HTTP_SSD_PASS = 'HTTP_SSD_PASS_NOT_INDEPENDENT_QUALIFICATION'


def temperatures(root=Path('/sys/class/hwmon'), ceiling=85, cpuinfo=Path('/proc/cpuinfo'), observe_cpu_gpu=False):
    if type(ceiling) not in (int,float) or not math.isfinite(ceiling) or not 30<=ceiling<=98:
        raise ValueError('invalid thermal ceiling')
    if type(observe_cpu_gpu) is not bool:
        raise ValueError('invalid thermal observation policy')
    if (ceiling>85 or observe_cpu_gpu) and 'ryzen ai max+ 395' not in cpuinfo.read_text().lower():
        raise ValueError('raised thermal ceiling requires the qualified Strix Halo 395 host')
    rows=[]
    for device in sorted(root.glob('hwmon*')):
        name=(device/'name').read_text().strip()
        if name not in ('k10temp','coretemp','amdgpu','nvme'):continue
        for path in sorted(device.glob('temp*_input')):
            limit=min(ceiling,85) if name=='nvme' else None if observe_cpu_gpu else ceiling
            for suffix in ('max','crit'):
                bound=path.with_name(path.name[:-6]+'_'+suffix)
                if bound.exists():
                    value=int(bound.read_text())/1000
                    if 30<=value<=150:limit=value if limit is None else min(limit,value)
            value=int(path.read_text())/1000
            if not -40<=value<=150:raise ValueError('invalid temperature sensor')
            rows.append({'name':name,'path':str(path),'value_c':value,'limit_c':limit,
                         'policy':'hardware-bounds-only' if observe_cpu_gpu and name!='nvme' else 'operating-ceiling'})
    if not any(r['name'] in ('k10temp','coretemp') for r in rows):raise ValueError('CPU temperature unavailable')
    return rows


def require_cool(rows):
    if any(r['limit_c'] is not None and r['value_c']>=r['limit_c'] for r in rows):raise RuntimeError('thermal limit')


def private_directory(path):
    """Open an existing private store without following any path symlink."""
    path=Path(path)
    if not path.is_absolute() or any(p in ('.','..') for p in path.parts):raise ValueError('absolute canonical store path required')
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try:
        for part in path.parts[1:]:
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
            os.close(fd);fd=child
        s=os.fstat(fd)
        if s.st_uid!=os.geteuid() or stat.S_IMODE(s.st_mode)!=0o700:raise ValueError('store must be owned and mode 0700')
        return fd
    except BaseException:
        os.close(fd);raise


def ssd_inventory(path,check_thermal=lambda:None):
    """Full checkpoint hashes under the campaign leases; never model hashes."""
    fd=private_directory(path);entries={}
    try:
        names=os.listdir(fd)
        if len(names)>65537:raise ValueError('SSD qualification inventory entry limit')
        for name in sorted(names):
            if name!='.lie-prefix.lock' and not re.fullmatch(r'(?:[0-9a-f]{64}\.lie|[0-9a-f]{40}\.kv)',name):
                raise ValueError('uncommitted or unknown SSD entry')
            entry=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,dir_fd=fd)
            with os.fdopen(entry,'rb') as f:
                before=os.fstat(f.fileno())
                if not stat.S_ISREG(before.st_mode) or before.st_uid!=os.geteuid() or before.st_nlink!=1 or stat.S_IMODE(before.st_mode)!=0o600:
                    raise ValueError('unsafe SSD entry')
                if name=='.lie-prefix.lock':continue
                digest=hashlib.sha256()
                while chunk:=f.read(8*1024*1024):
                    check_thermal();digest.update(chunk)
                after=os.fstat(f.fileno());live=os.stat(name,dir_fd=fd,follow_symlinks=False)
                fields=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
                if fields(before)!=fields(after) or fields(after)!=fields(live):raise ValueError('SSD inventory race')
                entries[name]={'bytes':after.st_size,'sha256':digest.hexdigest()}
        return entries
    finally:os.close(fd)


def bind_ssd(args,run,manifest,check_thermal=lambda:None):
    """Bind new stores or sealed preceding sibling stores; called inside leases."""
    options=dict(zip(args[::2],args[1::2]));declared=manifest.get('ssd_store')
    keys=('--prefix-ssd-dir','--prefix-ssd-quota-mib','--prefix-ssd-staging-mib')
    present=[k in options for k in keys]
    if not any(present):
        if declared is not None or '--state-ssd-mode' in options:raise ValueError('SSD manifest/options mismatch')
        return args,None
    if not all(present) or not isinstance(declared,dict) or options.get('--suite') not in ('core','state','http-ssd'):
        raise ValueError('complete explicit SSD declaration required')
    if declared.get('full_model_hash_authorized') is not True or declared.get('checkpoint_hash_authorized') is not True:
        raise ValueError('SSD full-content hashing admission required')
    if options[keys[0]]!='prefix-store':raise ValueError('SSD directory must use bound prefix-store name')
    budgets=[]
    for flag,field in zip(keys[1:],('quota_bytes','staging_bytes')):
        value=options[flag]
        if not value.isascii() or not value.isdecimal() or not 0<int(value)<=1048576:raise ValueError('invalid SSD budget')
        n=int(value)*1024**2
        if type(declared.get(field)) is not int or declared[field]!=n:raise ValueError('SSD budget declaration mismatch')
        budgets.append(n)
    if options['--suite'] in ('core','http-ssd'):
        ram=options.get('--prefix-cache-mib','4096')
        if not ram.isascii() or not ram.isdecimal() or int(ram)>1048576:raise ValueError('invalid RAM reserve')
        minimum=int(ram)*1024**2
    else:
        # State harness: 17 full-vocabulary rows plus one row and prompt IDs,
        # bounded by the public harness limits (not a total process-fit claim).
        minimum=80*1024**2
    reserve=manifest.get('ram_cache_reserve_bytes',0)
    if type(reserve) is not int or reserve<minimum:raise ValueError('SSD campaign RAM reserve is incomplete')
    mode=declared.get('mode');run=Path(run).resolve()
    if options['--suite']=='state' and options.get('--state-ssd-mode')!=('write' if mode=='create' else 'read'):
        raise ValueError('state SSD mode mismatch')
    if options['--suite']=='http-ssd' and options.get('--phase')!=('write' if mode=='create' else 'read'):
        raise ValueError('HTTP SSD mode mismatch')
    if mode=='create':
        if 'source_run' in declared or 'source_result_sha256' in declared:raise ValueError('new SSD store cannot have a source')
        path=run/'prefix-store'
        if os.path.lexists(path):raise ValueError('new SSD store already exists')
        before={}
    elif mode=='reuse':
        name=declared.get('source_run')
        if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*',name) or name==run.name:
            raise ValueError('SSD source must be a preceding sibling run')
        source=run.parent/name
        if source.resolve()!=source:raise ValueError('SSD source symlink')
        receipt=source/'results/result.json'
        if sha(receipt)!=declared.get('source_result_sha256'):raise ValueError('SSD source receipt identity mismatch')
        prior=json.loads(receipt.read_text());path=source/'prefix-store'
        required_state=HTTP_SSD_PASS if options['--suite']=='http-ssd' else BENCH_PASS
        if prior.get('state')!=required_state or prior.get('child_exit_code')!=0 or prior.get('ssd_store',{}).get('path')!=str(path):
            raise ValueError('SSD source was not a completed store producer')
        if prior.get('ssd_store',{}).get('mode')!='create':raise ValueError('SSD reuse must bind the original producer')
        if prior.get('ssd_store',{}).get('quota_bytes')!=budgets[0]:raise ValueError('SSD source quota mismatch')
        before=ssd_inventory(path,check_thermal)
        if not before or before!=prior.get('ssd_after'):raise ValueError('SSD checkpoint preservation mismatch')
    else:raise ValueError('invalid SSD campaign mode')
    parent=path.parent;space=os.statvfs(parent)
    free=space.f_bavail*space.f_frsize
    if free<budgets[0]:raise ValueError('SSD free-space reserve below explicit quota')
    result=list(args);result[result.index(keys[0])+1]=str(path)
    return result,{'path':str(path),'mode':mode,'quota_bytes':budgets[0],'staging_bytes':budgets[1],
                   'before':before,'free_bytes':free,'os_file_cache':'uncontrolled; identity/inventory hashing warms file cache'}


def validate_args(args):
    allowed={'--suite','--sizes','--depths','--users','--pp','--tg','--warmups','--repetitions','--execution'}
    if not isinstance(args,list) or len(args)%2 or any(type(x) is not str for x in args):
        raise ValueError('invalid declared benchmark arguments')
    keys=args[::2]
    options=dict(zip(keys,args[1::2]))
    if options.get('--suite')=='core':
        allowed={'--suite','--users','--tg','--warmups','--repetitions',
                 '--context','--chunk','--timeout-ms','--prompt-file','--tokens-file','--prefix-cache-mib',
                 '--cache-policy','--cache-text-prefix','--cache-capture-finish','--cache-min-tokens',
                 '--cache-cold-max-tokens','--cache-continued-tokens','--cache-trim-tokens','--cache-align-tokens'}
    if options.get('--suite')=='state':
        allowed={'--suite','--context','--chunk','--pp','--tokens-file','--capture-decode'}
        allowed.add('--state-ssd-mode')
    if options.get('--suite')=='http-ssd':
        allowed={'--suite','--cases-file','--context','--chunk','--users','--phase','--repetitions',
                 '--timeout-ms','--prefix-cache-mib','--overlap','--slow-client'}
    if options.get('--suite') in ('core','state','http-ssd'):
        allowed.update(('--prefix-ssd-dir','--prefix-ssd-quota-mib','--prefix-ssd-staging-mib'))
    if len(set(keys))!=len(keys) or any(k not in allowed for k in keys):
        raise ValueError('unapproved/duplicate benchmark option')
    if not args or '--suite' not in keys:
        raise ValueError('explicit benchmark suite required')
    return args


def bind_args(args, run, manifest):
    """Bind a core input to one immutable staged file, never an external path."""
    args=validate_args(args)
    options=dict(zip(args[::2],args[1::2]))
    if options['--suite'] not in ('core','state','http-ssd'):
        if manifest.get('benchmark_input') is not None:
            raise ValueError('input manifest only applies to core suite')
        return args
    keys=[k for k in (('--cases-file',) if options['--suite']=='http-ssd' else ('--prompt-file','--tokens-file')) if k in options]
    declared=manifest.get('benchmark_input')
    if len(keys)!=1 or not isinstance(declared,dict):
        raise ValueError('one bound core input required')
    name=options[keys[0]]
    if not name or name in ('.','..') or Path(name).name!=name or name.startswith('-'):
        raise ValueError('core input must be a staged basename')
    if declared.get('path')!=name or type(declared.get('bytes')) is not int or not 0<declared['bytes']<=8*1024*1024:
        raise ValueError('core input declaration mismatch')
    if manifest.get('files',{}).get(name)!=declared.get('sha256') or not isinstance(declared.get('sha256'),str):
        raise ValueError('core input missing from file identities')
    fd=os.open(Path(run)/name,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as f:
        info=os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size!=declared['bytes']:
            raise ValueError('core input size/type mismatch')
        data=f.read(8*1024*1024+1)
    import hashlib
    if len(data)!=declared['bytes'] or hashlib.sha256(data).hexdigest()!=declared['sha256']:
        raise ValueError('core input content mismatch')
    result=list(args);result[result.index(keys[0])+1]=str(Path(run).resolve()/name)
    return result


def http_ssd_plan(args, run, manifest):
    """Validate the HTTP profile before model open; bound inputs/store come first."""
    validate_args(args); options=dict(zip(args[::2],args[1::2]))
    required={'--suite','--cases-file','--context','--chunk','--users','--phase','--prefix-cache-mib',
              '--prefix-ssd-dir','--prefix-ssd-quota-mib','--prefix-ssd-staging-mib'}
    if not required <= options.keys() or options['--suite']!='http-ssd':
        raise ValueError('incomplete HTTP SSD profile')
    def integer(flag, low, high, default=None):
        value=options.get(flag,default)
        if not isinstance(value,str) or not value.isascii() or not value.isdecimal() or not low<=int(value)<=high:
            raise ValueError('invalid HTTP SSD option: '+flag)
        return int(value)
    context=integer('--context',128,262144);chunk=integer('--chunk',1,min(context,65535))
    integer('--users',2,2);integer('--prefix-cache-mib',0,0)
    integer('--prefix-ssd-quota-mib',1,1048576);integer('--prefix-ssd-staging-mib',1,1048576)
    repeats=integer('--repetitions',1,100,'3');timeout=integer('--timeout-ms',1000,1800000,'600000')
    overlap=integer('--overlap',0,1,'0');slow=integer('--slow-client',0,1,'0')
    phase=options['--phase']
    if phase not in ('write','read') or (phase=='write' and (overlap or slow)):
        raise ValueError('scheduling checks require a restarted reader')
    model=manifest.get('http_model_id'); provider=manifest['build_info']['engine']
    if not isinstance(model,str) or not model or len(model)>128:raise ValueError('explicit HTTP model ID required')
    api,management=H['serving_ports'](dict(manifest,api_port=manifest.get('api_port',8000)))
    out=Path(run)/'results'
    server=['--host','127.0.0.1','--management-host','127.0.0.1','--port',str(api),'--management-port',str(management),
            '--model-id',model,'--context',str(context),'--prefill-chunk',str(chunk),'--max-active','2',
            '--request-timeout-ms',str(timeout),'--prefix-cache-mib','0']
    for flag in ('--prefix-ssd-dir','--prefix-ssd-quota-mib','--prefix-ssd-staging-mib'):server += [flag,options[flag]]
    client=['--url',f'http://127.0.0.1:{api}/v1','--management-url',f'http://127.0.0.1:{management}',
            '--model',model,'--provider',provider,'--cases',options['--cases-file'],
            '--output',str(out/'http.jsonl'),'--phase',phase,'--chunk',str(chunk),
            '--repetitions',str(repeats),'--timeout',str(timeout/1000)]
    if overlap:client += ['--overlap']
    if slow:client += ['--slow-client']
    if phase=='read':
        source=manifest['ssd_store']['source_run']
        if not isinstance(source,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*',source):raise ValueError('invalid reference source')
        producer=Path(run).parent/source/'results';receipt=producer/'result.json'
        if sha(receipt)!=manifest['ssd_store']['source_result_sha256']:raise ValueError('HTTP source receipt drift')
        prior=json.loads(receipt.read_text());reference=producer/'http.jsonl.summary.json'
        if prior.get('state')!=HTTP_SSD_PASS or sha(reference)!=prior.get('http_summary_sha256'):
            raise ValueError('HTTP source summary identity mismatch')
        client += ['--reference',str(reference)]
    return dict(server=server,client=client,ports=[api,management],readiness_timeout=timeout/1000)


def http_ssd_check(plan, helper, check):
    """Run clients in one supervisor thread; the owned server alone uses the GPU."""
    deadline=time.monotonic()+plan['readiness_timeout']
    while True:
        check()
        try:
            health=H['http'](plan['ports'][1],'/actuator/health/readiness',timeout=2)
            if health['status']==200:break
        except (OSError,http.client.HTTPException):pass
        if time.monotonic()>=deadline:raise RuntimeError('HTTP model readiness deadline')
        time.sleep(.1)
    result=helper['main'](plan['client'],check=check)
    if result!=0:raise RuntimeError('HTTP SSD client failed')


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: run-bench.py PRIVATE-RUN-DIRECTORY')
    run = Path(sys.argv[1]).resolve()
    m = json.loads((run / 'manifest.json').read_text())
    if m['authorization']['kind'] != 'operator-one-shot-window' or not m['authorization']['gpu_test_authorized']:
        raise SystemExit('Fresh operator authorization required')
    out = run / 'results'
    out.mkdir()
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    r = {'state': 'PREFLIGHT', 'started_at': now(), 'manifest_sha256': sha(run / 'manifest.json'),
         'runner_sha256': sha(__file__), 'supervisor_pid': os.getpid(), 'supervisor_start_ticks': ticks(os.getpid()),
         'authorization': m['authorization'], 'ds4_ack_claimed': False, 'model_attempted': False,
         'commands': [], 'locks': []}
    locks, child, registered = [], None, False
    checker=None; checker_result={}; checker_done=threading.Event(); http_plan=None
    interrupted = False

    def save():
        tmp = out / 'result.tmp'
        tmp.write_text(json.dumps(r, indent=2) + '\n')
        tmp.replace(out / 'result.json')

    def stop(signum, frame):
        nonlocal interrupted
        interrupted = True
        r['received_signal'] = signum
        if child is not None and child.poll() is None:
            child.terminate()  # The C harness latches stop and retires completed work.

    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, stop)

    def register(event):
        row = {'owner': 'synapse-lie', 'event': event, 'at': now(), 'run': str(run),
               'pid': os.getpid(), 'start_ticks': r['supervisor_start_ticks'], 'state': r['state'],
               'authorization_kind': m['authorization']['kind'], 'source_commit': m['source_commit'],
               'model': m['models'][0]['path'], 'command': r.get('argv'), 'exit_code': r.get('child_exit_code')}
        fd = os.open('/tmp/synapse-lie-ds4-coordination/runs.jsonl', os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            payload = (json.dumps(row) + '\n').encode()
            if os.write(fd, payload) != len(payload):
                raise RuntimeError('incomplete register write')
            os.fsync(fd)
        finally:
            os.close(fd)

    def command(argv, env):
        p = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=30)
        r['commands'].append({'argv': argv, 'exit_code': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr})
        save()
        if p.returncode:
            raise RuntimeError('preflight command failed')
        return p.stdout

    def check_thermal():
        rows=temperatures(ceiling=m.get('thermal_limit_c',85),observe_cpu_gpu=m.get('thermal_observe_cpu_gpu',False))
        r['last_temperatures']=rows
        require_cool(rows)
        return rows

    try:
        for name in m['lock_order']:
            p = Path(name)
            fd = os.open(p, os.O_RDONLY | os.O_CLOEXEC)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BaseException:
                os.close(fd)
                raise
            locks.append(fd)
            s, live = os.fstat(fd), p.stat()
            if (s.st_dev, s.st_ino) != (live.st_dev, live.st_ino):
                raise RuntimeError('lock identity race')
            if m.get('lock_identities') and m['lock_identities'].get(name) != [s.st_dev,s.st_ino]:
                raise RuntimeError('unexpected established lease identity')
            r['locks'].append({'path': name, 'device': s.st_dev, 'inode': s.st_ino})
        r['models_before'] = [H['model_stat'](x) for x in m['models']]
        r['preflight_memory'] = H['memory']()
        r['preflight_kfd'] = sorted(H['kfd']())
        baseline_dri, denied = H['dri_clients']()
        r['preflight_dri'] = {'pids': sorted(baseline_dri), 'permission_denied': denied}
        if r['preflight_kfd']:
            raise RuntimeError('foreign KFD client before launch')
        trunk = sum(x['bytes'] for x in m['models'] if '/mtp-' not in x['path'])
        if r['preflight_memory']['MemAvailable'] <= trunk:
            raise RuntimeError('available RAM below trunk-size estimate, not OOM/fit evidence')
        reserve=m.get('ram_cache_reserve_bytes',0)
        if type(reserve) is not int or reserve<0 or r['preflight_memory']['MemAvailable']<=trunk+reserve:
            raise RuntimeError('RAM cache reserve admission failed; no memory-fit claim')
        for name, expected in m['files'].items():
            if sha(run / name) != expected:
                raise RuntimeError('staged file identity mismatch: ' + name)
        r['preflight_temperatures']=check_thermal()
        benchmark_args=bind_args(m['benchmark_args'],run,m)
        benchmark_args,r['ssd_store']=bind_ssd(benchmark_args,run,m,check_thermal)
        selected_suite = dict(zip(benchmark_args[::2],benchmark_args[1::2]))['--suite']
        binary=run/('synapse-lie-server' if selected_suite=='http-ssd' else 'synapse-lie-bench')
        if binary.name not in m['files']:raise ValueError('binary missing from staged identities')
        if selected_suite=='http-ssd':
            if 'bench-ssd-http.py' not in m['files']:raise ValueError('HTTP checker identity missing')
            http_plan=http_ssd_plan(benchmark_args,run,m);r['http_plan']=http_plan
            http_helper=runpy.run_path(str(run/'bench-ssd-http.py'))
            cases=http_helper['validate_cases'](json.loads(Path(dict(zip(benchmark_args[::2],benchmark_args[1::2]))['--cases-file']).read_text()))
            r['http_cases_sha256']=http_helper['digest'](cases)
            H['probe_ports'](http_plan['ports'])
        staging=r['ssd_store']['staging_bytes'] if r['ssd_store'] else 0
        # The dynamic SSD index is a separate pool, capped by staging size.
        # RAM entry records use at most another 16 MiB. Rendering offsets/text
        # are bounded per job in addition to normalized request storage.
        options=dict(zip(benchmark_args[::2],benchmark_args[1::2]))
        rows=int(options.get('--users','1'))
        policy_reserve=staging+16*1024**2+rows*(8*1024**2+(int(options.get('--context','262144'))+1)*8)
        r['cache_policy_extra_reserve_bytes']=policy_reserve
        if H['memory']()['MemAvailable']<=trunk+reserve+staging+policy_reserve:
            raise RuntimeError('SSD staging/index plus RAM reserve admission failed; no fit claim')
        env = {k: v for k, v in os.environ.items() if not k.startswith(('GUFO_', 'DS4_', 'HIP_', 'ROCR_', 'HSA_', 'CUDA_')) and k not in ('LD_PRELOAD', 'LD_LIBRARY_PATH')}
        for key, name in [('HOME', 'home'), ('XDG_CACHE_HOME', 'cache'), ('TMPDIR', 'tmp')]:
            p = run / name
            p.mkdir()
            env[key] = str(p)
        env.update(LC_ALL='C', LD_BIND_NOW='1', ROCR_VISIBLE_DEVICES='0', HIP_VISIBLE_DEVICES='0')
        masked = dict(env, ROCR_VISIBLE_DEVICES='-1', HIP_VISIBLE_DEVICES='-1')
        info = json.loads(command([str(binary), *(['--suite',selected_suite] if selected_suite in ('core','state') else []), '--build-info'], masked))
        synthetic=info.get('synthetic',False) if http_plan else info['synthetic']
        if info != m['build_info'] or synthetic or info['ownership'] != 'delegated':
            raise RuntimeError('provider/build identity mismatch')
        command(['uname', '-srmo'], masked)
        command(['readelf', '-d', str(binary)], masked)
        linked = command(['ldd', str(binary)], masked)
        if 'not found' in linked:
            raise RuntimeError('unresolved DSO')
        r['dsos'] = {}
        for word in linked.split():
            if word.startswith('/') and Path(word).is_file():
                p = Path(word).resolve()
                if not str(p).startswith(('/usr/', '/opt/rocm/')):
                    raise RuntimeError('unapproved DSO path')
                r['dsos'][str(p)] = sha(p)
        paths = list(Path('/sys/devices/system/cpu/cpufreq').glob('policy*/*'))
        paths += [Path('/sys/class/drm/card1/device') / x for x in ('power_dpm_force_performance_level', 'pp_power_profile_mode')]
        r['power_settings'] = read_power_settings(p for p in paths if p.name in (
            'scaling_governor', 'energy_performance_preference', 'power_dpm_force_performance_level', 'pp_power_profile_mode'))
        if interrupted or H['kfd']():
            raise RuntimeError('admission interrupted or foreign client appeared')
        check_thermal()
        r['argv'] = [str(binary), '--model', m['models'][0]['path']]
        r['argv'] += http_plan['server'] if http_plan else ['--output',str(out/'measurements.jsonl'),*benchmark_args]
        register('start')
        registered = True
        r['state'] = 'BENCHMARK_RUNNING'
        r['model_attempted'] = True
        with (out / 'stdout.log').open('xb') as log, (out / 'stderr.log').open('xb') as err:
            child = subprocess.Popen(r['argv'], cwd=run, env=env, stdout=log, stderr=err, start_new_session=True)
        r['child_pid'], r['child_start_ticks'] = child.pid, ticks(child.pid)
        if http_plan:
            def live():
                if interrupted or child.poll() is not None:raise RuntimeError('owned HTTP server retired/interrupted')
            def check_http():
                try:
                    http_ssd_check(http_plan,http_helper,live);checker_result['exit_code']=0
                except BaseException as ex:
                    checker_result.update(exit_code=1,error=repr(ex))
                finally:checker_done.set()
            checker=threading.Thread(target=check_http,name='lie-http-ssd-checker');checker.start()
        save()
        deadline = time.monotonic() + 3600
        with (out / 'telemetry.jsonl').open('x') as log:
            while child.poll() is None:
                kfd = H['kfd']()
                drm, denied = H['dri_clients']()
                foreign = (kfd - {child.pid}) | (drm - baseline_dri - {child.pid})
                thermal=temperatures(ceiling=m.get('thermal_limit_c',85),observe_cpu_gpu=m.get('thermal_observe_cpu_gpu',False));r['last_temperatures']=thermal
                log.write(json.dumps({'at': now(), 'memory': H['memory'](), 'gpu': H['gpu'](),
                                      'kfd': sorted(kfd), 'dri': sorted(drm), 'dri_permission_denied': denied,
                                      'temperatures':thermal,'process': H['process_status'](child.pid)}) + '\n')
                log.flush()
                if any(t['limit_c'] is not None and t['value_c']>=t['limit_c'] for t in thermal):
                    r['thermal_stop']=True
                    raise RuntimeError('thermal limit; retiring owned child')
                if foreign:
                    r['foreign_gpu_clients'] = sorted(foreign)
                    raise RuntimeError('foreign GPU client detected')
                if interrupted or time.monotonic() > deadline:
                    raise RuntimeError('benchmark interrupted/deadline')
                if http_plan and checker_done.is_set():
                    checker.join();r['http_checker']=checker_result
                    child.terminate();child.wait(timeout=120)
                    if checker_result['exit_code']!=0:raise RuntimeError('HTTP SSD checks failed; retained request evidence')
                    break
                time.sleep(1)
        r['child_exit_code'] = child.returncode
        if child.returncode:
            raise RuntimeError('benchmark failed; see retained measurements/stderr')
        if http_plan:
            if not checker_done.is_set() or checker_result.get('exit_code')!=0:raise RuntimeError('HTTP server exited before checks completed')
            summary=out/'http.jsonl.summary.json';r['summary']=json.loads(summary.read_text())
            if r['summary']['state']!='PASS':raise RuntimeError('incomplete HTTP summary')
            r['http_summary_sha256']=sha(summary);r['measurements_sha256']=sha(out/'http.jsonl')
        else:
            r['summary'] = REPORT['read_result'](out / 'measurements.jsonl')
            r['measurements_sha256'] = sha(out / 'measurements.jsonl')
        if r['ssd_store']:
            r['ssd_after']=ssd_inventory(Path(r['ssd_store']['path']),check_thermal)
        r['state'] = HTTP_SSD_PASS if http_plan else BENCH_PASS
    except BaseException as ex:
        r['state'], r['error'] = 'FAILED', repr(ex)
    finally:
        if child is not None:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5 if r.get('thermal_stop') else 120)
                except subprocess.TimeoutExpired:
                    r['forced_owned_child_kill'] = True
                    child.kill()
                    child.wait()
            r['child_exit_code'] = child.returncode
        if checker:
            checker.join(timeout=30);r['http_checker']=checker_result
            r['http_checker_retired']=not checker.is_alive()
            if checker.is_alive():r['state'],r['closure_error']='FAILED','HTTP checker failed to retire'
        try:
            r['models_after'] = [H['model_stat'](x) for x in m['models']]
            r['files_unchanged'] = all(sha(run / name) == expected for name, expected in m['files'].items())
            r['postflight_kfd'], r['postflight_memory'], r['postflight_gpu'] = sorted(H['kfd']()), H['memory'](), H['gpu']()
            if not r['files_unchanged'] or (child and child.pid in r['postflight_kfd']) or interrupted:
                raise RuntimeError('retirement/preservation/interruption failure')
        except Exception as ex:
            r['state'], r['closure_error'] = 'FAILED', repr(ex)
        r['finished_at'] = now()
        save()
        try:
            if registered:
                register('end')
        finally:
            for fd in reversed(locks):
                os.close(fd)
    print(json.dumps(r, indent=2), flush=True)
    return 0 if r['state'] in (BENCH_PASS,HTTP_SSD_PASS) else 1


if __name__ == '__main__':
    raise SystemExit(main())
