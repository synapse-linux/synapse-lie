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
import math
import os
from pathlib import Path
import re
import signal
import struct
import subprocess
import sys
import time
import zlib

BASE = Path('/home/pop/workspace/synapse-lie')
SERVICE = 'llama-router.service'
IMAGE = 'sha256:29e3b2b4b984ddb2614068271b2967bdc941664690468390c907508b5da8c2ac'
ROCM = '/home/pop/.local/opt/rocm-7.2-root/opt/rocm-7.2.0'
ROCM10_SOURCE = BASE/'rocm10-fedora-161'/'source'
ROCM10_RPM_CONTEXT = BASE/'rocm10-fedora-161'/'fedora44-rpm'
ROCM10_RPM_TAG = 'synapse-lie-rocm10-fedora44-rpm:gfx1150-r1'
ROCM10_ALMA_CONTEXT = BASE/'rocm10-almalinux-161'/'context'
ROCM10_ALMA_TAG = 'synapse-lie-rocm10-almalinux10-rpm:gfx1150-r1'
def core_generation(value, historical=False):
    """Typed sampler identity; historical absent filters mean disabled, not DS4 defaults."""
    defaults = {'temperature':0, 'top_p':1, 'frequency_penalty':0,
                'presence_penalty':0, 'seed':-1, 'top_k':0, 'min_p':0}
    if value is None and historical:
        return defaults
    if (type(value) is not dict or
            (not historical and set(value) != set(defaults)) or
            (historical and (not set(defaults).difference({'top_k','min_p'}).issubset(value)
                             or not set(value).issubset(defaults)))):
        raise ValueError('Invalid complete core sampling controls')
    out = dict(defaults, **value)
    for name, low, high in (('temperature',0,2), ('top_p',0,1), ('min_p',0,1),
                            ('frequency_penalty',-2,2), ('presence_penalty',-2,2)):
        x = out[name]
        if type(x) not in (int,float) or not low <= x <= high or not math.isfinite(x):
            raise ValueError('Invalid core sampling number: '+name)
    if (out['top_p'] == 0 or type(out['top_k']) is not int or not 0 <= out['top_k'] <= 2147483647 or
            type(out['seed']) is not int or not -1 <= out['seed'] <= 9223372036854775807 or
            (out['temperature'] > 0 and out['seed'] < 0)):
        raise ValueError('Invalid core sampling filter or seed')
    return out

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
CPU_GUARD_QUOTE = 'è la CPU che deve avere il guard, non la gpu'
CPU_GUARD_POLICY = 'cpu-98-nvme-85-gpu-observe-v1'
VISION_PROMPT = 'Describe the main color and shape shown in the image in one sentence.'
HTTP_CONTROL_CHECKS = {
    'chat_choices_json', 'chat_choices_sse', 'chat_seed_replay',
    'chat_logprobs', 'chat_logprobs_sse', 'chat_bias_positive', 'chat_bias_negative',
    'chat_stop_json', 'chat_stop_sse', 'chat_json_object', 'chat_json_schema',
    'responses_json_object', 'responses_json_schema', 'chat_store_crud',
    'responses_background_disconnect', 'responses_cursor_replay',
    'responses_input_pagination', 'responses_cancel_after_output',
    'responses_delete', 'responses_truncation', 'unsupported_fields',
}

def validate_core_progress(path, jobs, settings):
    """Stream native stderr; require live and matching retired final observations.

    Provider diagnostics may accompany the JSONL. An observation is metadata,
    not a benchmark sample or proof of completion on its own.
    """
    total = settings['warmups'] + settings['repetitions']
    fields = ('prompt_tokens', 'cached_tokens', 'prefill_tokens', 'prefill_calls',
              'output_tokens', 'decode_calls', 'prefill_ns', 'decode_ns')
    expected = {(row['rep'], row['user']): row for row in jobs}
    if (len(expected) != total * settings['users'] or
            set(expected) != {(r, u) for r in range(total) for u in range(settings['users'])}):
        raise RuntimeError('Progress requires complete job identities')
    latest = {}; final = set(); live = set(); begin = {}; previous_time = 0
    observations = partial_prefill = inflight_prefill = 0
    with path.open(encoding='utf-8') as stream:
        while raw := stream.readline(65537):
            if len(raw) > 65536:
                raise RuntimeError('Oversized core progress line')
            if not raw.lstrip().startswith('{'):
                continue
            try:
                row = json.loads(raw)
            except ValueError as exc:
                raise RuntimeError('Malformed core progress JSON') from exc
            if row.get('event') != 'core_progress':
                continue
            if (row.get('schema') != 'synapse-lie.core-progress.v1' or
                    row.get('synthetic') is not False or
                    type(row.get('final_snapshot')) is not bool or
                    row.get('executor_phase') not in ('idle', 'prefill', 'decode', 'capture', 'restore')):
                raise RuntimeError('Unexpected core progress identity')
            numbers = ('rep', 'warmup', 'snapshot_monotonic_ns', 'elapsed_ns',
                       'queued', 'active', 'output_blocked', 'prefill_started', 'prefill_returned')
            if any(type(row.get(k)) is not int or not 0 <= row[k] <= 2**64-1 for k in numbers):
                raise RuntimeError('Invalid core progress counters')
            rep = row['rep']; stamp = row['snapshot_monotonic_ns']
            if (not 0 <= rep < total or row['warmup'] != int(rep < settings['warmups']) or
                    rep in final or stamp <= previous_time or row['elapsed_ns'] > stamp):
                raise RuntimeError('Invalid core progress ordering')
            origin = stamp - row['elapsed_ns']
            if begin.setdefault(rep, origin) != origin:
                raise RuntimeError('Core progress clock origin drift')
            previous_time = stamp
            states = row.get('jobs')
            if (type(states) is not list or len(states) != settings['users'] or
                    any(type(s) is not dict or type(s.get('user')) is not int for s in states) or
                    {s['user'] for s in states} != set(range(settings['users']))):
                raise RuntimeError('Incomplete core progress jobs')
            for state in states:
                key = (rep, state['user'])
                if (any(type(state.get(k)) is not int or not 0 <= state[k] <= 2**64-1
                        for k in (*fields, 'consumer_tokens')) or
                        any(type(state.get(k)) is not bool for k in
                            ('prepared', 'retired', 'terminal_observed')) or state.get('error')):
                    raise RuntimeError('Invalid core progress job counters')
                prior = latest.get(key)
                if prior and any(state[k] < prior[k] for k in (*fields, 'consumer_tokens')):
                    raise RuntimeError('Core progress job counter regression')
                latest[key] = state
                if row['final_snapshot']:
                    measured = expected[key]
                    if (not all(state[k] for k in ('prepared', 'retired', 'terminal_observed')) or
                            state['consumer_tokens'] != measured['output_tokens'] or
                            any(state[k] != measured[k] for k in fields)):
                        raise RuntimeError('Core progress final state differs from completed job')
                elif not state['retired']:
                    if 0 < state['prefill_tokens'] < expected[key]['prompt_tokens']:
                        partial_prefill += 1
            observations += 1
            if row['final_snapshot']:
                final.add(rep)
            else:
                live.add(rep)
                if row['executor_phase'] == 'prefill':
                    inflight_prefill += 1
    if final != set(range(total)) or live != final:
        raise RuntimeError('Missing live or final core progress observation')
    return {'observations': observations, 'live_samples': len(live),
            'final_samples': len(final), 'partial_prefill_job_observations': partial_prefill,
            'inflight_prefill_observations': inflight_prefill, 'stderr_sha256': sha(path)}

