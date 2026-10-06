#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Integrate the measured LDS producer with disjoint ordinary-row packing."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'src/models/qwen38_flash_next/'
ROCM = MODEL + 'kernels/rocm/'
spec = importlib.util.spec_from_file_location('prior', ROOT / 'tools/prepare-q2-iq2-tail16.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
sha, inventory, once = prior.sha, prior.inventory, prior.once


def main():
    parent_path = ROOT / 'config/q2-iq2-fixed-bounds-source.json'
    parent = json.loads(parent_path.read_text())['variants']['iq2-fixed-bounds']
    base = ROOT / parent['source']
    assert inventory(base) == parent['files']
    donor = ROOT / 'experiments/q2-iq2-whole640-wave16-lds-draft.inc'
    static_path = ROOT / 'config/q2-iq2-whole640-wave16-static.json'
    static = json.loads(static_path.read_text())['variants']['lds']
    assert sha(donor) == static['draft_sha256']
    results_path = ROOT / 'config/q2-iq2-whole640-wave16-results.json'
    measured = json.loads(results_path.read_text())
    assert measured['exact_output_pairs'] == 104 and measured['commands'] == [0, 0, 0]
    target = ROOT / '.deps/gufo-q2-iq2-whole640-chain-run'
    manifest = ROOT / 'config/q2-iq2-whole640-chain-source.json'
    patch = ROOT / 'experiments/q2-iq2-whole640-chain.patch'
    assert not any(path.exists() for path in (target, manifest, patch))
    names = (MODEL + 'CMakeLists.txt', ROCM + 'executor.cpp', ROCM + 'executor.hpp',
             ROCM + 'kernels.hip.cpp', ROCM + 'kernels.hpp')
    original = {name: (base / name).read_text() for name in names}
    changed = dict(original)
    changed[names[0]] = once(changed[names[0]], '    ${QFN_ROCM_DIR}/iq2_mixed_tiles.c)',
        '    ${QFN_ROCM_DIR}/iq2_mixed_tiles.c\n'
        '    ${QFN_ROCM_DIR}/q2_iq2_tail16.c\n'
        '    ${QFN_ROCM_DIR}/q2_iq2_whole640_tiles.c)')
    changed[names[2]] = once(changed[names[2]],
        '  mutable std::uint32_t routed_iq2_tail_tiles_{0};',
        '  mutable std::uint32_t routed_iq2_tail_tiles_{0};\n'
        '  mutable std::uint32_t routed_iq2_whole640_tiles_{0};')
    text = changed[names[1]]
    text = once(text, '#include "iq2_mixed_tiles.h"',
                '#include "iq2_mixed_tiles.h"\n#include "q2_iq2_whole640_tiles.h"')
    text = once(text, '  routed_iq2_tail_tiles_ = 0;',
                '  routed_iq2_tail_tiles_ = 0;\n  routed_iq2_whole640_tiles_ = 0;')
    start = text.index('    // Keep the original down map at offset zero.')
    end = text.index('  } else if (n_tokens >= 1024', start)
    text = text[:start] + '''    // Preserve down descriptors and the original reservation. Only the full
    // 2048-row prefill partitions short tails into a fused producer span.
    const auto capacity = RoutedTileCapacity(
        static_cast<std::size_t>(n_tokens) * c.num_experts_used, c);
    routed_pair_offset_ = n_tiles;
    routed_pair_rows_ = 128;
    if (n_tokens == 2048) {
      lie_iq2_tail16_spans spans{};
      if (!lie_iq2_whole640_tiles(counts_host_, c.num_experts, n_tokens,
                                  c.num_experts_used, tiles_host_ + n_tiles,
                                  capacity, &spans)) {
        AssignError(error_msg, "invalid IQ2 whole640 expert map");
        return false;
      }
      routed_pair_tiles_ = spans.wide128;
      routed_iq2_tail_tiles_ = spans.tail64;
      routed_iq2_whole640_tiles_ = spans.tail16;
      n_tiles += spans.wide128 + spans.tail64 + spans.tail16;
    } else {
      lie_iq2_tile_spans spans{};
      if (!lie_iq2_mixed_tiles(counts_host_, c.num_experts, n_tokens,
                               c.num_experts_used, tiles_host_ + n_tiles,
                               capacity, &spans)) {
        AssignError(error_msg, "invalid IQ2 mixed expert map");
        return false;
      }
      routed_pair_tiles_ = spans.wide;
      routed_iq2_tail_tiles_ = spans.tail;
      n_tiles += spans.wide + spans.tail;
    }
    routed_iq2_mixed_ = true;
''' + text[end:]
    text = once(text, '                    routed_iq2_tail_tiles_, 64)))',
        '''                    routed_iq2_tail_tiles_, 64)) &&
               (!routed_iq2_whole640_tiles_ ||
                RoutedGatedIQ2Whole640(
                    l.ffn_gate_exps.data, l.ffn_up_exps.data,
                    static_cast<const __half*>(s_.x_half),
                    s_.routed_tiles + routed_pair_offset_ + routed_pair_tiles_ +
                        routed_iq2_tail_tiles_,
                    routed_iq2_whole640_tiles_, s_.routed_bounds,
                    s_.rows_token, s_.rows_slot, scaled, inverse, stream_)))''')
    text = once(text,
        '''        !PackQ2ScaledRows(s_.gate_e, scaled, inverse, n_tokens * used,
                          c.expert_ff, stream_) ||''',
        '''        !(routed_iq2_whole640_tiles_
              ? PackQ2ScaledOrdinaryRows(
                    s_.gate_e, scaled, inverse,
                    s_.routed_tiles + routed_pair_offset_, routed_pair_tiles_,
                    routed_iq2_tail_tiles_, s_.routed_bounds, s_.rows_slot,
                    stream_)
              : PackQ2ScaledRows(s_.gate_e, scaled, inverse, n_tokens * used,
                                  c.expert_ff, stream_)) ||''')
    changed[names[1]] = text
    changed[names[3]] = once(changed[names[3]], '#include "q2_scaled_input.inc"',
        '#include "q2_scaled_input.inc"\n#include "q2_iq2_whole640_kernel.inc"\n'
        '#include "q2_iq2_whole640_chain.inc"')
    changed[names[4]] = once(changed[names[4]], 'bool PackQ2ScaledRows(', '''// Disjoint producer/packing ownership for full Q2 prefill expert tails.
bool RoutedGatedIQ2Whole640(const void*, const void*, const __half*,
                            const std::int32_t*, std::uint32_t,
                            const std::int32_t*, const std::int32_t*,
                            const std::int32_t*, __half*, float*, hipStream_t);
bool PackQ2ScaledOrdinaryRows(const float*, __half*, float*,
                             const std::int32_t*, std::uint32_t, std::uint32_t,
                             const std::int32_t*, const std::int32_t*,
                             hipStream_t);
bool PackQ2ScaledRows(''')
    added_sources = {ROCM + name: ROOT / 'experiments' / name for name in
        ('q2_iq2_tail16.c', 'q2_iq2_tail16.h',
         'q2_iq2_whole640_tiles.c', 'q2_iq2_whole640_tiles.h')}
    added_sources[ROCM + 'q2_iq2_whole640_kernel.inc'] = donor
    added_sources[ROCM + 'q2_iq2_whole640_chain.inc'] = ROOT / 'experiments/q2-iq2-whole640-chain.inc'
    additions = {name: path.read_bytes() for name, path in added_sources.items()}
    shutil.copytree(base, target)
    for name, data in changed.items():
        (target / name).write_text(data)
    for name, data in additions.items():
        (target / name).write_bytes(data)
    files = inventory(target)
    delta = sorted(name for name in files if files[name] != parent['files'].get(name))
    assert len(files) == 1034 and delta == sorted([*changed, *additions])
    with patch.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n')
        for name in names:
            stream.write(''.join(difflib.unified_diff(original[name].splitlines(True),
                changed[name].splitlines(True), fromfile='a/' + name, tofile='b/' + name)))
        for name, data in additions.items():
            stream.write(''.join(difflib.unified_diff([], data.decode().splitlines(True),
                fromfile='/dev/null', tofile='b/' + name)))
    row = dict(source=str(target.relative_to(ROOT)), files=files, changed_files=delta,
        mechanism='Preserve original down map. Partition full2048 IQ2 gate/up into wide128, '
                  'ordinary64 and whole640 spans. Fuse only the last span and pack only ordinary '
                  'slots, preserving dyadic scale, row ownership and the unchanged down consumer.',
        eligibility='Original IQ2 mixed WMMA path, n_tokens==2048, <=512 experts; tails1..16.',
        added_source_hashes={str(path.relative_to(ROOT)): sha(path) for path in added_sources.values()},
        additional_device_allocations=0, additional_streams=0,
        additional_count_downloads=0, descriptor_capacity_unchanged=True,
        inherited_fused_device_source_exact=True, original_down_sources_unchanged=True,
        partial_F32_intermediate=True, numerical_acceptance=False,
        GPU_run=False, full_model_measured=False, goal_met=False)
    for key, path in dict(parent_manifest=parent_path, measured_parent=ROOT / 'config/q2-iq2-fixed-bounds-model-results.json',
                          qualified_component=results_path, qualified_static=static_path,
                          generator=Path(__file__), patch=patch).items():
        row[key], row[key + '_sha256'] = str(path.relative_to(ROOT)), sha(path)
    with manifest.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-iq2-whole640-chain-source.v1',
                       variants={'iq2-whole640-chain': row}), stream, indent=2)
        stream.write('\n')
    assert inventory(base) == parent['files']
    print(json.dumps(dict(provider_files=1034, changed_files=delta, GPU_run=False)))


if __name__ == '__main__':
    main()
