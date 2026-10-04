// SPDX-License-Identifier: MIT
// Original raw-HC producer and full shared-expert consumer; no model inference.
#define Q2_HC_UP_CHAINS_CHECKS 1
#include "q2_hc_up_fused.cpp"
#include <memory>

constexpr unsigned hidden = 2560, rank = 320, shared = 640, streams = 4;
constexpr std::size_t tile_tokens = 16, tile_bytes = 576, scale_offset = 512;
extern "C" hipError_t q2_shared_q8_scalar_oracle(const float*, void*,
                                                 std::size_t, std::size_t,
                                                 hipStream_t);

static std::vector<unsigned char> Q8Weights(unsigned m, unsigned k, Random &rng) {
  Require(k % 32 == 0, "Invalid synthetic Q8 weight geometry");
  std::vector<unsigned char> bytes(std::size_t(m) * (k / 32) * 34);
  const __half d = __float2half_rn(0x1p-10f);
  for (std::size_t block = 0; block < bytes.size() / 34; ++block) {
    std::memcpy(bytes.data() + block * 34, &d, 2);
    for (unsigned i = 0; i < 32; ++i)
      bytes[block * 34 + 2 + i] = static_cast<unsigned char>(
          static_cast<signed char>(std::round(rng.Next() * 63.0f)));
  }
  return bytes;
}

struct Weights {
  Device hc, gate, up, down, inject;
  explicit Weights(unsigned seed)
      : hc(std::size_t(streams) * hidden * rank * 2),
        gate(std::size_t(shared) * (hidden / 32) * 34),
        up(std::size_t(shared) * (hidden / 32) * 34),
        down(std::size_t(hidden) * (shared / 32) * 34),
        inject(std::size_t(streams) * streams * hidden * 4) {
    Random rng{seed};
    std::vector<__half> h(std::size_t(streams) * hidden * rank);
    for (auto &v : h) v = __float2half_rn(rng.Next() * .03125f);
    Upload(hc, h);
    Upload(gate, Q8Weights(shared, hidden, rng));
    Upload(up, Q8Weights(shared, hidden, rng));
    Upload(down, Q8Weights(hidden, shared, rng));
    std::vector<float> iw(std::size_t(streams) * streams * hidden);
    for (auto &v : iw) v = __half2float(__float2half_rn(rng.Next() * .03125f));
    Upload(inject, iw);
  }
  static constexpr std::size_t Bytes() {
    return std::size_t(streams) * hidden * rank * 2 +
        3 * std::size_t(shared) * (hidden / 32) * 34 +
        std::size_t(streams) * streams * hidden * 4;
  }
};

struct Buffers {
  Output<float> mixed, gate, up, down, inject;
  Output<__half> half, activated;
  Output<unsigned char> q8;
  explicit Buffers(unsigned n)
      : mixed(std::size_t(n) * hidden), gate(std::size_t(n) * shared),
        up(std::size_t(n) * shared), down(std::size_t(n) * hidden),
        inject(std::size_t(n) * streams * q::HcInjectPartsVec4(hidden)),
        half(std::size_t(n) * hidden), activated(std::size_t(n) * shared),
        q8(q::Q8TiledBytes(n, hidden)) {}
};

static void Launch(bool fused, bool complete, Weights &w, Device &low, Device &xn,
                   Buffers &b, unsigned n, hipStream_t stream,
                   bool injection = true, bool half = true) {
  const auto *lr = static_cast<const __half *>(low.data);
  const auto *norm = static_cast<const float *>(xn.data);
  const auto *iw = injection ? static_cast<const float *>(w.inject.data) : nullptr;
  if (fused) {
    Require(q::HcMixRawQ8F16Gemm(w.hc.data, lr, norm, iw, b.mixed.Data(),
                                 half ? b.half.Data() : nullptr, b.q8.Data(),
                                 injection ? b.inject.Data() : nullptr,
                                 n, hidden, rank, stream), "Raw-HC Q8 dispatch refused");
  } else {
    Require(q::HcMixRawF16Gemm(w.hc.data, lr, norm, iw, b.mixed.Data(),
                               half ? b.half.Data() : nullptr,
                               injection ? b.inject.Data() : nullptr,
                               n, hidden, rank, stream), "Reference raw-HC refused");
    q::QuantizeQ8Tiled(b.mixed.Data(), b.q8.Data(), n, hidden, stream);
  }
  if (complete) {
    Require(q::W8A8Gemm(w.gate.data, b.q8.Data(), b.gate.Data(), n, shared,
                         hidden, stream), "Shared gate refused");
    Require(q::W8A8Gemm(w.up.data, b.q8.Data(), b.up.Data(), n, shared,
                         hidden, stream), "Shared up refused");
    q::SwigluHalf(b.gate.Data(), b.up.Data(), b.activated.Data(),
                   std::size_t(n) * shared, stream);
    Require(q::DenseF16Gemm(w.down.data, b.activated.Data(), b.down.Data(), n,
                            hidden, shared, stream), "Shared down refused");
  }
  Hip(hipGetLastError());
}

