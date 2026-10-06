# SPDX-License-Identifier: MIT
"""No GPU: reject changed sources/admission and model-option leakage."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import q2_counter_calibration as calibration

spec = importlib.util.spec_from_file_location('remote', ROOT / 'tools/q2-remote.py')
remote = importlib.util.module_from_spec(spec)
spec.loader.exec_module(remote)


class CalibrationTests(unittest.TestCase):
    def test_invalid_options_never_stage_or_launch(self):
        for flags in (['--source-variant', 'hc'], ['--rebuild-mmq'], ['--detach'],
                      ['--native-curve'], ['--point-only'],
                      ['--replay-from', 'q2-norm-fixed-model-before-r1']):
            with self.subTest(flags=flags), patch.object(sys, 'argv',
                    ['q2-remote.py', 'counter-calibration', 'q2-calibration-test', *flags]), \
                    patch.object(Path, 'mkdir', side_effect=AssertionError('Staging forbidden')), \
                    patch.object(remote.subprocess, 'run', side_effect=AssertionError('Launch forbidden')), \
                    contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    remote.main()
                self.assertEqual(raised.exception.code, 2)

    def scenario(self, mutation=None):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / 'q2-calibration-test'
            (root / 'config').mkdir(parents=True)
            (root / 'fixture').write_text('bound')
            installed = parent / 'installed'
            installed.write_text('installed')
            plan = dict(fixtures={'fixture': calibration.sha(root / 'fixture')},
                        installed_files=[dict(path=str(installed), sha256=calibration.sha(installed))],
                        previous_release_sha256='previous')
            (root / 'config/q2-counter-calibration-plan.json').write_text(json.dumps(plan))
            admission = dict(previous_release_sha256='previous', planned_labels=[root.name], gpu_reserved=True)
            if mutation == 'admission': admission['gpu_reserved'] = False
            (parent / 'q2-counter-calibration-window-admission.json').write_text(json.dumps(admission))
            if mutation == 'source': (root / 'fixture').write_text('changed')
            if mutation == 'installed': installed.write_text('changed')
            calls = []

            def run(argv, env, limit):
                calls.append((argv, env.copy(), limit))
                if len(calls) == 1:
                    Path(argv[-1]).write_bytes(b'compiled probe')

            result = {}
            env = {'HIP_VISIBLE_DEVICES': '-1', 'ROCR_VISIBLE_DEVICES': '-1', 'LC_ALL': 'C'}
            if mutation:
                with self.assertRaises(RuntimeError):
                    calibration.execute(root, result, run, env, lambda: None)
                self.assertEqual(calls, [])
                return
            calibration.execute(root, result, run, env, lambda: None)
            self.assertEqual(len(calls), 6)
            self.assertEqual(calls[0][1]['HIP_VISIBLE_DEVICES'], '-1')
            for argv, active_env, limit in calls[1:]:
                self.assertNotIn('HIP_VISIBLE_DEVICES', active_env)
                self.assertNotIn('ROCR_VISIBLE_DEVICES', active_env)
                self.assertLessEqual(limit, 120)
                self.assertFalse(any('.gguf' in arg for arg in argv))
            self.assertEqual(result['binary_sha256'], result['binary_sha256_after'])
            self.assertFalse(result['headline_eligible'])
            self.assertEqual([c[0][-1] for c in calls[1:]], ['waves', 'read', 'waves', 'waves', 'read'])

    def test_bound_dispatch(self): self.scenario()
    def test_changed_source_refused(self): self.scenario('source')
    def test_changed_installation_refused(self): self.scenario('installed')
    def test_missing_admission_refused(self): self.scenario('admission')


if __name__ == '__main__':
    unittest.main()
