#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Probe the existing GDN recurrence with proven complete four-token windows."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new, 1)


def main():
    manifest_path = ROOT / 'config/q2-iq2-fixed-bounds-source.json'
    parent = json.loads(manifest_path.read_text())['variants']['iq2-fixed-bounds']
    base = ROOT / parent['source']
    original_path = base / REL
    assert sha(original_path) == parent['files'][REL]
    original = original_path.read_text()
    start = original.index('__launch_bounds__(256) __global__\n    void GdnRowSplitKernel(')
    end = original.index('\n}\n', start) + 2
    body = original[start:end].replace('GdnRowSplitKernel', 'GdnFullWindowDraftKernel')
    body = once(body, '  constexpr int d = kGdnDim;', '''  // A future selector must require n_tokens > 0 and n_tokens % 4 == 0.
  // Keep the original dimension, state ownership, window ring and arithmetic.
  constexpr int d = kGdnDim;''')
    body = once(body, '    const int last = static_cast<int>(n_tokens) - 1;\n', '')
    for kind in ('qk', 'v', 'm'):
        body = once(body, f'min((w * kW) + {kind}_tok, last)', f'(w * kW) + {kind}_tok')
    body = once(body, '(static_cast<int>(n_tokens) + kW - 1) / kW',
                      'static_cast<int>(n_tokens) / kW')
    body = once(body, '    const int t_end = min(kW, static_cast<int>(n_tokens) - (w * kW));\n    for',
                      '    constexpr int t_end = kW;\n#pragma unroll\n    for')
    out = ROOT / 'experiments/q2-gdn-full-window-draft.inc'
    prep = ROOT / 'evidence/q2-gdn-full-window-draft-preparation'
    assert not out.exists() and not prep.exists()
    prep.mkdir()
    out.write_text('// SPDX-License-Identifier: MIT\n'
                   '// Derived from independently pinned official Gufo; compiler-only draft.\n' + body + '\n')
    wrapper = prep / 'candidate.hip'
    wrapper.write_text('// SPDX-License-Identifier: MIT\n'
        '#include "' + str(original_path) + '"\n'
        'namespace gufo::models::qwen38_flash_next::rocm { namespace {\n'
        '#include "' + str(out) + '"\n'
        'void GdnFullWindowDraftLaunch(const float* conv, const float* scales,\n'
        '    const float* ab, float* state, float* raw, unsigned n,\n'
        '    unsigned kh, unsigned vh, hipStream_t stream) {\n'
        '  hipLaunchKernelGGL(GdnFullWindowDraftKernel, dim3(kGdnDim / 64, vh),\n'
        '    dim3(256), 0, stream, conv, scales, ab, state, raw, n, kh, vh);\n'
        '}\n}}\n')
    argv = json.loads((ROOT / 'evidence/q2-iq2-fixed-bounds-preparation/assembly-argv.json').read_text())
    argv[argv.index('-S') + 1] = str(wrapper)
    argv[argv.index('-o') + 1] = str(prep / 'candidate.s')
    (prep / 'assembly-argv.json').write_text(json.dumps(argv, indent=2) + '\n')
    report = dict(schema='synapse-lie.q2-gdn-full-window-draft.v1',
        source_manifest=str(manifest_path.relative_to(ROOT)), source_manifest_sha256=sha(manifest_path),
        donor=str(original_path.relative_to(ROOT)), donor_sha256=sha(original_path),
        include=str(out.relative_to(ROOT)), include_sha256=sha(out),
        generator=str(Path(__file__).relative_to(ROOT)), generator_sha256=sha(Path(__file__)),
        proposed_guard='n_tokens > 0 && n_tokens % 4 == 0; existing row-split dimension/snapshot guards',
        recurrence_order_changed=False, final_state_format_changed=False,
        previous_GPU_trials_rerun=False, provider_created=False, GPU_run=False,
        performance_claim=False, GPU_admission=False)
    with (ROOT / 'config/q2-gdn-full-window-draft.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(local_draft=True, tokens='positive multiples of four', GPU_run=False)))


if __name__ == '__main__':
    main()
