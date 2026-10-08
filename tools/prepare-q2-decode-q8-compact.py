#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare a scalar Q8 sweep with uniform full blocks and exact lane exchange."""
import datetime
import difflib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prior', ROOT / 'tools/prepare-q2-ssm-row-group.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
sha, once = prior.sha, prior.once
REL = 'src/models/qwen38_flash_next/kernels/rocm/mmq/'
PREFIX = 'q2-decode-q8-compact'


def main():
    manifest = ROOT / 'config/q2-iq2-fixed-bounds-source.json'
    parent = json.loads(manifest.read_text())['variants']['iq2-fixed-bounds']
    base = ROOT / parent['source']
    assert prior.inventory(base) == parent['files']
    path = REL + 'mmvq.hip.cpp'
    original = (base / path).read_text()
    start = original.index('template<int ncols_dst, bool has_gate, int token_waves = 1, bool ragged = false>')
    end = original.index('// Integer matrix products', start)
    body = original[start:end]
    body = once(body, 'template<int ncols_dst, bool has_gate, int token_waves = 1, bool ragged = false>',
                'template<bool has_gate>')
    body = once(body, '__launch_bounds__(32 * token_waves, 1)', '__launch_bounds__(32, 1)')
    body = body.replace('mul_mat_vec_q8(', 'mul_mat_vec_q8_compact(')
    body = once(body, 'const uint32_t valid_tokens = ncols_dst)', 'const uint32_t valid_tokens = 1)')
    body = once(body, '  constexpr int qi = QI8_0;',
                '  constexpr int ncols_dst = 1, token_waves = 1;\n'
                '  constexpr bool ragged = false;\n'
                '  constexpr int qi = QI8_0;')
    begin = body.index('  for (int kbx = lane / (qi / vdr);')
    finish = body.index('#pragma unroll\n  for (int j = 0; j < ncols_dst;', begin)
    original_loop = body[begin:finish]
    loop_body = original_loop[original_loop.index('#pragma unroll'):].rsplit('  }\n', 1)[0]
    body = body[:begin] + '''  // Every lane has a valid block in the complete part. Only the final
  // partial group needs a per-lane bound; each lane retains its K order.
  const int full = blocks_per_row / blocks_per_iter * blocks_per_iter;
  const int lane_block = lane / (qi / vdr);
  for (int base = 0; base < full; base += blocks_per_iter) {
    const int kbx = base + lane_block;
''' + loop_body + '''  }
  const int kbx = full + lane_block;
  if (kbx < blocks_per_row) {
''' + loop_body + '  }\n' + body[finish:]
    body = body.replace('warp_reduce_sum<32>(', 'Q8CompactSum(')
    helpers = '''// SPDX-License-Identifier: MIT
// Derived from independently pinned Gufo, including its GDN DPP exchange.
// Only the one-token Q8 consumer is selected. No different dot products,
// scale contraction, persistent format, allocation or stream is introduced.
template<int mask>
__device__ __forceinline__ float Q8CompactXorAdd(float x) {
  const int peer = __builtin_amdgcn_update_dpp(
      0, __builtin_bit_cast(int, x), 0x160 | mask, 0xf, 0xf, false);
  return x + __builtin_bit_cast(float, peer);
}
__device__ __forceinline__ float Q8CompactSum(float x) {
  // All32 lanes are active here, after the optional tail reconverges.
  // Exchange opposite16-lane rows, then the original descending XOR tree.
  const unsigned bits = __builtin_bit_cast(unsigned, x);
  const unsigned peer = __builtin_amdgcn_permlanex16(
      bits, bits, 0x76543210u, 0xfedcba98u, false, false);
  x += __builtin_bit_cast(float, peer);
  x = Q8CompactXorAdd<8>(x);
  x = Q8CompactXorAdd<4>(x);
  x = Q8CompactXorAdd<2>(x);
  return Q8CompactXorAdd<1>(x);
}

'''
    inc = ROOT / ('experiments/' + PREFIX + '.inc')
    target = ROOT / ('.deps/gufo-' + PREFIX + '-run')
    out = ROOT / ('evidence/' + PREFIX + '-preparation')
    source_manifest = ROOT / ('config/' + PREFIX + '-source.json')
    patch = ROOT / ('experiments/' + PREFIX + '.patch')
    assert not any(p.exists() for p in (inc, target, out, source_manifest, patch))
    inc.write_text(helpers + body)
    changed = once(original, '// Integer matrix products reuse each Q8 weight across up to 48 inputs.',
        '#include "q2_decode_q8_compact.inc"\n\n'
        '// Integer matrix products reuse each Q8 weight across up to 48 inputs.')
    anchor = '                      float* output, int k, int rows, int input_stride, hipStream_t stream) {\n    if (gate) {'
    selected = '''                      float* output, int k, int rows, int input_stride, hipStream_t stream) {
    if constexpr (tokens == 1) {
        if (gate)
            mul_mat_vec_q8_compact<true><<<rows, 32, 0, stream>>>(
                weights, gate, input, output, k, rows, input_stride);
        else
            mul_mat_vec_q8_compact<false><<<rows, 32, 0, stream>>>(
                weights, nullptr, input, output, k, rows, input_stride);
        return;
    }
    if (gate) {'''
    changed = once(changed, anchor, selected)
    shutil.copytree(base, target)
    (target / path).write_text(changed)
    (target / REL / 'q2_decode_q8_compact.inc').write_bytes(inc.read_bytes())
    files = prior.inventory(target)
    assert len(files) == 1029 and [n for n in parent['files'] if files[n] != parent['files'][n]] == [path]
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True), changed.splitlines(True),
                                               fromfile='a/' + path, tofile='b/' + path)))
    out.mkdir()
    argv = ['/opt/rocm/llvm/bin/clang++', '-x', 'hip', '--offload-arch=gfx1151',
            '--offload-device-only', '-std=c++17', '-O3', '-ffast-math', '-fno-finite-math-only',
            '-DGGML_HIP_NO_VMM', '-Wno-unused-value', '-Wno-unused-command-line-argument',
            '-I' + str(target), '-I' + str(target / REL), '-isystem', '/opt/rocm/include',
            '-S', str(target / path), '-o', str(out / 'candidate.s')]
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with (out / 'assembly.stdout').open('x') as stdout, (out / 'assembly.stderr').open('x') as stderr:
        result = subprocess.run(argv, cwd=ROOT, stdout=stdout, stderr=stderr)
    receipt = dict(argv=argv, started_at=started, finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        exit_code=result.returncode, assembly_sha256=sha(out / 'candidate.s') if (out / 'candidate.s').exists() else None)
    (out / 'assembly-command.json').write_text(json.dumps(receipt, indent=2) + '\n')
    bindings = {'parent_manifest': str(manifest.relative_to(ROOT)), 'private_include': str(inc.relative_to(ROOT)),
                'patch': str(patch.relative_to(ROOT)), 'generator': str(Path(__file__).relative_to(ROOT))}
    report = dict(schema='synapse-lie.' + PREFIX + '-source.v1',
        official_gufo_pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
        variants={'decode-q8-compact': dict(source=str(target.relative_to(ROOT)), files=files,
            **bindings, **{k + '_sha256': sha(ROOT / v) for k, v in bindings.items()},
            changed_parent_files=[path], new_source_files=[REL + 'q2_decode_q8_compact.inc'],
            selection='tokens1 dense Q8; tokens2..48 and prefill dispatch unchanged',
            per_row_dot_and_reduction_order_preserved=True, extra_device_or_persistent_bytes=0,
            new_streams_or_callbacks=0, GPU_run=False, measured_model_speedup=False,
            priority='PP/TG through128K; fixed-point parity remains paused')})
    source_manifest.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(compile_exit_code=result.returncode, provider_files=len(files), GPU_run=False)))
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
