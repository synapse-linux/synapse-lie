#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare a whole-output RMS-owner fixture; no selector or remote execution."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_exact(path, data):
    if path.exists():
        if path.read_text() != data:
            raise ValueError('Existing preparation differs: ' + str(path))
        return
    with path.open('x') as stream:
        stream.write(data)


BODY = r'''
struct Inputs {
  unsigned n, used, parts, offset;
  std::vector<float> initial, block, gamma, injection, weights, shared, gate;
  Device r, b, gm, iw, wt, sh, g, experts;
  std::array<std::string, 8> identities;
  Inputs(unsigned tokens, unsigned pattern, unsigned expert_count,
         unsigned inject_parts, bool misaligned, hipStream_t stream)
      : n(tokens), used(expert_count), parts(inject_parts), offset(misaligned ? 4 : 0),
        initial(std::size_t(n) * 4 * kHidden), block(std::size_t(n) * kHidden),
        gamma(4 * kHidden), injection(std::size_t(n) * 4 * parts),
        weights(std::size_t(n) * used), shared(block.size()), gate(std::size_t(n) * 3),
        r(initial.size() * 4), b(block.size() * 4), gm(gamma.size() * 4),
        iw(injection.size() * 4), wt(weights.size() * 4), sh(shared.size() * 4),
        g(gate.size() * 4), experts(std::size_t(n) * used * kHidden * 2 + 16) {
    Random random;
    const float magnitude = pattern ? 0.0001f : 0.5f;
    for (std::size_t i = 0; i < initial.size(); ++i)
      initial[i] = i % 41 == 0 ? -0.0f : random.Next(magnitude);
    for (auto& v : block) v = random.Next(magnitude);
    for (auto& v : gamma) v = 1.0f + random.Next(0.5f);
    for (auto& v : injection) v = random.Next(0.0625f);
    for (auto& v : weights) v = (1.0f + random.Next(0.5f)) / float(used);
    for (auto& v : shared) v = random.Next(magnitude);
    for (auto& v : gate) v = random.Next(0.5f);
    std::vector<std::uint8_t> packed(experts.bytes, 0xa5);
    for (std::size_t i = 0; i < std::size_t(n) * used * kHidden; ++i) {
      const __half value = __float2half_rn(random.Next(magnitude));
      std::memcpy(packed.data() + offset + i * 2, &value, 2);
    }
    Upload(r, initial, stream); Upload(b, block, stream);
    Upload(gm, gamma, stream); Upload(iw, injection, stream);
    Upload(wt, weights, stream); Upload(sh, shared, stream);
    Upload(g, gate, stream); Upload(experts, packed, stream);
    unsigned index = 0;
    for (const Device* buffer : {&r, &b, &gm, &iw, &wt, &sh, &g, &experts})
      identities[index++] = Hash(Read(*buffer, stream));
  }
  void Unchanged(hipStream_t stream) {
    unsigned index = 0;
    for (const Device* buffer : {&r, &b, &gm, &iw, &wt, &sh, &g, &experts})
      Require(Hash(Read(*buffer, stream)) == identities[index++], "RMS input mutated");
  }
};
struct Outputs {
  Guarded residual, norm, half, scales;
  explicit Outputs(unsigned n)
      : residual(std::size_t(n) * 4 * kHidden * 4),
        norm(residual.payload), half(std::size_t(n) * 4 * kHidden * 2),
        scales(std::size_t(n) * 4 * 4) {}
  void Reset(Inputs& in, hipStream_t stream) {
    residual.Reset(4, stream); norm.Reset(4, stream);
    half.Reset(2, stream); scales.Reset(4, stream);
    Hip(hipMemcpyAsync(residual.Data(), in.r.data, residual.payload,
                       hipMemcpyDeviceToDevice, stream));
    Hip(hipStreamSynchronize(stream));
  }
};
static void Launch(bool candidate, bool moe, bool gamma, bool half,
                   Inputs& in, Outputs& out, hipStream_t stream) {
  auto* res = static_cast<float*>(out.residual.Data());
  const auto* gm = gamma ? static_cast<const float*>(in.gm.data) : nullptr;
  const auto* iw = static_cast<const float*>(in.iw.data);
  auto* narrowed = half ? static_cast<__half*>(out.half.Data()) : nullptr;
  if (moe) {
    const auto* expert = reinterpret_cast<const __half*>(
        static_cast<const std::uint8_t*>(in.experts.data) + in.offset);
    const auto* weights = static_cast<const float*>(in.wt.data);
    const auto* shared = static_cast<const float*>(in.sh.data);
    const auto* gate = static_cast<const float*>(in.g.data);
    auto* scales = static_cast<float*>(out.scales.Data());
    if (candidate)
      hipLaunchKernelGGL(q::HcNormOwnerDraftMoeKernel, dim3(in.n), dim3(256), 0,
          stream, res, expert, weights, shared, gate, 3, in.used, iw, in.parts,
          gm, scales, kHidden, 0.00001f, narrowed);
    else
      hipLaunchKernelGGL(q::HcCombineMoeHalfDeferredNormKernel, dim3(in.n),
          dim3(256), 0, stream, res, expert, weights, shared, gate, 3, in.used,
          iw, in.parts, gm, scales, kHidden, 0.00001f, narrowed);
  } else {
    Require(!gamma || half, "Ordinary normalization requires half output");
    const auto* block = static_cast<const float*>(in.b.data);
    auto* norm = static_cast<float*>(out.norm.Data());
    if (candidate)
      hipLaunchKernelGGL(q::HcNormOwnerDraftOrdinaryKernel, dim3(in.n), dim3(256),
          0, stream, res, block, iw, in.parts, gm, norm, narrowed, kHidden, 0.00001f);
    else
      hipLaunchKernelGGL(q::HcCombineF32HalfKernel, dim3(in.n), dim3(256), 0,
          stream, res, block, iw, in.parts, gm, norm, narrowed, kHidden, 0.00001f);
  }
  Hip(hipGetLastError());
}
static void Untouched(const std::vector<std::uint8_t>& bytes, unsigned width) {
  const std::uint32_t f32 = 0x7fc12345;
  const std::uint16_t f16 = 0x7e55;
  for (std::size_t i = 64; i + 64 < bytes.size(); i += width) {
    if (width == 4)
      Require(std::memcmp(bytes.data() + i, &f32, 4) == 0, "Unused F32 output changed");
    else
      Require(std::memcmp(bytes.data() + i, &f16, 2) == 0, "Unused F16 output changed");
  }
}
static void Save(const std::string& name, const std::vector<std::uint8_t>& data) {
  std::ofstream file(name, std::ios::binary | std::ios::trunc);
  file.write(reinterpret_cast<const char*>(data.data()), data.size());
  Require(file.good(), "Failed to preserve whole RMS difference");
}
static bool Pair(const std::string& name, const std::string& field,
                 Guarded& ref, Guarded& candidate, unsigned width, bool written,
                 hipStream_t stream) {
  const auto a = ref.Checked(stream, width, written);
  const auto b = candidate.Checked(stream, width, written);
  if (!written) { Untouched(a, width); Untouched(b, width); }
  const auto nonfinite = written ? Nonfinite(a, width) + Nonfinite(b, width) : 0;
  const bool exact = a == b && nonfinite == 0;
  if (!exact) {
    Save(name + "-" + field + "-reference.bin", a);
    Save(name + "-" + field + "-candidate.bin", b);
  }
  std::cout << "{\"event\":\"hc_norm_owner_replay\",\"case\":\"" << name
            << "\",\"field\":\"" << field << "\",\"bytes\":" << ref.payload
            << ",\"width\":" << width << ",\"exact\":" << (exact ? "true" : "false")
            << ",\"guards_exact\":true,\"written_checked\":"
            << (written ? "true" : "false") << ",\"unused_untouched\":"
            << (!written ? "true" : "false") << ",\"nonfinite_values\":" << nonfinite
            << ",\"reference_sha256\":\"" << Hash(a) << "\",\"candidate_sha256\":\""
            << Hash(b) << "\"}\n";
  return exact;
}
static bool Check(const std::string& name, bool moe, bool gamma, bool half,
                  Outputs& ref, Outputs& candidate, hipStream_t stream) {
  bool ok = Pair(name, "residual", ref.residual, candidate.residual, 4, true, stream);
  ok &= Pair(name, moe ? "scales" : "norm", moe ? ref.scales : ref.norm,
             moe ? candidate.scales : candidate.norm, 4, gamma, stream);
  ok &= Pair(name, "half", ref.half, candidate.half, 2, gamma && half, stream);
  // The nonselected output is also bounded and must remain untouched.
  auto unused_ref = (moe ? ref.norm : ref.scales).Checked(stream, 4, false);
  auto unused_candidate = (moe ? candidate.norm : candidate.scales).Checked(stream, 4, false);
  Untouched(unused_ref, 4); Untouched(unused_candidate, 4);
  return ok;
}
static void Time(const std::string& name, bool candidate, bool moe, Inputs& in,
                 Outputs& out, unsigned rep, unsigned order, hipStream_t stream) {
  constexpr unsigned iterations = 6;
  out.Reset(in, stream);
  hipEvent_t begin, end;
  Hip(hipEventCreate(&begin)); Hip(hipEventCreate(&end));
  const auto started = std::chrono::steady_clock::now();
  Hip(hipEventRecord(begin, stream));
  for (unsigned i = 0; i < iterations; ++i)
    Launch(candidate, moe, true, true, in, out, stream);
  Hip(hipEventRecord(end, stream)); Hip(hipEventSynchronize(end));
  const auto finished = std::chrono::steady_clock::now();
  float elapsed;
  Hip(hipEventElapsedTime(&elapsed, begin, end));
  std::uint32_t bits; std::memcpy(&bits, &elapsed, 4);
  Hip(hipEventDestroy(begin)); Hip(hipEventDestroy(end));
  const double wall = std::chrono::duration<double, std::micro>(finished - started).count();
  Require(std::isfinite(wall) && wall > 0, "Invalid RMS cycle wall timer");
  std::cout << std::setprecision(12)
            << "{\"event\":\"hc_norm_owner_timing\",\"case\":\"" << name
            << "\",\"rep\":" << rep << ",\"order\":" << order
            << ",\"candidate\":" << (candidate ? "true" : "false")
            << ",\"warmup\":" << (rep < 2 ? "true" : "false")
            << ",\"iterations\":" << iterations
            << ",\"residual_payload_bytes\":" << out.residual.payload
            << ",\"wall_us_per_cycle\":" << wall / iterations
            << ",\"hip_ms_raw\":";
  if (std::isfinite(elapsed)) std::cout << elapsed;
  else std::cout << "null";
  std::cout << ",\"hip_ms_raw_bits\":" << bits
            << ",\"hip_timer_valid\":" << (std::isfinite(elapsed) && elapsed > 0 ? "true" : "false")
            << "}\n";
}
static bool Case(unsigned n, bool moe, unsigned pattern, unsigned used,
                 unsigned parts, bool misaligned, bool gamma, bool half,
                 bool timed, hipStream_t stream) {
  const std::string name = "n" + std::to_string(n) + "-moe" + std::to_string(moe)
      + "-p" + std::to_string(pattern) + "-used" + std::to_string(used)
      + "-parts" + std::to_string(parts) + "-offset" + std::to_string(misaligned ? 4 : 0)
      + "-gamma" + std::to_string(gamma) + "-half" + std::to_string(half);
  Inputs in(n, pattern, used, parts, misaligned, stream);
  Outputs ref(n), candidate(n);
  ref.Reset(in, stream); candidate.Reset(in, stream);
  Launch(false, moe, gamma, half, in, ref, stream);
  Launch(true, moe, gamma, half, in, candidate, stream);
  Hip(hipStreamSynchronize(stream));
  bool ok = Check(name, moe, gamma, half, ref, candidate, stream);
  if (timed) {
    for (unsigned rep = 0; rep < 7; ++rep)
      for (unsigned order = 0; order < 2; ++order) {
        const bool cand = (rep + order) % 2 != 0;
        Time(name, cand, moe, in, cand ? candidate : ref, rep, order, stream);
      }
    ok &= Check(name + "-post", moe, true, true, ref, candidate, stream);
  }
  in.Unchanged(stream);
  std::cout << "{\"event\":\"hc_norm_owner_inputs\",\"case\":\"" << name
            << "\",\"immutable\":true,\"unused_output_untouched\":true}\n";
  return ok;
}
int main() {
  hipStream_t stream{};
  try {
    Hip(hipStreamCreateWithFlags(&stream, hipStreamNonBlocking));
    bool ok = true;
    unsigned cases = 0;
    for (unsigned n : {1u, 17u, 97u, 129u, 257u})
      for (unsigned mode = 0; mode < 3; ++mode)
        for (unsigned pattern = 0; pattern < 2; ++pattern) {
          ok &= Case(n, mode != 0, pattern, 10, 3, mode == 2, true, true, false, stream);
          ++cases;
        }
    ok &= Case(129, false, 0, 10, 3, false, false, false, false, stream); ++cases;
    ok &= Case(129, true, 0, 10, 3, false, false, false, false, stream); ++cases;
    ok &= Case(129, true, 0, 10, 3, false, true, false, false, stream); ++cases;
    ok &= Case(129, true, 0, 1, 3, false, true, true, false, stream); ++cases;
    ok &= Case(129, true, 0, 16, 3, false, true, true, false, stream); ++cases;
    ok &= Case(129, false, 0, 10, 10, false, true, true, false, stream); ++cases;
    ok &= Case(2048, false, 0, 10, 3, false, true, true, true, stream); ++cases;
    ok &= Case(2048, true, 0, 10, 3, false, true, true, true, stream); ++cases;
    Require(cases == 38, "RMS case coverage changed");
    Hip(hipStreamDestroy(stream)); stream = nullptr;
    std::cout << "{\"event\":\"hc_norm_owner_complete\",\"cases\":38,\"output_records\":120"
              << ",\"timing_samples\":28,\"timing_retained\":true,\"numerical_pass\":"
              << (ok ? "true" : "false") << ",\"model_inference\":false}\n";
    return ok ? 0 : 1;
  } catch (const std::exception& error) {
    if (stream) hipStreamDestroy(stream);
    std::cerr << error.what() << '\n';
    return 2;
  }
}
'''


