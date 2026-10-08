#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Expose known down-only output arguments to a local compiler probe."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new, 1)


def main():
    donor = ROOT / 'experiments/q2-down-fixed-bounds-draft.inc'
    manifest = ROOT / 'config/q2-down-fixed-bounds-draft.json'
    assert sha(donor) == json.loads(manifest.read_text())['include_sha256']
    text = donor.read_text().replace('RoutedQ2FixedBoundsDraftKernel', 'RoutedQ2FixedContractDraftKernel')
    text = once(text, 'const float* __restrict__ swiglu_gate, float* __restrict__ out,',
                      'const float* __restrict__ unused_swiglu_gate, float* __restrict__ out,')
    text = once(text, '__half* __restrict__ out_half, std::size_t input_m,',
                      '__half* __restrict__ unused_out_half, std::size_t input_m,')
    text = once(text, '  constexpr std::size_t m = 2560, k = 640;', '''  constexpr std::size_t m = 2560, k = 640;
  // LaunchRoutedQ2HalfStorage always supplies these two null arguments.
  // Keep the same ABI in this probe; a provider still needs a guarded selector.
  constexpr const float* swiglu_gate = nullptr;
  constexpr __half* out_half = nullptr;''')
    text = once(text, 'if (m % 8 == 0 && reinterpret_cast<std::uintptr_t>(out) % 16 == 0)',
                      'if constexpr (true)')
    text = once(text, 'if (slot >= 0 && row < m_i)', 'if (slot >= 0)')
    out = ROOT / 'experiments/q2-down-fixed-contract-draft.inc'
    prep = ROOT / 'evidence/q2-down-fixed-contract-draft-preparation'
    assert not out.exists() and not prep.exists()
    prep.mkdir()
    out.write_text(text)
    old_prep = ROOT / 'evidence/q2-down-fixed-bounds-draft-preparation'
    wrapper = (old_prep / 'candidate.hip').read_text().replace('q2-down-fixed-bounds-draft',
        'q2-down-fixed-contract-draft').replace('RoutedQ2FixedBoundsDraftKernel', 'RoutedQ2FixedContractDraftKernel')
    (prep / 'candidate.hip').write_text(wrapper)
    argv = json.loads((old_prep / 'assembly-argv.json').read_text())
    argv = [value.replace('q2-down-fixed-bounds-draft', 'q2-down-fixed-contract-draft') for value in argv]
    (prep / 'assembly-argv.json').write_text(json.dumps(argv, indent=2) + '\n')
    report = dict(schema='synapse-lie.q2-down-fixed-contract-draft.v1',
        donor=str(donor.relative_to(ROOT)), donor_sha256=sha(donor),
        include=str(out.relative_to(ROOT)), include_sha256=sha(out),
        generator=str(Path(__file__).relative_to(ROOT)), generator_sha256=sha(Path(__file__)),
        shape=dict(m=2560,k=640,BN=[16,48,64],output_alignment=16,swiglu_gate=None,out_half=None),
        active_path_change='Expose null output arguments, remove active aligned-output and proven row-tail tests; existing half-word exchange/arithmetic order stays.',
        provider_created=False, runtime_selector=False, GPU_run=False, performance_claim=False)
    with (ROOT / 'config/q2-down-fixed-contract-draft.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(local_draft=True, GPU_run=False, provider_created=False)))


if __name__ == '__main__':
    main()
