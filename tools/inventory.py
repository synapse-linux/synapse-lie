#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only .157 inventory: bounded metadata, never hash tensor payloads/load HIP."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess

D = Path('/home/paperboy/workspace/projects/cachyos/ai/ds4-gufo')
M = Path('/home/paperboy/ds4-tests/gufo-qwen38-38bb39ee/model')
O = Path('/home/paperboy/ds4-launcher/models/gguf')
LIMIT = 24 * 1024 * 1024


def command(argv):
    p = subprocess.run(argv, capture_output=True, text=True, timeout=20)
    return {'argv': argv, 'exit_code': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}


def metadata(path):
    # GGUF v2/v3 little-endian metadata only. Seek/reads cannot reach tensors.
    with path.open('rb') as f:
        def read(n):
            if n < 0 or f.tell() + n > LIMIT:
                raise ValueError('metadata read bound')
            data = f.read(n)
            if len(data) != n:
                raise ValueError('truncated GGUF')
            return data

        def u32(): return struct.unpack('<I', read(4))[0]
        def u64(): return struct.unpack('<Q', read(8))[0]
        def string(): return read(u64())
        widths = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}

        def value(t):
            if t == 8:
                return string()
            if t == 9:
                subtype, count = u32(), u64()
                if count > 1000000 or subtype == 9:
                    raise ValueError('unsupported metadata array')
                if subtype == 8:
                    h = hashlib.sha256()
                    for _ in range(count):
                        s = string(); h.update(struct.pack('<Q', len(s))); h.update(s)
                    return {'element_type': subtype, 'count': count, 'length_prefixed_sha256': h.hexdigest()}
                data = read(count * widths[subtype])
                return {'element_type': subtype, 'count': count, 'raw_sha256': hashlib.sha256(data).hexdigest()}
            raw = read(widths[t])
            if t in (6, 12):
                return struct.unpack('<f' if t == 6 else '<d', raw)[0]
            return int.from_bytes(raw, 'little', signed=t in (1, 3, 5, 11))

        if read(4) != b'GGUF':
            raise ValueError('not GGUF')
        version, tensors, entries = u32(), u64(), u64()
        if version not in (2, 3) or entries > 10000:
            raise ValueError('unsupported GGUF header')
        result = {'version': version, 'tensor_count': tensors, 'metadata_entries': entries, 'selected': {}}
        for _ in range(entries):
            key = string().decode('utf-8'); v = value(u32())
            if key.startswith(('general.', 'tokenizer.', 'split.')) or any(x in key for x in ('context_length', 'rope', 'block_count', 'ssm.')):
                if isinstance(v, bytes):
                    v = {'bytes': len(v), 'sha256': hashlib.sha256(v).hexdigest(), 'text': v.decode('utf-8') if len(v) < 24000 else None}
                result['selected'][key] = v
        result['metadata_bytes_read'] = f.tell()
        return result


def main():
    report = {'schema': 'synapse-lie.inventory.v1', 'time': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'ssh_connection': os.getenv('SSH_CONNECTION'), 'gpu_probe_executed': False,
              'full_weight_hashes_recomputed': False, 'global_gpu_exclusivity_proved': False}
    report['commands'] = [command(a) for a in [
        ['uname', '-srmo'], ['lscpu'], ['df', '-B1', '/home/paperboy', '/tmp'],
        ['ss', '-ltnp'], ['ps', '-eo', 'pid,ppid,user,stat,etime,comm'],
        ['lslocks', '-o', 'PID,COMMAND,PATH'], ['gcc', '--version'],
        ['/opt/rocm/bin/hipcc', '--version'],
        ['pkg-config', '--modversion', 'icu-uc', 'libuv', 'json-c', 'libcurl']]]
    report['os_release'] = Path('/etc/os-release').read_text()
    report['meminfo'] = Path('/proc/meminfo').read_text()
    report['gpu_sysfs'] = {}
    for p in Path('/sys/class/drm').glob('card[0-9]/device/*'):
        if p.name.startswith('mem_info_') or p.name == 'gpu_busy_percent':
            try: report['gpu_sysfs'][str(p)] = p.read_text().strip()
            except OSError: pass
    report['files'] = []
    paths = sorted(M.glob('*.gguf')) + [O / 'Qwen3.8-Flash-Next-Q2.gguf', O / 'Qwen3.8-Flash-Next-Q4.gguf', O / 'mmproj-Qwen3.8-Flash-Next-Q8_0.gguf']
    for p in paths:
        s = p.stat()
        entry = {'path': str(p), 'bytes': s.st_size, 'device': s.st_dev, 'inode': s.st_ino,
                 'mtime_ns': s.st_mtime_ns, 'ctime_ns': s.st_ctime_ns, 'read_only_by_policy': True}
        # Inspect trunk metadata and MTP, not each duplicate split header.
        if '00001-of-' in p.name or 'mtp-' in p.name or p.name.endswith('-Q2.gguf'):
            entry['gguf'] = metadata(p)
            after = p.stat()
            if (s.st_size,s.st_mtime_ns,s.st_ctime_ns) != (after.st_size,after.st_mtime_ns,after.st_ctime_ns):
                raise RuntimeError('model changed during bounded metadata inspection')
        report['files'].append(entry)
    report['historical_receipts'] = {}
    for p in [M.parent / 'DOWNLOAD-RECEIPT.json', D / 'build-native/BUILD-RECEIPT.json',
              D / 'qualification/native-perf-closure-r1/result.json',
              D / 'qualification/native-perf-closure-r1/measurements.json']:
        if p.is_file():
            raw = p.read_bytes()
            doc = json.loads(raw)
            # Evidence only; do not import source files or executable artifacts.
            report['historical_receipts'][str(p)] = {'sha256': hashlib.sha256(raw).hexdigest(),
                'value': {k: v for k, v in doc.items() if k not in ('source_inputs', 'inputs')}}
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
