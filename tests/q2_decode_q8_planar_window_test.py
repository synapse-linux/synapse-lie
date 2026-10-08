#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU-only owned-child and epoch-window checks; never opens a GPU device."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
spec = importlib.util.spec_from_file_location('window', ROOT/'tools/q2-decode-q8-planar-window.py')
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)


def test(exit_code, timeout=False):
    with tempfile.TemporaryDirectory(prefix='lie-q8-planar-window-') as temp:
        root = Path(temp)
        here = root/w.LABEL
        here.mkdir()
        prior = root/'q2-native128-profile-r1/release.json'
        prior.parent.mkdir()
        leases = []
        for i in range(5):
            path = root/f'lease-{i}'
            path.write_bytes(b'')
            st = path.stat()
            leases.append(dict(path=str(path), device=st.st_dev, inode=st.st_ino))
        previous = dict(boot_id=w.epoch.EXPECTED_BOOT, models=[], leases=leases[1:],
            core_cpu_lease=leases[0], retired_identities=[], retired_groups=[],
            historical_release='fixture', historical_release_sha256='fixture', gpu_reserved=False)
        prior.write_text(json.dumps(previous)+'\n')
        registry = root/'runs.jsonl'
        registry.write_text(json.dumps(dict(event='window_release', receipt_sha256=w.sha(prior)))+'\n')
        program = here/'q2_decode_q8_planar_check'
        program.write_text('#!/usr/bin/env python3\nimport time\ntime.sleep(.3)\n'
                           f'print("fixture")\nraise SystemExit({exit_code})\n')
        program.chmod(0o700)
        plan = dict(schema='synapse-lie.q2-decode-q8-planar-window-plan.v1', label=w.LABEL,
            boot_id=w.epoch.EXPECTED_BOOT, component_only=True, model_access=False,
            remote_build=False, remote_cleanup=False, timeout_seconds=300,
            previous_release=str(prior.relative_to(root)), previous_release_sha256=w.sha(prior),
            staged_sha256={program.name:w.sha(program)})
        w.HERE=here; w.PLAN=here/'plan.json'; w.ADMISSION=here/'admission.json'
        w.RELEASE=here/'release.json'; w.RESULT=here/'result.json'
        w.epoch.ROOT=root; w.epoch.REGISTRY=registry
        boot=root/'boot'; boot.write_text(w.epoch.EXPECTED_BOOT+'\n'); w.epoch.BOOT_ID=boot
        w.PLAN.write_text(json.dumps(plan)+'\n')
        def clear(previous, own=None):
            w.epoch.assert_retired(previous, own)
        w.epoch.clear=clear
        w.epoch.power_check=lambda path=None: dict(cpu_fixture=True)
        w.sample=lambda: [dict(device='k10temp',temperature_mc=35000,over_limit=False),
                          dict(device='amdgpu',temperature_mc=35000,over_limit=False)]
        with contextlib.redirect_stdout(io.StringIO()):
            loaded, prior_data=w.load()
            w.admit('verify',loaded,prior_data)
            assert not w.ADMISSION.exists()
            w.admit('admit',loaded,prior_data)
            if timeout:
                loaded['timeout_seconds']=.01
            actual=w.run(loaded,prior_data)
            w.release(loaded,prior_data)
        result=w.read(w.RESULT); release=w.read(w.RELEASE)
        assert actual == (2 if timeout or exit_code == 2 else exit_code)
        assert result['exit_code'] == (-15 if timeout else exit_code)
        assert result['state'] == ('FAILED' if timeout or exit_code == 2 else 'COMPLETE')
        assert release['component_exit_code'] == result['exit_code']
        assert release['retired_identities'] == result['owned_identities']
        assert release['original_leases_free'] and not release['gpu_reserved']
        assert w.epoch.registry_rows()[-1]['receipt_sha256'] == w.sha(w.RELEASE)
        try:
            w.active()
        except ValueError:
            pass
        else:
            raise AssertionError('A released window was reused')


if __name__ == '__main__':
    for code in (0,1,2):
        test(code)
    test(0,timeout=True)
    print('Q8 planar CPU fixture: success, finite mismatch, unsafe failure and timeout retired')
