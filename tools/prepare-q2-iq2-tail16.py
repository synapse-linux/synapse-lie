#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Integrate bounded C17 short-expert spans into the measured Q2 parent."""
import argparse
import difflib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'src/models/qwen38_flash_next/'
ROCM = MODEL + 'kernels/rocm/'
spec = importlib.util.spec_from_file_location('prior', ROOT/'tools/prepare-q2-iq2-slice-commit.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
sha, inventory, once = prior.sha, prior.inventory, prior.once


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--record-usage', action='store_true', default=True,
        help='Prepare a distinct candidate with bounded post-timer usage records')
    args = parser.parse_args()
    parent_path = ROOT/'config/q2-ssm-fixed-bounds-source.json'
    parent = json.loads(parent_path.read_text())['variants']['ssm-fixed-bounds']
    base = ROOT/parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Measured parent inventory changed')
    out = ROOT/('.deps/gufo-q2-iq2-tail16-counted-run' if args.record_usage
                else '.deps/gufo-q2-iq2-tail16-run')
    manifest = ROOT/('config/q2-iq2-tail16-source-v2.json' if args.record_usage
                     else 'config/q2-iq2-tail16-source.json')
    patch = ROOT/('experiments/q2-iq2-tail16-v2.patch' if args.record_usage
                  else 'experiments/q2-iq2-tail16.patch')
    if any(p.exists() for p in (out, manifest, patch)):
        raise ValueError('Refusing to overwrite retained candidate')
    names = (MODEL+'CMakeLists.txt', ROCM+'executor.cpp', ROCM+'executor.hpp')
    original = {n:(base/n).read_text() for n in names}
    changed = dict(original)
    changed[names[0]] = once(changed[names[0]],
        '    ${QFN_ROCM_DIR}/iq2_mixed_tiles.c)',
        '    ${QFN_ROCM_DIR}/iq2_mixed_tiles.c\n    ${QFN_ROCM_DIR}/q2_iq2_tail16.c)')
    changed[names[2]] = once(changed[names[2]],
        '  mutable std::uint32_t routed_iq2_tail_tiles_{0};',
        '  mutable std::uint32_t routed_iq2_tail_tiles_{0};\n'
        '  mutable std::uint32_t routed_iq2_tail16_tiles_{0};')
    text = changed[names[1]]
    text = once(text, '#include "iq2_mixed_tiles.h"',
                '#include "iq2_mixed_tiles.h"\n#include "q2_iq2_tail16.h"')
    text = once(text, '  routed_iq2_tail_tiles_ = 0;',
                '  routed_iq2_tail_tiles_ = 0;\n  routed_iq2_tail16_tiles_ = 0;')
    text = once(text, '    lie_iq2_tile_spans spans{};', '    lie_iq2_tail16_spans spans{};')
    text = once(text, '    if (!lie_iq2_mixed_tiles(counts_host_,',
                '    if (!lie_iq2_tail16(counts_host_,')
    text = once(text, '    routed_pair_tiles_ = spans.wide;\n'
                '    routed_iq2_tail_tiles_ = spans.tail;',
                '    routed_pair_tiles_ = spans.wide128;\n'
                '    routed_iq2_tail_tiles_ = spans.tail64;\n'
                '    routed_iq2_tail16_tiles_ = spans.tail16;')
    text = once(text, '    n_tiles += spans.wide + spans.tail;',
                '    n_tiles += spans.wide128 + spans.tail64 + spans.tail16;')
    text = once(text, '    // Keep the original down map at offset zero. Append only the two\n'
                '    // gate/up spans; their total fits one existing map-capacity reservation.',
                '    // Keep down routing unchanged. Append128/64/16 gate/up spans;\n'
                '    // selecting16 for short tails adds no descriptors or memory.')
    text = once(text, '                    routed_iq2_tail_tiles_, 64)))',
                '                    routed_iq2_tail_tiles_, 64)) &&\n'
                '           (!routed_iq2_tail16_tiles_ ||\n'
                '            gate_up(routed_pair_offset_ + routed_pair_tiles_ +\n'
                '                        routed_iq2_tail_tiles_,\n'
                '                    routed_iq2_tail16_tiles_, 16)))')
    if args.record_usage:
        changed[names[2]] = once(changed[names[2]],
            '#include "lie_q2_deferred_norm_state.h"',
            '#include "lie_q2_deferred_norm_state.h"\n#include "q2_iq2_tail16.h"')
        changed[names[2]] = once(changed[names[2]],
            '  mutable std::uint32_t routed_iq2_tail16_tiles_{0};',
            '  mutable std::uint32_t routed_iq2_tail16_tiles_{0};\n'
            '  mutable lie_iq2_tail16_spans short_tile_records_[256]{};\n'
            '  mutable std::uint32_t short_tile_record_count_{0};\n'
            '  mutable std::uint64_t short_tile_calls_{0};')
        text = once(text, '#include <cstddef>', '#include <cstddef>\n#include <cstdio>')
        text = once(text, 'Executor::~Executor() {', '''Executor::~Executor() {
  // Bounded host copies are charged to inference; only output is deferred.
  // The original tester's complete event precedes executor teardown.
  if (short_tile_calls_ != 0) {
    std::fprintf(stdout, "{\\"event\\":\\"iq2_short_tile_usage\\",\\"calls\\":%llu,"
        "\\"records\\":%u,\\"capacity\\":256}\\n",
        static_cast<unsigned long long>(short_tile_calls_), short_tile_record_count_);
    for (std::uint32_t i = 0; i < short_tile_record_count_; ++i) {
      const auto& s = short_tile_records_[i];
      std::fprintf(stdout, "{\\"event\\":\\"iq2_short_tile_map\\",\\"index\\":%u,"
          "\\"wide128\\":%u,\\"tail64\\":%u,\\"tail16\\":%u}\\n",
          i, s.wide128, s.tail64, s.tail16);
    }
  }''')
        text = once(text, '    routed_iq2_tail16_tiles_ = spans.tail16;',
            '    routed_iq2_tail16_tiles_ = spans.tail16;\n'
            '    ++short_tile_calls_;\n'
            '    if (short_tile_record_count_ < 256)\n'
            '      short_tile_records_[short_tile_record_count_++] = spans;')
    changed[names[1]] = text
    additions = {ROCM+n:(ROOT/'experiments'/n).read_bytes()
                 for n in ('q2_iq2_tail16.c','q2_iq2_tail16.h')}
    shutil.copytree(base, out)
    for name, data in changed.items():
        (out/name).write_text(data)
    for name, data in additions.items():
        (out/name).write_bytes(data)
    files = inventory(out)
    delta = sorted(n for n in files if files[n] != parent['files'].get(n))
    if len(files) != 1029 or delta != sorted([*changed, *additions]):
        raise ValueError('Unexpected provider delta')
    with patch.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n')
        for name in names:
            stream.write(''.join(difflib.unified_diff(original[name].splitlines(True),
                changed[name].splitlines(True), fromfile='a/'+name, tofile='b/'+name)))
        for name, data in additions.items():
            stream.write(''.join(difflib.unified_diff([], data.decode().splitlines(True),
                fromfile='/dev/null', tofile='b/'+name)))
    variant = dict(source=str(out.relative_to(ROOT)), files=files, changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
        measured_parent='config/q2-ssm-fixed-bounds-model-results.json',
        measured_parent_sha256=sha(ROOT/'config/q2-ssm-fixed-bounds-model-results.json'),
        routing_audit='config/q2-current-routing-v2-results.json', routing_audit_sha256=sha(ROOT/'config/q2-current-routing-v2-results.json'),
        patch=str(patch.relative_to(ROOT)), patch_sha256=sha(patch),
        c17_map_files={str((ROOT/'experiments'/n).relative_to(ROOT)):sha(ROOT/'experiments'/n)
                       for n in ('q2_iq2_tail16.c','q2_iq2_tail16.h')},
        mechanism='Use existing BN16 IQ2 gate/up only for tails with1..16 live rows, including nonzero offsets; '
                  'retain original128/64 descriptors for other buckets and original down map.',
        numerical_contract='Existing original kernels/tables/arithmetic unchanged; new mixed '
                           'launch geometry still needs full-output and model qualification.',
        unchanged_numerical_sources={n:files[n] for n in files if n.startswith(ROCM) and
            n.endswith(('.hip','.hip.cpp','.inc'))},
        additional_allocations=0, additional_streams=0, additional_count_downloads=0,
        descriptor_capacity_unchanged=True, maximum_new_dispatches_per_eligible_layer=1,
        eligibility='Original IQ2 WMMA mixed map,1024<=n_tokens<=4096,<=512experts; tails1..16; descriptor indices converted to width16 units.',
        bounded_host_usage_records=args.record_usage,
        host_record_capacity=256 if args.record_usage else 0,
        usage_output_scope='Executor teardown after original complete event; host copies remain inside inference timers'
                           if args.record_usage else 'No usage logging',
        gpu_run=False, full_model_measured=False, numerical_acceptance=False, goal_met=False)
    report = dict(schema='synapse-lie.q2-iq2-tail16-source.v1', variants={'iq2-tail16':variant},
        gpu_run=False, goal_met=False)
    with manifest.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(variant='iq2-tail16', files=len(files), changed_files=delta,
        numerical_sources_unchanged=len(variant['unchanged_numerical_sources']), gpu_run=False)))


if __name__ == '__main__':
    main()
