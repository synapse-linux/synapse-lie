#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU-only process fixtures: no device, model or foreign process mutation."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from q2_process import identity, members, owns_process, supervise


class ProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.row = {}

    def tearDown(self):
        self.temp.cleanup()

    def run_child(self, code, **kwargs):
        with (self.root / 'log').open('wb') as log:
            return supervise([sys.executable, '-c', code], cwd=self.root,
                             env=os.environ.copy(), log=log, row=self.row,
                             timeout=kwargs.pop('timeout', 5), interval=0.02, **kwargs)

    def assert_retired(self):
        self.assertEqual(members(self.row['pid'], self.row['start_ticks']), [])

    def test_exit_code(self):
        with self.assertRaisesRegex(RuntimeError, 'Qualification command failed'):
            self.run_child('raise SystemExit(73)')
        self.assertEqual(self.row['exit_code'], 73)
        self.assert_retired()

    def test_success(self):
        self.run_child('print("fixture")')
        self.assertEqual(self.row['exit_code'], 0)
        self.assert_retired()

    def test_descendant_owned_foreign_rejected(self):
        observed = []
        foreign = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)'],
                                   start_new_session=True)
        try:
            def observe(leader):
                child_file = self.root / 'child'
                if not child_file.exists():
                    return
                child_pid = int(child_file.read_text())
                observed.append(child_pid)
                self.assertTrue(owns_process(child_pid, leader, self.row['start_ticks']))
                self.assertFalse(owns_process(foreign.pid, leader, self.row['start_ticks']))
                self.assertFalse(owns_process(child_pid, leader, self.row['start_ticks'] + 1))
            self.run_child('import subprocess,sys,pathlib; '
                           'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(3)"]); '
                           'pathlib.Path("child").write_text(str(p.pid)); p.wait()', observe=observe)
            self.assertTrue(observed)
            self.assertIsNone(foreign.poll())
            self.assert_retired()
        finally:
            foreign.terminate()
            foreign.wait(timeout=5)

    def test_foreign_client_stops_owned_only(self):
        with self.assertRaisesRegex(RuntimeError, 'Foreign KFD client'):
            self.run_child('import time; time.sleep(10)', clients=lambda: [os.getpid()])
        self.assertEqual(self.row['foreign_kfd'], [os.getpid()])
        self.assert_retired()

    def test_timeout_cleans_signal_ignoring_descendant(self):
        with self.assertRaisesRegex(RuntimeError, 'timed out'):
            self.run_child('import subprocess,sys; '
                           'p=subprocess.Popen([sys.executable,"-c",'
                           '"import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(10)"]); '
                           'p.wait()', timeout=0.5)
        self.assertTrue(self.row['timeout'])
        self.assert_retired()

    def test_wrapper_exit_cleans_descendant(self):
        with self.assertRaisesRegex(RuntimeError, 'live descendants'):
            self.run_child('import subprocess,sys; '
                           'subprocess.Popen([sys.executable,"-c","import time; time.sleep(10)"])')
        self.assertEqual(self.row['exit_code'], 0)
        self.assertTrue(self.row['lingering_descendants'])
        self.assert_retired()

    def test_observer_failure_stops_owned(self):
        def hot(pid):
            raise RuntimeError('Thermal limit reached')
        with self.assertRaisesRegex(RuntimeError, 'Thermal limit'):
            self.run_child('import time; time.sleep(10)', observe=hot)
        self.assert_retired()
        self.assertIsNotNone(self.row['exit_code'])

    def test_disappeared_client(self):
        self.assertIsNone(identity(2147483647))
        self.run_child('pass', clients=lambda: [2147483647])
        self.assert_retired()


if __name__ == '__main__':
    unittest.main()
