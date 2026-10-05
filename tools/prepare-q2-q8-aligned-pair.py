#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Cooperative aligned Q8 pair fetch; original encoded bytes and arithmetic."""
import difflib,importlib.util,json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REL='src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'
def module(name):
 spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/name);v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v);return v
common=module('prepare-q2-q8-halfpair.py');literal=module('prepare-q2-q8-grouped.py')
sha,inventory,once=common.sha,common.inventory,common.once

def main():
 parent_path=ROOT/'config/q2-half-consumer-eight-source.json';parent=json.loads(parent_path.read_text())['variants']['half-consumer-eight'];base=ROOT/parent['source']
 if inventory(base)!=parent['files']:raise ValueError('Measured parent provider changed')
 original=(base/REL).read_text();kernel=literal.function(original,'template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,')
 anchor='''      } else {
        const std::uint8_t* blk =
            a_ptr[p] +
            (static_cast<std::size_t>(live ? kb : (num_kb - 1)) * 34);'''
 new='''      } else {
        // Adjacent lanes own the two K32 blocks of one row. Read all68
        // original bytes once at4-byte-aligned offsets; preserve both scales
        // and every signed code. Other geometry/odd K/unaligned bases retain
        // the original fetch. No extra weight copy or arithmetic change.
        if constexpr (BM == 256 && BN == 128 && BK == 2 && WM == 8 &&
                      WN == 1 && kRowGroup == 1 && !kHcMix) {
          if ((num_kb & 1) == 0 &&
              (reinterpret_cast<std::uintptr_t>(w_bytes) & 3u) == 0) {
            const auto* pair = static_cast<const std::uint8_t*>(
                __builtin_assume_aligned(
                    a_ptr[p] + static_cast<std::size_t>(kb & ~1) * 34, 4));
            const bool odd = (lane_id & 1) != 0;
            const unsigned offset = odd ? 36u : 0u;
            uint4 lo, hi;
            __builtin_memcpy(&lo, pair + offset, 16);
            __builtin_memcpy(&hi, pair + offset + 16, 16);
            std::uint32_t end_word = 0;
            if (!odd)
              __builtin_memcpy(&end_word, pair + 32, 4);
            // All lanes participate after the conditional load. An even
            // lane supplies its own adjacent odd lane's original scale.
            end_word = __shfl(end_word, lane_id & ~1);
            a_d[p] = live ? (odd ? end_word >> 16 : lo.x & 0xffffu) : 0u;
            if (odd) {
              a_codes[p][0] = lo;
              a_codes[p][1] = hi;
            } else {
              a_codes[p][0] = make_uint4(
                  (lo.x >> 16) | (lo.y << 16),
                  (lo.y >> 16) | (lo.z << 16),
                  (lo.z >> 16) | (lo.w << 16),
                  (lo.w >> 16) | (hi.x << 16));
              a_codes[p][1] = make_uint4(
                  (hi.x >> 16) | (hi.y << 16),
                  (hi.y >> 16) | (hi.z << 16),
                  (hi.z >> 16) | (hi.w << 16),
                  (hi.w >> 16) | (end_word << 16));
            }
            continue;
          }
        }
        const std::uint8_t* blk =
            a_ptr[p] +
            (static_cast<std::size_t>(live ? kb : (num_kb - 1)) * 34);'''
 changed=once(original,kernel,once(kernel,anchor,new))
 source=ROOT/'.deps/gufo-q2-q8-aligned-pair-run';patch=ROOT/'experiments/q2-q8-aligned-pair.patch';control=ROOT/'experiments/q2-q8-aligned-pair-control.inc';manifest=ROOT/'config/q2-q8-aligned-pair-source.json'
 if any(p.exists() for p in (source,patch,control,manifest)):raise ValueError('Refusing to overwrite retained experiment')
 fmt=subprocess.run(['/opt/rocm/llvm/bin/clang-format','--sort-includes=false','--style=file:'+str(base/'.clang-format'),'--assume-filename='+str(base/REL)],input=changed,text=True,capture_output=True)
 if fmt.returncode:raise ValueError('Provider format failed: '+fmt.stderr)
 changed=fmt.stdout;shutil.copytree(base,source);(source/REL).write_text(changed);files=inventory(source);delta=[n for n in files if files[n]!=parent['files'].get(n)]
 if len(files)!=1026 or delta!=[REL]:raise ValueError('Unexpected source delta')
 with control.open('x') as f:f.write('// SPDX-License-Identifier: MIT\n// Literal saved1571 parent dense kernel; shared helpers unchanged.\n'+kernel.replace('DenseF16GEMMKernel','DenseQ8AlignedPairControlKernel')+'\n')
 with patch.open('x') as f:f.write('// SPDX-License-Identifier: MIT\n'+''.join(difflib.unified_diff(original.splitlines(True),changed.splitlines(True),fromfile='a/'+REL,tofile='b/'+REL)))
 variant=dict(source=str(source.relative_to(ROOT)),files=files,changed_files=delta,parent_manifest=str(parent_path.relative_to(ROOT)),parent_manifest_sha256=sha(parent_path),measured_parent='config/q2-half-consumer-eight-model-results.json',measured_parent_sha256=sha(ROOT/'config/q2-half-consumer-eight-model-results.json'),control_include=str(control.relative_to(ROOT)),control_include_sha256=sha(control),patch=str(patch.relative_to(ROOT)),patch_sha256=sha(patch),affected='Three wide Q8 dense BM256/BN128/BK2/WM8/WN1 bodies:plain,SSM,attention; all other specializations unchanged.',numerical_contract='Retain both original scale bit patterns,all64 signed payload bytes,zero-scale ragged rows,half add/FMA,original K16 WMMA sequence and unchanged epilogues. Odd K32/unaligned bases use original fetch.',mechanism='Two adjacent lanes fetch the original68-byte weight pair as four16-byte plus one4-byte aligned loads. Even payload uses16-bit reassembly; second scale is exchanged by lane shuffle.',risks='Extra shifts/lane exchange,parity scheduling,register growth and fallback branching may outweigh alignment; logical load count is not hardware transaction evidence.',stage_layout_unchanged=True,tile_geometry_unchanged=True,additional_runtime_allocations=0,additional_streams=0,additional_device_tables=0,gpu_run=False,full_model_measured=False,numerical_acceptance=False,goal_met=False)
 with manifest.open('x') as f:json.dump(dict(schema='synapse-lie.q2-q8-aligned-pair-source.v1',variants={'q8-aligned-pair':variant},gpu_run=False,goal_met=False),f,indent=2);f.write('\n')
 print(json.dumps(dict(provider_files=len(files),changed_files=delta,gpu_run=False)))
if __name__=='__main__':main()
