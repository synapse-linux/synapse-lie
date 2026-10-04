#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare a separate bounded-register reuse probe for 640-column Q2 rows."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/q2_scaled_input.inc'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Unexpected source anchor')
    return text.replace(old, new, 1)


def main():
    parent_path = ROOT/'config/q2-iq2-signs-ordered-asm-source.json'
    parent = json.loads(parent_path.read_text())
    base = ROOT/parent['candidate']
    files = {str(p.relative_to(base)): sha(p) for p in base.rglob('*') if p.is_file()}
    if files != parent['files']:
        raise ValueError('Measured parent inventory changed')
    original = (base/REL).read_text()
    modified = replace_once(original,
        '''  float local = 0.0F;
  for (std::size_t c = tid; c < cols; c += 256)
    local = fmaxf(local, fabsf(x[row * cols + c]));''',
        '''  // The launcher admits only 640 columns. Retain the at most three
  // original values per thread across the unchanged maximum reduction.
  // This avoids reading the complete F32 row again after the barrier.
  float values[3] = {};
  float local = 0.0F;
#pragma unroll
  for (unsigned i = 0; i < 3; ++i) {
    const std::size_t c = tid + i * 256;
    if (c < cols) {
      values[i] = x[row * cols + c];
      local = fmaxf(local, fabsf(values[i]));
    }
  }''')
    modified = replace_once(modified,
        '''  for (std::size_t c = tid; c < cols; c += 256)
    out[row * cols + c] = __float2half_rn(x[row * cols + c] * multiplier);''',
        '''#pragma unroll
  for (unsigned i = 0; i < 3; ++i) {
    const std::size_t c = tid + i * 256;
    if (c < cols)
      out[row * cols + c] = __float2half_rn(values[i] * multiplier);
  }''')
    tag = 'q2-scaled-row-reuse'
    out = ROOT/'.deps'/('gufo-'+tag)
    manifest = ROOT/'config'/(tag+'-source.json')
    patch = ROOT/'experiments'/(tag+'.patch')
    if any(p.exists() for p in (out, manifest, patch)):
        raise ValueError('Refusing to overwrite a candidate')
    shutil.copytree(base, out)
    (out/REL).write_text(modified)
    actual = {str(p.relative_to(out)): sha(p) for p in out.rglob('*') if p.is_file()}
    if actual.keys() != files.keys() or [k for k in files if files[k] != actual[k]] != [REL]:
        raise ValueError('Unexpected candidate delta')
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True), modified.splitlines(True),
                                               fromfile='a/'+REL, tofile='b/'+REL)))
    report = dict(schema='synapse-lie.q2-scaled-row-reuse-source.v1',
        base=parent['candidate'], candidate=str(out.relative_to(ROOT)), files=actual,
        parent_manifest_sha256=sha(parent_path), patch_sha256=sha(patch),
        changed_files=[REL], unchanged_files=len(actual)-1,
        mechanism='Retain up to three F32 values per thread across the row-max reduction, replacing the second global row read; fixed 640-column launcher contract.',
        unchanged='Row maximum order, wave reduction, power-of-two scale and inverse, F16 conversion, output layout, barriers, gate/up, down and routing.',
        risk='Longer-lived registers and unrolling can increase instruction/register cost. Nonaliasing production buffers and exact GPU output replay remain required.',
        provenance='First-party adaptation of bounded input reuse; independent official Gufo DeepSeek inspection motivates reuse, no DeepSeek project code copied.',
        scope='Separate source/static experiment only; excluded from the admitted four-arm IQ2-scale canonical campaign.',
        runtime_validated=False, performance_validated=False, promoted=False, goal_met=False)
    manifest.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('candidate','changed_files','unchanged_files')}))


if __name__ == '__main__':
    main()
