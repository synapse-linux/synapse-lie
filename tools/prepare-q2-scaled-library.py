#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compose the measured scaled-Q2 and HC-library performance experiments."""
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-scaled-input'
OUT = ROOT / '.deps/gufo-q2-bench-scaled-library'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/blaslt.cpp')
PATCH = ROOT / 'experiments/q2-hc-library-down.patch'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    if sha(PATCH) != 'e03f06c02819fedecf1614df30b36b84b9d5a6c165ae5ce6f1ace16f8e8a45dc':
        raise ValueError('Measured HC-library patch changed')
    if sha(BASE / REL) != 'c96c993d97baa3253190491c96dac16b6ede767eff8460fc24d7b9e0f5d0f590':
        raise ValueError('Cumulative base library source changed')
    kernel = REL.with_name('kernels.hip.cpp')
    if sha(BASE / kernel) != '0a72a7524c9cb04f967503a01b114b22f28cc3d63c44891a7b598e9553c949b4':
        raise ValueError('Measured scaled kernel source changed')
    files = {str(p.relative_to(BASE)): sha(p) for p in sorted(BASE.rglob('*')) if p.is_file()}
    shutil.copytree(BASE, OUT)
    evidence = ROOT / 'evidence/q2-scaled-library-static'
    evidence.mkdir()
    checks = []

    def run(argv, cwd=OUT):
        started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        value = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
        checks.append(dict(argv=argv, cwd=str(cwd), exit_code=value.returncode,
                           started_at=started,
                           finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                           stdout=value.stdout, stderr=value.stderr))
        (evidence / 'checks.json').write_text(json.dumps(checks, indent=2) + '\n')
        if value.returncode:
            raise RuntimeError('Static command failed; actual exit retained')

    run(['patch', '--batch', '--fuzz=0', '--no-backup-if-mismatch', '-p1', '-i', str(PATCH)])
    changed = [str(p.relative_to(OUT)) for p in sorted(OUT.rglob('*'))
               if p.is_file() and sha(p) != files.get(str(p.relative_to(OUT)))]
    if changed != [str(REL)]:
        raise ValueError('Unexpected source composition')
    if sha(OUT / REL) != 'd43ef4c976cce42fe5fd145d401c140472aa5d4200d482ee69b713981dd4df5f':
        raise ValueError('Composed library implementation differs from measured source')
    run(['clang-format', '--dry-run', '--Werror', str(OUT / REL)])
    run(['clang++', '-std=c++20', '-D__HIP_PLATFORM_AMD__', '-DENGINE_ENABLE_HIP=1',
         '-I/opt/rocm/include', '-I' + str(OUT), '-include', 'chrono', '-fsyntax-only', str(OUT / REL)])
    manifest = dict(scope='Prepared arithmetic composition, not numerical acceptance or model performance',
                    pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
                    base=str(BASE.relative_to(ROOT)), candidate=str(OUT.relative_to(ROOT)),
                    base_files=files, changed_files=changed,
                    applied_patch=str(PATCH.relative_to(ROOT)), patch_sha256=sha(PATCH),
                    candidate_library_sha256=sha(OUT / REL),
                    composition=['Cumulative paired HC-up, HC16, MoE fusion and Q2 palette',
                                 'Existing one-plane scaled Q2 down',
                                 'Existing zero-workspace HC-down library algorithm 7526'],
                    dispatch='Library only for F16 M320/K10240/n2048; fail if unsupported',
                    extra_tensor_bytes=0, model_conversion=False, numerical_limits_changed=False,
                    promoted=False, goal_met=False,
                    limits='Inherited scaled and HC-library numerical failures remain. Library index is installation-specific; no serving dispatch or public C ABI change.')
    (ROOT / 'config/q2-scaled-library-source.json').write_text(json.dumps(manifest, indent=2) + '\n')
    report = dict(scope='Local source identity, patch application, format and host syntax only; no GPU',
                  checks=checks, source_files=len(files), changed_files=changed,
                  unchanged_files=len(files) - 1, existing_patch_applied_with_zero_fuzz=True,
                  library_matches_previous_experiment=True, kernel_source_unchanged=True,
                  source_file_hashes={str(p.relative_to(OUT)): sha(p)
                                      for p in sorted(OUT.rglob('*')) if p.is_file()},
                  exit_code=0)
    (ROOT / 'config/q2-scaled-library-static.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(candidate=manifest['candidate'], source_files=len(files),
                         changed_files=changed, static_exit_codes=[r['exit_code'] for r in checks])))


if __name__ == '__main__':
    main()
