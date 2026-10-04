#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only .161 inventory. No HIP initialization or model payload access."""
import datetime
import json
import os
from pathlib import Path
import platform
import shutil

def read(path):
    try:
        return Path(path).read_text().strip()
    except OSError as error:
        return {'unavailable': str(error)}

def main():
    report = {'scope': 'READ_ONLY_NOT_INFERENCE',
              'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'ssh_connection': os.environ.get('SSH_CONNECTION'),
              'uname': list(platform.uname()), 'uid': os.getuid(),
              'memory': read('/proc/meminfo'), 'kfd_clients': [], 'denied_fd_directories': 0,
              'tools': {name: shutil.which(name) for name in ('c++', 'cc', 'cmake', 'ninja', 'hipcc', 'docker')},
              'topology': {}, 'drm': {}, 'sensors': [], 'models': []}
    for path in sorted(Path('/sys/class/kfd/kfd/topology/nodes').glob('*/properties')):
        report['topology'][str(path)] = read(path)
    for card in sorted(Path('/sys/class/drm').glob('card[0-9]*')):
        if '-' in card.name:
            continue
        report['drm'][card.name] = {name: read(card/'device'/name) for name in
            ('gpu_busy_percent', 'mem_info_vram_total', 'mem_info_vram_used',
             'mem_info_gtt_total', 'mem_info_gtt_used')}
    for device in sorted(Path('/sys/class/hwmon').glob('hwmon*')):
        name = read(device/'name')
        for path in sorted(device.glob('temp*_input')):
            report['sensors'].append({'name': name, 'path': str(path), 'millidegrees_c': read(path)})
    for process in Path('/proc').iterdir():
        if not process.name.isdecimal():
            continue
        try:
            fds = list((process/'fd').iterdir())
        except OSError:
            report['denied_fd_directories'] += 1
            continue
        devices = set()
        for fd in fds:
            try:
                target = os.readlink(fd)
            except OSError:
                continue
            if target == '/dev/kfd' or target.startswith('/dev/dri/'):
                devices.add(target)
        if '/dev/kfd' in devices:
            report['kfd_clients'].append({'pid': int(process.name), 'comm': read(process/'comm'),
                'stat': read(process/'stat'), 'cgroup': read(process/'cgroup'), 'devices': sorted(devices)})
    # Known model directories only. Stat filenames; never open GGUF contents.
    for directory in (Path('/home/pop/llama-models'), Path('/home/pop/hf-cache')):
        for path in sorted(directory.glob('*/*.gguf')):
            stat = path.stat()
            report['models'].append({'path': str(path), 'bytes': stat.st_size,
                'device': stat.st_dev, 'inode': stat.st_ino, 'mtime_ns': stat.st_mtime_ns})
    report['gpu_admission'] = 'BLOCKED_FOREIGN_KFD_CLIENT' if report['kfd_clients'] else 'NOT_ACQUIRED'
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
