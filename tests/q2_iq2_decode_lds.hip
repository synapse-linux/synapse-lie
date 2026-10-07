// SPDX-License-Identifier: MIT
// Original IQ2_XXS scalar decode: native quantizer/gated projection with LDS codebook.
#include "qfn_mmq_prelude.h"
namespace qfn_mmq {
#include "mmvq.hpp"
#include "quantize.hpp"
#include "unary.hpp"
#include "vecdotq.hpp"
// This kernel body depends on the preceding vendor definitions.
void Iq2DecodeLdsProbe(bool, const void*, const void*, const block_q8_1*,
                       const int32_t*, float*, int, int, int, int, hipStream_t);
}  // namespace qfn_mmq
#include <array>
#include <chrono>
#include <cmath>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <vector>

namespace q = qfn_mmq;
static void Require(bool ok, const char* text) {
  if (!ok)
    throw std::runtime_error(text);
}
static void Hip(hipError_t rc) {
  if (rc != hipSuccess)
    throw std::runtime_error(hipGetErrorString(rc));
}
struct Device {
  void* storage{};
  void* data{};
  size_t bytes;
  explicit Device(size_t n) : bytes(n) {
    Hip(hipMalloc(&storage, n + 128));
    data = static_cast<unsigned char*>(storage) + 64;
    Hip(hipMemset(storage, 0xa7, n + 128));
  }
  ~Device() {
    if (storage) {
      const auto rc = hipFree(storage);
      (void)rc;
    }
  }
  Device(const Device&) = delete;
  Device& operator=(const Device&) = delete;
  void Put(const void* p) {
    Hip(hipMemcpy(data, p, bytes, hipMemcpyHostToDevice));
  }
  void Clear() { Hip(hipMemset(data, 0xff, bytes)); }
  std::vector<unsigned char> Read() const {
    std::array<unsigned char, 128> guard{};
    Hip(hipMemcpy(guard.data(), storage, 64, hipMemcpyDeviceToHost));
    Hip(hipMemcpy(guard.data() + 64,
                  static_cast<const unsigned char*>(data) + bytes, 64,
                  hipMemcpyDeviceToHost));
    Require(std::all_of(guard.begin(), guard.end(),
                        [](auto x) { return x == 0xa7; }),
            "Device guard changed");
    std::vector<unsigned char> out(bytes);
    Hip(hipMemcpy(out.data(), data, bytes, hipMemcpyDeviceToHost));
    return out;
  }
};

