#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze two private host-capacity variants; retain all numerical sources."""
import hashlib
import json
from pathlib import Path
import shutil
from q2_curve_headroom import ENGINE, extend_engine

ROOT = Path(__file__).resolve().parents[1]


def inventory(path):
    return {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(path.rglob('*')) if p.is_file()}


def main():
    source = ROOT / 'config/q2-curve256-source.json'
    output = ROOT / 'config/q2-curve256-headroom-source.json'
    assert not output.exists()
    report = json.loads(source.read_text())
    for variant, entry in report['variants'].items():
        original = ROOT / entry['source']
        assert inventory(original) == entry['files']
        target = ROOT / ('.deps/gufo-q2-curve256-headroom-' + variant)
        assert not target.exists()
        shutil.copytree(original, target)
        (target / ENGINE).write_text(extend_engine((original / ENGINE).read_text()))
        files = inventory(target)
        assert set(files) == set(entry['files'])
        assert [n for n in files if files[n] != entry['files'][n]] == [ENGINE]
        report['variants'][variant] = dict(source=str(target.relative_to(ROOT)), files=files,
            parent_source=entry['source'], host_changed_files=[ENGINE], numerical_changes=False)
    report.update(schema='synapse-lie.q2-curve256-headroom-source.v1',
        parent_manifest=str(source.relative_to(ROOT)),
        parent_manifest_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        generator='tools/prepare-q2-curve256-headroom.py',
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        scope='Private AR-only capacity extrapolation262144 to266240 before DeviceModel upload. '
              'Both providers use the same guard; all numerical kernels, weights and RoPE parameters unchanged. '
              'Original GGUF metadata is untouched; quality beyond the declared model limit is not established.',
        GPU_admission=False, model_inference=False)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(host_changed_files=[ENGINE],
        provider_file_counts={k:len(v['files']) for k,v in report['variants'].items()},
        model_inference=False)))


if __name__ == '__main__':
    main()
