#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compose the existing Q2 scaled 64-row kernel with a bounded C17 selector."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(folder):
    return {str(p.relative_to(folder)): sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}


def once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Unexpected source anchor: ' + before[:120])
    return text.replace(before, after, 1)


def main():
    parent_path = ROOT / 'config/q2-hc-moe-deferred-source.json'
    parent = json.loads(parent_path.read_text())
    base = parent['variants']['hc-moe-deferred']
    source = ROOT / base['source']
    if inventory(source) != base['files']:
        raise ValueError('Measured parent provider changed')
    candidate = ROOT / '.deps/gufo-q2-scaled-selective-run'
    output = ROOT / 'config/q2-scaled-selective-source.json'
    patch_path = ROOT / 'experiments/q2-scaled-selective.patch'
    if any(p.exists() for p in (candidate, output, patch_path)):
        raise ValueError('Refusing to overwrite a retained candidate')
    replacements = {REL + name: (ROOT / 'experiments' / name).read_text()
                    for name in ('q2_scaled_tiles_map.h', 'q2_scaled_tiles_map.c')}
    cmake = 'src/models/qwen38_flash_next/CMakeLists.txt'
    replacements[cmake] = once((source / cmake).read_text(),
        '    ${QFN_ROCM_DIR}/iq2_mixed_tiles.c)',
        '    ${QFN_ROCM_DIR}/iq2_mixed_tiles.c\n    ${QFN_ROCM_DIR}/q2_scaled_tiles_map.c)')
    header = (source / (REL + 'executor.hpp')).read_text()
    header = once(header, '#include "lie_q2_deferred_norm_state.h"',
        '#include "lie_q2_deferred_norm_state.h"\n#include "q2_scaled_tiles_map.h"')
    header = once(header, '  mutable bool routed_iq2_mixed_{false};',
        '  mutable bool routed_iq2_mixed_{false};\n'
        '  mutable std::uint32_t routed_q2_down64_tiles_{0};\n'
        '  mutable lie_q2_scaled_tile_spans scaled_tile_records_[256]{};\n'
        '  mutable std::uint32_t scaled_tile_record_count_{0};\n'
        '  mutable std::uint64_t scaled_tile_calls_{0};')
    replacements[REL + 'executor.hpp'] = header
    text = (source / (REL + 'executor.cpp')).read_text()
    text = once(text, '#include <cstddef>', '#include <cstddef>\n#include <cstdio>')
    text = once(text, 'Executor::~Executor() {', '''Executor::~Executor() {
  // This isolated candidate records routing in bounded host storage. Emit it
  // only at executor teardown, after the original benchmark's complete event
  // and outside every PP/TG timer; no I/O is added to RouteHints.
  if (scaled_tile_calls_ != 0) {
    std::fprintf(stdout, "{\\"event\\":\\"q2_scaled_tile_usage\\",\\"calls\\":%llu,"
        "\\"records\\":%u,\\"capacity\\":256}\\n",
        static_cast<unsigned long long>(scaled_tile_calls_), scaled_tile_record_count_);
    for (std::uint32_t i = 0; i < scaled_tile_record_count_; ++i) {
      const auto& s = scaled_tile_records_[i];
      std::fprintf(stdout, "{\\"event\\":\\"q2_scaled_tile_map\\",\\"index\\":%u,"
          "\\"narrow\\":%u,\\"wide\\":%u,\\"selected_experts\\":%u,\\"selected_rows\\":%u,"
          "\\"original_tiles\\":%u,\\"original_reserved_rows\\":%u,\\"reserved_rows\\":%u,"
          "\\"max_rows\\":%u,\\"histogram\\":[%u,%u,%u,%u,%u,%u]}\\n",
          i, s.narrow, s.wide, s.selected_experts, s.selected_rows,
          s.original_tiles, s.original_reserved_rows, s.reserved_rows, s.max_rows,
          s.histogram[0], s.histogram[1], s.histogram[2], s.histogram[3],
          s.histogram[4], s.histogram[5]);
    }
  }''')
    text = once(text, '  routed_iq2_mixed_ = false;',
        '  routed_iq2_mixed_ = false;\n  routed_q2_down64_tiles_ = 0;')
    text = once(text, '  for (std::uint32_t e = 0; e < c.num_experts; ++e) {\n'
                     '    const std::uint32_t padded = (counts_host_[e] + 15u) / 16u * 16u;\n'
                     '    max_rows = std::max(max_rows, counts_host_[e]);',
        '  const bool selective_q2 = mixed_iq2 && n_tokens >= 1024 && n_tokens <= 4096 &&\n'
        '      c.num_experts <= 512 && routed_tile_rows_ == kRoutedTileRowsWide;\n'
        '  for (std::uint32_t e = 0; e < c.num_experts; ++e) {\n'
        '    const std::uint32_t padded = (counts_host_[e] + 15u) / 16u * 16u;\n'
        '    max_rows = std::max(max_rows, counts_host_[e]);\n'
        '    if (selective_q2) continue;')
    text = once(text,
        '  if (mixed_iq2 && n_tokens >= 1024 && n_tokens <= 4096 &&\n'
        '      c.num_experts <= 512 && routed_tile_rows_ == kRoutedTileRowsWide) {\n'
        '    // Keep the original down map at offset zero. Append only the two\n'
        '    // gate/up spans; their total fits one existing map-capacity reservation.\n'
        '    lie_iq2_tile_spans spans{};\n'
        '    const auto capacity = RoutedTileCapacity(\n'
        '        static_cast<std::size_t>(n_tokens) * c.num_experts_used, c);',
        '''  if (selective_q2) {
    // Replace the original down reservation with disjoint 48/64-row spans.
    // No more rows or descriptors than the original 48 map are reserved.
    const auto capacity = RoutedTileCapacity(
        static_cast<std::size_t>(n_tokens) * c.num_experts_used, c);
    lie_q2_scaled_tile_spans down{};
    if (!lie_q2_scaled_tiles_map(counts_host_, c.num_experts, n_tokens,
          c.num_experts_used, tiles_host_, capacity, &down)) {
      AssignError(error_msg, "invalid selective Q2 down map");
      return false;
    }
    routed_n_tiles_ = down.narrow;
    routed_q2_down64_tiles_ = down.wide;
    n_tiles = down.narrow + down.wide;
    ++scaled_tile_calls_;
    if (scaled_tile_record_count_ < 256) {
      scaled_tile_records_[scaled_tile_record_count_++] = down;
    }
    // Append the unchanged original gate/up spans within their reservation.
    lie_iq2_tile_spans spans{};''')
    text = once(text,
        '    if (!gate_ok ||\n'
        '        !PackQ2ScaledRows(s_.gate_e, scaled, inverse, n_tokens * used,\n'
        '                          c.expert_ff, stream_) ||\n'
        '        !RoutedQ2ScaledGemm(l.ffn_down_exps.data, scaled, inverse,\n'
        '                            s_.routed_tiles, routed_n_tiles_, routed_tile_rows_,\n'
        '                            s_.routed_bounds, s_.rows_slot, s_.down_e,\n'
        '                            c.hidden_size, c.expert_ff, stream_)) {',
        '''    const auto down = [&](std::uint32_t offset, std::uint32_t count,
                          std::uint32_t rows) {
      return count == 0 || RoutedQ2ScaledGemm(l.ffn_down_exps.data, scaled, inverse,
          s_.routed_tiles + offset, count, rows, s_.routed_bounds, s_.rows_slot,
          s_.down_e, c.hidden_size, c.expert_ff, stream_);
    };
    if (!gate_ok ||
        !PackQ2ScaledRows(s_.gate_e, scaled, inverse, n_tokens * used,
                          c.expert_ff, stream_) ||
        !down(0, routed_n_tiles_, routed_tile_rows_) ||
        !down(routed_n_tiles_, routed_q2_down64_tiles_, 64)) {''')
    replacements[REL + 'executor.cpp'] = text
    shutil.copytree(source, candidate)
    for name, value in replacements.items():
        (candidate / name).write_text(value)
    files = inventory(candidate)
    changed = [name for name, digest in files.items() if base['files'].get(name) != digest]
    if set(changed) != set(replacements) or len(files) != 1027:
        raise ValueError('Unexpected source delta')
    patch = '// SPDX-License-Identifier: MIT\n'
    for name in changed:
        before = (source / name).read_text() if (source / name).exists() else ''
        patch += ''.join(difflib.unified_diff(before.splitlines(True),
            (candidate / name).read_text().splitlines(True), fromfile='a/' + name, tofile='b/' + name))
    with patch_path.open('x') as stream:
        stream.write(patch)
    variant = dict(source=str(candidate.relative_to(ROOT)), files=files, changed_files=changed,
        unchanged_files=len(files)-len(changed), parent_variant='hc-moe-deferred',
        parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
        patch=str(patch_path.relative_to(ROOT)), patch_sha256=sha(patch_path),
        c17_policy_files={name:sha(ROOT/'experiments'/name) for name in ('q2_scaled_tiles_map.h','q2_scaled_tiles_map.c')},
        existing_kernel_files_unchanged=True, gate_up_maps_unchanged=True,
        selector='Per expert: >=256 padded rows and reserved64<=reserved48; otherwise48',
        map_capacity_unchanged=True, additional_device_allocations=0, additional_streams=0,
        additional_host_record_bytes=256*14*4, record_capacity=256,
        route_event_io_scope='Executor destructor after original complete event; outside PP/TG',
        gpu_run=False, model_forward=False, numerical_qualification=False, performance_qualification=False)
    report = dict(schema='synapse-lie.q2-scaled-selective-source.v1', variants={'scaled-selective':variant},
        control_files=parent['control_files'], control_parent=parent['control_parent'],
        control_parent_manifest=parent['control_parent_manifest'],
        control_parent_manifest_sha256=parent['control_parent_manifest_sha256'],
        measured_parent='config/q2-hc-moe-deferred-model-results.json',
        measured_parent_sha256=sha(ROOT/'config/q2-hc-moe-deferred-model-results.json'),
        retained_component='config/q2-scaled-tiles-results.json',
        retained_component_sha256=sha(ROOT/'config/q2-scaled-tiles-results.json'),
        gpu_run=False, model_forward=False, goal_met=False)
    with output.open('x') as stream:
        json.dump(report,stream,indent=2); stream.write('\n')
    print(json.dumps(dict(files=len(files),changed=changed,c17_policy=True,
                         kernel_files_unchanged=True,new_device_allocation_bytes=0,gpu_run=False)))


if __name__ == '__main__':
    main()
