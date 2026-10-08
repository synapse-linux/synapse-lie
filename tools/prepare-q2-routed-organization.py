#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Isolate routed GPU code for review without changing its token sequence."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-up-chains'
OUT = ROOT / '.deps/gufo-q2-bench-routed-organization'
DIR = Path('src/models/qwen38_flash_next/kernels/rocm')
REL = DIR / 'kernels.hip.cpp'
INC = DIR / 'routed_gemm.inc'
EXPECTED = 'a5ccc81f7762beae74cf0bbb06e6aeebd44edf1c804c1473b63619af023a6cd5'


def main():
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if sha(BASE / REL) != EXPECTED:
        raise ValueError('Retained paired-HC-up source changed')
    original = (BASE / REL).read_text()
    start = original.index('template<WeightType kType, int BM, int BN, int BK, bool kPair = false,')
    end = original.index('/// Compacts the routed assignments', start)
    body = original[start:end]
    header = '''// SPDX-License-Identifier: MIT
// Routed projection implementation extracted verbatim from the independently
// fetched Gufo-derived kernels.hip.cpp. See this experiment's source manifest.
// Included once inside that translation unit's anonymous namespace, after the
// common WMMA/format helpers. This is not a standalone public header.

'''
    include = '#include "' + str(INC) + '"\n\n'
    changed = original[:start] + include + original[end:]
    shutil.copytree(BASE, OUT)
    (OUT / REL).write_text(changed)
    (OUT / INC).write_text(header + body)
    if changed.replace(include, (OUT / INC).read_text()[len(header):]) != original:
        raise ValueError('Textual reconstruction changed')
    patch = ''.join(difflib.unified_diff(original.splitlines(True),
        changed.splitlines(True), fromfile='a/' + str(REL), tofile='b/' + str(REL)))
    patch += ''.join(difflib.unified_diff([], (header + body).splitlines(True),
        fromfile='/dev/null', tofile='b/' + str(INC)))
    patch_path = ROOT / 'experiments/q2-routed-organization.patch'
    patch_path.write_text(patch)
    anchors = {
        'dispatch_geometry_and_LDS': '  static_assert(BM == 128',
        'routing_and_buffer_views': '  const std::int32_t tile = tiles[blockIdx.y];',
        'weight_and_activation_prefetch': '  const auto fetch_stage =',
        'LDS_staging_and_affine_metadata': '  const auto commit_stage =',
        'WMMA_compute': '  const auto compute_stage =',
        'stage_pipeline': '  fetch_stage(0);',
        'compensated_result': '  if constexpr (kQ2) {\n#pragma unroll\n    for (int u',
        'paired_gate_up_epilogue': '  if constexpr (kPair) {\n    // Four waves',
        'F16_block_scatter': '  // One wave writes a complete 128-byte line',
        'F32_wave_scatter': '  // Transpose each 16x16 tile through LDS',
    }
    text = header + body
    regions = {name: text[:text.index(anchor)].count('\n') + 1
               for name, anchor in anchors.items()}
    report = dict(scope='Organization-only source view; no runtime dispatch or performance claim',
        pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
        base=str(BASE.relative_to(ROOT)), candidate=str(OUT.relative_to(ROOT)),
        base_sha256=sha(BASE / REL), candidate_sha256=sha(OUT / REL),
        extracted_sha256=sha(OUT / INC), patch_sha256=sha(patch_path),
        extracted_file=str(INC), extracted_original_lines=body.count('\n'),
        textual_reconstruction_exact=True, regions=regions,
        remaining_work='Compare all compiled device functions and metadata; runtime source stays unchanged')
    (ROOT / 'config/q2-routed-organization-source.json').write_text(
        json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
