#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bounded read-only GGUF header/layout inventory. No tensor reads or HIP.
Storage extent is not resident memory: optional tensors and CPU tables differ.
"""
import collections
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import struct
import sys

LIMIT = 24 * 1024 * 1024
# GGML storage geometry, not a declaration of executor/kernel support.
# MXFP4 id/geometry independently checked against official antirez/ds4 c05cd8e2;
# see docs/ANTIREZ-BENCHMARKS.md. No decoder or model forward is imported here.
FORMATS = {0: ('F32', 1, 4), 1: ('F16', 1, 2), 2: ('Q4_0', 32, 18),
           3: ('Q4_1', 32, 20), 6: ('Q5_0', 32, 22), 7: ('Q5_1', 32, 24),
           8: ('Q8_0', 32, 34), 10: ('Q2_K', 256, 84), 11: ('Q3_K', 256, 110),
           12: ('Q4_K', 256, 144), 13: ('Q5_K', 256, 176), 14: ('Q6_K', 256, 210),
           16: ('IQ2_XXS', 256, 66), 20: ('IQ4_NL', 32, 18), 30: ('BF16', 1, 2),
           39: ('MXFP4', 32, 17)}


def identity(s):
    return {'bytes': s.st_size, 'device': s.st_dev, 'inode': s.st_ino,
            'mtime_ns': s.st_mtime_ns, 'ctime_ns': s.st_ctime_ns}


def inspect(path):
    path = Path(path)
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb', buffering=0) as f:
        before = os.fstat(f.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError('GGUF inspection requires a regular file')
        header_hash = hashlib.sha256()

        def read(n):
            if n < 0 or f.tell() + n > LIMIT:
                raise ValueError('bounded GGUF header limit')
            b = f.read(n)
            if len(b) != n:
                raise ValueError('truncated GGUF header')
            header_hash.update(b)
            return b

        def u32(): return struct.unpack('<I', read(4))[0]
        def u64(): return struct.unpack('<Q', read(8))[0]
        def string(): return read(u64())
        widths = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}

        def value(t):
            if t == 8:
                b = string()
                return {'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest(),
                        'text': b.decode('utf-8') if len(b) < 24000 else None}
            if t == 9:
                subtype, count = u32(), u64()
                if count > 1000000 or (subtype != 8 and subtype not in widths):
                    raise ValueError('unsupported metadata array')
                h = hashlib.sha256()
                if subtype == 8:
                    for _ in range(count):
                        b = string()
                        h.update(struct.pack('<Q', len(b)))
                        h.update(b)
                else:
                    h.update(read(count * widths[subtype]))
                return {'element_type': subtype, 'count': count, 'sha256': h.hexdigest()}
            if t not in widths:
                raise ValueError('unknown metadata type')
            b = read(widths[t])
            if t in (6, 12):
                x = struct.unpack('<f' if t == 6 else '<d', b)[0]
                if not math.isfinite(x):
                    raise ValueError('nonfinite metadata')
                return x
            x = int.from_bytes(b, 'little', signed=t in (1, 3, 5, 11))
            if t == 7 and x not in (0, 1):
                raise ValueError('invalid boolean metadata')
            return x

        if read(4) != b'GGUF':
            raise ValueError('not GGUF')
        version, count, entries = u32(), u64(), u64()
        if version not in (2, 3) or count > 100000 or entries > 10000:
            raise ValueError('unsupported GGUF header counts/version')
        meta, meta_types = {}, {}
        for _ in range(entries):
            key = string().decode('utf-8')
            if not key or key in meta:
                raise ValueError('duplicate/empty metadata key')
            kind = u32()
            meta_types[key] = kind
            meta[key] = value(kind)
        table = []
        names = set()
        for _ in range(count):
            name = string().decode('utf-8')
            dims = u32()
            if not name or name in names or not 1 <= dims <= 8:
                raise ValueError('invalid tensor name/dimensions')
            names.add(name)
            shape = [u64() for _ in range(dims)]
            elements = math.prod(shape)
            if not elements or elements > (1 << 64) - 1:
                raise ValueError('invalid tensor extent')
            kind, offset = u32(), u64()
            fmt = FORMATS.get(kind)
            size = None
            if fmt:
                if shape[0] % fmt[1]:
                    raise ValueError('invalid block-aligned row')
                size = elements // fmt[1] * fmt[2]
            table.append({'name': name, 'shape': shape, 'type_id': kind,
                          'type': fmt[0] if fmt else 'UNKNOWN', 'bytes': size, 'offset': offset})
        header_bytes = f.tell()
        alignment = meta.get('general.alignment', 32)
        if (meta_types.get('general.alignment', 4) != 4 or not isinstance(alignment, int) or
                alignment <= 0 or alignment > 1024 * 1024 or alignment & (alignment - 1)):
            raise ValueError('invalid alignment')
        data_start = (header_bytes + alignment - 1) // alignment * alignment
        extents = []
        for t in table:
            start = data_start + t['offset']
            if t['offset'] % alignment or start > before.st_size:
                raise ValueError('tensor offset outside file/alignment')
            if t['bytes'] is not None:
                end = start + t['bytes']
                if end > before.st_size:
                    raise ValueError('tensor payload extent outside file')
                extents.append((start, end))
        extents.sort()
        if any(b[0] < a[1] for a, b in zip(extents, extents[1:])):
            raise ValueError('overlapping tensor extents')
        if identity(before) != identity(os.fstat(f.fileno())) or identity(before) != identity(path.stat()):
            raise ValueError('file identity changed during header read')
        return {'path': str(path), **identity(before), 'allocated_file_bytes': before.st_blocks * 512,
                'version': version, 'metadata': meta, 'metadata_types': meta_types, 'tensor_count': count,
                'header_bytes_read': header_bytes, 'header_sha256': header_hash.hexdigest(),
                'data_start': data_start, 'tensor_payload_read': False, 'full_hash_recomputed': False,
                'inference_support_assessed': False,
                'extent_validation_complete': all(t['bytes'] is not None for t in table),
                'unknown_storage_types': sorted({t['type_id'] for t in table if t['bytes'] is None}),
                'storage_type_counts': dict(collections.Counter(t['type'] for t in table)),
                'known_encoded_tensor_bytes': sum(t['bytes'] or 0 for t in table), 'tensors': table}


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit('Usage: gguf-layout.py MODEL-GGUF [MODEL-GGUF ...]')
    print(json.dumps({'schema': 'synapse-lie.gguf-layout.v1',
                      'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      'gpu_execution': False, 'models': [inspect(p) for p in sys.argv[1:]]}, indent=2))
