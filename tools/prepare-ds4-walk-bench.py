#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the DS4-walk source capsule from independently pinned LIE sources."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    exact = json.loads((ROOT / 'config/q2-exact-bench-source.json').read_text())
    counting = json.loads((ROOT / 'config/q2-counting-bench-source.json').read_text())
    parent = ROOT / exact['source']
    out = ROOT / '.deps/lie-ds4-walk-bench'
    if out.exists():
        raise SystemExit('Preserve existing DS4-walk source capsule')
    for name, digest in exact['files'].items():
        assert sha(parent / name) == digest, name
    shutil.copytree(parent, out)
    subprocess.run(['git', 'apply', str(ROOT / 'experiments/q2-counting-bench.patch')],
                   cwd=out, check=True)
    shutil.copyfile(ROOT / 'experiments/q2_counting_prompt.inc',
                    out / 'tools/q2_counting_prompt.inc')
    shutil.copyfile(ROOT / 'experiments/q2_bench_fixture_trace.inc',
                    out / 'tests/q2_bench_fixture_trace.inc')
    for name, digest in counting['files'].items():
        assert sha(out / name) == digest, name
    subprocess.run(['git', 'apply', str(ROOT / 'experiments/ds4-walk-bench.patch')],
                   cwd=out, check=True)
    manifest = dict(schema='synapse-lie.ds4-walk-bench-source.v1',
                    source=str(out.relative_to(ROOT)),
                    parent_manifest_sha256=sha(ROOT / 'config/q2-counting-bench-source.json'),
                    patch_sha256=sha(ROOT / 'experiments/ds4-walk-bench.patch'),
                    generator_sha256=sha(Path(__file__)),
                    files={str(path.relative_to(out)): sha(path)
                           for path in sorted(out.rglob('*')) if path.is_file()})
    (ROOT / 'config/ds4-walk-bench-source.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(dict(source=manifest['source'], files=len(manifest['files']))))


if __name__ == '__main__':
    main()
