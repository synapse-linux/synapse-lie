#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Alternate SSM activation LDS slots; retain wave ownership and final retirement."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ssm', ROOT / 'tools/prepare-q2-ssm-row-group.py')
ssm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ssm)


def schedule_checks():
    # Integer ownership/version model, not GPU execution or CPU model forward.
    for wave in range(8):
        for tile in range(2):
            for sub_lane in range(16):
                row = (wave * 2 + tile) * 16 + sub_lane
                assert row // 32 == wave  # BK1's writer thread is exactly row.

    def simulate(slots, seed, priority=False):
        stage = [0] * 8
        committed = [-1] * 8
        needs_commit = [True] * 8
        a_version = [-1] * 8
        b_version = [[-1] * 4 for _ in range(slots)]
        reads = events = 0
        while min(stage) < 80:
            available = [w for w in range(8) if stage[w] < 80 and
                         (needs_commit[w] or min(committed) >= stage[w])]
            assert available, 'Modeled barrier deadlock'
            seed = (1664525 * seed + 1013904223) & 0xFFFFFFFF
            wave = available[0] if priority else available[seed % len(available)]
            k = stage[wave]
            if needs_commit[wave]:
                a_version[wave] = k
                if wave < 4:
                    b_version[k % slots][wave] = k
                committed[wave] = k
                needs_commit[wave] = False
            else:
                if a_version[wave] != k or b_version[k % slots] != [k] * 4:
                    return dict(safe=False, wave=wave, stage=k, events=events,
                                activation_versions=b_version[k % slots])
                stage[wave] += 1
                needs_commit[wave] = True
                reads += 1
            events += 1
        assert reads == 640 and events == 1280
        return dict(safe=True, reads=reads, events=events)

    runs = [simulate(2, seed) for seed in range(128)] + [simulate(2, 0, True)]
    assert all(run['safe'] for run in runs)
    negative = simulate(1, 0, True)
    assert not negative['safe']  # One B slot cannot lose its retirement barrier.
    # A wave's final transpose owns4KiB, but its A slice owns2KiB. Without
    # the final block barrier, wave0 can overwrite wave1's still-live weights.
    overlap = set(range(0, 4096)) & set(range(2048, 4096))
    assert len(overlap) == 2048
    return dict(weight_rows_with_wave_local_ownership=256,
        activation_producer_waves=4, activation_consumer_waves=8,
        activation_slots=2, weight_stage_bytes=16384, activation_slot_bytes=8192,
        shared_stage_bytes=32768, schedules=len(runs),
        version_checked_stage_reads=sum(run['reads'] for run in runs),
        modeled_events=sum(run['events'] for run in runs),
        single_slot_negative_control=negative,
        missing_final_barrier_negative_overlap_bytes=len(overlap),
        retirement_argument='Writing B[k+2] requires passing publication barrier k+1. '
            'Every wave must finish reading k before committing k+1, so B[k] is retired. '
            'A rows have one owning wave, with a wave barrier before their next write. '
            'The final block barrier retires all matrix reads before transpose reuse.',
        source_block_barriers_parent=160, source_block_barriers_candidate=81,
        source_wave_barriers_added=80, final_block_barrier_required=True,
        hardware_scheduling_tested=False, floating_arithmetic_tested=False)


