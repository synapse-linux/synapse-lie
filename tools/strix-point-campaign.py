#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""One-shot .161 campaign under the operator's explicit llama stop/restore grant.
Remote entry point. Inputs/results live in an exclusive persistent run directory.
The opt-in ROCm 10 build is GPU-device-free but still requires the same lease.
No host install, tuning, foreign signals or automatic retries.
"""
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

BASE = Path('/home/pop/workspace/synapse-lie')
SERVICE = 'llama-router.service'
IMAGE = 'sha256:29e3b2b4b984ddb2614068271b2967bdc941664690468390c907508b5da8c2ac'
ROCM = '/home/pop/.local/opt/rocm-7.2-root/opt/rocm-7.2.0'
ROCM10_SOURCE = BASE/'rocm10-fedora-161'/'source'
BENCH_PROFILES = {
    # Same direct-executor workloads as docs/CONTEXT-COMPARISON.md on .157.
    'single': ('single', 'reactive', 1, 1, ('--depths', '0,4096,8192,12288,16384,32768,65536,131072')),
    'single-parity': ('single', 'reactive', 0, 1, ('--depths', '0,4096')),
    'fresh-128k': ('fresh', 'reactive', 0, 2, ('--sizes', '1500,8000,8192,32768,131072')),
    'fresh-256k': ('fresh', 'reactive', 0, 2, ('--sizes', '258794')),
    'multi': ('multi', 'reactive', 1, 3, ('--users', '1,2,4,6,8')),
    'multi-serial': ('multi', 'serial', 1, 3, ('--users', '1,2,4,6,8')),
    'memory': ('memory', 'reactive', 1, 1, ()),
    'loading': ('loading', 'reactive', 0, 1, ()),
}
THERMAL_OVERRIDE_QUOTE = ('la gpu arriva a 100 gradi senza problemi ed è importante '
                          'testare la sua capacità, non limitarsi a 85*')

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
def ticks(pid): return int(Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19])
def save(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, indent=2)+'\n')
    tmp.replace(path)
def checked_path(value):
    path = Path(value)
    if not path.is_absolute() or not path.is_relative_to(BASE) or path.resolve() != path:
        raise ValueError('Path must be persistent and private to this LIE checkout')
    if path.stat().st_uid != os.getuid(): raise ValueError('Unexpected path owner')
    return path
def observe(ceiling_c=85.0):
    result = {'at': now(), 'kfd': [], 'dri': [], 'denied_fd': 0, 'temperatures': [], 'memory': {}}
    # The kernel list supplements /proc when FD observations are denied.
    result['kernel_kfd'] = sorted(int(p.name) for p in Path('/sys/class/kfd/kfd/proc').iterdir() if p.name.isdecimal())
    for proc in Path('/proc').iterdir():
        if not proc.name.isdecimal(): continue
        try: fds = list((proc/'fd').iterdir())
        except FileNotFoundError: continue
        except PermissionError:
            result['denied_fd'] += 1
            continue
        devices = set()
        for fd in fds:
            try: device = os.readlink(fd)
            except OSError: continue
            if device == '/dev/kfd' or device.startswith('/dev/dri/'): devices.add(device)
        if devices:
            try:
                row = {'pid': int(proc.name), 'start_ticks': ticks(proc.name),
                       'cgroup': (proc/'cgroup').read_text(), 'devices': sorted(devices)}
            except FileNotFoundError: continue
            result['dri'].append(row)
            if '/dev/kfd' in devices: result['kfd'].append(row)
    for hw in sorted(Path('/sys/class/hwmon').glob('hwmon*')):
        name = (hw/'name').read_text().strip()
        if name not in ('k10temp', 'amdgpu', 'nvme'): continue
        for path in sorted(hw.glob('temp*_input')):
            value = int(path.read_text())/1000
            limit = ceiling_c
            for suffix in ('max', 'crit'):
                bound = path.with_name(path.name[:-6]+'_'+suffix)
                if bound.exists():
                    threshold = int(bound.read_text())/1000
                    if 30 <= threshold <= 150: limit = min(limit, threshold)
            if not -40 <= value <= 150: raise RuntimeError('Invalid temperature reading')
            result['temperatures'].append({'name': name, 'path': str(path), 'value_c': value, 'limit_c': limit})
    if not any(t['name'] == 'k10temp' for t in result['temperatures']):
        raise RuntimeError('Missing CPU temperature sensor')
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        if key in ('MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree'):
            result['memory'][key] = int(value.split()[0])*1024
    # Match the admitted render node; card numbering can change after reboot.
    device = Path('/sys/class/drm/renderD128/device')
    result['gpu'] = {}
    for name in ('gpu_busy_percent', 'mem_info_gtt_total', 'mem_info_gtt_used', 'mem_info_vram_total', 'mem_info_vram_used'):
        try: result['gpu'][name] = int((device/name).read_text())
        except (OSError, ValueError): result['gpu'][name] = None
    return result

class Campaign:
    def __init__(self, root, manifest):
        self.root, self.m = root, manifest
        ceiling = manifest.get('thermal_ceiling_c', 85)
        if type(ceiling) not in (int, float) or ceiling not in (85, 100):
            raise ValueError('Unsupported thermal ceiling')
        if ceiling == 100 and manifest.get('thermal_override_quote') != THERMAL_OVERRIDE_QUOTE:
            raise ValueError('Explicit operator 100 C thermal override required')
        self.thermal_ceiling_c = float(ceiling)
        self.r = {'state': 'PREFLIGHT', 'started_at': now(), 'pid': os.getpid(), 'start_ticks': ticks(os.getpid()),
                  'manifest_sha256': sha(root/'manifest.json'), 'runner_sha256': sha(__file__),
                  'authorization': manifest['authorization'], 'commands': [], 'container': None,
                  'thermal_ceiling_c': self.thermal_ceiling_c,
                  'model_attempted': False,
                  'service_restore_required': False, 'exit_code': 1}
        self.lock = None
        self.child = None
        self.interrupted = None
        self.cid = None
        self.baseline = set()
    def record(self): save(self.root/'result.json', self.r)
    def command(self, argv, check=True, timeout=30):
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        self.r['commands'].append({'argv': argv, 'exit_code': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr})
        self.record()
        if check and p.returncode: raise RuntimeError('Command failed: '+repr(argv))
        return p
    def image_and_rocm(self):
        stack = self.m.get('stack', 'rocm7.2-arch')
        if stack == 'rocm7.2-arch':
            if 'image' in self.m: raise ValueError('Legacy image is fixed')
            return IMAGE, ROCM
        if stack == 'rocm10-fedora43':
            image = self.m.get('image')
            if type(image) is not str or not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
                raise ValueError('ROCm 10 image must be pinned by local image ID')
            inspected = json.loads(self.command(['docker', 'image', 'inspect', image,
                '--format', '{{json .}}']).stdout)
            if inspected['Id'] != image or inspected['Architecture'] != 'amd64':
                raise ValueError('ROCm 10 image identity mismatch')
            return image, None
        raise ValueError('Unknown ROCm stack')
    def service(self):
        p = self.command(['systemctl', '--user', 'show', SERVICE, '--property=ActiveState,SubState,MainPID'])
        return dict(line.split('=', 1) for line in p.stdout.splitlines())
    def sample(self, retiring=None):
        row = observe(self.thermal_ceiling_c)
        owned = set()
        if self.cid:
            for proc in row['dri']:
                if self.cid in proc['cgroup']:
                    owned.add(proc['pid'])
                    try:
                        fields = dict(line.split(':', 1) for line in Path(f"/proc/{proc['pid']}/status").read_text().splitlines())
                        proc['status'] = {key: fields[key].strip() for key in ('Threads', 'VmRSS', 'VmHWM', 'VmSwap') if key in fields}
                    except OSError: proc['status'] = {'unavailable': True}
        with (self.root/'telemetry.jsonl').open('a') as log: log.write(json.dumps(row)+'\n')
        if self.interrupted: raise RuntimeError('Interrupted: '+str(self.interrupted))
        if any(t['value_c'] >= t['limit_c'] for t in row['temperatures']): raise RuntimeError('Thermal limit')
        clients = {p['pid'] for p in row['kfd']} | set(row['kernel_kfd'])
        new_dri = {p['pid'] for p in row['dri'] if (p['pid'], p['start_ticks']) not in self.baseline}
        if retiring:
            pid, start = retiring
            try:
                if ticks(pid) != start: raise RuntimeError('Retiring service PID identity changed')
            except FileNotFoundError: pass
            owned.add(pid)  # Admission still waits below; never launches while present.
        if (clients | new_dri) - owned: raise RuntimeError('Foreign GPU client observed')
        return row
    def enter(self):
        self.r['service_before'] = self.service()
        before = observe(self.thermal_ceiling_c)
        self.r['before'] = before
        self.baseline = {(p['pid'], p['start_ticks']) for p in before['dri']}
        # This serializes LIE only. Actual handover is the explicit user grant.
        path = BASE/'campaign.lock'
        self.lock = os.open(path, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
        fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        st, live = os.fstat(self.lock), path.stat()
        if (st.st_dev, st.st_ino) != (live.st_dev, live.st_ino) or st.st_uid != os.getuid():
            raise RuntimeError('Campaign lock identity mismatch')
        self.r['lease'] = {'path': str(path), 'device': st.st_dev, 'inode': st.st_ino, 'cooperative_lie_only': True}
        self.record()
        active = self.r['service_before']['ActiveState']
        if active not in ('active', 'inactive'): raise RuntimeError('Unexpected initial service state')
        if active == 'active':
            # Set before issuing stop, so even interrupted/failed stop restores it.
            self.r['service_restore_required'] = True
            self.record()
            self.command(['systemctl', '--user', 'stop', SERVICE], timeout=45)
        self.r['service_stopped'] = self.service()
        if self.r['service_stopped']['ActiveState'] != 'inactive': raise RuntimeError('Service did not retire')
        retiring = next(((p['pid'], p['start_ticks']) for p in before['kfd']
                         if p['pid'] == int(self.r['service_before']['MainPID'])), None)
        deadline = time.monotonic()+5
        while True:
            row = self.sample(retiring)
            if not row['kernel_kfd'] and not row['kfd']: break
            if time.monotonic() >= deadline: raise RuntimeError('Stopped service GPU retirement deadline')
            time.sleep(0.1)
        self.r['admission'] = row
        self.r['state'] = 'ADMITTED'
        self.record()
    def execute_container(self, argv, timeout, model_attempted=False):
        self.sample()
        self.cid = self.command(argv).stdout.strip()
        if not re.fullmatch('[a-f0-9]{64}', self.cid): raise RuntimeError('Invalid container identity')
        self.r['container'] = self.cid
        self.r['model_attempted'] = model_attempted
        self.record()
        self.command(['docker', 'start', self.cid])
        deadline = time.monotonic()+timeout
        while True:
            row = json.loads(self.command(['docker', 'inspect', '--format', '{{json .State}}', self.cid]).stdout)
            if not row['Running']:
                self.r['container_state'] = row
                self.r['child_exit_code'] = row['ExitCode']
                break
            self.r['container_host_pid'] = row['Pid']
            self.r['container_start_ticks'] = ticks(row['Pid'])
            self.sample()
            if time.monotonic() >= deadline: raise RuntimeError('Device command deadline')
            time.sleep(1)
        p = self.command(['docker', 'logs', self.cid], check=False)
        (self.root/'stdout.log').write_text(p.stdout)
        (self.root/'stderr.log').write_text(p.stderr)
        if row['ExitCode'] or row['OOMKilled']: raise RuntimeError('Container child failed; see retained logs')
    def run_container(self, command, bundle, timeout, model=None):
        bundle = checked_path(bundle)
        for name, expected in self.m['artifacts'].items():
            path = checked_path(bundle/name)
            if sha(path) != expected: raise RuntimeError('Artifact drift: '+name)
        image, rocm = self.image_and_rocm()
        self.sample()
        for directory in ('home', 'cache', 'tmp'): (self.root/directory).mkdir()
        argv = ['docker', 'create', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
                '--security-opt', 'no-new-privileges', '--user', f'{os.getuid()}:{os.getgid()}',
                '--group-add', str(Path('/dev/kfd').stat().st_gid), '--pids-limit', '512',
                '--device', '/dev/kfd', '--device', '/dev/dri/renderD128',
                '--label', 'synapse-lie.run='+str(self.root),
                '--mount', 'type=bind,src='+str(bundle)+',dst=/bundle,readonly',
                '--mount', 'type=bind,src='+str(self.root)+',dst=/work',
                '--workdir', '/work', '--env', 'LD_LIBRARY_PATH=/bundle/runtime/lib:/opt/rocm/lib',
                '--env', 'LD_BIND_NOW=1', '--env', 'LC_ALL=C',
                '--env', 'HOME=/work/home', '--env', 'XDG_CACHE_HOME=/work/cache', '--env', 'TMPDIR=/work/tmp',
                '--env', 'ROCR_VISIBLE_DEVICES=0', '--env', 'HIP_VISIBLE_DEVICES=0']
        if rocm: argv += ['--mount', 'type=bind,src='+rocm+',dst=/opt/rocm,readonly']
        if model: argv += ['--mount', 'type=bind,src='+str(checked_path(model))+',dst=/model,readonly']
        argv += ['--entrypoint', command[0], image, *command[1:]]
        self.execute_container(argv, timeout, model is not None)
    def build(self):
        if self.m.get('stack') != 'rocm10-fedora43':
            raise ValueError('Build requires the explicit ROCm 10 stack')
        image, rocm = self.image_and_rocm()
        if rocm is not None or checked_path(ROCM10_SOURCE) != ROCM10_SOURCE:
            raise ValueError('Unexpected build source/runtime')
        archive = ROCM10_SOURCE.parent/'source.tar.gz'
        if sha(archive) != self.m.get('source_archive_sha256'):
            raise ValueError('Build source archive drift')
        helper = ROCM10_SOURCE/'tools/strix-point-rocm10-compile.py'
        if sha(helper) != self.m.get('compile_helper_sha256'):
            raise ValueError('Build helper drift')
        for directory in ('build', 'evidence'): (ROCM10_SOURCE/directory).mkdir(exist_ok=True)
        for directory in ('tmp', 'home'): (ROCM10_SOURCE/'build'/directory).mkdir(exist_ok=True)
        argv = ['docker', 'create', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
                '--security-opt', 'no-new-privileges', '--user', f'{os.getuid()}:{os.getgid()}',
                '--pids-limit', '512', '--cpus', '2', '--memory', '16g',
                '--label', 'synapse-lie.run='+str(self.root),
                '--mount', 'type=bind,src='+str(ROCM10_SOURCE)+',dst=/source',
                '--workdir', '/source', '--env', 'LC_ALL=C',
                '--env', 'HOME=/source/build/home', '--env', 'TMPDIR=/source/build/tmp',
                '--env', 'LIE_ROCM10_BUILD_WINDOW=admitted',
                '--env', 'ROCR_VISIBLE_DEVICES=-1', '--env', 'HIP_VISIBLE_DEVICES=-1',
                '--entrypoint', '/usr/bin/python3', image, '-B',
                'tools/strix-point-rocm10-compile.py']
        self.execute_container(argv, 7200)
        result = json.loads((ROCM10_SOURCE/'evidence/rocm10-point-compile-r1/result.json').read_text())
        if result.get('state') != 'BUILT_NOT_GPU_TESTED' or result.get('exit_code') != 0:
            raise RuntimeError('Incomplete ROCm 10 build receipt')
        self.r['build_result'] = result
        self.record()
    def download(self):
        if sha(self.root/'download.py') != self.m['download_sha256']: raise RuntimeError('Download helper drift')
        env = dict(os.environ, LIE_ADMITTED_RUN=str(self.root), LC_ALL='C', ROCR_VISIBLE_DEVICES='-1', HIP_VISIBLE_DEVICES='-1')
        with (self.root/'download.log').open('x') as log:
            self.child = subprocess.Popen([sys.executable, '-B', str(self.root/'download.py'), str(self.root)],
                                          env=env, stdout=log, stderr=subprocess.STDOUT)
            self.r['child_pid'], self.r['child_start_ticks'] = self.child.pid, ticks(self.child.pid)
            self.r['state'] = 'DOWNLOADING'; self.record()
            # The pinned 111 GB payload can exceed four hours on this Wi-Fi WAN.
            deadline = time.monotonic()+28800
            while self.child.poll() is None:
                self.sample()
                if time.monotonic() >= deadline: raise RuntimeError('Download deadline')
                time.sleep(1)
            self.r['child_exit_code'] = self.child.returncode
        if (self.root/'download-result.json').exists():
            self.r['download'] = json.loads((self.root/'download-result.json').read_text())
        if self.child.returncode: raise RuntimeError('Pinned download failed; see retained download.log')
    def verified_model(self):
        model = checked_path(self.m['model_plan']['destination'])
        source = json.loads((model/'SOURCE.json').read_text())
        if source['result']['state'] != 'VERIFIED' or source['plan'] != self.m['model_plan']:
            raise RuntimeError('Pinned model staging receipt mismatch')
        rows = []
        for expected, staged in zip(self.m['model_plan']['files'], source['result']['files'], strict=True):
            path = checked_path(model/expected['name']); s = path.stat()
            current = {'path': str(path), 'bytes': s.st_size, 'device': s.st_dev, 'inode': s.st_ino,
                       'mtime_ns': s.st_mtime_ns, 'ctime_ns': s.st_ctime_ns}
            if any(current[k] != staged[k] for k in current) or staged['sha256'] != expected['sha256']:
                raise RuntimeError('Model identity drift before launch')
            rows.append(current)
        self.r['models_before'] = rows
        return model, rows
    def check_model_after(self, rows):
        after = []
        for before in rows:
            s = Path(before['path']).stat()
            current = {'path': before['path'], 'bytes': s.st_size, 'device': s.st_dev, 'inode': s.st_ino,
                       'mtime_ns': s.st_mtime_ns, 'ctime_ns': s.st_ctime_ns}
            after.append(current)
        self.r['models_after'] = after
        self.r['model_stat_unchanged'] = rows == after
        if rows != after: raise RuntimeError('Model identity drift during run')
    def core(self):
        model, rows = self.verified_model()
        settings = self.m['settings']
        if settings != {'context': 4096, 'chunk': 2048, 'users': 1, 'tg': 32, 'warmups': 1, 'repetitions': 3}:
            raise ValueError('Expected bounded initial C1 settings')
        (self.root/'prompt.txt').write_text('The sum of 2 and 2 is')
        command = ['/bundle/runtime/bin/synapse-lie-bench', '--suite', 'core',
                   '--model', '/model/'+self.m['model_plan']['files'][0]['name'],
                   '--prompt-file', '/work/prompt.txt', '--output', '/work/measurements.jsonl',
                   '--timeout-ms', '600000']
        for key, value in settings.items(): command += ['--'+key, str(value)]
        # Preserve the engine's default RAM cache; report warm hits separately.
        try:
            self.run_container(command, self.m['bundle'], 900, model)
            self.r['measurements'] = [json.loads(line) for line in (self.root/'measurements.jsonl').read_text().splitlines()]
            if self.r['measurements'][-1] != {'event': 'complete', 'exit_code': 0}:
                raise RuntimeError('Incomplete core benchmark')
        finally:
            if (self.root/'measurements.jsonl').exists():
                self.r['measurements_raw'] = (self.root/'measurements.jsonl').read_text()
            self.check_model_after(rows)
    def bench(self):
        profile = self.m.get('bench_profile')
        if type(profile) is not str or profile not in BENCH_PROFILES:
            raise ValueError('Unknown fixed benchmark profile')
        implementation = self.m.get('bench_impl', 'lie')
        if implementation not in ('lie', 'gufo'):
            raise ValueError('Unknown fixed benchmark implementation')
        model, rows = self.verified_model()
        suite, execution, warmups, repetitions, extra = BENCH_PROFILES[profile]
        binary = 'synapse-lie-bench' if implementation == 'lie' else 'synapse-lie-bench-gufo-reference'
        command = ['/bundle/runtime/bin/'+binary, '--suite', suite,
                   '--model', '/model/'+self.m['model_plan']['files'][0]['name'],
                   '--output', '/work/measurements.jsonl',
                   '--pp', '2048', '--tg', '128', '--warmups', str(warmups),
                   '--repetitions', str(repetitions), *extra]
        if implementation == 'lie': command += ['--execution', execution]
        self.r['bench_command'] = command
        self.record()
        try:
            self.run_container(command, self.m['bundle'], 3600, model)
            measurements = [json.loads(line) for line in (self.root/'measurements.jsonl').read_text().splitlines()]
            if not measurements or measurements[-1] != {'event': 'complete', 'exit_code': 0}:
                raise RuntimeError('Incomplete direct benchmark')
            identity = measurements[0]
            expected_execution = 'upstream-native-batch' if implementation == 'gufo' else 'LIE-serial-interleaved' if execution == 'serial' else 'LIE-reactive-ready-batch'
            if (identity.get('schema') != 'synapse-lie.bench.v1' or identity.get('suite') != suite or
                identity.get('synthetic') or identity.get('execution') != expected_execution):
                raise RuntimeError('Unexpected benchmark identity')
            self.r['bench_result'] = {'profile': profile, 'suite': suite, 'implementation': implementation,
                                      'execution': identity['execution'],
                                      'rows': len(measurements), 'samples': sum(r.get('event') == 'sample' for r in measurements),
                                      'measurements_sha256': sha(self.root/'measurements.jsonl')}
        finally:
            if (self.root/'measurements.jsonl').exists():
                self.r['bench_partial'] = {'measurements_sha256': sha(self.root/'measurements.jsonl'),
                                            'bytes': (self.root/'measurements.jsonl').stat().st_size}
            self.check_model_after(rows)
    def finish(self):
        failures = []
        if self.cid and re.fullmatch('[a-f0-9]{64}', self.cid):
            try:
                p = self.command(['docker', 'inspect', '--format', '{{index .Config.Labels "synapse-lie.run"}}', self.cid])
                if p.stdout.strip() != str(self.root): raise RuntimeError('Container ownership mismatch')
                self.command(['docker', 'stop', '--time', '10', self.cid], check=False)
                p = self.command(['docker', 'logs', self.cid], check=False)
                (self.root/'stdout.log').write_text(p.stdout)
                (self.root/'stderr.log').write_text(p.stderr)
                self.r['final_container_state'] = json.loads(self.command(['docker', 'inspect', '--format', '{{json .State}}', self.cid]).stdout)
                self.command(['docker', 'rm', self.cid])
            except Exception as ex: failures.append(repr(ex))
        if self.child and self.child.poll() is None:
            self.child.terminate()
            try: self.child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.child.kill(); self.child.wait()
        if self.child is not None:
            self.r['child_exit_code'] = self.child.returncode
        try: self.r['postflight_before_restore'] = observe(self.thermal_ceiling_c)
        except Exception as ex: failures.append(repr(ex))
        if self.r['service_restore_required']:
            try:
                self.command(['systemctl', '--user', 'start', SERVICE], timeout=45)
                self.r['service_after'] = self.service()
                if self.r['service_after']['ActiveState'] != 'active': raise RuntimeError('Service restoration failed')
            except Exception as ex: failures.append(repr(ex))
        if self.lock is not None:
            os.close(self.lock); self.lock = None
            if 'lease' in self.r: self.r['lease_released_at'] = now()
        self.r['cleanup_failures'] = failures
        self.r['ended_at'] = now()
        if failures: self.r['exit_code'] = 1
        self.record()

def main():
    if len(sys.argv) != 2: raise SystemExit('Usage: strix-point-campaign.py PRIVATE-RUN-DIRECTORY')
    root = checked_path(sys.argv[1])
    if (root/'result.json').exists(): raise SystemExit('Refusing campaign replay')
    if os.getuid() != 1000 or os.environ.get('SSH_CONNECTION', '').split()[2:3] != ['192.168.5.161']:
        raise SystemExit('Expected pop@192.168.5.161 SSH target')
    m = json.loads((root/'manifest.json').read_text())
    if m.get('action') not in ('probe', 'download', 'core', 'bench', 'build'): raise SystemExit('Unsupported campaign action')
    if m['authorization'] != {'kind': 'operator-one-shot-window', 'service': SERVICE,
                              'stop_restore_authorized': True, 'quote': 'llama si può stoppaare'}:
        raise SystemExit('Explicit scoped operator handover required')
    c = Campaign(root, m)
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, lambda signum, frame: setattr(c, 'interrupted', signum))
    try:
        c.enter()
        if m['action'] == 'probe':
            c.run_container(['/bundle/runtime/bin/lie-hip-probe', '--run'], m['bundle'], 60)
            c.r['probe'] = json.loads((root/'stdout.log').read_text())
            if c.r['probe'].get('scope') != 'GPU_RUNTIME_PROBE_NOT_MODEL_INFERENCE' or c.r['probe'].get('sgemm_elements_verified') != 4:
                raise RuntimeError('Invalid device probe result')
        elif m['action'] == 'download': c.download()
        elif m['action'] == 'core': c.core()
        elif m['action'] == 'bench': c.bench()
        elif m['action'] == 'build': c.build()
        else: raise ValueError('Unsupported campaign action')
        c.r.update(state='PASSED', exit_code=0)
    except BaseException as ex:
        c.r.update(state='FAILED', error=repr(ex), exit_code=1)
    finally: c.finish()
    print(json.dumps(c.r), flush=True)
    return c.r['exit_code']

if __name__ == '__main__': raise SystemExit(main())