static std::vector<unsigned char> ScalarQ8(const std::vector<float> &x, unsigned n) {
  std::vector<unsigned char> bytes(q::Q8TiledBytes(n, hidden), 0xFF);
  for (unsigned t = 0; t < n; ++t)
    for (unsigned block = 0; block < hidden / 32; ++block) {
      float maximum = 0;
      for (unsigned i = 0; i < 32; ++i)
        maximum = std::fmax(maximum, std::fabs(x[std::size_t(t) * hidden + block * 32 + i]));
      // Production HIP fast math multiplies by the rounded F32 reciprocal
      // of 127. A correctly rounded CPU division differs by one ULP in317
      // retained R1 blocks although reference/candidate GPU bytes are equal.
      const float d = maximum * 0x1.020408p-7F;
      const float id = d != 0 ? 1.0f / d : 0.0f;
      const std::size_t tile = ((std::size_t(t / tile_tokens) * (hidden / 32)) + block) * tile_bytes;
      for (unsigned i = 0; i < 32; ++i) {
        const auto code = static_cast<signed char>(std::round(
            x[std::size_t(t) * hidden + block * 32 + i] * id));
        bytes[tile + (i / 16) * 256 + (t % tile_tokens) * 16 + i % 16] =
            static_cast<unsigned char>(code);
      }
      std::memcpy(bytes.data() + tile + scale_offset + (t % tile_tokens) * 4, &d, 4);
    }
  return bytes;
}

template<class T>
static void Pair(const std::string &name, Output<T> &a, Output<T> &b,
                 bool written = true, bool save = true) {
  const auto x = a.Read(written), y = b.Read(written);
  Require(Exact(x, y), "Producer/consumer byte replay differs");
  if (save && written) {
    Save(name + "-reference.bin", x);
    Save(name + "-candidate.bin", y);
  }
  std::cout << "{\"event\":\"shared_q8_exact\",\"name\":\"" << name
            << "\",\"bytes\":" << x.size() * sizeof(T) << ",\"exact\":true}\n";
}

static bool Check(unsigned n, unsigned pattern, bool injection, bool half,
                  Weights &w) {
  Random rng{917+n};
  std::vector<__half> low(std::size_t(n) * rank);
  std::vector<float> xn(std::size_t(n) * streams * hidden);
  for (auto &v : low) v = __float2half_rn(rng.Next() * .125f);
  for (auto &v : xn) v = pattern == 1 ? 0.0f : rng.Next() * (pattern == 2 ? 0x1p-18f : 1.0f);
  Device ld(low.size() * 2), xd(xn.size() * 4);
  Upload(ld, low); Upload(xd, xn);
  Buffers ref(n), fused(n);
  hipStream_t stream{};
  Hip(hipStreamCreateWithFlags(&stream, hipStreamNonBlocking));
  Launch(false, true, w, ld, xd, ref, n, stream, injection, half);
  Launch(true, true, w, ld, xd, fused, n, stream, injection, half);
  Hip(hipStreamSynchronize(stream));
  const std::string prefix = "shared-q8-n"+std::to_string(n)+"-p"+std::to_string(pattern);
  Pair(prefix+"-mixed", ref.mixed, fused.mixed);
  Pair(prefix+"-half", ref.half, fused.half, half);
  Pair(prefix+"-q8", ref.q8, fused.q8);
  Pair(prefix+"-inject", ref.inject, fused.inject, injection);
  Pair(prefix+"-gate", ref.gate, fused.gate);
  Pair(prefix+"-up", ref.up, fused.up);
  Pair(prefix+"-activated", ref.activated, fused.activated);
  Pair(prefix+"-down", ref.down, fused.down);
  // Retain correctly rounded CPU reciprocal/tie behavior as a diagnostic.
  // Production HIP fast math differs on12 half-code boundaries in R2; both
  // original and fused outputs agree there. An independent serial GPU oracle
  // checks the actual production FP32 contract without sharing its helpers.
  const auto cpu_expected = ScalarQ8(ref.mixed.Read(), n);
  const auto reference_q8 = ref.q8.Read();
  std::size_t cpu_different_bytes = 0;
  for (std::size_t i = 0; i < cpu_expected.size(); ++i)
    cpu_different_bytes += cpu_expected[i] != reference_q8[i];
  std::cout << "{\"event\":\"shared_q8_cpu_diagnostic\",\"n\":" << n
            << ",\"different_bytes\":" << cpu_different_bytes << "}\n";
  Output<unsigned char> independent(q::Q8TiledBytes(n, hidden));
  Hip(q2_shared_q8_scalar_oracle(ref.mixed.Data(), independent.Data(), n, hidden, stream));
  Hip(hipStreamSynchronize(stream));
  const auto expected = independent.Read();
  const bool oracle_exact = Exact(expected, reference_q8) && Exact(expected, fused.q8.Read());
  Save(prefix+"-independent-q8.bin", expected);
  std::cout << "{\"event\":\"shared_q8_gpu_oracle\",\"n\":" << n
            << ",\"exact\":" << (oracle_exact ? "true" : "false") << "}\n";
  CheckInput(ld, low); CheckInput(xd, xn);
  auto refused = [&](const void *weights, void *q8, unsigned rows, unsigned width,
                     unsigned r, const float *iw, float *out) {
    Require(!q::HcMixRawQ8F16Gemm(weights, static_cast<const __half *>(ld.data),
        static_cast<const float *>(xd.data), iw, fused.mixed.Data(), nullptr,
        q8, out, rows, width, r, stream), "Invalid Q8 producer request accepted");
  };
  refused(w.hc.data, fused.q8.Data(), 95, hidden, rank, nullptr, nullptr);
  refused(w.hc.data, fused.q8.Data(), n, 2564, rank, nullptr, nullptr);
  refused(w.hc.data, fused.q8.Data(), n, hidden, 321, nullptr, nullptr);
  refused(nullptr, fused.q8.Data(), n, hidden, rank, nullptr, nullptr);
  refused(w.hc.data, nullptr, n, hidden, rank, nullptr, nullptr);
  refused(w.hc.data, fused.q8.Data(), n, hidden, rank,
          static_cast<const float *>(w.inject.data), nullptr);
  Hip(hipGetLastError());
  Hip(hipStreamSynchronize(stream));
  Pair(prefix+"-reject-q8", ref.q8, fused.q8, true, false);
  Hip(hipStreamDestroy(stream));
  return oracle_exact;
}

