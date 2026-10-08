#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare a component-only shared-down mirror; leave model dispatch unchanged."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ssm', ROOT / 'tools/prepare-q2-ssm-row-group.py')
ssm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ssm)


def main():
    parent_path = ROOT / 'config/q2-down-register-scatter-pair-source.json'
    parent = json.loads(parent_path.read_text())['variants']['down-register-scatter']
    base = ROOT / parent['source']
    assert ssm.inventory(base) == parent['files']
    original = (base / ssm.REL).read_text()
    body = ssm.function(original, 'template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,')
    assert body.count('kHalfWeights && !kHcUpChains') == 4
    mirror = body.replace('DenseF16GEMMKernel', 'SharedDownMirrorKernel')
    mirror = mirror.replace('kHalfWeights && !kHcUpChains', 'false')
    mirror = ssm.once(mirror,
        '  // Separate K16 chains reduce FP32 accumulation error for the sensitive\n'
        '  // unquantized router/gate projections, with the same order in every chunk.',
        '  // Q8-derived half weights retain the original single K16 chain.\n'
        '  // This isolated copy is instantiated only by SharedDownMirrorGemm.')
    conversion_path = ROOT / 'experiments/q2_q8_mirror_kernels.inc'
    conversion = conversion_path.read_text().split('\nbool DenseQ8MirrorGemm(', 1)[0]
    generated = ('// SPDX-License-Identifier: MIT\n'
                 '// Derived from the retained Gufo dense kernel; see the source manifest.\n'
                 + mirror + '\n' + conversion + '\n' + '''bool SharedDownMirrorGemm(const void* weights, const __half* x, float* out,
                          std::size_t batch, std::size_t m, std::size_t k,
                          hipStream_t stream) {
  if (batch < 96 || m != 2560 || k != 640 || weights == nullptr ||
      x == nullptr || out == nullptr)
    return false;
  hipLaunchKernelGGL(
      (SharedDownMirrorKernel<256, 128, 1, 4, 2, 1, false, false, false, true>),
      dim3((batch + 127) / 128, 10), dim3(256), 0, stream,
      weights, x, out, batch, m, k);
  return hipGetLastError() == hipSuccess;
}
''')
    rel = str(Path(ssm.REL).parent / 'q2_shared_down_mirror.inc')
    changed = ssm.once(original, '\nbool AttentionF16Gemm(',
                       '\n#include "q2_shared_down_mirror.inc"\n\nbool AttentionF16Gemm(')
    destination = ROOT / '.deps/gufo-q2-shared-down-mirror-run'
    manifest = ROOT / 'config/q2-shared-down-mirror-source.json'
    patch = ROOT / 'experiments/q2-shared-down-mirror.patch'
    assert not any(p.exists() for p in (destination, manifest, patch))
    shutil.copytree(base, destination)
    (destination / ssm.REL).write_text(changed)
    (destination / rel).write_text(generated)
    files = ssm.inventory(destination)
    delta = [p for p in files if files[p] != parent['files'].get(p)]
    assert len(files) == 1028 and delta == sorted([ssm.REL, rel])
    with patch.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n')
        for name, before, after in ((ssm.REL, original, changed), (rel, '', generated)):
            stream.write(''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                fromfile='a/' + name if before else '/dev/null', tofile='b/' + name)))
    variant = dict(source=str(destination.relative_to(ROOT)), files=files, changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=ssm.sha(parent_path),
        measured_parent='config/q2-down-register-scatter-model-results.json',
        measured_parent_sha256=ssm.sha(ROOT / 'config/q2-down-register-scatter-model-results.json'),
        parent_prefill_tok_s=1580.226725, parent_decode_steps_s=25.10411864,
        patch=str(patch.relative_to(ROOT)), patch_sha256=ssm.sha(patch),
        conversion_source=str(conversion_path.relative_to(ROOT)), conversion_source_sha256=ssm.sha(conversion_path),
        conversion_body_exact_to_qualified_mirror=True,
        mechanism='Component-only persistent Q8-to-F16 mirror for shared down M2560/K640; '
                  'same BM256/BN128/BK1/WM4/WN2 and original single K16 accumulation chain.',
        model_upload_changed=False, model_dispatch_changed=False, additional_model_allocations=0,
        prospective_model_mirrors=48, prospective_payload_bytes=48 * 2560 * 640 * 2,
        prospective_allocation_bytes=48 * (2560 * 640 * 2 + 4096),
        risks='F16 weights increase encoded bytes34 to64 per32 values. Small-shape reuse may '
              'differ from the already-negative large mirror; only GPU timing can decide.',
        scalar_decode_changed=False, ssm_changed=False, parent_recompiled=False,
        current_frozen_campaign_changed=False, model_file_conversion=False,
        gpu_run=False, model_inference=False, numerical_acceptance=False, goal_met=False)
    with manifest.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-shared-down-mirror-source.v1',
                       variants={'shared-down-mirror': variant}, goal_met=False), stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(provider_files=len(files), changed_files=delta,
                         model_dispatch_changed=False, gpu_run=False)))


if __name__ == '__main__':
    main()
