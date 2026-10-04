#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent DS4 framing/payload oracle for shared live-state APIs; synthetic."""
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from test_kvc_map_fixture import fixture

with tempfile.TemporaryDirectory(prefix='lie-kvc-state-') as directory:
    p = Path(directory)
    for n in (1, 3, 4, 2048, 2049, 131072):
        record, _ = fixture(n, 2048)
        src, dst = p / f'{n}.kv', p / f'{n}-saved.kv'
        src.write_bytes(record)
        subprocess.run([sys.argv[1], str(src), str(dst)], check=True)
        saved = dst.read_bytes()
        assert saved[:12] == record[:12]
        assert saved[16:32] == record[16:32]
        assert saved[40:len(record)] == record[40:]
        assert saved[len(record):len(record)+17] == b'fixture-extension'
        assert saved[-192:-184] == b'LIEKVC1\0'
        assert struct.unpack_from('<I', saved, 12)[0] == 7
    print('Exact DS4 payloads retained by shared RAM/SSD APIs: PASS (NOT-INFERENCE)')
