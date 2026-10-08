#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Stage HC injection coefficients once in existing dead projection LDS."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    previous_path = ROOT / 'config/q2-hc-inject-reuse-draft-v2.json'
    previous = json.loads(previous_path.read_text())
    source = ROOT / previous['include']
    assert sha(source) == previous['include_sha256']
    text = source.read_text()
    anchor = '''    float* gates = reinterpret_cast<float*>(s_lds);
    const std::size_t hidden = m / 4;
#pragma unroll
    for (int j = 0; j < kWaveTokTiles; ++j) {'''
    assert text.count(anchor) == 2
    replacement = '''    float* gates = reinterpret_cast<float*>(s_lds);
    const std::size_t hidden = m / 4;
    // SPDX-License-Identifier: MIT
    // K staging is dead after the projection's last block barrier. The gate
    // transpose uses only the prefix; keep exact F32 coefficients in its tail.
    // All writers reach the existing first gate-publication barrier before
    // any injection reader. No extra allocation or block barrier is added.
    constexpr unsigned kInjectFloats = 4 * 4 * kHiddenTile;
    static_assert((4 * kPlane + kInjectFloats) * sizeof(float) <= sizeof(s_lds));
    float* inject_coeff = gates + 4 * kPlane;
    if (inject_w != nullptr && tid < kInjectFloats / 4) {
      const unsigned group = tid / (kHiddenTile / 4);
      const unsigned h_local = (tid % (kHiddenTile / 4)) * 4;
      const std::size_t h = r_block / 4 + h_local;
      *reinterpret_cast<float4*>(inject_coeff + group * kHiddenTile + h_local) =
          Load4(inject_w + group * hidden + h);
    }
#pragma unroll
    for (int j = 0; j < kWaveTokTiles; ++j) {'''
    text = text.replace(anchor, replacement)
    old = 'const float4 q = Load4(inject_w + o * m + stream * hidden + h);'
    new = 'const float4 q = Load4(inject_coeff + (o * 4 + stream) * kHiddenTile + h_local);'
    assert text.count(old) == 2
    text = text.replace(old, new).replace('HcInjectReuseDraft', 'HcInjectReuseLdsDraft')
    output = ROOT / 'experiments/q2-hc-inject-reuse-draft-v3.inc'
    with output.open('x') as stream:
        stream.write(text)
    prep = ROOT / 'evidence/q2-hc-inject-reuse-draft-preparation'
    probe = prep / 'probe-v3.hip'
    with probe.open('x') as stream:
        stream.write((ROOT / previous['compiler_probe']).read_text().replace(str(source), str(output)))
    argv = json.loads((prep / 'assembly-v2-argv.json').read_text())
    argv[argv.index('-S') + 1] = str(probe)
    argv[-1] = str(prep / 'candidate-v3.s')
    with (prep / 'assembly-v3-argv.json').open('x') as stream:
        json.dump(argv, stream, indent=2)
        stream.write('\n')
    report = dict(previous)
    report.update(
        schema='synapse-lie.q2-hc-inject-reuse-draft.v3',
        previous_manifest_sha256=sha(previous_path),
        previous_include_sha256=sha(source),
        include=str(output.relative_to(ROOT)), include_sha256=sha(output),
        compiler_probe=str(probe.relative_to(ROOT)), compiler_probe_sha256=sha(probe),
        generator_sha256=sha(Path(__file__)),
        new_mechanism='One exact F32 coefficient tile per CTA in dead projection LDS tail; reuse across all128 token rows without changing dot/reduction order',
        coefficient_tile_bytes=4096, gate_transpose_bytes=16640,
        existing_lds_bytes=24576, extra_lds_allocation_bytes=0,
        extra_block_barriers=0,
        coefficient_publication='The first existing gate-publication barrier follows all coefficient stores and precedes every dot read',
        projection_stage_retirement='The final existing K-loop barrier precedes all coefficient stores',
        performance_measured=False, production_provider=False, gpu_run=False,
        numerical_acceptance=False, goal_met=False)
    with (ROOT / 'config/q2-hc-inject-reuse-draft-v3.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(include=report['include'], coefficient_tile_bytes=4096,
                         extra_lds=0, extra_barriers=0, GPU_run=False)))


if __name__ == '__main__':
    main()
