#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Correct draft epilogue capacity and stage its exact half palette in registers."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    base=ROOT/'evidence/q2-down-register-stage-draft-preparation'
    initial=ROOT/'experiments/q2-down-register-stage-draft.inc'
    v2=initial.read_text().replace('RoutedQ2RegisterStageDraftKernel','RoutedQ2RegisterStageDraftV2Kernel')
    v2=v2.replace('constexpr int kLdsBytes = kStageBytes > 8 * 1024 ? kStageBytes : 8 * 1024;',
        'constexpr int kEpilogueBytes = 16 * (BM + 2) * sizeof(float);\n  constexpr int kLdsBytes = kStageBytes > kEpilogueBytes ? kStageBytes : kEpilogueBytes;')
    assert v2==(ROOT/'experiments/q2-down-register-stage-draft-v2.inc').read_text()
    s=v2.replace('RoutedQ2RegisterStageDraftV2Kernel','RoutedQ2RegisterStageDraftV3Kernel')
    s=s.replace('std::uint32_t stage_affine[kWaveRowTiles][4];','uint2 stage_palette[kWaveRowTiles][2];')
    old='''          stage_affine[u][2 * part] = __builtin_bit_cast(std::uint32_t, d);
          stage_affine[u][2 * part + 1] = __builtin_bit_cast(std::uint32_t, b);'''
    new='''          stage_palette[u][part] = make_uint2(
              __builtin_bit_cast(std::uint32_t,
                  __floats2half2_rn(fmaf(0.0F, d, b), fmaf(1.0F, d, b))),
              __builtin_bit_cast(std::uint32_t,
                  __floats2half2_rn(fmaf(2.0F, d, b), fmaf(3.0F, d, b))));'''
    assert s.count(old)==1;s=s.replace(old,new)
    a=s.index('            const float d = __builtin_bit_cast(float, stage_word(stage_affine')
    b=s.index('\n          }\n        }\n#pragma unroll',a)
    s=s[:a]+'''            palette[part] = make_uint2(
                stage_word(stage_palette[u][part].x, kb),
                stage_word(stage_palette[u][part].y, kb));'''+s[b:]
    output=ROOT/'experiments/q2-down-register-stage-draft-v3.inc'
    assert not output.exists();output.write_text(s)
    wrapper=(base/'probe-v2.hip').read_text().replace('draft-v2.inc','draft-v3.inc').replace('DraftV2Kernel','DraftV3Kernel')
    (base/'probe-v3.hip').write_text(wrapper)
    args=json.loads((base/'assembly-v2-argv.json').read_text());args=[v.replace('probe-v2','probe-v3').replace('candidate-v2','candidate-v3') for v in args]
    (base/'assembly-v3-argv.json').write_text(json.dumps(args,indent=2)+'\n')
    report=dict(schema='synapse-lie.q2-down-register-stage-draft-v3.v1',initial_sha256=sha(initial),
        v2_reconstruction_exact=True,candidate_include=str(output.relative_to(ROOT)),candidate_include_sha256=sha(output),
        epilogue_bound_preserved=True,original_palette_fma_and_half_rounding=True,
        mechanism='Form exact four-value half palettes once at stage commit; exchange those bits instead of F32 affine and avoid recomputing them for both halves',
        gpu_run=False,model_measured=False,numerical_qualification=False)
    with (base/'generation-v3.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(report))
if __name__=='__main__':main()
