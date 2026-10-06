#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare exact IQ2 high-byte signs without the original sign-table load."""
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prepare', ROOT / 'tools/prepare-q2-iq2-register-stage.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)
sha, inventory, once = prepare.sha, prepare.inventory, prepare.once
REL = prepare.REL
INC = 'src/models/qwen38_flash_next/kernels/rocm/q2_iq2_half_sign_arithmetic.inc'
NAME = 'RoutedIq2HalfSignArithmeticKernel'


def main():
    parent_path = ROOT / 'config/q2-ssm-fixed-bounds-source.json'
    parent = json.loads(parent_path.read_text())['variants']['ssm-fixed-bounds']
    base = ROOT / parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Measured parent inventory differs')
    common_path = base / 'src/models/qwen38_flash_next/kernels/rocm/mmq/ggml-common.h'
    common = common_path.read_text()
    match = re.search(r'GGML_TABLE_BEGIN\(uint64_t, ksigns64, 128\)(.*?)GGML_TABLE_END', common, re.S)
    if not match:
        raise ValueError('Missing original sign table')
    table = [int(value.rstrip('uUlL'), 16) for value in re.findall(r'0x[0-9a-fA-F]+[uUlL]*', match[1])]
    if len(table) != 128:
        raise ValueError('Sign-table inventory differs')
    masks = []
    for tag, value in enumerate(table):
        completed = tag | ((tag.bit_count() & 1) << 7)
        expected = sum(0x80 << (8 * bit) for bit in range(8) if completed & (1 << bit))
        lo = (((tag & 15) * 0x10204080) & 0xffffffff) & 0x80808080
        hi = (((completed >> 4) * 0x10204080) & 0xffffffff) & 0x80808080
        if expected != (value & 0x8080808080808080) or expected != lo | (hi << 32):
            raise ValueError('Packed integer sign identity differs')
        masks.append([lo, hi])
    original = (base / REL).read_text()
    original_kernel = prepare.function(original, prepare.PREFIX)
    old = '''          const uint2 mask = reinterpret_cast<const uint2*>(ksigns64)[sign];
          const uint2 decoded =
              make_uint2(magnitude.x ^ (mask.x & 0x80808080U),
                         magnitude.y ^ (mask.y & 0x80808080U));'''
    new = '''          const uint2 mask = Iq2HalfSignByteMasks(sign);
          const uint2 decoded =
              make_uint2(magnitude.x ^ mask.x, magnitude.y ^ mask.y);'''
    kernel = once(original_kernel, old, new).replace('RoutedF16GEMMKernel', NAME)
    isolated = '''// SPDX-License-Identifier: MIT
// Official-Gufo-derived private IQ2 high-byte specialization.
// Same original group ownership, half rounding and matrix accumulation.
__device__ __forceinline__ uint2 Iq2HalfSignByteMasks(unsigned sign) {
  const unsigned completed = sign | ((__popc(sign) & 1U) << 7U);
  // Multiplication deposits four sign bits into bit7 of four bytes.
  // The high-byte format needs only XOR, with no signed-integer negation.
  return make_uint2(((sign & 15U) * 0x10204080U) & 0x80808080U,
                    ((completed >> 4U) * 0x10204080U) & 0x80808080U);
}

''' + kernel + '\n'
    candidate = once(original, original_kernel,
                     original_kernel + '\n\n#include "q2_iq2_half_sign_arithmetic.inc"')
    launch = '''  hipLaunchKernelGGL(
      (RoutedF16GEMMKernel<WeightType::kIQ2_XXS, 128, BN, 2, true, kPacked>),
      grid, dim3(kThreads), 0, stream, gate, x, tiles, bounds, rows_token,
      rows_slot, nullptr, out, nullptr, m, k, up);'''
    selected = '''  if constexpr ((BN == 64 || BN == 128) && !kPacked) {
    if (m == 640 && k == 2560) {
      hipLaunchKernelGGL(
          (RoutedIq2HalfSignArithmeticKernel<WeightType::kIQ2_XXS, 128, BN, 2,
                                             true, false>),
          grid, dim3(kThreads), 0, stream, gate, x, tiles, bounds, rows_token,
          rows_slot, nullptr, out, nullptr, m, k, up);
      return;
    }
  }
''' + launch
    candidate = once(candidate, launch, selected)
    out = ROOT / '.deps/gufo-q2-iq2-half-sign-arithmetic-run'
    manifest = ROOT / 'config/q2-iq2-half-sign-arithmetic-source.json'
    patch = ROOT / 'experiments/q2-iq2-half-sign-arithmetic.patch'
    if any(path.exists() for path in (out, manifest, patch)):
        raise ValueError('Preserve existing experiment')
    shutil.copytree(base, out)
    (out / REL).write_text(candidate)
    (out / INC).write_text(isolated)
    files = inventory(out)
    differences = sorted(name for name in files if files[name] != parent['files'].get(name))
    if len(files) != 1028 or differences != sorted([REL, INC]):
        raise ValueError('Provider scope differs')
    if prepare.function(candidate, prepare.PREFIX) != original_kernel:
        raise ValueError('Original template changed')
    patch.write_text('// SPDX-License-Identifier: MIT\n' + ''.join(difflib.unified_diff(
        original.splitlines(True), candidate.splitlines(True), fromfile='a/' + REL, tofile='b/' + REL)) +
        ''.join(difflib.unified_diff([], isolated.splitlines(True), fromfile='/dev/null', tofile='b/' + INC)))
    source = dict(source=str(out.relative_to(ROOT)), files=files, changed_files=differences,
        parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
        measured_parent='config/q2-ssm-fixed-bounds-model-results.json',
        measured_parent_sha256=sha(ROOT / 'config/q2-ssm-fixed-bounds-model-results.json'),
        patch=str(patch.relative_to(ROOT)), patch_sha256=sha(patch),
        generator=str(Path(__file__).relative_to(ROOT)), generator_sha256=sha(Path(__file__)),
        numerical_include=INC, numerical_include_sha256=sha(out / INC),
        original_template_source_unchanged=True, independently_pinned_sign_table=str(common_path.relative_to(ROOT)),
        original_sign_table_sha256=sha(common_path), exact_sign_tags=128,
        exact_sign_bytes=1024, expanded_masks_sha256=hashlib.sha256(json.dumps(masks).encode()).hexdigest(),
        selected_shapes=dict(BN=[64, 128], m=640, k=2560, packed=False),
        additional_runtime_allocations=0, callbacks_or_streams_changed=False,
        mechanism='Replace compact half-high-byte sign table+AND with parity and two packed integer products+XOR; retain four-lane commit ownership.',
        previous_sign_trial_difference='Older WMMA signs negated integer magnitude bytes before half-byte LDS and four-lane ownership existed. This route only toggles the IEEE-half sign bit.',
        numerical_contract='Original magnitude bits, scale owner/rounding, F16 FMA, K16 WMMA order, routing, SwiGLU, full640 scale/packing and down unchanged.',
        risk='Integer work/register scheduling may outweigh cached sign loads; no speedup follows from algebra.',
        gpu_run=False, full_model_measured=False, numerical_acceptance=False, goal_met=False)
    with manifest.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-iq2-half-sign-arithmetic-source.v1',
                       official_gufo_pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
                       variants={'iq2-half-sign-arithmetic': source}), stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(provider_files=1028, original_template_unchanged=True,
                         sign_tags_exact=128, changed_files=differences, gpu_run=False)))


if __name__ == '__main__':
    main()
