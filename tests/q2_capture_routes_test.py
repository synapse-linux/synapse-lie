#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise the installed debugger on owned host children, including failures."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from q2_capture_routes import validate_counts
from q2_process import members, owns_process, supervise

BINARY = sys.argv.pop(1) if len(sys.argv) > 1 else None


class CaptureTests(unittest.TestCase):
    @unittest.skipUnless(BINARY, 'Host fixture path required')
    def test_real_debugger_under_process_supervisor(self):
        directory = Path(tempfile.mkdtemp(prefix='supervised-routing-', dir=Path.cwd()))
        env = dict(os.environ, LIE_Q2_ROUTING_OUTPUT=str(directory),
                   ASAN_OPTIONS='detect_leaks=0:halt_on_error=1')
        row, observed = {}, []
        def clients():
            children = [r for r in members(row['pid'], row['start_ticks'], True)
                        if r['group'] != row['pid']]
            observed.extend(children)
            for child in children:
                self.assertFalse(owns_process(child['pid'], row['pid'], row['start_ticks']))
            return [r['pid'] for r in children]
        argv = ['gdb', '-nx', '-nh', '--batch', '-iex', 'set auto-load off',
                '-ex', 'set pagination off', '-ex', 'set confirm off',
                '-ex', 'set print thread-events off', '-ex', 'set disable-randomization off',
                '-x', str(ROOT/'tools/q2_capture_routes.py'), '--args', BINARY, 'good']
        with (directory/'stdout.txt').open('wb') as stream:
            supervise(argv, cwd=directory, env=env, log=stream, row=row,
                      timeout=30, clients=clients, interval=.01, allow_child_groups=True)
        (directory/'command.json').write_text(json.dumps(row, indent=2))
        self.assertTrue(observed, 'Did not exercise the real debugger child group')
        self.assertTrue(row['owned_kfd_identities'])
        self.assertEqual(members(row['pid'], row['start_ticks'], True), [])
        self.assertEqual(json.loads((directory/'routing-capture.json').read_text())['captures'], 96)

    def test_shape_and_bounds(self):
        raw = (40).to_bytes(4, 'little', signed=True)*512
        self.assertEqual(validate_counts(raw, 512, 2048, 10), [40]*512)
        for value in (-1, 2049, 39):
            with self.assertRaises(ValueError):
                validate_counts(value.to_bytes(4, 'little', signed=True)+raw[4:], 512, 2048, 10)
        for data, experts, tokens, used in ((raw[:-1], 512, 2048, 10),
                (raw, 511, 2048, 10), (raw, 512, 1024, 10), (raw, 512, 2048, 8)):
            with self.assertRaises(ValueError):
                validate_counts(data, experts, tokens, used)

    @unittest.skipUnless(BINARY, 'Host fixture path required')
    def test_real_gdb_child_lifecycle(self):
        # Keep calibration transcripts durable in this private CTest build.
        directory = Path(tempfile.mkdtemp(prefix='routing-capture-', dir=Path.cwd()))
        for mode in ('good', 'short', 'extra', 'bad-count', 'bad-shape', 'exit-error', 'signal'):
            with self.subTest(mode=mode):
                case = directory/mode
                case.mkdir()
                env = dict(os.environ, LIE_Q2_ROUTING_OUTPUT=str(case))
                # ASan executes in the child; LeakSanitizer cannot run under ptrace.
                # Retain ASan/UBSan, and disable leak detection only in this owned fixture.
                env['ASAN_OPTIONS'] = 'detect_leaks=0:halt_on_error=1'
                result = subprocess.run(['gdb', '-nx', '-nh', '--batch',
                    '-iex', 'set auto-load off', '-ex', 'set pagination off',
                    '-ex', 'set confirm off', '-ex', 'set print thread-events off',
                    '-ex', 'set disable-randomization off',
                    '-x', str(ROOT/'tools/q2_capture_routes.py'), '--args', BINARY, mode],
                    env=env, capture_output=True, timeout=30)
                (case/'stdout.txt').write_bytes(result.stdout)
                (case/'stderr.txt').write_bytes(result.stderr)
                (case/'command.json').write_text(json.dumps(dict(argv=result.args, exit_code=result.returncode)))
                report = json.loads((case/'routing-capture.json').read_text())
                self.assertEqual(result.returncode, 0 if mode == 'good' else 2, result.stderr.decode())
                self.assertEqual(report['state'], 'COMPLETE' if mode == 'good' else 'FAILED')
                self.assertFalse(report['headline_eligible'])
                if mode == 'good':
                    rows = [json.loads(line) for line in (case/'routing-counts.jsonl').read_text().splitlines()]
                    self.assertEqual(len(rows), 96)
                    self.assertEqual(rows[48]['phase'], 'profile')
                    self.assertTrue(all(r['counts'] == [40]*512 for r in rows))
                    self.assertEqual(report['inferior_exit_codes'], [0])
                if mode == 'exit-error':
                    self.assertEqual(report['inferior_exit_codes'], [7])
                if mode == 'signal':
                    self.assertEqual(report['signals'], ['SIGTERM'])


if __name__ == '__main__':
    unittest.main()