constexpr unsigned kLive = 2560, kPadded = 2560, kExperts = 512;
// Literal table from independently pinned Gufo/ggml; generated in the build capsule.
static constexpr uint64_t grid[256] = {
#include "iq2-grid.inc"
};
struct Inputs {
  unsigned rows, slots, steps;
  std::vector<q::block_iq2_xxs> gate, up;
  std::vector<float> x;
  std::vector<int32_t> ids;
  Device gd, ud, xd, id;
  Inputs(unsigned m, unsigned n, unsigned calls, unsigned family, bool inactive)
      : rows(m), slots(n), steps(calls),
        gate(size_t(kExperts) * m * (kLive / 256)), up(gate.size()),
        x(kLive), ids(size_t(n) * calls), gd(gate.size() * sizeof(gate[0])),
        ud(up.size() * sizeof(up[0])), xd(x.size() * sizeof(float)),
        id(ids.size() * sizeof(ids[0])) {
    uint32_t rng = 713;
    const auto next = [&]() { rng = rng * 1664525u + 1013904223u; return rng; };
    for (auto* bank : {&gate, &up})
      for (auto& b : *bank) {
        b.d = __float2half(0.000513f * float(1 + next() % 3));
        for (auto& v : b.qs) v = next() >> 16;
      }
    for (unsigned i = 0; i < x.size(); ++i) {
      float v = float(int(next() >> 24) - 128) / 256.f;
      if (family == 1) v *= 0.002f;
      if (family == 2) v = (i & 1) ? -0.f : 0.f;
      if (family == 3) v = (i & 1) ? -0.499f : 0.5f;
      x[i] = v;
    }
    for (unsigned i = 0; i < ids.size(); ++i)
      ids[i] = inactive && i % 3 == 0 ? -1 : int((i * 37) % kExperts);
    gd.Put(gate.data()); ud.Put(up.data()); xd.Put(x.data()); id.Put(ids.data());
  }
  void Unchanged() const {
    const auto g = gd.Read(), u = ud.Read(), a = xd.Read(), b = id.Read();
    Require(std::memcmp(g.data(), gate.data(), g.size()) == 0 &&
            std::memcmp(u.data(), up.data(), u.size()) == 0 &&
            std::memcmp(a.data(), x.data(), a.size()) == 0 &&
            std::memcmp(b.data(), ids.data(), b.size()) == 0, "Immutable input changed");
  }
};
static void Launch(unsigned arm, const Inputs& in, Device& packed, Device& out,
                   unsigned step, hipStream_t stream) {
  q::quantize_row_q8_1_hip(static_cast<const float*>(in.xd.data), nullptr,
      packed.data, q::GGML_TYPE_IQ2_XXS, kLive, kLive, kLive, kLive,
      kPadded, 1, 1, 1, stream);
  const auto* x = static_cast<const q::block_q8_1*>(packed.data);
  const auto* ids = static_cast<const int32_t*>(in.id.data) + step * in.slots;
  auto* y = static_cast<float*>(out.data);
  if (arm == 0)
    q::mul_mat_vec_moe_gated(in.gd.data, in.ud.data, q::GGML_TYPE_IQ2_XXS,
        x, ids, nullptr, y, kLive, in.rows, 1, in.slots, kPadded / 32, stream);
  else {
    Require(arm == 1 || arm == 2, "Invalid arm");
    q::Iq2DecodeLdsProbe(arm == 2, in.gd.data, in.ud.data, x, ids, y,
                        kLive, in.rows, in.slots, kPadded / 32, stream);
  }
  Hip(hipGetLastError());
}
static double Weight(const q::block_iq2_xxs& b, unsigned col) {
  const auto* bytes = reinterpret_cast<const unsigned char*>(b.qs);
  const unsigned group = (col % 256) / 32, part = (col % 32) / 8, lane = col % 8;
  uint32_t bits; std::memcpy(&bits, bytes + group * 8 + 4, 4);
  const unsigned sign7 = (bits >> (7 * part)) & 127;
  const unsigned signs = sign7 | ((__builtin_popcount(sign7) & 1u) << 7);
  const unsigned code = bytes[group * 8 + part];
  return double(__half2float(b.d)) * (2 * (bits >> 28) + 1) * 0.125 *
         ((grid[code] >> (8 * lane)) & 255) * ((signs & (1u << lane)) ? -1 : 1);
}
static bool Oracle(const Inputs& in, const Device& packed,
                   const std::vector<unsigned char>& bytes, unsigned step,
                   unsigned arm, const char* label, int rep) {
  const auto raw = packed.Read();
  std::vector<q::block_q8_1> x(raw.size() / sizeof(q::block_q8_1));
  std::memcpy(x.data(), raw.data(), raw.size());
  std::vector<float> y(bytes.size() / sizeof(float));
  std::memcpy(y.data(), bytes.data(), bytes.size());
  Require(std::all_of(y.begin(), y.end(), [](float f) { return std::isfinite(f); }),
          "Nonfinite or unwritten output");
  double err = 0, norm = 0, peak_error = 0, peak = 0;
  unsigned count = 0;
  for (unsigned slot = 0; slot < in.slots; ++slot) {
    const int expert = in.ids[step * in.slots + slot];
    for (unsigned row : {0u, std::min(1u,in.rows-1), in.rows / 2,
                         in.rows > 1 ? in.rows-2 : 0, in.rows-1}) {
      double expected = 0, g = 0, u = 0;
      if (expert >= 0) {
        for (unsigned col = 0; col < kLive; ++col) {
          const size_t offset = (size_t(expert) * in.rows + row) * (kLive/256) + col/256;
          const auto& a = x[col/32];
          const double activation = double(__low2float(a.ds)) * a.qs[col%32];
          g += Weight(in.gate[offset], col) * activation;
          u += Weight(in.up[offset], col) * activation;
        }
        const double sigmoid = g >= 0 ? 1/(1+std::exp(-g)) : std::exp(g)/(1+std::exp(g));
        expected = g * sigmoid * u;
      }
      const double delta = y[slot * in.rows + row] - expected;
      err += delta*delta; norm += expected*expected;
      peak_error = std::max(peak_error,std::abs(delta)); peak = std::max(peak,std::abs(expected));
      ++count;
    }
  }
  const double rms = std::sqrt(err / std::max(norm,1e-30));
  const double scaled = peak_error / std::max(peak,1e-20);
  const bool pass = rms <= 0.002 && scaled <= 0.002;
  std::cout << "{\"event\":\"iq2_decode_lds_oracle\",\"case\":\"" << label
            << "\",\"arm\":" << arm << ",\"step\":" << step << ",\"rep\":" << rep
            << ",\"values\":" << count << ",\"relative_rms\":" << rms
            << ",\"peak_scaled\":" << scaled << ",\"limit\":0.002,\"pass\":" << pass << "}\n";
  return pass;
}
static bool Check(const Inputs& in, Device& packed, const Device& control,
                  const Device& candidate, unsigned step, unsigned arm,
                  const char* label, int rep) {
  const auto a = control.Read(), b = candidate.Read();
  const bool exact = a == b;
  const bool oracle = Oracle(in, packed, b, step, arm, label, rep);
  std::cout << "{\"event\":\"iq2_decode_lds_replay\",\"case\":\"" << label
            << "\",\"arm\":" << arm << ",\"step\":" << step
            << ",\"rep\":" << rep << ",\"bytes\":" << a.size() << ",\"exact\":" << exact
            << ",\"guards_exact\":true}\n";
  if (!exact || !oracle) {
    const std::string prefix = std::string("results/iq2-decode-lds-") + label + "-" +
                               std::to_string(rep) + "-" + std::to_string(step) + "-" + std::to_string(arm);
    for (const auto& entry : {std::make_pair("-original.f32", &a),
                              std::make_pair("-candidate.f32", &b)}) {
      std::ofstream f(prefix + entry.first, std::ios::binary);
      f.write(reinterpret_cast<const char*>(entry.second->data()),
              entry.second->size());
      Require(bool(f), "Cannot preserve failed output");
    }
  }
  return exact && oracle;
}

