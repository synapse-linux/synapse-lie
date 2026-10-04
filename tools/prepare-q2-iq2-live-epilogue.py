#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Skip IQ2 paired epilogue fragments already known to have no output rows."""
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
    actual = {str(f.relative_to(base)):sha(f) for f in base.rglob('*') if f.is_file()}
    if actual != parent['files']:
        raise ValueError('Measured ordered-IQ2 provider changed')
    original = (base/REL).read_text()
    old = '''    float* scratch = base + wave_id * plane;
#pragma unroll
    for (int j = 0; j < kTokTiles; ++j) {
#pragma unroll'''
    new = '''    float* scratch = base + wave_id * plane;
#pragma unroll
    for (int j = 0; j < kTokTiles; ++j) {
      // Uniform for the whole workgroup. The matrix loop already omits
      // these empty fragments; they have no output row or later consumer.
      // Keep both barriers for every live fragment, including the last.
      if constexpr (kIQ2 && kTokTiles > 1) {
        if (j >= live_tok_tiles)
          continue;
      }
#pragma unroll'''
    if original.count(old) != 1:
        raise ValueError('Unexpected paired epilogue anchor')
    modified = original.replace(old,new,1)
    out = ROOT/'.deps/gufo-q2-curve-iq2-live-epilogue'
    manifest = ROOT/'config/q2-iq2-live-epilogue-source.json'
    if out.exists() or manifest.exists():
        raise ValueError('Refusing to overwrite a candidate')
    shutil.copytree(base,out)
    (out/REL).write_text(modified)
    files = {str(f.relative_to(out)):sha(f) for f in out.rglob('*') if f.is_file()}
    if files.keys()!=actual.keys() or [k for k in actual if actual[k]!=files[k]]!=[REL]:
        raise ValueError('Unexpected candidate delta')
    patch=ROOT/'experiments/q2-iq2-live-epilogue.patch'
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True),modified.splitlines(True),
                                               fromfile='a/'+REL,tofile='b/'+REL)))
    report=dict(schema='synapse-lie.q2-iq2-live-epilogue-source.v1',
        base=parent['candidate'],candidate=str(out.relative_to(ROOT)),files=files,
        parent_manifest_sha256=sha(parent_path),patch_sha256=sha(patch),
        changed_files=[REL],unchanged_files=len(files)-1,
        mechanism='Uniform IQ2 paired epilogue guard before shared stores and two workgroup barriers for wholly empty 16-row fragments.',
        unchanged='Live fragment arithmetic/barriers, weight decode, WMMA accumulation, routing maps, tile geometry, down projection, ordered decode and original PLE.',
        risk='Compiler code layout or extra branch can outweigh saved tail work. Same mathematical live output does not prove identical compiled output.',
        scope='Local source preparation only; not selected by the active routing diagnostic or admitted for GPU execution.',
        runtime_validated=False,performance_validated=False,promoted=False,goal_met=False)
    manifest.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('candidate','changed_files','unchanged_files')}))


if __name__=='__main__':
    main()
