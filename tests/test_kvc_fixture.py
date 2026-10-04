#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent struct-based wire oracle. Synthetic bytes, NOT-INFERENCE."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile


def fixture(mtp=3, vision=False):
    chunks = [struct.pack('<13I', 0x34565344, 2, 64, 8, 64, 64, 6, 5, 5, 4, 3, 32, 0x51573802),
              struct.pack('<5I', 1, 2, 3, 4, 5), struct.pack('<32f', *[i / 8 for i in range(32)]),
              struct.pack('<I', mtp)]
    def tensor(width, count, salt):
        # Deliberately include arbitrary float bit patterns; codec is lossless.
        chunks.append(bytes((i * 29 + salt) % 256 for i in range(width * count)))
    for layer in range(5):
        if layer < 4 and layer % 2 == 0:
            tensor(4, 2 * 3 * 3, layer + 10)
            tensor(4, 2 * 5, layer + 20)
        else:
            rows = 5 if layer < 4 else mtp
            tensor(2, rows * 4, layer + 30)
            tensor(2, rows * 4, layer + 40)
            tensor(4, rows * 3, layer + 50)
            tensor(2, (rows // 4) * 3, layer + 60)
    tensor(4, 2 * 6, 90)
    chunks += [struct.pack('<8I', 5, 4, 3, 2, 1, 31, 31, 31), struct.pack('<i', -2 if vision else 0)]
    for row in range(5):
        chunks.append(struct.pack('<4I', row, 0 if vision else row, row, 0))
    payload = b''.join(chunks)
    text = b'a\x00bc\xe2\x82\xac'  # Exact length, never strlen or normalized text.
    trailer = b'\xffopaque\x00extension'
    header = struct.pack('<3s5B3IB3x3Q', b'KVC', 1, 4, 6, 15, 5, 5, 7, 64, 2, 123456789, 123456999, len(payload))
    assert len(header) == 48
    return header + struct.pack('<I', len(text)) + text + payload + trailer, text


def main():
    test, cli = map(str, map(Path, sys.argv[1:3]))
    with tempfile.TemporaryDirectory(prefix='lie-kvc-') as temp:
        root = Path(temp)
        raw, text = fixture()
        source, output, shape = root/'fixture.kv', root/'rebuilt.kv', root/'geometry.txt'
        source.write_bytes(raw)
        shape.write_text('4 1 2 1 4 3 2 3 2 5 2 6 32\n')
        subprocess.run([test, str(source), str(output)], check=True)
        assert output.read_bytes() == raw
        def run(*args, code=0):
            p = subprocess.run([cli, *map(str, args)], text=True, capture_output=True)
            assert p.returncode == code, (args, p.returncode, p.stdout, p.stderr)
            return json.loads(p.stdout) if code == 0 else p
        record = run('inspect', source, '--qwen-geometry', shape)
        assert record['qwen_layout_validated'] and not record['inference_qualified']
        assert record['text_positions'] and record['mtp_tokens'] == 3
        assert record['text_key'] == hashlib.sha1(text).hexdigest() + '.kv'
        assert not run('inspect', source)['qwen_layout_validated']
        copy = root/'copy.kv'
        assert run('copy', source, copy, '--qwen-geometry', shape)['copied']
        assert copy.read_bytes() == raw and copy.stat().st_mode & 0o777 == 0o600
        run('copy', source, copy, code=1)
        assert copy.read_bytes() == raw  # Never replaces existing files.
        assert not list(root.glob('*.partial.*'))
        for mtp, vision in [(0, False), (5, True)]:
            source.write_bytes(fixture(mtp, vision)[0])
            record = run('inspect', source, '--qwen-geometry', shape)
            assert record['mtp_tokens'] == mtp and record['text_positions'] == (not vision)
        # Opaque reserved bytes are preserved during file round-trip.
        changed = bytearray(raw)
        changed[5], changed[6], changed[21] = 255, 128, 99
        source.write_bytes(changed)
        opaque = root/'opaque.kv'
        run('copy', source, opaque)
        assert opaque.read_bytes() == changed
        changed[8] = 4  # Envelope/payload frontier disagreement.
        source.write_bytes(changed)
        run('inspect', source, '--qwen-geometry', shape, code=1)
        # All invalid inputs fail without publishing a destination.
        for data in [raw[:51], raw[:70], b'LIEPFX1' + raw[7:]]:
            source.write_bytes(data)
            run('copy', source, root/'bad.kv', code=1)
            assert not (root/'bad.kv').exists()
        source.write_bytes(raw)
        for value in ['0', '-1', '+1', '1x', '18446744073709551616']:
            run('inspect', source, '--max-mib', value, code=2)
        shape.write_text('4 1 2 1 4 3 2 3 2 5 2 6 32 garbage\n')
        run('inspect', source, '--qwen-geometry', shape, code=1)
        fifo = root/'fifo'
        os.mkfifo(fifo)
        run('inspect', fifo, code=1)  # Must not block opening a FIFO.
    print('Independent KVC byte oracle and offline CLI: PASS (NOT-INFERENCE)')


if __name__ == '__main__':
    main()