def main():
    draft_path = ROOT / 'config/q2-hc-norm-owner-draft.json'
    draft = json.loads(draft_path.read_text())
    parent_path = ROOT / draft['parent_manifest']
    assert sha(parent_path) == draft['parent_manifest_sha256']
    parent = json.loads(parent_path.read_text())['variants']['ssm-fixed-bounds']
    base = ROOT / parent['source']
    assert {str(p.relative_to(base)): sha(p) for p in base.rglob('*')
            if p.is_file()} == parent['files']
    include_path = ROOT / draft['include']
    assert sha(include_path) == draft['include_sha256']
    prior_fixture = ROOT / 'tests/q2_hc_inject_reuse.hip'
    prelude = prior_fixture.read_text().split('struct Inputs {', 1)[0]
    assert prelude.count('experiments/q2-hc-inject-reuse-draft-v3.inc') == 1
    prelude = prelude.replace('experiments/q2-hc-inject-reuse-draft-v3.inc',
                              'experiments/q2-hc-norm-owner-draft.inc')
    prelude = prelude.replace('Guarded complete HC mix/injection cycles',
                              'Guarded complete ordinary/MoE RMS ownership cycles')
    fixture = ROOT / 'tests/q2_hc_norm_owner.hip'
    save_exact(fixture, prelude + BODY)
    prep = ROOT / 'evidence/q2-hc-norm-owner-component-preparation'
    prep.mkdir(exist_ok=True)
    argv = json.loads((ROOT / 'evidence/q2-hc-norm-owner-draft-preparation/assembly-argv.json').read_text())
    argv[argv.index('-S') + 1] = str(fixture)
    argv.extend(['-I', str(ROOT)])
    output_index = argv.index('-o') + 1
    argv[output_index] = str(prep / 'fixture.s')
    for key, value in {'assembly-argv.json': argv,
                      'host-syntax-argv.json': [v for v in argv if v != '-S']}.items():
        if key.startswith('host'):
            value[value.index('--offload-device-only')] = '--offload-host-only'
            value[value.index('-o') + 1] = str(prep / 'host-syntax.o')
            value.insert(value.index('--offload-host-only'), '-fsyntax-only')
        save_exact(prep / key, json.dumps(value, indent=2) + '\n')
    report = dict(schema='synapse-lie.q2-hc-norm-owner-component-preparation.v1',
        generator='tools/prepare-q2-hc-norm-owner-component.py',
        generator_sha256=sha(Path(__file__)), fixture=str(fixture.relative_to(ROOT)),
        fixture_sha256=sha(fixture), original_helper_fixture=str(prior_fixture.relative_to(ROOT)),
        original_helper_fixture_sha256=sha(prior_fixture), draft_manifest=str(draft_path.relative_to(ROOT)),
        draft_manifest_sha256=sha(draft_path), parent_manifest=str(parent_path.relative_to(ROOT)),
        parent_manifest_sha256=sha(parent_path), source_inventory_exact=len(parent['files']),
        include=str(include_path.relative_to(ROOT)), include_sha256=sha(include_path),
        cases=38, output_records=120, input_immutability_checks=38, timing_samples=28,
        timed_shapes=['ordinary/n2048', 'MoE10/n2048'], warmups=2, measured_pairs=5,
        iterations_per_cycle=6, residual_payload_bytes_per_timed_arm=83886080,
        timing_scope='Six complete combines; event submission and terminal synchronization included. Reset/copy/upload/read/hash/allocation are outside the timer.',
        finite_written_checks=True, guards_bytes_per_output=128,
        no_gamma_and_optional_half_untouched_checks=True,
        expert_counts=[1, 10, 16], misaligned_expert_offset_bytes=4, gate_stride=3,
        compact_synthetic_operands=True, original_model=False,
        CPU_forward=False, behavioral_tests_executed=False, GPU_run=False,
        CMake_target_registered=False, remote_launcher_registered=False,
        production_provider_changed=False, numerical_acceptance=False,
        borrowed_executor_scratch=False, performance_increment_found=False,
        controls_rebuilt_or_rerun=False, goal_met=False)
    with (ROOT / 'config/q2-hc-norm-owner-component-preparation.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(cases=38, outputs=120, timings=28,
                         source_files_exact=len(parent['files']), GPU_run=False)))


if __name__ == '__main__':
    main()
