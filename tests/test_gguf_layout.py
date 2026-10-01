#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bounded GGUF header inspector: generated storage fixtures, NOT-INFERENCE."""
import hashlib
import importlib.util
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOL = Path(__file__).resolve().parents[1] / 'tools/gguf-layout.py'
spec = importlib.util.spec_from_file_location('lie_gguf_layout', TOOL)
layout = importlib.util.module_from_spec(spec); spec.loader.exec_module(layout)


def string(s):
    b = s.encode() if isinstance(s, str) else s
    return struct.pack('<Q', len(b)) + b


def fixture(tensors=(), metadata=(), version=3, alignment=32, payload_size=0):
    header = b'GGUF' + struct.pack('<IQQ', version, len(tensors), len(metadata))
    for key, kind, value in metadata:
        header += string(key) + struct.pack('<I', kind) + value
    for name, shape, kind, offset in tensors:
        header += string(name) + struct.pack('<I', len(shape))
        header += b''.join(struct.pack('<Q', n) for n in shape) + struct.pack('<IQ', kind, offset)
    data_start = (len(header) + alignment - 1) // alignment * alignment
    return header + b'\xa5' * (data_start-len(header)) + b'\x5a' * payload_size, header


class LayoutTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='lie-gguf-NOT-INFERENCE-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'fixture.gguf'

    def inspect(self, data):
        self.path.write_bytes(data)
        return layout.inspect(self.path)

    def rejects(self, data, message):
        with self.assertRaisesRegex(ValueError, message): self.inspect(data)

    def test_antirez_storage_geometries_not_inference_support(self):
        tensors = [('q2', [256, 2, 3], 10, 0), ('iq2', [256, 2], 16, 512),
                   ('q4', [32, 4], 2, 672), ('bf16', [32], 30, 768)]
        data, header = fixture(tensors, payload_size=832)
        r = self.inspect(data)
        self.assertEqual([t['bytes'] for t in r['tensors']], [504, 132, 72, 64])
        self.assertEqual(r['known_encoded_tensor_bytes'], 772)
        self.assertEqual(r['storage_type_counts'], {'Q2_K': 1, 'IQ2_XXS': 1, 'Q4_0': 1, 'BF16': 1})
        self.assertEqual(r['header_bytes_read'], len(header))
        self.assertEqual(r['header_sha256'], hashlib.sha256(header).hexdigest())
        self.assertFalse(r['tensor_payload_read']); self.assertFalse(r['full_hash_recomputed'])
        self.assertEqual(r['unknown_storage_types'], [])
        self.assertTrue(r['extent_validation_complete']); self.assertFalse(r['inference_support_assessed'])

    def test_exact_header_reads_no_padding_or_tensor_payload(self):
        data, header = fixture([('x', [32], 2, 0)], payload_size=1024)
        self.path.write_bytes(data); real_fdopen = os.fdopen; calls = []
        class Tracking:
            def __init__(self, f): self.f = f
            def __enter__(self): return self
            def __exit__(self, *a): self.f.close()
            def fileno(self): return self.f.fileno()
            def tell(self): return self.f.tell()
            def read(self, n):
                calls.append((self.f.tell(), n))
                if self.f.tell()+n > len(header): raise AssertionError('payload/padding read')
                return self.f.read(n)
        with patch.object(layout.os, 'fdopen', side_effect=lambda *a, **k: Tracking(real_fdopen(*a, **k))):
            r = layout.inspect(self.path)
        self.assertTrue(calls, 'I/O observation must not be vacuous')
        self.assertEqual(sum(n for _, n in calls), len(header))
        self.assertEqual(r['header_bytes_read'], len(header))

    def test_metadata_hashes_and_version_two(self):
        words = ['hello', '🙂']; raw_strings = b''.join(string(s) for s in words)
        raw_floats = struct.pack('<ff', 1.5, -2.25)
        meta = [('general.name', 8, string('Fixture')), ('words', 9, struct.pack('<IQ', 8, 2)+raw_strings),
                ('numbers', 9, struct.pack('<IQ', 6, 2)+raw_floats), ('signed', 5, struct.pack('<i', -3)),
                ('scalar', 12, struct.pack('<d', 1.25)), ('flag', 7, b'\x01')]
        r = self.inspect(fixture(metadata=meta, version=2)[0])
        self.assertEqual(r['version'], 2); self.assertEqual(r['metadata']['general.name']['text'], 'Fixture')
        self.assertEqual(r['metadata']['words']['sha256'], hashlib.sha256(raw_strings).hexdigest())
        self.assertEqual(r['metadata']['numbers']['sha256'], hashlib.sha256(raw_floats).hexdigest())
        self.assertEqual(r['metadata']['signed'], -3); self.assertEqual(r['metadata']['scalar'], 1.25)
        self.assertEqual(r['metadata_types']['signed'], 5); self.assertEqual(r['metadata_types']['flag'], 7)

    def test_unknown_format_is_retained_without_inventing_bytes(self):
        r = self.inspect(fixture([('future', [32], 4242, 0)], payload_size=64)[0])
        self.assertEqual(r['unknown_storage_types'], [4242]); self.assertEqual(r['tensors'][0]['type'], 'UNKNOWN')
        self.assertIsNone(r['tensors'][0]['bytes']); self.assertEqual(r['known_encoded_tensor_bytes'], 0)
        self.assertFalse(r['extent_validation_complete']); self.assertFalse(r['inference_support_assessed'])

    def test_every_truncation_inside_header_is_refused(self):
        data, header = fixture([('x', [32], 8, 0)], metadata=[('x', 8, string('value'))], payload_size=64)
        for n in range(len(header)):
            with self.subTest(length=n): self.rejects(data[:n], 'truncated')

    def test_versions_magic_and_counts(self):
        for data in (b'bad!', b'GGUF'+struct.pack('<IQQ', 1, 0, 0),
                     b'GGUF'+struct.pack('<IQQ', 3, 100001, 0), b'GGUF'+struct.pack('<IQQ', 3, 0, 10001)):
            with self.subTest(data=data): self.rejects(data, 'not GGUF|unsupported GGUF')

    def test_metadata_refusals(self):
        for metadata, message in [([('x', 4, b'\0'*4)]*2, 'duplicate'),
                                  ([('', 4, b'\0'*4)], 'empty'),
                                  ([('x', 99, b'')], 'unknown metadata'),
                                  ([('x', 6, struct.pack('<f', float('nan')))], 'nonfinite'),
                                  ([('x', 12, struct.pack('<d', float('inf')))], 'nonfinite'),
                                  ([('x', 9, struct.pack('<IQ', 9, 0))], 'metadata array'),
                                  ([('x', 9, struct.pack('<IQ', 8, 1000001))], 'metadata array'),
                                  ([('x', 7, b'\x02')], 'boolean')]:
            with self.subTest(metadata=metadata): self.rejects(fixture(metadata=metadata)[0], message)

    def test_tensor_shape_and_names(self):
        for tensors, message in [([('x', [32], 2, 0)]*2, 'tensor name'), ([('', [32], 2, 0)], 'tensor name'),
                                  ([('x', [], 0, 0)], 'dimensions'), ([('x', [1]*9, 0, 0)], 'dimensions'),
                                  ([('x', [0], 0, 0)], 'extent'), ([('x', [2**63, 2], 0, 0)], 'extent'),
                                  ([('x', [33, 32], 2, 0)], 'block-aligned')]:
            with self.subTest(tensors=tensors): self.rejects(fixture(tensors, payload_size=256)[0], message)

    def test_alignment(self):
        for alignment in (0, 3, 2**21):
            self.rejects(fixture(metadata=[('general.alignment', 4, struct.pack('<I', alignment))])[0], 'alignment')
        self.rejects(fixture(metadata=[('general.alignment', 7, b'\x01')])[0], 'alignment')
        self.rejects(fixture([('x', [32], 2, 1)], payload_size=64)[0], 'alignment')
        data, _ = fixture([('x', [32], 2, 64)], [('general.alignment', 4, struct.pack('<I', 64))], alignment=64, payload_size=96)
        self.assertEqual(self.inspect(data)['data_start'] % 64, 0)

    def test_extent_and_overlap(self):
        self.rejects(fixture([('x', [32], 8, 0)], payload_size=33)[0], 'payload extent')
        self.rejects(fixture([('x', [32], 8, 1024)], payload_size=64)[0], 'offset outside')
        self.rejects(fixture([('x', [64], 0, 0), ('y', [32], 0, 32)], payload_size=256)[0], 'overlapping')

    def test_each_declared_geometry(self):
        # Independent GGML row-size expectations; no payload decoding is done.
        expected = {0:(1,4),1:(1,2),2:(32,18),3:(32,20),6:(32,22),7:(32,24),8:(32,34),
                    10:(256,84),11:(256,110),12:(256,144),13:(256,176),14:(256,210),
                    16:(256,66),20:(32,18),30:(1,2),39:(32,17)}
        for kind, (block, size) in expected.items():
            with self.subTest(kind=kind):
                r = self.inspect(fixture([('x',[block,3],kind,0)], payload_size=size*3)[0])
                self.assertEqual(r['known_encoded_tensor_bytes'],size*3)

    def test_mxfp4_rows_are_not_q4_zero_rows(self):
        r = self.inspect(fixture([('down',[640,2],39,0)], payload_size=680)[0])
        self.assertEqual(r['tensors'][0]['type'],'MXFP4')
        self.assertEqual(r['known_encoded_tensor_bytes'],680)
        self.rejects(fixture([('down',[639,2],39,0)], payload_size=680)[0],'block-aligned')
        self.rejects(fixture([('down',[640,2],39,0)], payload_size=679)[0],'payload extent')

    def test_header_bound_without_large_allocation(self):
        data = b'GGUF'+struct.pack('<IQQ', 3, 0, 1)+struct.pack('<Q', layout.LIMIT+1)
        self.rejects(data, 'header limit')
        data, _ = fixture(metadata=[('x', 9, struct.pack('<IQ', 8, 4)+string('x')*4)])
        with patch.object(layout, 'LIMIT', 50): self.rejects(data, 'header limit')

    def test_identity_drift(self):
        data, _ = fixture([('x', [32], 2, 0)], payload_size=32)
        self.path.write_bytes(data); real_stat = Path.stat
        other = self.path.with_name('replacement'); other.write_bytes(data)
        with patch.object(layout.Path, 'stat', side_effect=lambda: real_stat(other)):
            with self.assertRaisesRegex(ValueError, 'identity changed'): layout.inspect(self.path)

    def test_nonregular_fifo_refused_without_blocking(self):
        os.mkfifo(self.path)
        p = subprocess.Popen([sys.executable, '-B', str(TOOL), str(self.path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            try: stdout, stderr = p.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                p.kill(); stdout, stderr = p.communicate(); self.fail('inspector blocked opening FIFO')
            self.assertNotEqual(p.returncode, 0); self.assertIn(b'regular file', stderr); self.assertEqual(stdout, b'')
        finally:
            if p.poll() is None: p.kill(); p.wait()


if __name__ == '__main__': unittest.main()