static bool Case(unsigned rows, unsigned slots, unsigned family, bool inactive,
                 bool timed, const char* label) {
  Inputs in(rows, slots, timed ? 64 : 1, family, inactive);
  Device packed(size_t(kPadded / 32) * sizeof(q::block_q8_1));
  std::array<std::vector<std::unique_ptr<Device>>, 3> outputs;
  for (auto& arm : outputs)
    for (unsigned i = 0; i < in.steps; ++i) {
      arm.push_back(
          std::make_unique<Device>(size_t(rows) * slots * sizeof(float)));
      arm.back()->Clear();
    }
  hipStream_t stream{};
  Hip(hipStreamCreateWithFlags(&stream, hipStreamNonBlocking));
  bool pass = true;
  for (unsigned a = 0; a < 3; ++a)
    Launch(a, in, packed, *outputs[a][0], 0, stream);
  Hip(hipStreamSynchronize(stream));
  pass &= Oracle(in, packed, outputs[0][0]->Read(), 0, 0, label, -1);
  for (unsigned a = 1; a < 3; ++a)
    pass &=
        Check(in, packed, *outputs[0][0], *outputs[a][0], 0, a, label, -1);
  if (timed) {
    Require((in.gd.bytes + in.ud.bytes) > 32u * 1024 * 1024, "Weight bank fits in MALL");
    std::array<hipGraph_t, 3> graphs{};
    std::array<hipGraphExec_t, 3> execs{};
    for (unsigned a = 0; a < 3; ++a) {
      Hip(hipStreamBeginCapture(stream, hipStreamCaptureModeThreadLocal));
      for (unsigned i = 0; i < in.steps; ++i)
        Launch(a, in, packed, *outputs[a][i], i, stream);
      Hip(hipStreamEndCapture(stream, &graphs[a]));
      Hip(hipGraphInstantiate(&execs[a], graphs[a], nullptr, nullptr, 0));
    }
    for (unsigned rep = 0; rep < 7; ++rep) {
      for (unsigned order = 0; order < 3; ++order) {
        const unsigned a = (rep + order) % 3;
        for (auto& out : outputs[a])
          out->Clear();
        Hip(hipStreamSynchronize(stream));
        const auto begin = std::chrono::steady_clock::now();
        Hip(hipGraphLaunch(execs[a], stream));
        Hip(hipStreamSynchronize(stream));
        const double us = std::chrono::duration<double, std::micro>(
                              std::chrono::steady_clock::now() - begin)
                              .count() /
                          in.steps;
        std::cout << "{\"event\":\"iq2_decode_lds_timing\",\"case\":\"" << label
                  << "\",\"arm\":" << (a) << ",\"rep\":" << rep
                  << ",\"order\":" << order << ",\"warmup\":" << (rep < 2)
                  << ",\"calls\":" << in.steps
                  << ",\"weight_bytes\":" << (in.gd.bytes + in.ud.bytes)
                  << ",\"complete_cycle_us\":" << us << "}\n";
      }
      // Each output belongs to a different call and survives until checked.
      for (unsigned i = 0; i < in.steps; ++i) {
        pass &= Oracle(in, packed, outputs[0][i]->Read(), i, 0, label, rep);
        for (unsigned a = 1; a < 3; ++a)
          pass &= Check(in, packed, *outputs[0][i], *outputs[a][i], i, a,
                        label, rep);
      }
    }
    for (unsigned a = 0; a < 3; ++a) {
      Hip(hipGraphExecDestroy(execs[a]));
      Hip(hipGraphDestroy(graphs[a]));
    }
  }
  in.Unchanged();
  packed.Read();
  Hip(hipStreamDestroy(stream));
  return pass;
}

int main() {
  try {
    std::cout << std::boolalpha << std::setprecision(12);
    bool pass = true;
    pass &= Case(640, 10, 0, false, true, "scalar10");
    pass &= Case(639, 9, 1, true, false, "ragged9");
    pass &= Case(1, 1, 2, false, false, "zero1");
    pass &= Case(31, 8, 3, false, false, "cancel8");
    pass &= Case(31, 11, 0, true, false, "inactive11");
    std::cout << "{\"event\":\"iq2_decode_lds_complete\",\"numerical_pass\":" << pass
              << ",\"safe_completion\":true,\"model_inference\":false}\n";
    return pass ? 0 : 1;
  } catch (const std::exception& e) {
    std::cerr << e.what() << '\n';
    return 2;
  }
}
