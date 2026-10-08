#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare ordered half-K phases for the active wide Q8 dense projection."""
import difflib,importlib.util,json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REL='src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'
def module(name):
 spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/name);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
common=module('prepare-q2-q8-halfpair.py');literal=module('prepare-q2-q8-grouped.py')
sha,inventory,once=common.sha,common.inventory,common.once

def main():
 parent_path=ROOT/'config/q2-iq2-raw-prefetch-source.json';parent=json.loads(parent_path.read_text())['variants']['iq2-raw-prefetch'];base=ROOT/parent['source']
 if inventory(base)!=parent['files']:raise ValueError('Measured parent provider changed')
 original=(base/REL).read_text();kernel=literal.function(original,'template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,')
 start=kernel.index('      v16h a_lo[kWaveRowTiles];');end=kernel.index('    }\n    __syncthreads();\n  }\n\n  if constexpr (kHalfWeights',start);body=kernel[start:end]
 phases="""      // SPDX-License-Identifier: MIT
      // Consume low K16 for each independent output, then its high K16.
      // The per-output accumulation sequence and all staged operands stay exact.
      if constexpr (!kHalfWeights && BM == 256 && BN == 128 && BK == 2 &&
                    WM == 8 && WN == 1 && kRowGroup == 1) {
#pragma unroll
        for (int half = 0; half < 2; ++half) {
          v16h a[kWaveRowTiles];
#pragma unroll
          for (int i = 0; i < kWaveRowTiles; ++i) {
            const int row = (((wave_row * kWaveRowTiles) + i) * 16) + sub_lane;
            uint4 c[2];
#pragma unroll
            for (int q = 0; q < 2; ++q)
              c[q] = s_a[kb][row][swizzle(row, q + 2 * half)];
            __builtin_memcpy(&a[i], &c[0], 32);
          }
#pragma unroll
          for (int j = 0; j < kWaveTokTiles; ++j) {
            const int t = (((wave_tok * kWaveTokTiles) + j) * 16) + sub_lane;
            uint4 c[2];
#pragma unroll
            for (int q = 0; q < 2; ++q)
              c[q] = s_b[kb][t][swizzle(t, q + 2 * half)];
            v16h b;
            __builtin_memcpy(&b, &c[0], 32);
#pragma unroll
            for (int i = 0; i < kWaveRowTiles; ++i)
              acc[i][j] = Wmma(a[i], b, acc[i][j]);
          }
        }
      } else {
"""+body+"""      }
"""
 changed=once(original,kernel,once(kernel,body,phases))
 source=ROOT/'.deps/gufo-q2-q8-k16-phases-run';patch=ROOT/'experiments/q2-q8-k16-phases.patch';control=ROOT/'experiments/q2-q8-k16-phases-control.inc';manifest=ROOT/'config/q2-q8-k16-phases-source.json'
 if any(p.exists() for p in (source,patch,control,manifest)):raise ValueError('Refusing to overwrite retained experiment')
 fmt=subprocess.run(['/opt/rocm/llvm/bin/clang-format','--style=file:'+str(base/'.clang-format'),'--assume-filename='+str(base/REL)],input=changed,text=True,capture_output=True)
 if fmt.returncode:raise ValueError('Provider format failed: '+fmt.stderr)
 changed=fmt.stdout;shutil.copytree(base,source);(source/REL).write_text(changed);files=inventory(source);delta=[n for n in files if files[n]!=parent['files'].get(n)]
 if len(files)!=1025 or delta!=[REL]:raise ValueError('Unexpected source delta')
 with control.open('x') as f:f.write('// SPDX-License-Identifier: MIT\n// Literal retained parent dense kernel; shared helpers are unchanged.\n'+kernel.replace('DenseF16GEMMKernel','DenseQ8K16ControlKernel')+'\n')
 with patch.open('x') as f:f.write('// SPDX-License-Identifier: MIT\n'+''.join(difflib.unified_diff(original.splitlines(True),changed.splitlines(True),fromfile='a/'+REL,tofile='b/'+REL)))
 variant=dict(source=str(source.relative_to(ROOT)),files=files,changed_files=delta,parent_manifest=str(parent_path.relative_to(ROOT)),parent_manifest_sha256=sha(parent_path),measured_parent='config/q2-iq2-raw-prefetch-model-results.json',measured_parent_sha256=sha(ROOT/'config/q2-iq2-raw-prefetch-model-results.json'),control_include=str(control.relative_to(ROOT)),control_include_sha256=sha(control),patch=str(patch.relative_to(ROOT)),patch_sha256=sha(patch),affected='Three wide Q8 dense BM256/BN128/BK2/WM8/WN1 bodies: plain,SSM,attention. All F16-weight,other dense,routed and decode specializations remain unchanged.',numerical_contract='Original Q8 codes/scale/F16 construction,staged bytes,low then high K16 WMMA per output,all K32 blocks in order,and unchanged epilogues. Only independent outputs are interleaved differently.',mechanism='Consume two K16 operand halves in separate unrolled phases, shortening simultaneous A/B half-fragment lifetimes and increasing distance between dependent WMMA on each output.',risks='Reordered LDS reads and scheduling may expose latency or increase instructions; lower register count is not occupancy/performance evidence.',stage_layout_unchanged=True,tile_geometry_unchanged=True,additional_runtime_allocations=0,additional_streams=0,additional_device_tables=0,gpu_run=False,full_model_measured=False,numerical_acceptance=False,goal_met=False)
 with manifest.open('x') as f:json.dump(dict(schema='synapse-lie.q2-q8-k16-phases-source.v1',variants={'q8-k16-phases':variant},gpu_run=False,goal_met=False),f,indent=2);f.write('\n')
 print(json.dumps(dict(provider_files=len(files),changed_files=delta,gpu_run=False)))
if __name__=='__main__':main()