def main():
    previous_path = ROOT / 'config/q2-ssm-compact-lds-source.json'
    previous = json.loads(previous_path.read_text())['variants']['ssm-compact-lds']
    base = ROOT / previous['source']
    assert ssm.inventory(base) == previous['files']
    original = (base / ssm.REL).read_text()
    prefix = 'template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,'
    body = ssm.function(original, prefix)
    changed_body = ssm.once(body, '  constexpr int kLdsChunks = BK * (BM + BN) * 4;',
        '  // SSM A is wave-owned; B alternates two slots across all eight waves.\n'
        '  constexpr int kLdsChunks = BK * (BM + (kSsmConv ? 2 : 1) * BN) * 4;')
    changed_body = ssm.once(changed_body, '  const auto commit_stage = [&]() {',
        '  const auto commit_stage = [&](int stage_slot) {')
    changed_body = ssm.once(changed_body,
        '        s_b[kk][t][swizzle(t, c)] = b_data[p][c];',
        '        s_b[(kSsmConv ? stage_slot * BK : 0) + kk][t][swizzle(t, c)] =\n'
        '            b_data[p][c];')
    changed_body = ssm.once(changed_body, '    commit_stage();',
        '    commit_stage(kSsmConv ? (kb0 & 1) : 0);')
    changed_body = ssm.once(changed_body,
        '          c[q] = s_b[kb][t][swizzle(t, q + (kHcUpChains ? chain * 2 : 0))];',
        '          c[q] = s_b[(kSsmConv ? (kb0 & 1) * BK : 0) + kb][t]\n'
        '                    [swizzle(t, q + (kHcUpChains ? chain * 2 : 0))];')
    changed_body = ssm.once(changed_body, '''    __syncthreads();
  }

  if constexpr (kHalfWeights && !kHcUpChains) {''', '''    if constexpr (kSsmConv) {
      // A readers/writers belong to one wave; the next B slot is disjoint.
      static_assert(BK == 1 && WM == 8 && WN == 1 && kWaveRowTiles == 2);
      __builtin_amdgcn_wave_barrier();
    } else {
      __syncthreads();
    }
  }
  if constexpr (kSsmConv) {
    // The transpose reuses other waves' A/B bytes: retire the complete block.
    __syncthreads();
  }

  if constexpr (kHalfWeights && !kHcUpChains) {''')
    changed = ssm.once(original, body, changed_body)
    destination = ROOT / '.deps/gufo-q2-ssm-pingpong-run'
    manifest = ROOT / 'config/q2-ssm-pingpong-source.json'
    patch = ROOT / 'experiments/q2-ssm-pingpong.patch'
    assert not any(p.exists() for p in (destination, manifest, patch))
    proof = schedule_checks()
    shutil.copytree(base, destination)
    (destination / ssm.REL).write_text(changed)
    parent = json.loads((ROOT / previous['parent_manifest']).read_text())['variants']['down-register-scatter']
    parent_source = (ROOT / parent['source'] / ssm.REL).read_text()
    files = ssm.inventory(destination)
    assert len(files) == 1027 and [p for p in files if files[p] != parent['files'][p]] == [ssm.REL]
    with patch.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n' + ''.join(difflib.unified_diff(
            parent_source.splitlines(True), changed.splitlines(True), fromfile='a/' + ssm.REL, tofile='b/' + ssm.REL)))
    variant = dict(previous)
    variant['inherited_compact_layout_proof'] = previous['source_layout_proof']
    variant['source_layout_proof'] = dict(previous['source_layout_proof'],
        source_stage_bytes=[49152, 32768], source_barriers_per_block=[80, 81],
        block_barriers_per_k_stage=1, final_block_barriers=1,
        wave_barriers_per_k_stage=1)
    variant.update(source=str(destination.relative_to(ROOT)), files=files,
        patch=str(patch.relative_to(ROOT)), patch_sha256=ssm.sha(patch),
        preceding_local_manifest=str(previous_path.relative_to(ROOT)), preceding_local_manifest_sha256=ssm.sha(previous_path),
        mechanism='Compact SSM BK1 with wave-owned A and two alternating B slots. '
                  'Replace the per-stage block retirement with a wave barrier, keeping '
                  'one final block retirement before convolution transpose reuse.',
        synchronization_proof=proof,
        risks='Wave ownership and double-slot retirement require actual GPU validation. '
              'Extra slot addressing and compiler scheduling can offset fewer block barriers. '
              'Source integer schedules do not prove device memory ordering or speed.')
    with manifest.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-ssm-pingpong-source.v1',
                       variants={'ssm-pingpong': variant}, goal_met=False), stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(provider_files=1027, synchronization_proof=proof, gpu_run=False)))


if __name__ == '__main__':
    main()
