#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read bounded PLE extent metadata on .157; no payload, cache or policy change."""
import datetime
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys

ROOT = Path('/home/paperboy/workspace/projects/synapse-linux/synapse-lie/run/q2-ple-model-r1')
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'source/tools'))
from gufo.gguf import parse_gguf, tensor_bytes
from q2_process import identity


def main():
    spec = importlib.util.spec_from_file_location('runner', ROOT / 'tools/q2-runner.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    held, leases, files = [], [], []
    try:
        for path, expected in zip(runner.LOCKS, [(52, 3232146), (52, 3206482), (52, 3228451), (55, 45067)]):
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
            held.append(fd)
            st = os.fstat(fd)
            if (st.st_dev, st.st_ino) != expected:
                raise RuntimeError('Unexpected lease identity')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            leases.append({'path': path, 'device': st.st_dev, 'inode': st.st_ino})
        if list(Path('/sys/class/kfd/kfd/proc').glob('[0-9]*')):
            raise RuntimeError('Foreign GPU client before metadata inspection')
        inventory = json.loads((ROOT / 'config/models-157.inventory.json').read_text())['files']
        for entry in inventory:
            path = entry['path']
            if not (path.endswith('/Qwen3.8-Flash-Next-Q2.gguf') or 'Qwen3.8-Flash-Next-UD-Q4_K_XL-' in path):
                continue
            st = os.stat(path)
            if (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns) != (
                    entry['device'], entry['inode'], entry['bytes'], entry['mtime_ns'], entry['ctime_ns']):
                raise RuntimeError('Model identity differs')
            metadata = parse_gguf(path)  # Independently fetched pinned helper, metadata only.
            for tensor in metadata['tensors']:
                if tensor['name'] != 'per_layer_token_embd.weight':
                    continue
                begin = metadata['data_offset'] + tensor['offset']
                size = tensor_bytes(metadata, tensor)
                samples = []
                fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
                try:
                    for part in range(5):
                        offset = (begin + size * (part + 1) // 6) // 4096 * 4096
                        # FIEMAP, flags 0: do not request a filesystem sync.
                        data = bytearray(struct.pack('=QQIIII', offset, 65536, 0, 0, 4, 0) + bytes(4 * 56))
                        fcntl.ioctl(fd, 0xC020660B, data, True)
                        header = struct.unpack_from('=QQIIII', data)
                        extents = []
                        for i in range(header[3]):
                            v = struct.unpack_from('=QQQQQIIII', data, 32 + i * 56)
                            extents.append({'logical': v[0], 'length': v[2], 'flags': v[5],
                                            'encoded': bool(v[5] & 8)})
                        samples.append({'offset': offset, 'extents': extents})
                finally:
                    os.close(fd)
                files.append({'path': path, 'tensor': tensor['name'], 'type': tensor['type_name'],
                              'table_offset': begin, 'table_bytes': size, 'samples': samples})
        if len(files) != 2:
            raise RuntimeError('Expected one PLE table per model')
        print(json.dumps({'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                          'scope': 'Read-only metadata and five 64-KiB FIEMAP windows per PLE table; no payload reads',
                          'kernel': os.uname().release, 'observer': identity(os.getpid()),
                          'leases': leases, 'files': files}))
    finally:
        for fd in reversed(held):
            os.close(fd)


if __name__ == '__main__':
    main()
