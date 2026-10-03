#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Synthetic archive fixtures; never task or model-quality evidence."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

MODULE = Path(__file__).resolve().parents[1] / 'tools/collect-q2-terminal.py'
spec = importlib.util.spec_from_file_location('terminal_collection', MODULE)
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)
LABEL = 'q2-collection-fixture'
COMPLETE = 'TERMINAL_BENCH_COMMAND_COMPLETE_INSPECT_REWARDS'


class Collection(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='q2-collection-')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.remote = self.root / 'remote'
        self.receipt = self.remote / LABEL / 'results/result.json'
        self.receipt.parent.mkdir(parents=True)
        self.receipt.write_text(json.dumps({'state': COMPLETE, 'finished_at': 'fixture',
                                           'mode': 'q2-terminal-full'}))
        self.export = self.remote / 'q2-terminal-bench/benchmark/results/fixture/summary.json'
        self.export.parent.mkdir(parents=True)
        self.export.write_text(json.dumps({'tag': LABEL, 'scope': 'synthetic fixture'}))
        self.job = self.remote / 'q2-terminal-bench/benchmark/jobs' / LABEL / 'trajectory.json'
        self.job.parent.mkdir(parents=True)
        self.job.write_text('synthetic task transcript\n' * 100)

    def remote_bytes(self, mode='q2-terminal-full'):
        output = io.BytesIO()
        with patch.object(collector, 'REMOTE', str(self.remote)), \
                patch.object(sys, 'stdout', Mock(buffer=output)):
            exec(compile(collector.remote_script(LABEL, mode), '<collection fixture>', 'exec'), {})
        return output.getvalue()

    def test_full_cap_does_not_expand_smoke_scope(self):
        member = tarfile.TarInfo('terminal-benchmark/jobs/fixture/trajectory.json')
        archive = Mock()
        archive.getmembers.return_value = [member]
        member.size = 1024**3
        collector.validate_archive(archive, collector.collection_limit('q2-terminal-full'))
        with self.assertRaisesRegex(ValueError, 'Oversized'):
            collector.validate_archive(archive, collector.collection_limit('q2-terminal-smoke'))
        member.size = 2 * 1024**3 + 1000001
        with self.assertRaisesRegex(ValueError, 'Oversized'):
            collector.validate_archive(archive, collector.collection_limit('q2-terminal-full'))
        with self.assertRaisesRegex(ValueError, 'scored Terminal-Bench'):
            collector.collection_limit('cpu')

    def test_archive_paths_links_duplicates_and_negative_sizes_refused(self):
        for name, kind, size in [('../escape', tarfile.REGTYPE, 1),
                                 ('/absolute', tarfile.REGTYPE, 1),
                                 ('', tarfile.REGTYPE, 1),
                                 ('foreign/file', tarfile.REGTYPE, 1),
                                 ('terminal-benchmark/link', tarfile.SYMTYPE, 1),
                                 ('terminal-benchmark/link', tarfile.LNKTYPE, 1),
                                 ('terminal-benchmark/file', tarfile.REGTYPE, -1)]:
            member = tarfile.TarInfo(name)
            member.type, member.size = kind, size
            archive = Mock()
            archive.getmembers.return_value = [member]
            with self.subTest(name=name, kind=kind, size=size), \
                    self.assertRaisesRegex(ValueError, 'Unsafe'):
                collector.validate_archive(archive, 1000)
        member = tarfile.TarInfo('terminal-benchmark/file')
        archive.getmembers.return_value = [member, member]
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            collector.validate_archive(archive, 1000)

    def test_remote_mode_must_match_collected_receipt(self):
        with self.assertRaisesRegex(RuntimeError, 'mode changed'):
            self.remote_bytes('q2-terminal-smoke')

    def test_remote_bound_is_checked_before_hashing(self):
        with patch.object(collector, 'collection_limit', return_value=1), \
                patch.object(hashlib, 'file_digest', side_effect=AssertionError('No hashing')), \
                self.assertRaisesRegex(RuntimeError, 'scope bound'):
            self.remote_bytes()

    def test_remote_refuses_incomplete_campaign(self):
        self.receipt.write_text(json.dumps({'state': 'RUNNING', 'mode': 'q2-terminal-full'}))
        with self.assertRaisesRegex(RuntimeError, 'incomplete'):
            self.remote_bytes()

    def test_remote_exact_tag_and_symlink_guards(self):
        self.export.write_text(json.dumps({'tag': 'q2-foreign'}))
        with self.assertRaisesRegex(RuntimeError, 'exact-tag'):
            self.remote_bytes()
        self.export.write_text(json.dumps({'tag': LABEL}))
        (self.job.parent / 'link').symlink_to(self.job)
        with self.assertRaisesRegex(RuntimeError, 'symlink'):
            self.remote_bytes()

    def test_complete_streamed_round_trip_without_network_or_overwrite(self):
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('No whole-file reads')):
            payload = self.remote_bytes()
        out = self.root / 'evidence' / LABEL
        (out / 'results').mkdir(parents=True)
        (out / 'results/result.json').write_text(self.receipt.read_text())

        def transfer(argv, *, stdout, stderr):
            self.assertEqual(argv[0], 'ssh')
            stdout.write(payload)
            return Mock(returncode=0)

        with patch.object(collector, 'ROOT', self.root), \
                patch.object(sys, 'argv', [str(MODULE), LABEL]), \
                patch.object(collector.subprocess, 'run', side_effect=transfer) as run, \
                patch.object(Path, 'read_bytes', side_effect=AssertionError('No whole-file reads')), \
                contextlib.redirect_stdout(io.StringIO()):
            collector.main()
            self.assertEqual(run.call_count, 1)
            result = json.loads((out / 'terminal-collection.json').read_text())
            self.assertEqual(result['verified_files'], 2)
            self.assertEqual(result['archive_sha256'], hashlib.sha256(payload).hexdigest())
            with self.assertRaisesRegex(ValueError, 'overwrite'):
                collector.main()
            self.assertEqual(run.call_count, 1)


if __name__ == '__main__':
    unittest.main()
