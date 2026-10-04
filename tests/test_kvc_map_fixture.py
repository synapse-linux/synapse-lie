#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent native and DS4 byte oracles, tiny model geometry; NOT-INFERENCE."""
import struct
import subprocess
import sys
import tempfile
from pathlib import Path


def fixture(n, threshold):
    roles = {}
    pieces = [struct.pack('<13I', 0x34565344, 2, max(64, n), 8, max(64, n), max(64, n),
                          6, n, 5, 4, 3, 32, 0x51573802)]
    tokens = [1 + (i % 30) for i in range(n)]
    if n > 2:
        tokens[-2] = 31  # EOS must not fold stored history.
    def add(role, layer, data):
        roles[role, layer] = data
        pieces.append(data)
    def tensor(role, layer, width, count):
        size = width * count
        pattern = bytes((j * 29 + layer * 7 + role) % 256 for j in range(256))
        add(role, layer, (pattern * ((size + 255) // 256))[:size])
    add(1, 0, struct.pack(f'<{n}I', *tokens))
    add(2, 0, struct.pack('<32f', *[i / 8 for i in range(32)]))
    pieces.append(struct.pack('<I', 0))  # MTP layer exists, no live MTP rows.
    for layer in range(4):
        if layer % 2 == 0:
            tensor(6, layer, 4, 2 * 3 * 3)
            tensor(5, layer, 4, 2 * 5)
        else:
            tensor(3, layer, 2, n * 4)
            tensor(4, layer, 2, n * 4)
            tensor(9, layer, 4, n * 3)
            if n // 4:
                tensor(10, layer, 2, (n // 4) * 3)
    tensor(7, 0, 4, 2 * 6)
    add(8, 0, struct.pack('<8I', *[(tokens[-1-i] if i < n else 31) for i in range(8)]))
    pieces.append(struct.pack('<I', 0))
    pieces.append(b''.join(struct.pack('<4I', i, i, i, 0) for i in range(n)))
    payload = b''.join(pieces)
    outer = struct.pack('<3s5B3IB3x3Q', b'KVC', 1, 4, 1, 0, 5, n, 0, max(64, n), 2, 1, 2, len(payload))
    record = outer + struct.pack('<I', 3) + b'key' + payload
    # Native order differs: global history/PLE first, conv before GDN, aligned.
    result = bytearray()
    def native(data):
        result.extend(b'\0' * (-len(result) % 8))
        result.extend(data)
    native(roles[1, 0])
    native(roles[2, 0])
    native(struct.pack('<2i', *[(tokens[-1-i] if i < n else -1) for i in range(2)]))
    native(roles[7, 0])
    blocks = n // 4 if n > threshold else 0
    for layer in range(4):
        if layer % 2 == 0:
            native(roles[5, layer])
            native(roles[6, layer])
        else:
            native(roles[3, layer])
            native(roles[4, layer])
            if n - blocks * 4:
                native(roles[9, layer][blocks * 4 * 3 * 4:])
            if blocks:
                native(roles[10, layer])
    return record, bytes(result)


def main():
    with tempfile.TemporaryDirectory(prefix='lie-kvc-map-') as temp:
        p = Path(temp)
        cases = [(n, 8, 16) for n in (1, 2, 3, 4, 7, 8, 9, 11, 12)]
        cases += [(n, 2048, 4096) for n in (2047, 2048, 2049, 131072)]
        for n, threshold, ring in cases:
            raw, native = fixture(n, threshold)
            source, oracle, output = p/'input.kv', p/'expected.bin', p/'output.kv'
            source.write_bytes(raw)
            oracle.write_bytes(native)
            subprocess.run([sys.argv[1], str(source), str(oracle), str(output), str(n), str(threshold), str(ring)], check=True)
            assert output.read_bytes() == raw
            output.unlink()
    print('13 independent Qwen wire/native/wire pairs through 128K: PASS (NOT-INFERENCE, tiny geometry)')


if __name__ == '__main__':
    main()
