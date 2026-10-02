#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Tiny in-memory transfer fixtures; no network or model payload."""
import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('download', Path(__file__).resolve().parents[1]/'tools/strix-point-download.py')
download = importlib.util.module_from_spec(spec); spec.loader.exec_module(download)

class Tests(unittest.TestCase):
    def test_publish_verified_content_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/'fixture.gguf'; payload = b'tiny synthetic fixture'
            row = download.transfer(io.BytesIO(payload), target, len(payload), hashlib.sha256(payload).hexdigest(), lambda n: None)
            self.assertEqual(target.read_bytes(), payload)
            self.assertEqual(row['bytes'], len(payload))
            self.assertFalse(target.with_suffix('.gguf.part').exists())
            with self.assertRaises(FileExistsError):
                download.transfer(io.BytesIO(payload), target, len(payload), row['sha256'], lambda n: None)
    def test_bad_length_and_digest_remain_unpublished(self):
        for body, size, digest in ((b'abc', 4, hashlib.sha256(b'abc').hexdigest()),
                                   (b'abcde', 4, hashlib.sha256(b'abcd').hexdigest()),
                                   (b'abcd', 4, '0'*64)):
            with self.subTest(size=size, body=body), tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp)/'fixture.gguf'
                with self.assertRaises(ValueError): download.transfer(io.BytesIO(body), target, size, digest, lambda n: None)
                self.assertFalse(target.exists())
                self.assertTrue(target.with_suffix('.gguf.part').exists())
    def test_existing_partial_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/'fixture.gguf'
            target.with_suffix('.gguf.part').write_bytes(b'prior evidence')
            with self.assertRaises(FileExistsError): download.transfer(io.BytesIO(b'x'), target, 1, '0'*64, lambda n: None)
            self.assertEqual(target.with_suffix('.gguf.part').read_bytes(), b'prior evidence')
    def test_range_resume_and_existing_verification(self):
        payload = b'complete payload'
        row = {'url': 'fixture', 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/'fixture.gguf'; target.with_suffix('.gguf.part').write_bytes(payload[:4])
            def fetch(url, start, end, total):
                self.assertEqual((url, start, end, total), ('fixture', 4, len(payload)-1, len(payload)))
                return payload[start:end+1]
            with patch.object(download, 'fetch_range', fetch):
                download.transfer_ranges(row, target, 2, lambda n: None)
            self.assertEqual(target.read_bytes(), payload)
            with patch.object(download, 'fetch_range', side_effect=AssertionError('No network expected')):
                self.assertTrue(download.transfer_ranges(row, target, 2, lambda n: None)['reverified_existing'])
    def test_corrupt_resume_prefix_is_not_published(self):
        payload = b'abcdef'
        row = {'url': 'fixture', 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/'fixture.gguf'; target.with_suffix('.gguf.part').write_bytes(b'XXX')
            with patch.object(download, 'fetch_range', return_value=b'def'):
                with self.assertRaises(ValueError): download.transfer_ranges(row, target, 2, lambda n: None)
            self.assertFalse(target.exists())

if __name__ == '__main__': unittest.main()
