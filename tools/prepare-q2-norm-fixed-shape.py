#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Expose dispatch-proven HC dimensions without changing the norm divisor."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parent_path = ROOT/'config/q2-iq2-mixed-model-source.json'
    parent = json.loads(parent_path.read_text())
    base = ROOT/parent['candidate']
    files = {str(p.relative_to(base)): sha(p) for p in base.rglob('*') if p.is_file()}
    if files != parent['files']:
        raise ValueError('Fixed-reference mixed-map provider changed')
    out = ROOT/'.deps/gufo-q2-norm-fixed-shape'
    manifest = ROOT/'config/q2-norm-fixed-shape-source.json'
    patch = ROOT/'experiments/q2-norm-fixed-shape.patch'
    if any(p.exists() for p in (out, manifest, patch)):
        raise ValueError('Refusing to overwrite retained source')
    original = (base/REL).read_text()
    changed = original
    for name in ('HcCombineF32Half', 'HcCombineMoeF32Half'):
        start = changed.index('__global__ void '+name+'Kernel(')
        end = changed.index('\n}\n', start) + 3
        body = changed[start:end]
        if body.count('std::uint32_t hidden') != 1 or body.count('static_cast<float>(hidden)') != 1:
            raise ValueError('Unexpected kernel dimension or norm divisor')
        body = body.replace('std::uint32_t hidden', 'std::uint32_t normalization_hidden')
        body = body.replace('static_cast<float>(hidden)', 'static_cast<float>(normalization_hidden)')
        anchor = '  constexpr std::uint32_t kStreams = 4;'
        if body.count(anchor) != 1:
            raise ValueError('Unexpected stream count')
        body = body.replace(anchor, anchor+'\n'
            '  // The public dispatcher rejects every other width. Keep the original\n'
            '  // runtime norm divisor to preserve its floating-point instruction path.\n'
            '  constexpr std::uint32_t hidden = 2560;')
        public = original[original.index('bool '+name+'('):]
        public = public[:public.index('\n}\n')]
        if 'hidden != 2560 || streams != 4' not in public:
            raise ValueError('Required public shape guard is absent')
        changed = changed[:start]+body+changed[end:]
    shutil.copytree(base, out)
    (out/REL).write_text(changed)
    actual = {str(p.relative_to(out)): sha(p) for p in out.rglob('*') if p.is_file()}
    differences = sorted(k for k in actual if actual[k] != files[k])
    if actual.keys() != files.keys() or differences != [REL]:
        raise ValueError('Unexpected source delta')
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True), changed.splitlines(True),
                     fromfile='a/'+REL, tofile='b/'+REL)))
    report = dict(schema='synapse-lie.q2-norm-fixed-shape-source.v1',
        base=parent['candidate'], candidate=str(out.relative_to(ROOT)), files=actual,
        parent_manifest_sha256=sha(parent_path), patch_sha256=sha(patch),
        changed_files=differences, unchanged_files=len(files)-1,
        fixed_reference='config/q2-fixed-prefill-reference.json',
        mechanism='Constant-propagate the dispatcher-proven hidden2560/streams4 integer geometry inside the two paired F32/F16 norm producers.',
        arithmetic='Retain the runtime F32 norm divisor, expert FMA order, square/reduction tree, F32 output anchors and F16 conversion.',
        unchanged='Public guards/signatures, executor, buffers, dispatch, library algorithm, mixed expert maps, accepted IQ2 decode and PLE.',
        next_gate='Existing full ordinary/MoE producer plus HC-library consumer at 2048, with retained controls and original numerical thresholds; no new context curve.',
        runtime_validated=False, promoted=False, goal_met=False)
    manifest.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('candidate','changed_files','unchanged_files')}))


if __name__ == '__main__':
    main()
