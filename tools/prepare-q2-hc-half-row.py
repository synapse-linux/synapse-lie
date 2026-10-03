#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Balance HC row reuse with a 160x64 tile and 28 KiB shared stage."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-full-row'
OUT = ROOT / '.deps/gufo-q2-bench-hc-half-row'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp')
EXPECTED = 'dc94fbb95cdd4e9d3ddd58c12f2dbdb689854e4f2945da9169a812571a7c3445'


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Unexpected full-row source: ' + old[:90])
    return text.replace(old, new)


def main():
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if sha(BASE / REL) != EXPECTED:
        raise ValueError('Measured full-row source changed')
    original = (BASE / REL).read_text()
    changed = once(original, '!kHcUpChains && BM == 320 && BN == 32)',
                   '!kHcUpChains && BM == 160 && BN == 64)')
    changed = once(changed,
        '    // One row tile shares every input stripe across all 320 outputs.\n'
        '    // Narrower token tiles retain 64 independent blocks at n2048.',
        '    // Two row tiles share each input stripe across 160 outputs each.\n'
        '    // At n2048, 64 independent blocks use 28 KiB of shared memory.')
    changed = once(changed,
        '(DenseF16GEMMKernel<320, 32, 2, 4, 2, 1, false, false, false, true>),',
        '(DenseF16GEMMKernel<160, 64, 2, 2, 4, 2, false, false, false, true>),')
    changed = once(changed,
        '        dim3((batch + 31) / 32, 1), dim3(kThreads), 0, stream, w, x, out,',
        '        dim3((batch + 63) / 64, 2), dim3(kThreads), 0, stream, w, x, out,')
    shutil.copytree(BASE, OUT)
    target = OUT / REL
    target.write_text(changed)
    subprocess.run(['clang-format', '-i', str(target)], check=True)
    inventory = sorted(str(p.relative_to(BASE)) for p in BASE.rglob('*') if p.is_file()
                       and p.read_bytes() != (OUT / p.relative_to(BASE)).read_bytes())
    if inventory != [str(REL)]:
        raise ValueError('Unexpected changed inventory')
    patch = ROOT / 'experiments/q2-hc-half-row.patch'
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True),
        target.read_text().splitlines(True), fromfile='a/' + str(REL), tofile='b/' + str(REL))))
    report = dict(scope='Prepared half-row HC source; exactness and performance unproven',
        pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
        base=str(BASE.relative_to(ROOT)), candidate=str(OUT.relative_to(ROOT)),
        changed_files=inventory, base_sha256=sha(BASE / REL), candidate_sha256=sha(target),
        patch_sha256=sha(patch),
        dispatch='Original F16 HC down M320/K10240, n>=96; BM160/BN64/BK2/WM2/WN4, 256 threads',
        arithmetic='Both original ordered K16 accumulation chains and bounded five-tile epilogue retained',
        mechanism='Two row blocks instead of five retained blocks or one full-row block; balance input and weight staging',
        logical_staging_n2048=dict(reference_input_bytes=209715200,reference_weight_bytes=104857600,
            full_row_input_bytes=41943040,full_row_weight_bytes=419430400,
            candidate_input_bytes=83886080,candidate_weight_bytes=209715200),
        resources='64 blocks at n2048, 28672 LDS bytes; physical traffic, occupancy and speed unmeasured',
        unchanged='Paired HC up, scalar decode, routed IQ2/Q2, PLE, original models and public ABI',
        numerical_limits_changed=False, model_conversion=False, promoted=False)
    (ROOT / 'config/q2-hc-half-row-source.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
