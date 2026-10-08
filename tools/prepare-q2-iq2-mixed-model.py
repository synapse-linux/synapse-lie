#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Integrate the measured C17 mixed map into an isolated ordered-IQ2 provider."""
import difflib
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'src/models/qwen38_flash_next/'
ROCM = MODEL+'kernels/rocm/'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Unexpected source anchor: '+old[:100])
    return text.replace(old, new, 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume-verified-parent', action='store_true',
                        help='Resume only a complete byte-identical parent copy; never replace a candidate')
    args = parser.parse_args()
    parent_path = ROOT/'config/q2-iq2-signs-ordered-asm-source.json'
    parent = json.loads(parent_path.read_text())
    base = ROOT/parent['candidate']
    inventory = {str(p.relative_to(base)):sha(p) for p in base.rglob('*') if p.is_file()}
    if inventory != parent['files']:
        raise ValueError('Measured ordered-IQ2 parent changed')
    result_path = ROOT/'config/q2-iq2-mixed-results.json'
    result = json.loads(result_path.read_text())
    if not result['exact'] or not result['numerical_pass']:
        raise ValueError('Mixed component did not qualify numerically')
    if not all(cell[scope]['time_change_percent'] < 0
               for name,cell in result['cells'].items() if name != 'full-tiles'
               for scope in ('resident-map-cycle','map-upload-cycle')):
        raise ValueError('Measured routing did not improve')
    original = {name:(base/name).read_text() for name in
                (MODEL+'CMakeLists.txt', ROCM+'executor.cpp', ROCM+'executor.hpp')}
    changed = dict(original)
    name = MODEL+'CMakeLists.txt'
    changed[name] = replace(changed[name],
        '  target_sources(gufo_qwen38_flash_next PRIVATE ${QFN_HIP_SOURCES})',
        '''  target_sources(gufo_qwen38_flash_next PRIVATE ${QFN_HIP_SOURCES}
    ${QFN_ROCM_DIR}/iq2_mixed_tiles.c)
  set_target_properties(gufo_qwen38_flash_next PROPERTIES
    C_STANDARD 17 C_STANDARD_REQUIRED ON C_EXTENSIONS OFF)''')
    name = ROCM+'executor.hpp'
    changed[name] = replace(changed[name],
        '  bool RouteHints(std::uint32_t n_tokens, std::string* error_msg) const;',
        '''  bool RouteHints(std::uint32_t n_tokens, std::string* error_msg,
                  bool mixed_iq2 = false) const;''')
    changed[name] = replace(changed[name],
        '  mutable std::uint32_t routed_pair_rows_{64};',
        '''  mutable std::uint32_t routed_pair_rows_{64};
  mutable std::uint32_t routed_iq2_tail_tiles_{0};
  mutable bool routed_iq2_mixed_{false};''')
    name = ROCM+'executor.cpp'
    changed[name] = replace(changed[name], '#include "'+ROCM+'executor.hpp"',
                            '#include "'+ROCM+'executor.hpp"\n#include "iq2_mixed_tiles.h"')
    changed[name] = replace(changed[name],
        '''bool Executor::RouteHints(std::uint32_t n_tokens,
                          std::string* error_msg) const {''',
        '''bool Executor::RouteHints(std::uint32_t n_tokens,
                          std::string* error_msg, bool mixed_iq2) const {''')
    changed[name] = replace(changed[name], '  routed_pair_rows_ = 64;',
        '''  routed_pair_rows_ = 64;
  routed_iq2_tail_tiles_ = 0;
  routed_iq2_mixed_ = false;''')
    changed[name] = replace(changed[name],
        '  if (n_tokens >= 1024 && routed_tile_rows_ == kRoutedTileRowsWide) {',
        '''  if (mixed_iq2 && n_tokens >= 1024 && n_tokens <= 4096 &&
      c.num_experts <= 512 && routed_tile_rows_ == kRoutedTileRowsWide) {
    // Keep the original down map at offset zero. Append only the two
    // gate/up spans; their total fits one existing map-capacity reservation.
    lie_iq2_tile_spans spans{};
    const auto capacity = RoutedTileCapacity(
        static_cast<std::size_t>(n_tokens) * c.num_experts_used, c);
    if (!lie_iq2_mixed_tiles(counts_host_, c.num_experts, n_tokens,
                              c.num_experts_used, tiles_host_ + n_tiles,
                              capacity, &spans)) {
      AssignError(error_msg, "invalid IQ2 mixed expert map");
      return false;
    }
    routed_pair_offset_ = n_tiles;
    routed_pair_rows_ = 128;
    routed_pair_tiles_ = spans.wide;
    routed_iq2_tail_tiles_ = spans.tail;
    routed_iq2_mixed_ = true;
    n_tiles += spans.wide + spans.tail;
  } else if (n_tokens >= 1024 && routed_tile_rows_ == kRoutedTileRowsWide) {''')
    iq2 = '''  const bool iq2_wmma = ExpertMatrixRows(n_tokens) &&
                        l.ffn_gate_exps.type == GgmlType::kIQ2_XXS &&
                        l.ffn_up_exps.type == GgmlType::kIQ2_XXS &&
                        l.ffn_down_exps.type == GgmlType::kQ2_K &&
                        c.hidden_size == 2560 && c.expert_ff == 640 &&
                        l.ffn_down_exps.cols == 768;
'''
    changed[name] = replace(changed[name], iq2, '')
    changed[name] = replace(changed[name],
        '  if (!RouteHints(n_tokens, error_msg)) {',
        iq2+'  if (!RouteHints(n_tokens, error_msg, iq2_wmma)) {')
    changed[name] = replace(changed[name],
        '''    if (!RoutedGatedIQ2Gemm(
            l.ffn_gate_exps.data, l.ffn_up_exps.data,
            static_cast<const __half*>(s_.x_half),
            s_.routed_tiles + (pair_map ? routed_pair_offset_ : 0),
            pair_map ? routed_pair_tiles_ : routed_n_tiles_,
            pair_map ? routed_pair_rows_ : routed_tile_rows_, s_.routed_bounds,
            s_.rows_token, s_.rows_slot, s_.gate_e, c.expert_ff, c.hidden_size,
            stream_) ||''',
        '''    const auto gate_up = [&](std::uint32_t offset, std::uint32_t count,
                             std::uint32_t rows) {
      return RoutedGatedIQ2Gemm(
          l.ffn_gate_exps.data, l.ffn_up_exps.data,
          static_cast<const __half*>(s_.x_half), s_.routed_tiles + offset,
          count, rows, s_.routed_bounds, s_.rows_token, s_.rows_slot,
          s_.gate_e, c.expert_ff, c.hidden_size, stream_);
    };
    const bool gate_ok = routed_iq2_mixed_
        ? ((!routed_pair_tiles_ ||
            gate_up(routed_pair_offset_, routed_pair_tiles_, 128)) &&
           (!routed_iq2_tail_tiles_ ||
            gate_up(routed_pair_offset_ + routed_pair_tiles_,
                    routed_iq2_tail_tiles_, 64)))
        : gate_up(pair_map ? routed_pair_offset_ : 0,
                  pair_map ? routed_pair_tiles_ : routed_n_tiles_,
                  pair_map ? routed_pair_rows_ : routed_tile_rows_);
    if (!gate_ok ||''')
    additions = {ROCM+name: (ROOT/'experiments'/name).read_bytes()
                 for name in ('iq2_mixed_tiles.c','iq2_mixed_tiles.h')}
    host = json.loads((ROOT/'config/q2-iq2-mixed-host-results.json').read_text())
    for name in additions:
        local = 'experiments/'+Path(name).name
        if sha(ROOT/local) != host['fixtures'][local]:
            raise ValueError('C17 map differs from qualified component')
    out = ROOT/'.deps/gufo-q2-curve-iq2-mixed'
    manifest = ROOT/'config/q2-iq2-mixed-model-source.json'
    patch = ROOT/'experiments/q2-iq2-mixed-model.patch'
    if any(p.exists() for p in (manifest,patch)):
        raise ValueError('Refusing to overwrite candidate sources')
    if args.resume_verified_parent:
        copied = {str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()}
        if copied != inventory or any(p.is_symlink() for p in out.rglob('*')):
            raise ValueError('Resume requires a complete unchanged parent copy')
    else:
        shutil.copytree(base, out)
    for name,text in changed.items(): (out/name).write_text(text)
    for name,data in additions.items(): (out/name).write_bytes(data)
    files = {str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()}
    if set(files)-set(inventory) != set(additions) or any(
            files[name] != digest for name,digest in inventory.items() if name not in changed):
        raise ValueError('Unexpected provider changes')
    patch.write_text(''.join(''.join(difflib.unified_diff(
        original[name].splitlines(True),text.splitlines(True),
        fromfile='a/'+name,tofile='b/'+name)) for name,text in changed.items()))
    report = dict(schema='synapse-lie.q2-iq2-mixed-model-source.v1',
        base=parent['candidate'],candidate=str(out.relative_to(ROOT)),files=files,
        parent_manifest_sha256=sha(parent_path),component_result_sha256=sha(result_path),
        patch_sha256=sha(patch),changed_files=list(changed),added_files=list(additions),
        first_party_files={name:dict(source='experiments/'+Path(name).name,
                                    sha256=files[name],license='MIT') for name in additions},
        unchanged_parent_files=len(inventory)-len(changed),
        mechanism='Use the measured C17 mixed128/64 map only for eligible IQ2 matrix prefill. Preserve the original Q2 down map and all numerical kernels; upload one compact pair of gate/up spans.',
        unchanged='All numerical kernels, ordered IQ2 decode, Q2 scaled down, original PLE, allocation capacities, C17 core and ABI/state/metrics contracts.',
        scope='Model integration preparation; canonical PP/TG runtime remains required.',
        canonical_runtime_validated=False,promoted=False,goal_met=False)
    manifest.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('candidate','changed_files','added_files','unchanged_parent_files')}))


if __name__ == '__main__':
    main()
