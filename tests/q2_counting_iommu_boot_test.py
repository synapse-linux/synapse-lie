# SPDX-License-Identifier: MIT
"""CPU fixtures: private files and mocked boot commands; never reboots or uses GPU."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]/'tools/q2-counting-iommu-boot.py'
if not SOURCE.is_file():
    SOURCE = Path(__file__).resolve().with_name('q2-counting-iommu-boot.py')


class BootContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='q2-boot-cpu-fixture-')
        self.root = Path(self.temp.name)
        spec = importlib.util.spec_from_file_location('boot_fixture', SOURCE)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        m = self.m
        m.ROOT = self.root
        m.HERE = self.root/'transition'
        m.HERE.mkdir()
        m.CONFIG = self.root/'limine.conf'
        m.CONFIG.write_text('original\n')
        m.CONFIG.chmod(0o640)
        m.BOOT = self.root/'boot-id'
        m.BOOT.write_text('before')
        m.VARIABLE = self.root/'oneshot'
        m.SHADOW_CONFIGS = ()
        (m.HERE/'limine.original.conf').write_text('original\n')
        (m.HERE/'limine.iommu-off.conf').write_text('candidate\n')
        completion = dict(measured_points=176, total_samples=352, full_128k_curve=True,
                          analysis_exit_code=0, tables_presented_to_user=True)
        (m.HERE/'curve-completion.json').write_text(json.dumps(completion))
        source = self.root/'q2-counting-curve128-r1'
        source.mkdir()
        release = source/'release.json'
        release.write_text('{}')
        helper = source/'q2-counting-curve128-window.py'
        registry = self.root/'registry.jsonl'
        registry.write_text(json.dumps(dict(receipt_sha256=m.sha(release)))+'\n')
        helper.write_text('import contextlib,json\nfrom pathlib import Path\n'
                          f'REGISTRY=Path({str(registry)!r})\n'
                          'def leases(previous): return contextlib.nullcontext()\n'
                          'def clear(previous): pass\n'
                          'def registry_rows(): return [json.loads(x) for x in REGISTRY.read_text().splitlines()]\n')
        self.plan = dict(schema='synapse-lie.q2-counting-iommu-boot.v1', user_authorized=True,
                         boot_parameter='amd_iommu=off', before_window=source.name,
                         restore_exact_original_after_reconnect=True, before_boot_id='before',
                         before_release_sha256=m.sha(release), window_helper_sha256=m.sha(helper),
                         helper_sha256=m.sha(SOURCE), files={})
        self.write_plan()
        self.commands = []

    def tearDown(self):
        self.temp.cleanup()

    def write_plan(self):
        self.plan['files'] = {p.name:self.m.sha(p) for p in self.m.HERE.iterdir()
                              if p.name in ('limine.original.conf','limine.iommu-off.conf','curve-completion.json')}
        (self.m.HERE/'plan.json').write_text(json.dumps(self.plan))
        (self.m.HERE/'cpu-qualification.json').write_text(json.dumps(dict(
            exit_code=0, plan_sha256=self.m.sha(self.m.HERE/'plan.json'),
            helper_sha256=self.m.sha(SOURCE))))

    def fake_command(self, argv, **kwargs):
        self.commands.append(argv)
        if argv[:2] == ['bootctl','set-oneshot']:
            if argv[2]:
                self.m.VARIABLE.write_bytes(b'\x07\0\0\0'+(argv[2]+'\0').encode('utf-16-le'))
            else:
                self.m.VARIABLE.unlink(missing_ok=True)
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    def invoke(self, mode, command=None):
        with patch('sys.argv',[str(SOURCE),mode]), patch.object(os,'geteuid',return_value=0), \
             patch.object(self.m.subprocess,'run',side_effect=command or self.fake_command), \
             contextlib.redirect_stdout(io.StringIO()):
            self.m.main()

    def test_apply_reboot_restore_uses_owned_files_and_preserves_mode(self):
        self.invoke('apply')
        self.assertEqual(self.m.CONFIG.read_text(),'candidate\n')
        self.assertEqual(stat.S_IMODE(self.m.CONFIG.stat().st_mode),0o640)
        self.invoke('reboot')
        self.assertIn(['systemctl','reboot','--no-block'],self.commands)
        self.m.BOOT.write_text('after')
        self.m.VARIABLE.unlink()
        self.invoke('restore')
        self.assertEqual(self.m.CONFIG.read_text(),'original\n')
        self.assertEqual(stat.S_IMODE(self.m.CONFIG.stat().st_mode),0o640)
        self.assertTrue(json.loads((self.m.HERE/'restore.json').read_text())['exact_original_restored'])

    def test_rejects_incomplete_curve_before_any_change(self):
        p=self.m.HERE/'curve-completion.json'
        d=json.loads(p.read_text());d['measured_points']=175;p.write_text(json.dumps(d))
        self.write_plan()
        with self.assertRaisesRegex(ValueError,'Complete measured curves'):
            self.invoke('apply')
        self.assertEqual(self.m.CONFIG.read_text(),'original\n')
        self.assertEqual(self.commands,[])

    def test_preserves_foreign_oneshot(self):
        self.m.VARIABLE.write_bytes(b'foreign')
        with self.assertRaisesRegex(ValueError,'existing one-shot'):
            self.invoke('apply')
        self.assertEqual(self.m.VARIABLE.read_bytes(),b'foreign')
        self.assertEqual(self.m.CONFIG.read_text(),'original\n')

    def test_failed_oneshot_restores_original(self):
        with self.assertRaisesRegex(ValueError,'One-shot selection failed'):
            self.invoke('apply',lambda *a,**k:SimpleNamespace(returncode=7,stdout='',stderr='fixture failure'))
        self.assertEqual(self.m.CONFIG.read_text(),'original\n')
        self.assertEqual(json.loads((self.m.HERE/'apply-failed.json').read_text())['exit_code'],7)

    def test_changed_config_is_preserved(self):
        self.m.CONFIG.write_text('concurrent edit\n')
        with self.assertRaisesRegex(ValueError,'configuration changed'):
            self.invoke('apply')
        self.assertEqual(self.m.CONFIG.read_text(),'concurrent edit\n')
        self.assertEqual(self.commands,[])

    def test_symlink_is_rejected(self):
        self.m.CONFIG.unlink()
        self.m.CONFIG.symlink_to(self.m.HERE/'limine.original.conf')
        with self.assertRaisesRegex(ValueError,'configuration changed'):
            self.invoke('apply')
        self.assertTrue(self.m.CONFIG.is_symlink())

    def test_existing_stage_is_preserved(self):
        stage=self.m.CONFIG.with_name('.synapse-lie-iommu-next.conf')
        stage.write_text('existing stage\n')
        with self.assertRaises(FileExistsError):
            self.invoke('apply')
        self.assertEqual(stage.read_text(),'existing stage\n')
        self.assertEqual(self.m.CONFIG.read_text(),'original\n')


if __name__ == '__main__':
    unittest.main()
