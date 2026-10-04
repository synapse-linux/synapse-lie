#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare isolated IQ2 prefill reuse probes from the measured ordered provider."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Expected one source anchor: '+old[:60])
    return text.replace(old, new, 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('variant', choices=('grid-lds', 'scale-reuse'))
    args = parser.parse_args()
    parent_path = ROOT/'config/q2-iq2-signs-ordered-asm-source.json'
    parent = json.loads(parent_path.read_text())
    base = ROOT/parent['candidate']
    files = {str(p.relative_to(base)): sha(p) for p in base.rglob('*') if p.is_file()}
    if files != parent['files']:
        raise ValueError('Measured parent changed')
    original = (base/REL).read_text()
    if args.variant == 'grid-lds':
        modified = replace_once(original, '  const int r_block = static_cast<int>(blockIdx.x) * kRows;',
            '''  const int r_block = static_cast<int>(blockIdx.x) * kRows;
  // DeepSeek's IQ2 loaders stage this 2 KiB codebook once per workgroup.
  // Adapt only its storage: signed bytes and every floating operation stay.
  __shared__ uint2 iq2_grid_lds[kIQ2 && kPair ? 256 : 1];
  if constexpr (kIQ2 && kPair) {
    iq2_grid_lds[tid] = reinterpret_cast<const uint2*>(iq2xxs_grid)[tid];
    __syncthreads();
  }''')
        modified = replace_once(modified,
            '              reinterpret_cast<const uint2*>(iq2xxs_grid)[code];',
            '''              kPair ? iq2_grid_lds[code]
                    : reinterpret_cast<const uint2*>(iq2xxs_grid)[code];''')
        mechanism = 'Stage the 2 KiB magnitude codebook once in LDS for paired IQ2 prefill only; preserve sign-table lookup and arithmetic.'
        risk = 'Extra LDS residency, setup barrier and random LDS bank conflicts may outweigh removed global-cache lookups.'
    else:
        modified = replace_once(original, '  uint4 f_codes[kWaveRowTiles];',
            '''  uint4 f_codes[kWaveRowTiles];
  float iq2_block_scale[kWaveRowTiles] = {};''')
        modified = replace_once(modified,
            '''        __half d;
        __builtin_memcpy(&group, block + 2 + (sb32 % 8) * 8, 8);
        __builtin_memcpy(&d, block, 2);''',
            '''        __builtin_memcpy(&group, block + 2 + (sb32 % 8) * 8, 8);
        // Reuse the superblock header over its four two-block K stages.
        // Converting one F16 header to F32 is exact; scale-product order stays.
        if (kb0 % 8 == 0) {
          __half d;
          __builtin_memcpy(&d, block, 2);
          iq2_block_scale[u] = __half2float(d);
        }''')
        modified = replace_once(modified,
            '            __half2float(d) * float(2 * (group.y >> 28) + 1) * 0.125F;',
            '            iq2_block_scale[u] * float(2 * (group.y >> 28) + 1) * 0.125F;')
        mechanism = 'Reuse the IQ2 block-scale header over four K stages; adaptation of per-superblock reuse, with unchanged weight bytes and scale-product order.'
        risk = 'A uniform header-refresh branch and a longer-lived register may cost more than three saved header loads/conversions per superblock.'
    tag = 'q2-iq2-prefill-'+args.variant
    out = ROOT/'.deps'/('gufo-'+tag)
    manifest = ROOT/'config'/(tag+'-source.json')
    patch = ROOT/'experiments'/(tag+'.patch')
    if any(p.exists() for p in (out, manifest, patch)):
        raise ValueError('Refusing to replace candidate evidence')
    shutil.copytree(base, out)
    (out/REL).write_text(modified)
    actual = {str(p.relative_to(out)): sha(p) for p in out.rglob('*') if p.is_file()}
    if actual.keys() != files.keys() or [k for k in files if files[k] != actual[k]] != [REL]:
        raise ValueError('Unexpected source delta')
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True), modified.splitlines(True),
                                               fromfile='a/'+REL, tofile='b/'+REL)))
    report = dict(schema='synapse-lie.q2-iq2-prefill-reuse-source.v1', variant=args.variant,
        base=parent['candidate'], candidate=str(out.relative_to(ROOT)), files=actual,
        parent_manifest_sha256=sha(parent_path), patch_sha256=sha(patch),
        changed_files=[REL], unchanged_files=len(actual)-1, mechanism=mechanism, risk=risk,
        upstream_pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
        provenance='Read independently fetched official Gufo DeepSeek code; no sibling DS4 source or artifacts imported.',
        runtime_validated=False, performance_validated=False, promoted=False, goal_met=False)
    manifest.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('variant', 'candidate', 'changed_files', 'unchanged_files')}))


if __name__ == '__main__':
    main()