static void Timing() {
  constexpr unsigned n = 2048, matrices = 16, repetitions = 15;
  std::vector<std::unique_ptr<Weights>> weights;
  for (unsigned i = 0; i < matrices; ++i) weights.push_back(std::make_unique<Weights>(719+i));
  Random rng{819};
  std::vector<__half> low(std::size_t(n) * rank);
  std::vector<float> xn(std::size_t(n) * streams * hidden);
  for (auto &v : low) v = __float2half_rn(rng.Next() * .125f);
  for (auto &v : xn) v = rng.Next();
  Device ld(low.size() * 2), xd(xn.size() * 4);
  Upload(ld, low); Upload(xd, xn);
  Buffers ref(n), fused(n);
  hipEvent_t begin{}, end{};
  Hip(hipEventCreate(&begin)); Hip(hipEventCreate(&end));
  for (bool complete : {false, true}) {
    for (bool fusion : {false, true})
      for (unsigned i = 0; i < matrices; ++i)
        Launch(fusion, complete, *weights[i], ld, xd, fusion ? fused : ref, n, nullptr);
    Hip(hipDeviceSynchronize());
    for (unsigned rep = 0; rep < repetitions; ++rep)
      for (unsigned order = 0; order < 3; ++order) {
        // Reference before/candidate/reference after inside each repetition.
        const bool fusion = order == 1;
        Hip(hipEventRecord(begin, nullptr));
        for (unsigned i = 0; i < matrices; ++i)
          Launch(fusion, complete, *weights[i], ld, xd, fusion ? fused : ref, n, nullptr);
        Hip(hipEventRecord(end, nullptr)); Hip(hipEventSynchronize(end));
        float ms=0; Hip(hipEventElapsedTime(&ms, begin, end));
        std::cout << std::scientific << std::setprecision(12)
                  << "{\"event\":\"shared_q8_timing\",\"scope\":\""
                  << (complete ? "complete" : "producer") << "\",\"rep\":" << rep
                  << ",\"order\":" << order << ",\"fused\":" << (fusion ? "true" : "false")
                  << ",\"n\":" << n << ",\"launches\":" << matrices
                  << ",\"weight_bytes\":" << matrices*Weights::Bytes()
                  << ",\"us_per_cycle\":" << ms * 1000.0 / matrices << "}\n";
      }
    Pair(std::string("timed-")+(complete ? "complete" : "producer")+"-mixed",ref.mixed,fused.mixed,true,false);
    Pair(std::string("timed-")+(complete ? "complete" : "producer")+"-q8",ref.q8,fused.q8,true,false);
    if (complete) Pair("timed-complete-down",ref.down,fused.down,true,false);
  }
  Hip(hipEventDestroy(begin)); Hip(hipEventDestroy(end));
}

int main() {
  try {
    bool pass = Case(96, 0, true, true);
    pass = Case(129, 0, true, true) && pass;
    Weights weights(719);
    pass = Check(96, 0, true, true, weights) && pass;
    pass = Check(97, 1, true, true, weights) && pass;
    pass = Check(127, 2, true, true, weights) && pass;
    pass = Check(129, 0, false, false, weights) && pass;
    pass = Check(2048, 0, true, true, weights) && pass;
    Timing();
    std::cout << (pass ? "PASS" : "FAIL") << " synthetic shared Q8 producer; no model inference\n";
    return pass ? 0 : 1;
  } catch (const std::exception &error) {
    std::cerr << error.what() << '\n'; return 1;
  }
}
