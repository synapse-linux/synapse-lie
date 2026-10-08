#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare an exact transient Q8 stage layout; never run a GPU or model."""
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def once(s, old, new):
    if s.count(old) != 1:
        raise ValueError('Nonunique anchor: ' + old)
    return s.replace(old, new, 1)


def main():
    inc = ROOT/'experiments/q2-ssm-stage-q8.inc'
    fixture = ROOT/'tests/q2_ssm_stage_q8.hip'
    out = ROOT/'evidence/q2-ssm-stage-q8-preparation'
    manifest = ROOT/'config/q2-ssm-stage-q8-source.json'
    if any(p.exists() for p in (inc, fixture, out, manifest)):
        raise ValueError('Preserve existing experiment')
    parent_path = ROOT/'config/q2-decode-down-rows-model-source.json'
    parent = json.loads(parent_path.read_text())
    base = ROOT/parent['source']
    for name, digest in parent['files'].items():
        if sha(base/name) != digest:
            raise ValueError('Retained provider changed: ' + name)
    spec = importlib.util.spec_from_file_location('literal', ROOT/'tools/prepare-q2-iq2-halfstage.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    original = (base/REL).read_text()
    body = helper.function(original, 'template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,')
    body = body.replace('DenseF16GEMMKernel', 'DenseSsmStageQ8Kernel')
    body = once(body, '  // DenseF16SsmGemm already requires', '''  static_assert(BM == 256 && BN == 128 && BK == 2 && WM == 8 && WN == 1);
  static_assert(kSsmConv && !kHalfWeights && !kHcMix && !kAttention);
  static_assert(kRowGroup == 1 && !kHcUpChains);
  // DenseF16SsmGemm already requires''')
    start = body.index('  // Weight fetch unit p of a thread:')
    end = body.index('  const __half* b_ptr[kBPer];', start)
    body = body[:start] + '''  // Stage contains 512 original Q8 blocks: two contiguous uint4 planes
  // and their exact 16-bit scales. No affine conversion occurs in packing.
  constexpr std::size_t kStageBytes = 512 * 34;
  const auto* row_stages = w_bytes + (r_block / 256) * 40 * kStageBytes;
  bool a_live[kAPer];
#pragma unroll
  for (int p = 0; p < kAPer; ++p)
    a_live[p] = true;
''' + body[end:]
    start = body.index('      const int kb = kb0 +', body.index('  const auto fetch_stage'))
    end = body.index('\n    }\n#pragma unroll\n    for (int p = 0; p < kBPer;', start)
    body = body[:start] + '''      const int unit = p * 256 + tid;
      const auto* stage = row_stages + (kb0 / 2) * kStageBytes;
      const auto* codes = reinterpret_cast<const uint4*>(stage);
      a_codes[p][0] = codes[unit];
      a_codes[p][1] = codes[512 + unit];
      a_d[p] = reinterpret_cast<const std::uint16_t*>(stage + 16384)[unit];''' + body[end:]
    pack = '''// Every 34 input bytes have exactly one output location. The stored
// payload size is unchanged; the original weight allocation remains intact.
__global__ void PackSsmStageQ8Kernel(const std::uint8_t* input,
                                   std::uint8_t* output) {
  const std::size_t i = std::size_t(blockIdx.x) * 256 + threadIdx.x;
  if (i >= std::size_t(16384) * 80)
    return;
  const unsigned unit = i % 512;
  const unsigned stage = i / 512;
  const unsigned row = (stage / 40) * 256 + unit / 2;
  const unsigned kb = (stage % 40) * 2 + unit % 2;
  const auto* src = input + (std::size_t(row) * 80 + kb) * 34;
  auto* dst = output + std::size_t(stage) * 17408;
  uint4 lo, hi;
  __builtin_memcpy(&lo, src + 2, 16);
  __builtin_memcpy(&hi, src + 18, 16);
  reinterpret_cast<uint4*>(dst)[unit] = lo;
  reinterpret_cast<uint4*>(dst)[512 + unit] = hi;
  reinterpret_cast<std::uint16_t*>(dst + 16384)[unit] =
      *reinterpret_cast<const std::uint16_t*>(src);
}
'''
    wrapper = helper.function(original, 'bool DenseF16SsmGemm(')
    wrapper = wrapper.replace('DenseF16SsmGemm', 'DenseSsmStageQ8')
    wrapper = once(wrapper, 'hipStream_t stream) {', 'hipStream_t stream, void* packed) {')
    first_launch = wrapper.index('  hipLaunchKernelGGL(')
    wrapper = wrapper[:first_launch] + '''  if (packed == nullptr || packed == w)
    return false;
  hipLaunchKernelGGL(PackSsmStageQ8Kernel, dim3(5120), dim3(256), 0, stream,
                     static_cast<const std::uint8_t*>(w),
                     static_cast<std::uint8_t*>(packed));
  if (hipGetLastError() != hipSuccess)
    return false;
  w = packed;
''' + wrapper[first_launch:]
    wrapper = once(wrapper, 'DenseF16GEMMKernel<256, 128, 2, 8, 1, 1, false, true>',
                   'DenseSsmStageQ8Kernel<256, 128, 2, 8, 1, 1, false, true>')
    notice = (ROOT/'experiments/q2-attention-v-control.inc').read_text()
    notice = notice[:notice.index('*/') + 2]
    source = notice + '\n' + pack + '\n' + body + '\n' + wrapper + '\n'
    test = (ROOT/'tests/q2_ssm_bk4.hip').read_text()
    test = test.replace('wider K-stage experiment', 'exact stage-layout experiment')
    test = test.replace('q2-ssm-bk4.inc', 'q2-ssm-stage-q8.inc').replace('DenseSsmBk4', 'DenseSsmStageQ8')
    test = test.replace('ssm_bk4', 'ssm_stage_q8').replace('ssm-bk4-', 'ssm-stage-q8-')
    test = once(test, 'DenseSsmStageQ8Kernel<128, 128, 4, 4, 2, 1, false,',
                'DenseSsmStageQ8Kernel<256, 128, 2, 8, 1, 1, false,')
    test = once(test, '  std::size_t bytes{};', '  std::size_t bytes{};\n  bool end_operand{};')
    test = once(test, 'explicit Device(std::size_t size) : bytes(size) {\n    Hip(hipMalloc(&storage, bytes + 2 * guard));',
                'explicit Device(std::size_t size, bool at_end = false)\n      : bytes(size), end_operand(at_end) {\n    Hip(hipMalloc(&storage, bytes + (end_operand ? 1 : 2) * guard));')
    test = once(test, '    Hip(hipMemsetAsync(static_cast<std::uint8_t*>(data) + bytes,',
                '    if (!end_operand)\n      Hip(hipMemsetAsync(static_cast<std::uint8_t*>(data) + bytes,')
    test = once(test, '    std::array<std::uint8_t, 2 * guard> got{};',
                '    std::array<std::uint8_t, 2 * guard> got{};\n    got.fill(0xA7);')
    test = once(test, '    Hip(hipMemcpyAsync(got.data() + guard,',
                '    if (!end_operand)\n      Hip(hipMemcpyAsync(got.data() + guard,')
    test = once(test, '  std::array<std::unique_ptr<Device>, 3> w;',
                '  std::array<std::unique_ptr<Device>, 3> w, packed;')
    test = once(test, 'w[rotation] = std::make_unique<Device>(weights.size());',
                'w[rotation] = std::make_unique<Device>(weights.size(), true);\n'
                '      packed[rotation] = std::make_unique<Device>(weights.size());\n'
                '      packed[rotation]->Guard(stream);')
    check = '''  void CheckPacked(unsigned index, hipStream_t stream) {
    const auto input = Read(*w[index], stream);
    const auto output = Read(*packed[index], stream);
    // Inverse, row-major host enumeration is independent of the GPU map.
    for (unsigned row = 0; row < m; ++row)
      for (unsigned kb = 0; kb < k / 32; ++kb) {
        const std::size_t src = (std::size_t(row) * (k / 32) + kb) * 34;
        const std::size_t stage = (row / 256) * 40 + kb / 2;
        const std::size_t unit = (row % 256) * 2 + kb % 2;
        const auto* dst = output.data() + stage * 17408;
        Require(std::memcmp(input.data() + src, dst + 16384 + unit * 2, 2) == 0,
                "Packed scale bits differ");
        for (unsigned half = 0; half < 2; ++half)
          Require(std::memcmp(input.data() + src + 2 + half * 16,
                              dst + half * 8192 + unit * 16, 16) == 0,
                  "Packed code bits differ");
      }
    std::cout << "{\\"event\\":\\"ssm_stage_q8_pack_check\\",\\"rotation\\":" << index
              << ",\\"bytes\\":" << output.size() << ",\\"exact\\":true}\\n";
  }
'''
    test = once(test, '  void Unchanged(hipStream_t stream) {', check + '  void Unchanged(hipStream_t stream) {')
    start = test.index('  auto call = candidate ? q::DenseSsmStageQ8')
    end = test.index('  Require(good, "Q8 dispatch refused");', start)
    test = test[:start] + '''  const auto* conv = static_cast<const float*>(inputs.conv.data);
  const auto* past = static_cast<const float*>(inputs.past.data);
  auto* result = static_cast<float*>(state.convolved.data);
  const bool good = candidate
      ? q::DenseSsmStageQ8(w, x, conv, past, out, result, inputs.n,
                           inputs.m, inputs.k, 10240, 4, stream,
                           inputs.packed[index]->data)
      : q::DenseF16SsmGemm(w, x, conv, past, out, result, inputs.n,
                           inputs.m, inputs.k, 10240, 4, stream);
''' + test[end:]
    test = once(test, '    pass = Pair(reference.out, candidate.out,',
                '    in.CheckPacked(index, stream);\n    pass = Pair(reference.out, candidate.out,')
    test = once(test, '          check(states[rotation]->out, m, true);',
                '          if (is_candidate)\n            in.CheckPacked(rotation, stream);\n          check(states[rotation]->out, m, true);')
    domain = '''static void PackDomain(hipStream_t stream) {
  Inputs in(1, 16384, 2560, true, stream);
  for (std::size_t block = 0; block < in.weights.size() / 34; ++block) {
    const std::uint16_t bits = static_cast<std::uint16_t>(block);
    std::memcpy(in.weights.data() + block * 34, &bits, 2);
    for (unsigned code = 0; code < 32; ++code)
      in.weights[block * 34 + 2 + code] = static_cast<std::uint8_t>(block + code);
  }
  Upload(*in.w[0], in.weights, stream);
  in.w_sha[0] = Hash(in.weights);
  hipLaunchKernelGGL(q::PackSsmStageQ8Kernel, dim3(5120), dim3(256), 0, stream,
                     static_cast<const std::uint8_t*>(in.w[0]->data),
                     static_cast<std::uint8_t*>(in.packed[0]->data));
  Hip(hipGetLastError());
  Hip(hipStreamSynchronize(stream));
  in.CheckPacked(0, stream);
  in.Unchanged(stream);
  std::cout << "{\\"event\\":\\"ssm_stage_q8_pack_domain\\",\\"scale_patterns\\":65536,"
               "\\"all_codes\\":256,\\"allocation_end_input\\":true,\\"exact\\":true}\\n";
}
'''
    test = once(test, 'int main() {', domain + 'int main() {')
    test = once(test, '    bool pass = Case("ssm1024",',
                '    PackDomain(stream);\n    bool pass = Case("ssm1024",')
    test = once(test, 'rep < 7;', 'rep < 8;')
    # Packing happens on every Launch inside the existing complete timer.
    for path, value in ((inc, source), (fixture, test)):
        formatted = subprocess.run(['clang-format', '--style=file:'+str(base/'.clang-format')],
                                   input=value, text=True, capture_output=True, check=True)
        path.write_text(formatted.stdout)
    out.mkdir()
    old = json.loads((ROOT/'evidence/q2-ssm-bk4-preparation/commands.json').read_text())
    args = old[0]['argv'][:old[0]['argv'].index('-c')]
    args = ['-I'+parent['source'] if a.startswith('-I.deps/gufo-') else a for a in args]
    link_inputs = [ROOT/'evidence/q2-ssm-wave-balance-preparation/w8a8.o',
                   ROOT/'evidence/q2-ssm-wave-balance-preparation/sha256.o']
    link_hashes = {str(p.relative_to(ROOT)):sha(p) for p in link_inputs}
    binary = out/'q2_ssm_stage_q8_check'
    commands = [('object', args+['-c',str(fixture),'-o',str(out/'fixture.o')]),
                ('assembly', args+['--offload-device-only','-S',str(fixture),'-o',str(out/'candidate.s')]),
                ('link', ['/opt/rocm/llvm/bin/clang++','--hip-link','--offload-arch=gfx1151',
                          str(out/'fixture.o'), *map(str,link_inputs), '-o',str(binary),
                          '-lcrypto','-Wl,-rpath,/opt/rocm/lib'])]
    records = []
    for label, argv in commands:
        record = dict(label=label, argv=argv, started_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        with (out/(label+'.stdout')).open('x') as stdout, (out/(label+'.stderr')).open('x') as stderr:
            p = subprocess.run(argv,cwd=ROOT,stdout=stdout,stderr=stderr)
        record.update(exit_code=p.returncode, finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        records.append(record)
        (out/'commands.json').write_text(json.dumps(records,indent=2)+'\n')
        print(label,p.returncode,flush=True)
        if p.returncode:
            raise SystemExit(p.returncode)
    report = dict(schema='synapse-lie.q2-ssm-stage-q8-source.v1',
                  official_gufo_pin=parent['official_gufo_pin'],
                  parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
                  provider=parent['source'], provider_files=len(parent['files']),
                  files={str(p.relative_to(ROOT)):sha(p) for p in (inc,fixture,Path(__file__),ROOT/'experiments/q2-ssm-resident-oracle.inc')},
                  geometry=[256,128,2,8,1], temporary_bytes_per_projection=16384*80*34,
                  original_weight_bytes_unchanged=True, new_precision_boundary=False,
                  packing_in_each_complete_timer=True, persistent_weight_cache=False,
                  measured_pairs=6, warmup_pairs=2, weight_rotations=3,
                  compiled=True, gpu_run=False, model_run=False, dispatch_changed=False,
                  binary=str(binary.relative_to(ROOT)), binary_sha256=sha(binary),
                  retained_link_inputs_sha256=link_hashes,
                  object_sha256=sha(out/'fixture.o'), assembly_sha256=sha(out/'candidate.s'))
    manifest.write_text(json.dumps(report,indent=2)+'\n')
    print('Prepared transient original-Q8 stage layout; no GPU run.')


if __name__ == '__main__':
    main()
