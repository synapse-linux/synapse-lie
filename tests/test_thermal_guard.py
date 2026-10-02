#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Owned-child termination using synthetic sensor files, never host tuning."""
import importlib.util
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('thermal_guard', Path(__file__).resolve().parents[1]/'tools/thermal-run.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class Guard(unittest.TestCase):
    def run_guard(self, root, name, command):
        output = root/name
        handlers = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
        try:
            with patch.object(guard, 'HWMON', root/'sensors'), patch.object(sys, 'argv', ['guard','--output',str(output),'--',*command]):
                code = guard.main()
        finally:
            for s, h in handlers.items():
                signal.signal(s, h)
        return code, json.loads((output/'result.json').read_text())

    def test_preflight_and_only_owned_group(self):
        with tempfile.TemporaryDirectory(prefix='lie-thermal-fixture-') as tmp:
            root = Path(tmp);sensor = root/'sensors/hwmon0';sensor.mkdir(parents=True)
            (sensor/'name').write_text('k10temp\n');value = sensor/'temp1_input';value.write_text('85000\n')
            marker = root/'must-not-exist'
            code, result = self.run_guard(root,'refused',[sys.executable,'-c',f'open({str(marker)!r},"w").close()'])
            self.assertEqual(code,125);self.assertEqual(result['reason'],'thermal_limit')
            self.assertIsNone(result['child_exit_code']);self.assertFalse(marker.exists())
            value.write_text('50000\n');(sensor/'temp1_max').write_text('60000\n')
            peer = subprocess.Popen([sys.executable,'-c','import time;time.sleep(20)'],start_new_session=True)
            try:
                command = [sys.executable,'-c',f'from pathlib import Path;import time;Path({str(value)!r}).write_text("61000");time.sleep(20)']
                code, result = self.run_guard(root,'stopped',command)
                self.assertEqual(code,125);self.assertEqual(result['reason'],'thermal_limit')
                self.assertEqual(result['child_exit_code'],-signal.SIGTERM)
                self.assertIsNone(peer.poll())
            finally:
                peer.terminate();peer.wait(timeout=5)
            value.write_text('50000\n')
            code, result = self.run_guard(root,'child-failure',[sys.executable,'-c','raise SystemExit(7)'])
            self.assertEqual(code,7);self.assertEqual(result['child_exit_code'],7)
            self.assertIsNone(result['reason'])


if __name__ == '__main__':
    unittest.main()
