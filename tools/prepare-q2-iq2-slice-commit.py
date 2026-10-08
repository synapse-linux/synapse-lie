#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bound IQ2 decode/store lifetimes while retaining compact high-byte LDS."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'
spec = importlib.util.spec_from_file_location('prior', ROOT/'tools/prepare-q2-iq2-fused-grid.py')
prior = importlib.util.module_from_spec(spec); spec.loader.exec_module(prior)
sha, inventory, once = prior.sha, prior.inventory, prior.once


def main():
    parent_path = ROOT/'config/q2-iq2-raw-prefetch-source.json'
    parent = json.loads(parent_path.read_text())['variants']['iq2-raw-prefetch']
    base = ROOT/parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Measured raw-prefetch parent inventory changed')
    original = (base/REL).read_text()
    commit_start = original.index('  const auto commit_stage =')
    start = original.index('        // One packed group:', commit_start)
    end = original.index('        const float scale =', start)
    old_decode = original[start:end]
    stores = '''        s_codes[swizzle(row, 2 * f_c)] = f_codes[u];
        s_codes[swizzle(row, (2 * f_c) + 1)] = f_codes_hi[u];'''
    control = ROOT/'experiments/q2-iq2-slice-commit-control.inc'
    manifest = ROOT/'config/q2-iq2-slice-commit-source.json'
    paths = [manifest]
    for name in ('iq2-slice-commit', 'iq2-pair-commit'):
        paths.extend([ROOT/('.deps/gufo-q2-'+name+'-run'), ROOT/('experiments/q2-'+name+'.patch')])
    if any(p.exists() for p in paths):
        raise ValueError('Refusing to overwrite retained experiment')
    kernel = prior.literal.function(original, 'template<WeightType kType, int BM, int BN, int BK, bool kPair = false,')
    control_text = '// SPDX-License-Identifier: MIT\n// Literal measured raw-prefetch1505 parent; old cohorts are not rebuilt.\n'
    control_text += kernel.replace('RoutedF16GEMMKernel', 'RoutedIq2SliceControlKernel')+'\n'
    if control.exists():
        if control.read_text() != control_text:
            raise ValueError('Partial preparation control changed')
    else:
        with control.open('x') as stream:
            stream.write(control_text)
    variants = {}
    for name, unit in (('iq2-slice-commit', 8), ('iq2-pair-commit', 16)):
        if unit == 8:
            decode = '''        // SPDX-License-Identifier: MIT
        // Decode and retire one exact eight-value high-byte slice at a time.
        // The raw group/header prefetch and compact LDS layout are unchanged.
#pragma unroll
        for (int part = 0; part < 4; ++part) {
          const unsigned code = (group.x >> (8 * part)) & 255U;
          const unsigned sign = (group.y >> (7 * part)) & 127U;
          const uint2 magnitude =
              reinterpret_cast<const uint2*>(kIq2HalfHighGrid)[code];
          const uint2 mask = reinterpret_cast<const uint2*>(ksigns64)[sign];
          const uint2 high = make_uint2(magnitude.x ^ (mask.x & 0x80808080U),
                                        magnitude.y ^ (mask.y & 0x80808080U));
          auto* slice = reinterpret_cast<uint2*>(
              s_codes + swizzle(row, 2 * f_c + part / 2));
          slice[part & 1] = high;
          // Compiler scheduling only; this is not a GPU synchronization.
          __builtin_amdgcn_sched_barrier(0);
        }
'''
        else:
            decode = '''        // SPDX-License-Identifier: MIT
        // Decode two eight-value slices and retire their original16-byte store.
        // Preserve compact LDS bytes and avoid retaining the full32-byte group.
#pragma unroll
        for (int pair = 0; pair < 2; ++pair) {
          uint2 high[2];
#pragma unroll
          for (int slice = 0; slice < 2; ++slice) {
            const int part = 2 * pair + slice;
            const unsigned code = (group.x >> (8 * part)) & 255U;
            const unsigned sign = (group.y >> (7 * part)) & 127U;
            const uint2 magnitude =
                reinterpret_cast<const uint2*>(kIq2HalfHighGrid)[code];
            const uint2 mask = reinterpret_cast<const uint2*>(ksigns64)[sign];
            high[slice] = make_uint2(magnitude.x ^ (mask.x & 0x80808080U),
                                     magnitude.y ^ (mask.y & 0x80808080U));
          }
          s_codes[swizzle(row, 2 * f_c + pair)] =
              make_uint4(high[0].x, high[0].y, high[1].x, high[1].y);
          // Compiler scheduling only; this is not a GPU synchronization.
          __builtin_amdgcn_sched_barrier(0);
        }
'''
        changed = once(original, old_decode, decode)
        iq2_end = changed.index('      } else if constexpr (kSigned || kQ2) {', commit_start)
        changed = changed[:commit_start] + once(changed[commit_start:iq2_end], stores, '') + changed[iq2_end:]
        formatted = subprocess.run(['/opt/rocm/llvm/bin/clang-format',
            '--style=file:'+str(base/'.clang-format'), '--assume-filename='+str(base/REL)],
            input=changed, capture_output=True, text=True)
        if formatted.returncode:
            raise ValueError('Formatting failed: '+formatted.stderr)
        changed = formatted.stdout
        folder = ROOT/('.deps/gufo-q2-'+name+'-run')
        shutil.copytree(base, folder); (folder/REL).write_text(changed)
        files = inventory(folder)
        delta = [p for p in files if files[p] != parent['files'].get(p)]
        if len(files) != 1025 or delta != [REL]:
            raise ValueError('Unexpected provider delta')
        patch = ROOT/('experiments/q2-'+name+'.patch')
        with patch.open('x') as stream:
            stream.write('// SPDX-License-Identifier: MIT\n')
            stream.write(''.join(difflib.unified_diff(original.splitlines(True), changed.splitlines(True), fromfile='a/'+REL, tofile='b/'+REL)))
        variants[name] = dict(source=str(folder.relative_to(ROOT)), files=files, changed_files=delta,
            parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
            measured_parent='config/q2-iq2-raw-prefetch-model-results.json', measured_parent_sha256=sha(ROOT/'config/q2-iq2-raw-prefetch-model-results.json'),
            control_include=str(control.relative_to(ROOT)), control_include_sha256=sha(control),
            patch=str(patch.relative_to(ROOT)), patch_sha256=sha(patch),
            mechanism='Bound decoded high-byte temporaries to '+str(unit)+' values per commit, with a compiler barrier after each store. Original raw prefetch, compact LDS and scale publication retained.',
            numerical_contract='Same original codebook/sign-mask bits, F32 scale expression/F16 rounding, packed F16 FMA, low/high K16 updates, routing/tails/SwiGLU and packed residual.',
            affected='Eight IQ2 paired routed specializations; Q2 down/dense/decode/attention are unchanged.',
            risks='More or earlier LDS stores and serialized table loads may erase lower register demand. Static instruction/resource counts are not speed claims.',
            stored_values_per_commit=unit, raw_prefetch_bytes_per_thread=10,
            stage_layout_unchanged=True, tile_geometry_unchanged=True,
            additional_runtime_allocations=0, additional_streams=0, additional_device_tables=0,
            full_model_measured=False, numerical_acceptance=False, gpu_run=False, goal_met=False)
    with manifest.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-iq2-slice-commit-source.v1',variants=variants,gpu_run=False,goal_met=False),stream,indent=2);stream.write('\n')
    print(json.dumps(dict(provider_files_each=1025,variants=list(variants),additional_tables=0,gpu_run=False)))


if __name__ == '__main__':
    main()
