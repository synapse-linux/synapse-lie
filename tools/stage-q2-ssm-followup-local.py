#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise prepared source capsules, stopping before the first SSH call."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tarfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT / 'evidence/q2-ssm-followup-runtime-preparation'
OVERLAY = PREP / 'overlay'
sys.path.insert(0, str(OVERLAY / 'tools'))
spec = importlib.util.spec_from_file_location('followup_staging', OVERLAY / 'tools/q2-remote.py')
remote = importlib.util.module_from_spec(spec)
spec.loader.exec_module(remote)


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Staged(Exception):
    pass


def no_process(argv, **kwargs):
    if argv[:2] != ['ssh', '-F']:
        raise AssertionError('Unexpected subprocess before SSH boundary')
    raise Staged()


def main():
    registry = json.loads((ROOT / remote.SSM_FOLLOWUP_MANIFEST).read_text())['variants']
    changes = json.loads((PREP / 'preparation.json').read_text())['prepared_files']
    reports = []
    for variant, info in registry.items():
        provider = json.loads((ROOT / info['manifest']).read_text())['variants'][variant]
        for kind in ('component', 'model'):
            mode = info[kind + '_mode']
            label = 'q2-followup-local-' + variant + '-' + kind
            argv = ['q2-remote.py', mode, label, '--source-variant', variant]
            if kind == 'model':
                argv += ['--rebuild-mmq']
            with patch.object(sys, 'argv', argv), patch.object(remote.subprocess, 'run', side_effect=no_process) as calls:
                try:
                    remote.main()
                except Staged:
                    pass
                else:
                    raise AssertionError('Staging did not reach intercepted SSH')
                assert calls.call_count == 1
            capsule = OVERLAY / 'evidence' / label / 'source.tar.gz'
            with tarfile.open(capsule) as archive:
                files = {item.name: item for item in archive if item.isfile()}
                expected = {'source/' + path: digest for path, digest in provider['files'].items()}
                expected.update(info['bindings'])
                expected.update(changes)
                expected[remote.SSM_FOLLOWUP_MANIFEST] = sha((ROOT / remote.SSM_FOLLOWUP_MANIFEST).read_bytes())
                for name, digest in expected.items():
                    assert name in files, name
                    assert sha(archive.extractfile(name).read()) == digest, name
                assert len([n for n in files if n.startswith('source/')]) == 1027
            row = dict(variant=variant, mode=mode, kind=kind,
                       capsule=str(capsule.relative_to(ROOT)), capsule_sha256=sha(capsule.read_bytes()),
                       verified_files=len(expected), provider_files=1027, ssh_executed=False)
            reports.append(row)
            print(json.dumps(row), flush=True)
    with (ROOT / 'config/q2-ssm-followup-runtime-staging.json').open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-ssm-followup-runtime-staging.v1',
                       arms=reports, patch_applied=False, remote_run=False, gpu_run=False), stream, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