def vision_fixture_png():
    """An owned 224x224 white canvas with a central red square."""
    width = height = 224
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # PNG filter: none
        for x in range(width):
            raw.extend((220, 24, 24) if 32 <= x < 192 and 32 <= y < 192 else (255, 255, 255))
    def chunk(kind, data):
        return (struct.pack('>I', len(data)) + kind + data +
                struct.pack('>I', zlib.crc32(kind+data)))
    return (b'\x89PNG\r\n\x1a\n' +
            chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def kfd_group(): return Path('/dev/kfd').stat().st_gid
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
def observe(ceiling_c=85.0, gpu_observation_only=False):
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
            limit = min(ceiling_c, 85.0) if gpu_observation_only and name == 'nvme' else ceiling_c
            for suffix in ('max', 'crit'):
                bound = path.with_name(path.name[:-6]+'_'+suffix)
                if bound.exists():
                    threshold = int(bound.read_text())/1000
                    if 30 <= threshold <= 150: limit = min(limit, threshold)
            if not -40 <= value <= 150: raise RuntimeError('Invalid temperature reading')
            result['temperatures'].append({'name': name, 'path': str(path), 'value_c': value,
                                           'limit_c': limit,
                                           'guarded': not (gpu_observation_only and name == 'amdgpu')})
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
        self.thermal_policy = manifest.get('thermal_policy', 'legacy-all-sensors')
        if self.thermal_policy == CPU_GUARD_POLICY:
            if ceiling != 98 or manifest.get('thermal_policy_quote') != CPU_GUARD_QUOTE:
                raise ValueError('Explicit CPU guard and GPU observation policy required')
        elif self.thermal_policy != 'legacy-all-sensors':
            raise ValueError('Unsupported thermal policy')
        if type(ceiling) not in (int, float) or ceiling not in ((98,) if self.thermal_policy == CPU_GUARD_POLICY else (85, 100)):
            raise ValueError('Unsupported thermal ceiling')
        if self.thermal_policy == 'legacy-all-sensors' and ceiling == 100 and manifest.get('thermal_override_quote') != THERMAL_OVERRIDE_QUOTE:
            raise ValueError('Explicit operator 100 C thermal override required')
        self.thermal_ceiling_c = float(ceiling)
        self.memory_admission = manifest.get('memory_admission')
        if self.memory_admission is not None and (
                type(self.memory_admission) is not dict or
                set(self.memory_admission) != {'expected_peak_gtt_bytes', 'min_available_ram_bytes'} or
                any(type(value) is not int or not 1 <= value <= 2**63-1
                    for value in self.memory_admission.values())):
            raise ValueError('Memory admission requires positive byte budgets')
        self.staging_rebind = manifest.get('staging_filesystem_rebind')
        if self.staging_rebind is not None:
            b = self.staging_rebind
            if (type(b) is not dict or
                    set(b) != {'boot_id', 'filesystem_uuid', 'previous_device', 'current_device'} or
                    any(type(b[k]) is not str or not re.fullmatch(
                        r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', b[k])
                        for k in ('boot_id', 'filesystem_uuid')) or
                    any(type(b[k]) is not int or not 1 <= b[k] <= 2**63-1
                        for k in ('previous_device', 'current_device')) or
                    b['previous_device'] == b['current_device']):
                raise ValueError('Staging filesystem rebind requires explicit boot, UUID and device identities')
        self.r = {'state': 'PREFLIGHT', 'started_at': now(), 'pid': os.getpid(), 'start_ticks': ticks(os.getpid()),
                  'manifest_sha256': sha(root/'manifest.json'), 'runner_sha256': sha(__file__),
                  'authorization': manifest['authorization'], 'commands': [], 'container': None,
                  'thermal_ceiling_c': self.thermal_ceiling_c,
                  'thermal_policy': self.thermal_policy,
                  'model_attempted': False,
                  'service_restore_required': False, 'exit_code': 1}
        if self.memory_admission is not None:
            self.r['memory_admission'] = self.memory_admission
        self.lock = None
        self.child = None
        self.interrupted = None
        self.cid = None
        self.baseline = set()
        self.owned_kfd = {}
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
        if stack in ('rocm10-fedora43', 'rocm10-fedora44-rpm', 'rocm10-almalinux10-rpm'):
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
    def check_memory(self, row):
        if self.memory_admission is None:
            return
        available = row.get('memory', {}).get('MemAvailable')
        total = row.get('gpu', {}).get('mem_info_gtt_total')
        used = row.get('gpu', {}).get('mem_info_gtt_used')
        if (any(type(value) is not int for value in (available, total, used)) or
                available < 0 or total <= 0 or used < 0):
            raise RuntimeError('Missing or invalid memory admission telemetry')
        expected = self.memory_admission['expected_peak_gtt_bytes']
        floor = self.memory_admission['min_available_ram_bytes']
        if expected > total:
            raise RuntimeError('Expected GTT peak exceeds effective ceiling')
        if available < floor:
            raise RuntimeError('Available RAM floor reached')
        if available - max(expected-used, 0) < floor:
            raise RuntimeError('Projected available RAM below admitted floor')
    def sample(self, retiring=None):
        row = observe(self.thermal_ceiling_c, gpu_observation_only=True) if self.thermal_policy == CPU_GUARD_POLICY else observe(self.thermal_ceiling_c)
        owned = set()
        if self.cid:
            for proc in row['dri']:
                if self.cid in proc['cgroup']:
                    owned.add(proc['pid'])
                    if proc['pid'] in row['kernel_kfd']:
                        self.owned_kfd[proc['pid']] = proc['start_ticks']
                    try:
                        fields = dict(line.split(':', 1) for line in Path(f"/proc/{proc['pid']}/status").read_text().splitlines())
                        proc['status'] = {key: fields[key].strip() for key in ('Threads', 'VmRSS', 'VmHWM', 'VmSwap') if key in fields}
                    except OSError: proc['status'] = {'unavailable': True}
        with (self.root/'telemetry.jsonl').open('a') as log: log.write(json.dumps(row)+'\n')
        if self.interrupted: raise RuntimeError('Interrupted: '+str(self.interrupted))
        if any(t.get('guarded', True) and t['value_c'] >= t['limit_c'] for t in row['temperatures']): raise RuntimeError('Thermal limit')
        self.check_memory(row)
        clients = {p['pid'] for p in row['kfd']} | set(row['kernel_kfd'])
        new_dri = {p['pid'] for p in row['dri'] if (p['pid'], p['start_ticks']) not in self.baseline}
        # /proc/fd can disappear just before the kernel KFD list retires an
        # owned process. Keep its recorded PID/start/cgroup identity during
        # that gap; a reused PID or process outside this container is foreign.
        retired_owned = set()
        for pid in row['kernel_kfd']:
            start = self.owned_kfd.get(pid)
            if start is None:
                continue
            try:
                current = ticks(pid)
                cgroup = Path(f'/proc/{pid}/cgroup').read_text()
            except FileNotFoundError:
                retired_owned.add(pid)
            else:
                if current == start and self.cid and self.cid in cgroup:
                    owned.add(pid)
        if retiring:
            pid, start = retiring
            try:
                if ticks(pid) != start: raise RuntimeError('Retiring service PID identity changed')
            except FileNotFoundError: pass
            owned.add(pid)  # Admission still waits below; never launches while present.
        if (clients | new_dri) - owned - retired_owned: raise RuntimeError('Foreign GPU client observed')
        return row
    def wait_owned_gpu_retirement(self):
        deadline = time.monotonic()+5
        while True:
            row = self.sample()
            if not row['kernel_kfd'] and not row['kfd']: return
            if time.monotonic() >= deadline:
                raise RuntimeError('Owned GPU retirement deadline')
            time.sleep(0.1)
    def enter(self):
        self.r['service_before'] = self.service()
        before = observe(self.thermal_ceiling_c, gpu_observation_only=True) if self.thermal_policy == CPU_GUARD_POLICY else observe(self.thermal_ceiling_c)
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
        self.check_memory(before)
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
            # Docker inspect and /proc are not atomic: a child can exit after
            # inspect reports Running, leaving Pid=0 or no /proc entry.
            pid = row['Pid']
            if isinstance(pid, int) and pid > 0:
                try:
                    start_ticks = ticks(pid)
                except FileNotFoundError:
                    pass
                else:
                    self.r['container_host_pid'] = pid
                    self.r['container_start_ticks'] = start_ticks
            self.sample()
            if time.monotonic() >= deadline: raise RuntimeError('Device command deadline')
            time.sleep(1)
        p = self.command(['docker', 'logs', self.cid], check=False)
        (self.root/'stdout.log').write_text(p.stdout)
        (self.root/'stderr.log').write_text(p.stderr)
        if row['ExitCode'] or row['OOMKilled']: raise RuntimeError('Container child failed; see retained logs')
    def execute_distrobox(self, command, bundle, model, image, timeout):
        name = self.m.get('distrobox_name')
        if (self.m.get('action') != 'bench' or self.m.get('stack') != 'rocm10-fedora43' or
                type(name) is not str or not re.fullmatch(r'lie-[a-z0-9-]{1,50}', name) or
                model is None):
            raise ValueError('Distrobox benchmark requires explicit ROCm 10 name and model')
        root = str(self.root)
        home = self.root/'home'
        home.mkdir()
        flags = ('--device /dev/kfd --device /dev/dri/renderD128 '
                 '--group-add '+str(kfd_group())+' --pids-limit 512 '
                 '--label synapse-lie.run='+root)
        create = ['distrobox', 'create', '--yes', '--image', image, '--name', name,
                  '--home', str(home), '--volume', str(bundle)+':/bundle:ro',
                  '--volume', str(model)+':/model:ro', '--volume', root+':/work:rw',
                  '--additional-flags', flags, '--no-entry']
        if self.m.get('bench_profile') in ('modern-core', 'modern-core-ram', 'modern-core-ssd', 'modern-core-ssd-restart', 'modern-core-reactive-probe', 'modern-core-vision', 'modern-http', 'modern-http-multi', 'modern-http-depth') and self.m.get('decode_mode') == 'mtp':
            predictor = checked_path(self.m['predictor_plan']['destination'])
            create[create.index('--additional-flags'):create.index('--additional-flags')] = [
                '--volume', str(predictor)+':/mtp:ro']
        if self.m.get('bench_profile') == 'modern-core-vision':
            projector = checked_path(self.m['projector_plan']['destination'])
            create[create.index('--additional-flags'):create.index('--additional-flags')] = [
                '--volume', str(projector)+':/vision:ro']
        env = dict(os.environ, DBX_CONTAINER_MANAGER='docker', DBX_NON_INTERACTIVE='1')
        self.sample()
        with (self.root/'distrobox-create.log').open('x') as log:
            created = subprocess.run(create, stdout=log, stderr=subprocess.STDOUT,
                                     env=env, timeout=90)
        self.r['distrobox'] = {'name': name, 'create_argv': create,
                               'create_exit_code': created.returncode}
        # Even a failed create can leave an owned container to retire.
        p = self.command(['docker', 'inspect', name, '--format', '{{json .}}'], check=False)
        if p.returncode == 0:
            inspected = json.loads(p.stdout)
            if (inspected['Image'] != image or
                    inspected['Config']['Labels'].get('synapse-lie.run') != root):
                raise RuntimeError('Distrobox container identity mismatch')
            self.cid = inspected['Id']
            self.r['container'] = self.cid
            self.record()
        if created.returncode: raise RuntimeError('Distrobox create failed; see retained log')
        if not self.cid: raise RuntimeError('Distrobox create returned no owned container')
        enter = ['distrobox', 'enter', '--no-tty', '--name', name, '--',
                 '/usr/bin/env', 'LD_LIBRARY_PATH=/bundle/runtime/lib:/opt/rocm/lib',
                 'LC_ALL=C', 'ROCR_VISIBLE_DEVICES=0', 'HIP_VISIBLE_DEVICES=0',
                 *command]
        self.r['distrobox']['enter_argv'] = enter
        self.record()
        with (self.root/'distrobox.stdout.log').open('x') as stdout, \
             (self.root/'distrobox.stderr.log').open('x') as stderr:
            self.child = subprocess.Popen(enter, env=env, stdout=stdout, stderr=stderr)
            self.r['child_pid'] = self.child.pid
            self.r['child_start_ticks'] = ticks(self.child.pid)
            self.r['state'] = 'RUNNING_DISTROBOX'
            self.record()
            deadline = time.monotonic()+timeout
            while self.child.poll() is None:
                if not self.r['model_attempted'] and ((self.root/'measurements.jsonl').exists() or
                                                      (self.root/'http-started.marker').exists() or
                                                      (self.root/'restart-started.marker').exists()):
                    self.r['model_attempted'] = True
                    self.record()
                self.sample()
                if time.monotonic() >= deadline: raise RuntimeError('Distrobox benchmark deadline')
                time.sleep(1)
            self.r['child_exit_code'] = self.child.returncode
            if not self.r['model_attempted'] and ((self.root/'measurements.jsonl').exists() or
                                                  (self.root/'http-started.marker').exists() or
                                                  (self.root/'restart-started.marker').exists()):
                self.r['model_attempted'] = True
            # Do not close a GPU window until the kernel has retired its owner.
            self.wait_owned_gpu_retirement()
        if self.child.returncode: raise RuntimeError('Distrobox benchmark failed; see retained logs')
    def run_container(self, command, bundle, timeout, model=None):
        bundle = checked_path(bundle)
        for name, expected in self.m['artifacts'].items():
            path = checked_path(bundle/name)
            if sha(path) != expected: raise RuntimeError('Artifact drift: '+name)
        image, rocm = self.image_and_rocm()
        self.sample()
        if self.m.get('transport') == 'distrobox':
            self.execute_distrobox(command, bundle, model, image, timeout)
            return
        if self.m.get('transport', 'docker') != 'docker':
            raise ValueError('Unsupported benchmark transport')
        library_path = '/bundle/runtime/lib:/opt/rocm/lib'
        if self.m.get('stack') in ('rocm10-fedora44-rpm', 'rocm10-almalinux10-rpm'):
            library_path = '/bundle/runtime/lib:/opt/rocm/core/lib/rocm_sysdeps/lib:/opt/rocm/lib'
        full_profile = self.m.get('rocm10_diagnostic_full_profile', False)
        if type(full_profile) is not bool or (full_profile and
                (self.m.get('action') != 'diagnostic' or
                 self.m.get('stack') not in ('rocm10-fedora44-rpm', 'rocm10-almalinux10-rpm') or
                 not self.m.get('rocm10_seccomp_unconfined') or
                 not self.m.get('rocm10_published_container_profile'))):
            raise ValueError('Full ROCm profile requires explicit RPM diagnostic flags')
        argv = ['docker', 'create', '--network', 'none']
        if not full_profile:
            argv += ['--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges']
        argv += ['--user', f'{os.getuid()}:{os.getgid()}',
                '--group-add', str(kfd_group()), '--pids-limit', '512',
                '--device', '/dev/kfd', '--device', '/dev/dri/renderD128',
                '--label', 'synapse-lie.run='+str(self.root),
                '--mount', 'type=bind,src='+str(bundle)+',dst=/bundle,readonly',
                '--mount', 'type=bind,src='+str(self.root)+',dst=/work',
                '--workdir', '/work', '--env', 'LD_LIBRARY_PATH='+library_path,
                '--env', 'LD_BIND_NOW=1', '--env', 'LC_ALL=C',
                '--env', 'HOME=/work/home', '--env', 'XDG_CACHE_HOME=/work/cache', '--env', 'TMPDIR=/work/tmp',
                '--env', 'ROCR_VISIBLE_DEVICES=0', '--env', 'HIP_VISIBLE_DEVICES=0']
        relaxed_seccomp = self.m.get('rocm10_seccomp_unconfined', False)
        if type(relaxed_seccomp) is not bool or (relaxed_seccomp and rocm is not None):
            raise ValueError('Seccomp override is explicit and ROCm 10 only')
        if relaxed_seccomp:
            argv += ['--security-opt', 'seccomp=unconfined']
        published_profile = self.m.get('rocm10_published_container_profile', False)
        if type(published_profile) is not bool or (published_profile and rocm is not None):
            raise ValueError('Published ROCm container profile is explicit and ROCm 10 only')
        if published_profile:
            argv += ['--ipc', 'host', '--cap-add', 'SYS_PTRACE']
        for directory in ('home', 'cache', 'tmp'): (self.root/directory).mkdir()
        if self.m.get('action') == 'diagnostic':
            argv += ['--env', 'LIE_GPU_DIAGNOSTIC_WINDOW=admitted']
        if rocm: argv += ['--mount', 'type=bind,src='+rocm+',dst=/opt/rocm,readonly']
        if model: argv += ['--mount', 'type=bind,src='+str(checked_path(model))+',dst=/model,readonly']
        argv += ['--entrypoint', command[0], image, *command[1:]]
        self.execute_container(argv, timeout, model is not None)
    def build(self):
        if self.m.get('build_flavor') == 'gufo-point-server':
            return self.build_gufo_point_server()
        if self.m.get('build_flavor') == 'modern-cmake':
            return self.build_modern()
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
    def build_gufo_point_server(self):
        if self.m.get('stack') != 'rocm10-fedora43':
            raise ValueError('Point Gufo server build requires the pinned ROCm 10 stack')
        source = checked_path(BASE/'rocm10-fedora-161/source-modern-r6')
        wmma = checked_path(BASE/'rocm10-fedora-161/rocwmma-point-2.2.0')
        helper = checked_path(self.root/'gufo-build.py')
        if (sha(helper) != self.m.get('gufo_build_helper_sha256') or
                (source/'SOURCE-COMMIT.txt').read_text().strip() !=
                self.m.get('source_commit') or
                sha(source/'SOURCE-FILES.sha256') != self.m.get('source_files_sha256') or
                sha(wmma/'FILES.sha256') != self.m.get('rocwmma_files_sha256')):
            raise ValueError('Point Gufo build source/helper identity drift')
        image, rocm = self.image_and_rocm()
        if rocm is not None:
            raise ValueError('Unexpected Point Gufo ROCm runtime override')
        for directory in ('home', 'tmp'):
            (self.root/directory).mkdir()
        argv = ['docker', 'create', '--network', 'none', '--read-only',
                '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                '--user', f'{os.getuid()}:{os.getgid()}', '--pids-limit', '512',
                '--cpus', '2', '--memory', '16g',
                '--label', 'synapse-lie.run='+str(self.root),
                '--mount', 'type=bind,src='+str(source)+',dst=/source,readonly',
                '--mount', 'type=bind,src='+str(wmma)+',dst=/wmma,readonly',
                '--mount', 'type=bind,src='+str(self.root)+',dst=/work',
                '--workdir', '/work', '--env', 'LC_ALL=C',
                '--env', 'HOME=/work/home', '--env', 'TMPDIR=/work/tmp',
                '--env', 'LIE_POINT_GUIFO_BUILD_WINDOW=admitted',
                '--env', 'ROCR_VISIBLE_DEVICES=-1',
                '--env', 'HIP_VISIBLE_DEVICES=-1',
                '--entrypoint', '/usr/bin/python3', image,
                '-B', '/work/gufo-build.py']
        self.r['gufo_build_command'] = argv
        self.record()
        try:
            self.execute_container(argv, 7500)
            result = json.loads((self.root/'gufo-build-result.json').read_text())
            binary = checked_path(self.root/'gufo-build/gufo')
            if (result.get('schema') != 'synapse-lie.point-gufo-port-build.v1' or
                    result.get('state') != 'BUILT_NOT_GPU_TESTED' or
                    result.get('exit_code') != 0 or
                    result.get('upstream_pin') !=
                    'f783fedb9bea2ec7de941f6da4e02f4a4596b29e' or
                    result.get('target') != 'gfx1150' or
                    result.get('gpu_device_available') is not False or
                    result.get('installation') is not False or
                    result.get('binary_sha256') != sha(binary)):
                raise RuntimeError('Incomplete pinned Point Gufo server build')
            self.r['build_result'] = result
        finally:
            if (self.root/'gufo-build-result.json').exists():
                self.r['build_partial'] = {'result_sha256':
                                            sha(self.root/'gufo-build-result.json')}

    def build_modern(self):
        if self.m.get('stack') != 'rocm10-fedora43':
            raise ValueError('Modern build requires the explicit ROCm 10 stack')
        label = self.m.get('build_label')
        commit = self.m.get('source_commit')
        if (type(label) is not str or
                not re.fullmatch(r'rocm10-point-modern-r[1-9][0-9]*', label) or
                type(commit) is not str or not re.fullmatch(r'[0-9a-f]{7,40}', commit)):
            raise ValueError('Modern build label and source commit required')
        source = checked_path(BASE/'rocm10-fedora-161'/('source-'+label.removeprefix('rocm10-point-')))
        archive = checked_path(source.with_suffix('.tar.gz'))
        if sha(archive) != self.m.get('source_archive_sha256'):
            raise ValueError('Modern source archive drift')
        inventory = checked_path(source/'SOURCE-FILES.sha256')
        if sha(inventory) != self.m.get('source_files_sha256'):
            raise ValueError('Modern source inventory drift')
        listed = set()
        for line in inventory.read_text().splitlines():
            digest, separator, name = line.partition('  ')
            if (separator != '  ' or not re.fullmatch(r'[0-9a-f]{64}', digest) or
                    not name.startswith('./') or '..' in Path(name).parts or
                    name[2:] in listed):
                raise ValueError('Invalid modern source inventory')
            relative = name[2:]
            path = checked_path(source/relative)
            if not path.is_file() or sha(path) != digest:
                raise ValueError('Modern source file drift: '+relative)
            listed.add(relative)
        actual = {str(path.relative_to(source)) for path in source.rglob('*')
                  if path.is_file() or path.is_symlink()}
        if actual != listed | {'SOURCE-FILES.sha256'}:
            raise ValueError('Modern source inventory incomplete')
        helper = checked_path(source/'cmake/point/Build.cmake')
        if sha(helper) != self.m.get('compile_helper_sha256'):
            raise ValueError('Modern compile helper drift')
        if (source/'SOURCE-COMMIT.txt').read_text().strip() != commit:
            raise ValueError('Modern source commit mismatch')
        image, rocm = self.image_and_rocm()
        if rocm is not None:
            raise ValueError('Unexpected ROCm runtime override')
        for directory in ('build', 'evidence'):
            (source/directory).mkdir(exist_ok=True)
        for directory in ('tmp', 'home'):
            (source/'build'/directory).mkdir(exist_ok=True)
        argv = ['docker', 'create', '--network', 'none', '--read-only',
                '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                '--user', f'{os.getuid()}:{os.getgid()}', '--pids-limit', '512',
                '--cpus', '2', '--memory', '16g',
                '--label', 'synapse-lie.run='+str(self.root),
                '--mount', 'type=bind,src='+str(source)+',dst=/source',
                '--workdir', '/source', '--env', 'LC_ALL=C',
                '--env', 'HOME=/source/build/home', '--env', 'TMPDIR=/source/build/tmp',
                '--env', 'LIE_ROCM10_BUILD_WINDOW=admitted',
                '--env', 'ROCR_VISIBLE_DEVICES=-1', '--env', 'HIP_VISIBLE_DEVICES=-1',
                '--entrypoint', '/usr/bin/cmake', image,
                '-DLABEL='+label, '-DSOURCE_COMMIT='+commit,
                '-P', 'cmake/point/Build.cmake']
        self.execute_container(argv, 7200)
        receipt = checked_path(source/'evidence'/f'{label}-compile'/'result.json')
        result = json.loads(receipt.read_text())
        if (result.get('state') != 'BUILT_NOT_GPU_TESTED' or
                result.get('exit_code') != 0 or
                result.get('source_commit') != commit or
                result.get('label') != label or
                result.get('hip_architecture') != 'gfx1150' or
                result.get('checkpoint_compression') is not True):
            raise RuntimeError('Incomplete modern ROCm 10 build receipt')
        expected = {'synapse-lie-server', 'synapse-lie-bench',
                    'synapse-lie-bench-gufo-reference', 'lie-hip-probe'}
        if set(result.get('binaries', {})) != expected:
            raise RuntimeError('Modern binary inventory mismatch')
        for name, digest in result['binaries'].items():
            if sha(checked_path(source/'build'/f'{label}-runtime'/name)) != digest:
                raise RuntimeError('Modern binary drift: '+name)
        self.r['build_result'] = result
        self.record()
    def image_build(self):
        stack = self.m.get('stack')
        if stack == 'rocm10-fedora44-rpm':
            context, tag = ROCM10_RPM_CONTEXT, ROCM10_RPM_TAG
            expected_files = ['Dockerfile']
        elif stack == 'rocm10-almalinux10-rpm':
            context, tag = ROCM10_ALMA_CONTEXT, ROCM10_ALMA_TAG
            expected_files = ['Dockerfile', 'hip-smoke.cpp']
        else:
            raise ValueError('Image build requires an explicit ROCm 10 RPM stack')
        context = checked_path(context)
        dockerfile = checked_path(context/'Dockerfile')
        if sha(dockerfile) != self.m.get('dockerfile_sha256'):
            raise ValueError('RPM Dockerfile drift')
        if sorted(path.name for path in context.iterdir()) != expected_files:
            raise ValueError('Unexpected RPM build context contents')
        if stack == 'rocm10-almalinux10-rpm' and sha(context/'hip-smoke.cpp') != self.m.get('hip_smoke_sha256'):
            raise ValueError('Native HIP smoke source drift')
        self.sample()
        argv = ['docker', 'build', '--no-cache', '--pull', '--progress=plain',
                '--tag', tag, '--file', str(dockerfile), str(context)]
        self.r['image_build_argv'] = argv
        self.record()
        with (self.root/'image-build.log').open('xb') as log:
            self.child = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT)
            self.r['child_pid'], self.r['child_start_ticks'] = self.child.pid, ticks(self.child.pid)
            self.r['state'] = 'BUILDING_IMAGE'
            self.record()
            deadline = time.monotonic()+7200
            while self.child.poll() is None:
                self.sample()
                if time.monotonic() >= deadline: raise RuntimeError('Image build deadline')
                time.sleep(1)
            self.r['child_exit_code'] = self.child.returncode
        if self.child.returncode:
            raise RuntimeError('RPM image build failed; see retained image-build.log')
        inspected = json.loads(self.command(['docker', 'image', 'inspect', tag,
                                             '--format', '{{json .}}']).stdout)
        if inspected['Architecture'] != 'amd64' or not re.fullmatch(r'sha256:[0-9a-f]{64}', inspected['Id']):
            raise RuntimeError('Unexpected RPM image identity')
        self.r['image_build_result'] = {'tag': tag, 'id': inspected['Id'],
                                        'architecture': inspected['Architecture']}
        self.record()
    def diagnostic(self):
        self.image_and_rocm()
        implementation = self.m.get('diagnostic_impl', 'ctypes')
        if implementation == 'ctypes':
            command = ['/usr/bin/python3', '-B', '/bundle/runtime/hip-diag.py']
        elif implementation == 'native' and self.m.get('stack') == 'rocm10-almalinux10-rpm':
            command = ['/opt/lie/hip-smoke']
        else:
            raise ValueError('Unsupported HIP diagnostic implementation')
        self.r['diagnostic_impl'] = implementation
        self.run_container(command, self.m['bundle'], 60)
        result = json.loads((self.root/'stdout.log').read_text())
        if result.get('scope') != 'GPU_RUNTIME_DIAGNOSTIC_NO_MODEL' or not isinstance(result.get('steps'), list):
            raise RuntimeError('Malformed GPU diagnostic result')
        self.r['diagnostic'] = result
        self.record()
        if (result.get('device_count') != 1 or
                any(step['code'] != 0 for step in result['steps']) or
                result.get('output') != [1, 3, 2, 4, 5, 7, 6, 8]):
            raise RuntimeError('GPU diagnostic reported HIP errors')
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
    def staging_identity_matches(self, current, staged):
        if all(current[k] == staged[k] for k in current):
            return True
        b = self.staging_rebind
        # Device numbers can change across boots. Rebind only an explicitly
        # named old/new pair on the witnessed filesystem; preserve the pinned
        # SOURCE.json and every other stat field. Postflight compares the exact
        # new identity, so no exception applies to changes during a window.
        if (b is None or staged['device'] != b['previous_device'] or
                current['device'] != b['current_device'] or
                any(current[k] != staged[k] for k in current if k != 'device')):
            return False
        if Path('/proc/sys/kernel/random/boot_id').read_text().strip() != b['boot_id']:
            raise RuntimeError('Staging filesystem rebind boot mismatch')
        mount = json.loads(self.command(['findmnt', '--json', '--target', current['path'],
                                        '--output', 'UUID']).stdout)
        if mount.get('filesystems') != [{'uuid': b['filesystem_uuid']}]:
            raise RuntimeError('Staging filesystem rebind UUID mismatch')
        self.r['staging_filesystem_rebind'] = dict(b)
        return True
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
            if staged['sha256'] != expected['sha256'] or not self.staging_identity_matches(current, staged):
                raise RuntimeError('Model identity drift before launch')
            rows.append(current)
        self.r['models_before'] = rows
        return model, rows
    def verified_predictor(self):
        plan = self.m['predictor_plan']
        directory = checked_path(plan['destination'])
        source = json.loads((directory/'SOURCE.json').read_text())
        if source['result']['state'] != 'VERIFIED' or source['plan'] != plan or len(plan['files']) != 1:
            raise RuntimeError('Pinned predictor staging receipt mismatch')
        expected, staged = plan['files'][0], source['result']['files'][0]
        path = checked_path(directory/expected['name'])
        st = path.stat()
        current = {'path': str(path), 'bytes': st.st_size, 'device': st.st_dev,
                   'inode': st.st_ino, 'mtime_ns': st.st_mtime_ns, 'ctime_ns': st.st_ctime_ns}
        if (staged.get('sha256') != expected['sha256'] or
                not self.staging_identity_matches(current, staged)):
            raise RuntimeError('Predictor identity drift before launch')
        return path, current
    def verified_projector(self):
        plan = self.m['projector_plan']
        directory = checked_path(plan['destination'])
        source = json.loads((directory/'SOURCE.json').read_text())
        if source['result']['state'] != 'VERIFIED' or source['plan'] != plan or len(plan['files']) != 1:
            raise RuntimeError('Pinned projector staging receipt mismatch')
        expected, staged = plan['files'][0], source['result']['files'][0]
        path = checked_path(directory/expected['name'])
        st = path.stat()
        current = {'path': str(path), 'bytes': st.st_size, 'device': st.st_dev,
                   'inode': st.st_ino, 'mtime_ns': st.st_mtime_ns, 'ctime_ns': st.st_ctime_ns}
        if (staged.get('sha256') != expected['sha256'] or
                not self.staging_identity_matches(current, staged)):
            raise RuntimeError('Projector identity drift before launch')
        return path, current
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
        if profile == 'modern-http-depth':
            return self.modern_http_depth_gate()
        if profile == 'modern-http-multi':
            return self.modern_http_multi_gate()
        if profile == 'modern-http':
            return self.modern_http_gate()
        if profile == 'modern-core-ssd-restart':
            return self.modern_ssd_restart_gate()
        if profile == 'modern-core-vision':
            return self.modern_vision_bench()
        if profile in ('modern-core', 'modern-core-ram', 'modern-core-ssd', 'modern-core-reactive-probe'):
            return self.modern_core_bench()
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
    def modern_core_bench(self):
        if self.m.get('stack') != 'rocm10-fedora43' or self.m.get('transport') != 'distrobox':
            raise ValueError('Modern core benchmark requires ROCm 10 Distrobox')
        profile = self.m.get('bench_profile')
        ram_cache = profile == 'modern-core-ram'
        ssd_cache = profile == 'modern-core-ssd'
        reactive_probe = profile == 'modern-core-reactive-probe'
        progress_ms = self.m.get('progress_interval_ms', 0)
        if (type(progress_ms) is not int or
                (progress_ms != 0 and not 100 <= progress_ms <= 60000) or
                (reactive_probe and progress_ms)):
            raise ValueError('Core progress interval must be zero or 100..60000 ms, outside reactive probes')
        mode = self.m.get('decode_mode')
        if mode not in ('ar', 'mtp'):
            raise ValueError('Modern core benchmark mode must be ar or mtp')
        if (type(self.m.get('mtp_draft_tokens', 7)) is not int or
                not 1 <= self.m.get('mtp_draft_tokens', 7) <= 7):
            raise ValueError('Modern core predictor draft bound must be 1..7')
        settings = self.m.get('settings')
        rope = self.m.get('rope_scaling', 'native')
        if rope not in ('native', 'yarn2', 'yarn4'):
            raise ValueError('Invalid explicit static RoPE profile')
        context_limit = {'native':262144, 'yarn2':524288, 'yarn4':1048576}[rope]
        timeout_seconds = self.m.get('core_timeout_seconds', 3600)
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 86400:
            raise ValueError('Core deadline must be 1..86400 seconds')
        if (type(settings) is not dict or set(settings) !=
                {'context', 'chunk', 'users', 'tg', 'warmups', 'repetitions'} or
                any(type(value) is not int for value in settings.values()) or
                not 4096 <= settings['context'] <= context_limit or
                settings['chunk'] not in (256, 512, 1024, 2048) or
                settings['users'] not in (1, 2, 4) or settings['tg'] not in (32, 128) or
                settings['warmups'] not in (0, 1) or not 1 <= settings['repetitions'] <= 3):
            raise ValueError('Invalid bounded modern core settings')
        generation = (core_generation(self.m['generation']) if 'generation' in self.m
                      else core_generation(None, historical=True))
        eos_policy = self.m.get('eos_policy', 'stop')
        if type(eos_policy) is not str or eos_policy not in ('stop', 'ignore'):
            raise ValueError('Invalid core EOS policy')
        if eos_policy == 'ignore' and reactive_probe:
            raise ValueError('Reactive probe retains natural EOS')
        if (ram_cache or ssd_cache) and (settings['users'] != 1 or settings['warmups'] != 1 or
                                         settings['repetitions'] != 1):
            raise ValueError('Modern cache gate requires C1, one warmup and one measured run')
        if reactive_probe and (settings['users'] != 2 or settings['warmups'] != 0 or
                               settings['repetitions'] != 1):
            raise ValueError('Direct reactive gate requires C2, no warmup and one probe')
        tokens = checked_path(self.root/'tokens.json')
        if sha(tokens) != self.m.get('tokens_sha256'):
            raise ValueError('Physical prompt token file drift')
        prompt = json.loads(tokens.read_text())
        if (type(prompt) is not list or
                len(prompt) != self.m.get('prompt_tokens_expected') or
                not 1 <= len(prompt) <= settings['context']-settings['tg'] or
                any(type(token) is not int or token < 0 or token > 2147483647 for token in prompt)):
            raise ValueError('Invalid bounded physical prompt')
        model, rows = self.verified_model()
        predictor = None
        if mode == 'mtp':
            predictor, witness = self.verified_predictor()
            rows.append(witness)
        elif 'predictor_plan' in self.m:
            raise ValueError('AR benchmark must not admit a predictor')
        if ssd_cache:
            (self.root/'kv').mkdir(mode=0o700)
        command = ['/bundle/runtime/bin/synapse-lie-bench', '--suite', 'core',
                   '--model', '/model/'+self.m['model_plan']['files'][0]['name'],
                   '--tokens-file', '/work/tokens.json', '--output', '/work/measurements.jsonl',
                   '--kv-cache-ram-mb', '4096' if ram_cache else '0',
                   '--kv-cache-policy', 'ds4', '--timeout-ms', str(timeout_seconds * 1000)]
        if rope != 'native':
            command.extend(('--rope-scaling', rope))
        if progress_ms:
            command.extend(('--progress-ms', str(progress_ms)))
        if eos_policy == 'ignore':
            command.append('--ignore-eos')
        if reactive_probe:
            command.append('--reactive-probe')
        if ssd_cache:
            command.extend(('--kv-disk-dir', '/work/kv', '--kv-disk-space-mb', '4096',
                            '--kv-disk-staging-mb', '512'))
        for key in ('context', 'chunk', 'users', 'tg', 'warmups', 'repetitions'):
            command.extend(('--'+key, str(settings[key])))
        if 'generation' in self.m:
            for key, value in generation.items():
                if key != 'seed' or value >= 0:
                    command.extend(('--'+key.replace('_','-'), str(value)))
        if predictor:
            command.extend(('--model-mtp', '/mtp/'+predictor.name,
                            '--mtp-draft-tokens', str(self.m.get('mtp_draft_tokens', 7))))
        self.r['bench_command'] = command
        self.record()
        try:
            self.run_container(command, self.m['bundle'], timeout_seconds, model)
            measurements = [json.loads(line) for line in (self.root/'measurements.jsonl').read_text().splitlines()]
            if not measurements or measurements[-1] != {'event': 'complete', 'exit_code': 0}:
                raise RuntimeError('Incomplete modern core benchmark')
            identity = measurements[0]
            if (identity.get('schema') != 'synapse-lie.core-bench.v1' or
                    identity.get('mode') != mode or identity.get('synthetic') or
                    identity.get('build_id') != self.m.get('runtime_build_id') or
                    identity.get('rope_scaling', 'native') != rope or
                    type(identity.get('eos_policy', 'stop')) is not str or
                    identity.get('eos_policy', 'stop') != eos_policy or
                    type(identity.get('progress_interval_ms', 0)) is not int or
                    identity.get('progress_interval_ms', 0) != progress_ms or
                identity.get('cache_policy') != ('ram' if ram_cache else 'ssd' if ssd_cache else 'off') or
                identity.get('reactive_probe', False) != reactive_probe):
                raise RuntimeError('Unexpected modern core benchmark identity')
            try:
                if 'generation' in identity and identity['generation'] is None:
                    raise ValueError('Explicitly null sampling identity')
                actual_generation = core_generation(identity.get('generation'), historical=True)
            except ValueError as exc:
                raise RuntimeError('Malformed modern core sampling identity') from exc
            if actual_generation != generation:
                raise RuntimeError('Unexpected modern core sampling identity')
            jobs = [row for row in measurements if row.get('event') == 'job']
            samples = [row for row in measurements if row.get('event') == 'sample']
            if reactive_probe:
                reactive = [row for row in measurements if row.get('event') == 'reactive']
                if (len(reactive) != 1 or jobs or samples or
                    reactive[0].get('scope') != 'direct-c-core-held-loan-peer-cancel' or
                    reactive[0].get('synthetic') is not False or
                    reactive[0].get('peer_output_tokens') != settings['tg'] or
                    not 0 < reactive[0].get('held_output_tokens', 0) < settings['tg'] or
                    reactive[0].get('held_borrowed_tokens', 0) < 1 or
                    reactive[0].get('held_output_blocked') != 1 or
                    reactive[0].get('completed_delta') != 1 or
                    reactive[0].get('cancelled_delta') != 1 or
                    reactive[0].get('decode_batches_delta', 0) < 1 or
                    (mode == 'mtp' and reactive[0].get('mtp_accepted_delta', 0) < 1) or
                    (mode == 'ar' and (reactive[0].get('mtp_drafted_delta') or
                                       reactive[0].get('mtp_accepted_delta')))):
                    raise RuntimeError('Incomplete direct reactive GPU probe')
                self.r['bench_result'] = {'profile': profile, 'mode': mode,
                                          'eos_policy': eos_policy,
                                          'generation': generation,
                                          'reactive': reactive[0],
                                          'measurements_sha256': sha(self.root/'measurements.jsonl')}
                return
            if (len(jobs) != settings['users']*(settings['warmups']+settings['repetitions']) or
                    len(samples) != settings['warmups']+settings['repetitions'] or
                    any(row.get('prompt_tokens') != len(prompt) or
                        row.get('output_tokens') != settings['tg'] or
                        (eos_policy == 'ignore' and row.get('finish') != 'length') for row in jobs)):
                raise RuntimeError('Incomplete modern core output')
            drafted = sum(row.get('mtp_drafted_tokens', 0) for row in jobs)
            accepted = sum(row.get('mtp_accepted_tokens', 0) for row in jobs)
            if ((mode == 'mtp' and (drafted <= 0 or accepted <= 0)) or
                    (mode == 'ar' and (drafted or accepted))):
                raise RuntimeError('Modern core decode mode did not execute as requested')
            if ram_cache and (any(row.get('cached_tokens', 0) for row in jobs if row.get('warmup')) or
                              not any(row.get('cached_tokens', 0) > 0 for row in jobs if not row.get('warmup')) or
                              not any(row.get('cache_hits', 0) > 0 for row in samples if not row.get('warmup'))):
                raise RuntimeError('Modern RAM cache gate did not restore a measured prefix')
            if ssd_cache and (any(row.get('ssd_cached_tokens', 0) for row in jobs if row.get('warmup')) or
                              not any(row.get('ssd_cached_tokens', 0) > 0 for row in jobs if not row.get('warmup')) or
                              not any(row.get('ssd_hits', 0) > 0 for row in samples if not row.get('warmup')) or
                              any(row.get('ssd_errors', 0) for row in samples)):
                raise RuntimeError('Modern SSD cache gate did not restore a measured prefix')
            progress_result = (validate_core_progress(self.root/'distrobox.stderr.log', jobs, settings)
                               if progress_ms else None)
            self.r['bench_result'] = {'profile': profile, 'mode': mode,
                                      'eos_policy': eos_policy,
                                      'generation': generation,
                                      'jobs': len(jobs), 'samples': len(samples),
                                      'drafted': drafted, 'accepted': accepted,
                                      'measured_cached_tokens': sum(row.get('cached_tokens', 0) for row in jobs if not row.get('warmup')),
                                      'measured_cache_hits': sum(row.get('cache_hits', 0) for row in samples if not row.get('warmup')),
                                      'measured_ssd_cached_tokens': sum(row.get('ssd_cached_tokens', 0) for row in jobs if not row.get('warmup')),
                                      'measured_ssd_hits': sum(row.get('ssd_hits', 0) for row in samples if not row.get('warmup')),
                                      'measurements_sha256': sha(self.root/'measurements.jsonl')}
            if progress_result is not None:
                self.r['bench_result']['progress'] = progress_result
        finally:
            if (self.root/'measurements.jsonl').exists():
                self.r['bench_partial'] = {'measurements_sha256': sha(self.root/'measurements.jsonl'),
                                           'bytes': (self.root/'measurements.jsonl').stat().st_size}
            self.check_model_after(rows)
    def modern_vision_bench(self):
        if self.m.get('stack') != 'rocm10-fedora43' or self.m.get('transport') != 'distrobox':
            raise ValueError('Modern vision benchmark requires ROCm 10 Distrobox')
        mode = self.m.get('decode_mode')
        if mode not in ('ar', 'mtp'):
            raise ValueError('Modern vision mode must be ar or mtp')
        settings = self.m.get('settings')
        if settings != {'context':8192,'chunk':2048,'users':1,'tg':32,
                        'warmups':0,'repetitions':1}:
            raise ValueError('Expected bounded modern vision C1 settings')
        image = vision_fixture_png()
        prompt = VISION_PROMPT.encode()
        if (hashlib.sha256(image).hexdigest() != self.m.get('vision_fixture_sha256') or
                hashlib.sha256(prompt).hexdigest() != self.m.get('vision_prompt_sha256')):
            raise ValueError('Vision fixture or prompt identity mismatch')
        image_path = self.root/'image.png'
        prompt_path = self.root/'prompt.txt'
        with image_path.open('xb') as output: output.write(image)
        with prompt_path.open('xb') as output: output.write(prompt)
        model, rows = self.verified_model()
        projector, witness = self.verified_projector()
        rows.append(witness)
        predictor = None
        if mode == 'mtp':
            predictor, witness = self.verified_predictor()
            rows.append(witness)
        elif 'predictor_plan' in self.m:
            raise ValueError('AR vision benchmark must not admit a predictor')
        command = ['/bundle/runtime/bin/synapse-lie-bench', '--suite', 'core',
                   '--model', '/model/'+self.m['model_plan']['files'][0]['name'],
                   '--model-vision', '/vision/'+projector.name,
                   '--image-file', '/work/image.png', '--prompt-file', '/work/prompt.txt',
                   '--output', '/work/measurements.jsonl', '--kv-cache-ram-mb', '0',
                   '--timeout-ms', '3600000']
        for key in ('context', 'chunk', 'users', 'tg', 'warmups', 'repetitions'):
            command.extend(('--'+key, str(settings[key])))
        if predictor:
            command.extend(('--model-mtp', '/mtp/'+predictor.name,
                            '--mtp-draft-tokens', str(self.m.get('mtp_draft_tokens', 7))))
        self.r['bench_command'] = command
        self.record()
        try:
            self.run_container(command, self.m['bundle'], 3600, model)
            measurements = [json.loads(line) for line in (self.root/'measurements.jsonl').read_text().splitlines()]
            if not measurements or measurements[-1] != {'event':'complete','exit_code':0}:
                raise RuntimeError('Incomplete modern vision benchmark')
            identity = measurements[0]
            if (identity.get('schema') != 'synapse-lie.core-bench.v1' or
                    identity.get('mode') != ('mtp+vision' if predictor else 'vision') or
                    identity.get('synthetic') is not False or
                    identity.get('input_kind') != 'messages-with-image' or
                    identity.get('image_sha256') != self.m['vision_fixture_sha256'] or
                    identity.get('vision_model') != '/vision/'+projector.name or
                    identity.get('cache_policy') != 'off' or
                    identity.get('build_id') != self.m.get('runtime_build_id')):
                raise RuntimeError('Unexpected modern vision benchmark identity')
            inputs = [row for row in measurements if row.get('event') == 'input']
            jobs = [row for row in measurements if row.get('event') == 'job']
            samples = [row for row in measurements if row.get('event') == 'sample']
            if (len(inputs) != 1 or len(jobs) != 1 or len(samples) != 1 or
                    inputs[0].get('prompt_tokens', 0) < 1 or
                    not 0 < jobs[0].get('output_tokens', 0) <= settings['tg'] or
                    jobs[0].get('prefill_tokens', 0) < 1 or
                    len(jobs[0].get('output_ids', [])) != jobs[0]['output_tokens'] or
                    (mode == 'mtp' and jobs[0].get('mtp_accepted_tokens', 0) < 1) or
                    (mode == 'ar' and (jobs[0].get('mtp_drafted_tokens') or
                                       jobs[0].get('mtp_accepted_tokens')))):
                raise RuntimeError('Incomplete original-weight vision output')
            self.r['bench_result'] = {'profile':'modern-core-vision','mode':mode,
                                      'prompt_tokens':inputs[0]['prompt_tokens'],
                                      'physical_ids_sha256':inputs[0]['physical_ids_sha256'],
                                      'output_ids':jobs[0]['output_ids'],
                                      'output_tokens':jobs[0]['output_tokens'],
                                      'mtp_accepted_tokens':jobs[0].get('mtp_accepted_tokens', 0),
                                      'measurements_sha256':sha(self.root/'measurements.jsonl')}
        finally:
            if (self.root/'measurements.jsonl').exists():
                self.r['bench_partial'] = {'measurements_sha256':sha(self.root/'measurements.jsonl'),
                                           'bytes':(self.root/'measurements.jsonl').stat().st_size}
            self.check_model_after(rows)
    def modern_http_gate(self):
        if self.m.get('stack') != 'rocm10-fedora43' or self.m.get('transport') != 'distrobox':
            raise ValueError('Modern HTTP gate requires ROCm 10 Distrobox')
        mode = self.m.get('decode_mode')
        if mode not in ('ar', 'mtp'):
            raise ValueError('Modern HTTP mode must be ar or mtp')
        helper = checked_path(self.root/'http-gate.py')
        if sha(helper) != self.m.get('http_gate_sha256'):
            raise ValueError('Modern HTTP helper drift')
        model, rows = self.verified_model()
        predictor = None
        if mode == 'mtp':
            predictor, witness = self.verified_predictor()
            rows.append(witness)
        elif 'predictor_plan' in self.m:
            raise ValueError('AR HTTP gate must not admit a predictor')
        command = ['/usr/bin/python3', '-B', '/work/http-gate.py',
                   '/bundle/runtime/bin/synapse-lie-server',
                   '/model/'+self.m['model_plan']['files'][0]['name'], mode]
        if predictor:
            command.append('/mtp/'+predictor.name)
        if self.m.get('http_tool_gate', False):
            command.append('--tools')
        check_controls = self.m.get('http_control_gate', False)
        if type(check_controls) is not bool:
            raise ValueError('HTTP control gate requires a boolean selection')
        if check_controls:
            controls = checked_path(self.root/'http-controls.py')
            if sha(controls) != self.m.get('http_controls_sha256'):
                raise ValueError('Modern HTTP controls helper drift')
            command.append('--controls')
        self.r['bench_command'] = command
        self.record()
        try:
            self.run_container(command, self.m['bundle'], 1200, model)
            result = json.loads((self.root/'http-result.json').read_text())
            required = {'models', 'chat_json', 'chat_sse', 'responses_json', 'responses_sse'}
            if self.m.get('http_tool_gate', False):
                required |= {'chat_function_json', 'chat_function_sse', 'chat_tool_result',
                             'responses_function_json', 'responses_function_sse',
                             'responses_tool_replay', 'responses_tool_result', 'allowed_tools'}
            if check_controls:
                required |= HTTP_CONTROL_CHECKS
                checked = json.loads((self.root/'http-controls-result.json').read_text())
                if (checked.get('schema') != 'synapse-lie.point-openai-controls.v1' or
                        checked.get('state') != 'PASSED' or
                        set(checked.get('passed', [])) != HTTP_CONTROL_CHECKS or
                        len(checked.get('passed', [])) != len(HTTP_CONTROL_CHECKS)):
                    raise RuntimeError('Incomplete original-weight OpenAI controls')
                self.r['http_controls_sha256'] = sha(self.root/'http-controls-result.json')
            if (result.get('schema') != 'synapse-lie.point-http-original.v1' or
                    result.get('state') != 'PASSED' or result.get('mode') != mode or
                    result.get('server_exit_code') != 0 or
                    set(result.get('passed', [])) != required):
                raise RuntimeError('Incomplete original-weight HTTP gate')
            self.r['http_result'] = {'mode': mode, 'result_sha256': sha(self.root/'http-result.json'),
                                     'passed': result['passed']}
        finally:
            if (self.root/'http-result.json').exists():
                self.r['http_partial'] = {'result_sha256': sha(self.root/'http-result.json')}
            self.check_model_after(rows)
    def modern_http_depth_gate(self):
        if self.m.get('stack') != 'rocm10-fedora43' or self.m.get('transport') != 'distrobox':
            raise ValueError('Modern HTTP depth requires ROCm 10 Distrobox')
        impl, mode = self.m.get('http_impl'), self.m.get('decode_mode')
        size = self.m.get('http_size')
        if (impl not in ('lie', 'gufo') or mode not in ('ar', 'mtp') or
                type(size) is not int or size not in (1500, 8192, 32768, 131072, 258794) or
                self.m.get('http_repetitions') != 2):
            raise ValueError('Invalid bounded HTTP depth profile')
        helper = checked_path(self.root/'http-depth-gate.py')
        if sha(helper) != self.m.get('http_depth_gate_sha256'):
            raise ValueError('HTTP depth helper drift')
        if impl == 'gufo':
            artifacts = self.m['artifacts']
            control = self.m.get('gufo_control')
            bundle = checked_path(Path(self.m['bundle'])/'BUNDLE.json')
            if ('runtime/bin/gufo' not in artifacts or
                    sha(bundle) != artifacts.get('BUNDLE.json') or
                    type(control) is not dict or
                    set(control) != {'upstream_pin', 'upstream_manifest_sha256',
                                     'port_patch_sha256', 'port_build_result_sha256',
                                     'rocwmma_pin', 'rocwmma_files_sha256',
                                     'binary_sha256', 'target'} or
                    control['upstream_pin'] != 'f783fedb9bea2ec7de941f6da4e02f4a4596b29e' or
                    control['rocwmma_pin'] != '48b7db12a9ade97f0b7ab2ff9321ba0cbb4e5b77' or
                    control['target'] != 'gfx1150' or
                    control['binary_sha256'] != artifacts['runtime/bin/gufo'] or
                    json.loads(bundle.read_text()).get('gufo_control') != control):
                raise ValueError('Official Point Gufo control provenance drift')
        model, rows = self.verified_model()
        predictor = None
        if mode == 'mtp':
            predictor, witness = self.verified_predictor()
            rows.append(witness)
        elif 'predictor_plan' in self.m:
            raise ValueError('AR HTTP depth must not admit a predictor')
        command = ['/usr/bin/python3', '-B', '/work/http-depth-gate.py',
                   '--impl', impl, '--mode', mode, '--size', str(size),
                   '--repetitions', '2',
                   '--model', '/model/'+self.m['model_plan']['files'][0]['name'],
                   '--server', '/bundle/runtime/bin/'+
                   ('synapse-lie-server' if impl == 'lie' else 'gufo'),
                   '--client', '/bundle/runtime/bin/synapse-lie-bench']
        if predictor:
            command += ['--predictor', '/mtp/'+predictor.name]
        self.r['bench_command'] = command
        self.record()
        try:
            self.run_container(command, self.m['bundle'], 8200, model)
            result = json.loads((self.root/'http-depth-result.json').read_text())
            measurements = [json.loads(line) for line in
                            (self.root/'measurements.jsonl').read_text().splitlines()]
            if (result.get('schema') != 'synapse-lie.point-http-depth-original.v1' or
                    result.get('state') != 'PASSED' or result.get('client_exit_code') != 0 or
                    result.get('server_exit_code') not in (0, -15) or
                    result.get('implementation') != impl or result.get('mode') != mode or
                    result.get('size') != size or result.get('samples') != 2 or
                    result.get('measurements_sha256') != sha(self.root/'measurements.jsonl') or
                    result.get('requests_sha256') != sha(self.root/'requests.jsonl') or
                    not measurements or measurements[0].get('schema') != 'synapse-lie.http-bench.v1' or
                    measurements[-1] != {'event': 'complete', 'exit_code': 0}):
                raise RuntimeError('Incomplete original-weight HTTP depth comparison')
            self.r['bench_result'] = {'profile': 'modern-http-depth',
                                      'implementation': impl, 'mode': mode,
                                      'size': size, 'samples': 2,
                                      'measurements_sha256': result['measurements_sha256'],
                                      'requests_sha256': result['requests_sha256'],
                                      'result_sha256': sha(self.root/'http-depth-result.json')}
        finally:
            if (self.root/'http-depth-result.json').exists():
                self.r['http_partial'] = {'result_sha256': sha(self.root/'http-depth-result.json')}
            if (self.root/'measurements.jsonl').exists():
                self.r['bench_partial'] = {'measurements_sha256': sha(self.root/'measurements.jsonl'),
                                           'bytes': (self.root/'measurements.jsonl').stat().st_size}
            self.check_model_after(rows)
    def modern_http_multi_gate(self):
        if self.m.get('stack') != 'rocm10-fedora43' or self.m.get('transport') != 'distrobox':
            raise ValueError('Modern HTTP multi requires ROCm 10 Distrobox')
        impl, mode = self.m.get('http_impl'), self.m.get('decode_mode')
        users, case = self.m.get('http_users'), self.m.get('http_case')
        capacity_policy = self.m.get('http_capacity_policy', 'fixed-8')
        server_sessions = 8 if capacity_policy == 'fixed-8' else int(users) if users in ('1', '2', '4', '6', '8') else None
        if (impl not in ('lie', 'gufo') or mode not in ('ar', 'mtp') or
                users not in ('1', '2', '4', '6', '8', '1,2,4,6,8') or
                case not in ('prose', 'repetition') or
                capacity_policy not in ('fixed-8', 'fresh-per-level') or
                (capacity_policy == 'fresh-per-level' and
                 (users == '1,2,4,6,8' or self.m.get('http_server_sessions') != server_sessions)) or
                (capacity_policy == 'fixed-8' and
                 self.m.get('http_server_sessions', 8) != 8) or
                self.m.get('http_warmups') != 1 or self.m.get('http_repetitions') != 3):
            raise ValueError('Invalid fixed prepared HTTP comparison profile')
        helper = checked_path(self.root/'http-multi-gate.py')
        corpus = checked_path(self.root/'corpus.jsonl')
        if (sha(helper) != self.m.get('http_multi_gate_sha256') or
                sha(corpus) != self.m.get('corpus_sha256')):
            raise ValueError('Prepared HTTP helper or corpus drift')
        if impl == 'gufo':
            artifacts = self.m['artifacts']
            control = self.m.get('gufo_control')
            bundle = checked_path(Path(self.m['bundle'])/'BUNDLE.json')
            if ('runtime/bin/gufo' not in artifacts or
                    sha(bundle) != artifacts.get('BUNDLE.json') or
                    type(control) is not dict or
                    set(control) != {'upstream_pin', 'upstream_manifest_sha256',
                                     'port_patch_sha256', 'port_build_result_sha256',
                                     'rocwmma_pin', 'rocwmma_files_sha256',
                                     'binary_sha256', 'target'} or
                    control['upstream_pin'] !=
                    'f783fedb9bea2ec7de941f6da4e02f4a4596b29e' or
                    control['rocwmma_pin'] !=
                    '48b7db12a9ade97f0b7ab2ff9321ba0cbb4e5b77' or
                    control['target'] != 'gfx1150' or
                    control['binary_sha256'] != artifacts['runtime/bin/gufo'] or
                    json.loads(bundle.read_text()).get('gufo_control') != control):
                raise ValueError('Official Point Gufo control provenance drift')
        model, rows = self.verified_model()
        predictor = None
        if mode == 'mtp':
            predictor, witness = self.verified_predictor()
            rows.append(witness)
        elif 'predictor_plan' in self.m:
            raise ValueError('AR HTTP multi must not admit a predictor')
        command = ['/usr/bin/python3', '-B', '/work/http-multi-gate.py',
                   '--impl', impl, '--mode', mode, '--users', users,
                   '--capacity-policy', capacity_policy,
                   '--server-sessions', str(server_sessions),
                   '--warmups', '1', '--repetitions', '3',
                   '--model', '/model/'+self.m['model_plan']['files'][0]['name'],
                   '--server', '/bundle/runtime/bin/'+
                   ('synapse-lie-server' if impl == 'lie' else 'gufo'),
                   '--client', '/bundle/runtime/bin/synapse-lie-bench']
        if predictor:
            command += ['--predictor', '/mtp/'+predictor.name]
        self.r['bench_command'] = command
        self.record()
        try:
            self.run_container(command, self.m['bundle'], 6500, model)
            result = json.loads((self.root/'http-multi-result.json').read_text())
            measurements = [json.loads(line) for line in
                            (self.root/'measurements.jsonl').read_text().splitlines()]
            if (result.get('schema') != 'synapse-lie.point-http-multi-original.v1' or
                    result.get('state') != 'PASSED' or result.get('client_exit_code') != 0 or
                    result.get('server_exit_code') not in (0, -15) or
                    result.get('implementation') != impl or result.get('mode') != mode or
                    result.get('users') != users or
                    result.get('capacity_policy') != capacity_policy or
                    result.get('server_sessions') != server_sessions or
                    result.get('corpus_sha256') != self.m['corpus_sha256'] or
                    result.get('measurements_sha256') != sha(self.root/'measurements.jsonl') or
                    not measurements or measurements[0].get('schema') != 'synapse-lie.http-multi-bench.v1' or
                    measurements[0].get('model') != 'qwen3.8-flash-next' or
                    measurements[-1] != {'event': 'complete', 'exit_code': 0}):
                raise RuntimeError('Incomplete original-weight prepared HTTP comparison')
            self.r['bench_result'] = {'profile': 'modern-http-multi',
                                      'implementation': impl, 'mode': mode,
                                      'case': case, 'users': users,
                                      'capacity_policy': capacity_policy,
                                      'server_sessions': server_sessions,
                                      'cohorts': result['cohorts'],
                                      'measurements_sha256': result['measurements_sha256'],
                                      'result_sha256': sha(self.root/'http-multi-result.json')}
        finally:
            if (self.root/'http-multi-result.json').exists():
                self.r['http_partial'] = {'result_sha256': sha(self.root/'http-multi-result.json')}
            if (self.root/'measurements.jsonl').exists():
                self.r['bench_partial'] = {'measurements_sha256': sha(self.root/'measurements.jsonl'),
                                           'bytes': (self.root/'measurements.jsonl').stat().st_size}
            self.check_model_after(rows)
    def modern_ssd_restart_gate(self):
        if self.m.get('stack') != 'rocm10-fedora43' or self.m.get('transport') != 'distrobox':
            raise ValueError('Modern SSD restart gate requires ROCm 10 Distrobox')
        mode = self.m.get('decode_mode')
        if mode not in ('ar', 'mtp'):
            raise ValueError('Modern SSD restart mode must be ar or mtp')
        helper = checked_path(self.root/'ssd-restart-gate.py')
        tokens = checked_path(self.root/'tokens.json')
        if sha(helper) != self.m.get('ssd_restart_gate_sha256') or sha(tokens) != self.m.get('tokens_sha256'):
            raise ValueError('Modern SSD restart helper or tokens drift')
        prompt = json.loads(tokens.read_text())
        if type(prompt) is not list or len(prompt) != 8192 or any(type(t) is not int or t < 0 or t > 2147483647 for t in prompt):
            raise ValueError('Expected bounded 8192 physical tokens')
        model, rows = self.verified_model()
        predictor = None
        if mode == 'mtp':
            predictor, witness = self.verified_predictor()
            rows.append(witness)
        elif 'predictor_plan' in self.m:
            raise ValueError('AR SSD restart gate must not admit a predictor')
        (self.root/'kv').mkdir(mode=0o700, exist_ok=True)
        command = ['/usr/bin/python3', '-B', '/work/ssd-restart-gate.py',
                   '/bundle/runtime/bin/synapse-lie-bench',
                   '/model/'+self.m['model_plan']['files'][0]['name'], mode]
        if predictor:
            command.append('/mtp/'+predictor.name)
        self.r['bench_command'] = command
        self.record()
        try:
            self.run_container(command, self.m['bundle'], 1500, model)
            result = json.loads((self.root/'ssd-restart-result.json').read_text())
            if (result.get('schema') != 'synapse-lie.point-ssd-restart.v1' or
                    result.get('state') != 'PASSED' or result.get('mode') != mode or
                    result.get('cold_exit_code') != 0 or result.get('hot_exit_code') != 0 or
                    result.get('hot_cached_tokens') != 8192 or result.get('hot_prefill_tokens') != 0 or
                    result.get('hot_ssd_cached_tokens') != 8192 or result.get('hot_ssd_hits', 0) < 1 or
                    result.get('ssd_errors') != 0 or not result.get('output_ids_equal')):
                raise RuntimeError('Incomplete original-weight SSD restart gate')
            self.r['ssd_restart_result'] = {'mode': mode,
                                            'result_sha256': sha(self.root/'ssd-restart-result.json'),
                                            'hot_cached_tokens': result['hot_cached_tokens']}
        finally:
            if (self.root/'ssd-restart-result.json').exists():
                self.r['ssd_restart_partial'] = {'result_sha256': sha(self.root/'ssd-restart-result.json')}
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
        try:
            self.r['postflight_before_restore'] = (
                observe(self.thermal_ceiling_c, gpu_observation_only=True)
                if self.thermal_policy == CPU_GUARD_POLICY else observe(self.thermal_ceiling_c))
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
    if m.get('action') not in ('probe', 'download', 'core', 'bench', 'build', 'diagnostic', 'image-build'): raise SystemExit('Unsupported campaign action')
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
        elif m['action'] == 'image-build': c.image_build()
        elif m['action'] == 'diagnostic': c.diagnostic()
        else: raise ValueError('Unsupported campaign action')
        c.r.update(state='PASSED', exit_code=0)
    except BaseException as ex:
        c.r.update(state='FAILED', error=repr(ex), exit_code=1)
    finally: c.finish()
    print(json.dumps(c.r), flush=True)
    return c.r['exit_code']

if __name__ == '__main__': raise SystemExit(main())
