#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Omit IQ2 activation LDS stores beyond the last consumed 16-row fragment."""
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
    parent_path = ROOT/'config/q2-iq2-signs-ordered-asm-source.json'
    parent = json.loads(parent_path.read_text())
    base = ROOT/parent['candidate']
    original_files = {str(p.relative_to(base)): sha(p)
                      for p in base.rglob('*') if p.is_file()}
    if original_files != parent['files']:
        raise ValueError('Measured ordered-IQ2 provider changed')
    original = (base/REL).read_text()
    old = '''    // s_act[(kb * 4 + quarter) * kActStride + t]
    a_slot[i] = chunk < kActChunks ? (sub * kActStride) + t : -1;'''
    new = '''    // Every K stage consumes only the live 16-row fragments. Keep
    // zero padding inside the last live fragment; wholly dead fragments
    // have no LDS reader. Decide this once, outside the stage loop.
    const bool store_live =
        chunk < kActChunks &&
        (!(kIQ2 && kPair && kTokTiles > 1) || t < live_tok_tiles * 16);
    // s_act[(kb * 4 + quarter) * kActStride + t]
    a_slot[i] = store_live ? (sub * kActStride) + t : -1;'''
    if original.count(old) != 1:
        raise ValueError('Unexpected activation-slot anchor')
    modified = original.replace(old, new, 1)
    out = ROOT/'.deps/gufo-q2-curve-iq2-live-stage'
    manifest = ROOT/'config/q2-iq2-live-stage-source.json'
    patch = ROOT/'experiments/q2-iq2-live-stage.patch'
    if any(p.exists() for p in (out, manifest, patch)):
        raise ValueError('Refusing to overwrite a candidate')
    shutil.copytree(base, out)
    (out/REL).write_text(modified)
    files = {str(p.relative_to(out)): sha(p)
             for p in out.rglob('*') if p.is_file()}
    if (files.keys() != original_files.keys() or
            [k for k in original_files if original_files[k] != files[k]] != [REL]):
        raise ValueError('Unexpected candidate delta')
    patch.write_text(''.join(difflib.unified_diff(
        original.splitlines(True), modified.splitlines(True),
        fromfile='a/'+REL, tofile='b/'+REL)))
    report = dict(schema='synapse-lie.q2-iq2-live-stage-source.v1',
        base=parent['candidate'], candidate=str(out.relative_to(ROOT)), files=files,
        parent_manifest_sha256=sha(parent_path), patch_sha256=sha(patch),
        changed_files=[REL], unchanged_files=len(files)-1,
        mechanism='Mask activation LDS slots once before the K loop, omitting repeated zero stores for wholly unread 16-row fragments in paired IQ2 tiles wider than 16 rows.',
        unchanged='All live fragment inputs including partial-fragment zero padding, weight decode, WMMA accumulation, barriers, epilogue, routing, tile geometry, down projection and original PLE.',
        risk='Extra predicates, execution-mask changes or register pressure may cost more than the saved LDS stores. Source-level equivalence does not prove compiled numerical identity.',
        scope='Local preparation for the same complete measured-routing component fixture; no model comparison or GPU admission.',
        runtime_validated=False, performance_validated=False,
        promoted=False, goal_met=False)
    manifest.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('candidate', 'changed_files', 'unchanged_files')}))


if __name__ == '__main__':
    main()
