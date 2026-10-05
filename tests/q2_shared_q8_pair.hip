// SPDX-License-Identifier: MIT
// Shared Q8 gate/up fusion. Synthetic operators only; the original model
// throughput is measured by the separate frozen tester.
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "src/core/crypto/sha256.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
namespace q = gufo::models::qwen38_flash_next::rocm;

static void Require(bool condition, const char* message) {
  if (!condition)
    throw std::runtime_error(message);
}
static void Hip(hipError_t value) {
  if (value != hipSuccess)
    throw std::runtime_error(hipGetErrorString(value));
}
struct Device {
  void* storage{};
  void* data{};
  std::size_t bytes{};
  static constexpr std::size_t guard = 64;
  unsigned offset{};
  bool allocation_end{};
  explicit Device(std::size_t size, unsigned shift = 0, bool tail = false)
      : bytes(size), offset(shift), allocation_end(tail) {
    Hip(hipMalloc(&storage, bytes + guard + offset + (tail ? 0 : guard)));
    data = static_cast<std::uint8_t*>(storage) + guard + offset;
  }
  void Guard(hipStream_t stream) {
    Hip(hipMemsetAsync(static_cast<std::uint8_t*>(data) - guard, 0xA7, guard,
                       stream));
    if (!allocation_end)
      Hip(hipMemsetAsync(static_cast<std::uint8_t*>(data) + bytes, 0xA7, guard,
                         stream));
  }
  void CheckGuards(hipStream_t stream) const {
    std::array<std::uint8_t, 2 * guard> got{};
    Hip(hipMemcpyAsync(got.data(),
                       static_cast<const std::uint8_t*>(data) - guard, guard,
                       hipMemcpyDeviceToHost, stream));
    if (!allocation_end)
      Hip(hipMemcpyAsync(got.data() + guard,
                         static_cast<const std::uint8_t*>(data) + bytes, guard,
                         hipMemcpyDeviceToHost, stream));
    Hip(hipStreamSynchronize(stream));
    for (std::size_t i = 0; i < (allocation_end ? guard : got.size()); ++i)
      Require(got[i] == 0xA7, "Corrupted device guard");
  }
  Device(const Device&) = delete;
  Device& operator=(const Device&) = delete;
  ~Device() {
    if (storage)
      (void)hipFree(storage);
  }
};
static std::string Hash(const std::vector<std::uint8_t>& bytes) {
  return gufo::crypto::Sha256Hex(bytes);
}
static std::vector<std::uint8_t> Read(const Device& buffer,
                                      hipStream_t stream) {
  buffer.CheckGuards(stream);
  std::vector<std::uint8_t> result(buffer.bytes);
  Hip(hipMemcpyAsync(result.data(), buffer.data, buffer.bytes,
                     hipMemcpyDeviceToHost, stream));
  Hip(hipStreamSynchronize(stream));
  return result;
}
template<class T>
static void Upload(Device& destination, const std::vector<T>& source,
                   hipStream_t stream) {
  Require(destination.bytes == source.size() * sizeof(T),
          "Invalid input byte count");
  destination.Guard(stream);
  Hip(hipMemcpyAsync(destination.data, source.data(), destination.bytes,
                     hipMemcpyHostToDevice, stream));
  Hip(hipStreamSynchronize(stream));
}
struct Random {
  std::uint32_t state{713};
  std::uint32_t Next() {
    state = state * 1664525u + 1013904223u;
    return state;
  }
  float Value() { return (float(int(Next() >> 16) - 32768)) / 32768.0f; }
};

static std::vector<std::uint8_t> Weights(unsigned m, unsigned k, Random& rng) {
  std::vector<std::uint8_t> bytes(std::size_t(m) * (k / 32) * 34);
  for (std::size_t pos = 0; pos < bytes.size(); pos += 34) {
    const __half d =
        __float2half_rn(std::ldexp(1.0f + std::abs(rng.Value()), -10));
    std::memcpy(bytes.data() + pos, &d, 2);
    for (unsigned j = 0; j < 32; ++j)
      bytes[pos + 2 + j] = std::uint8_t(int(rng.Next() % 255) - 127);
  }
  return bytes;
}

struct Operand {
  unsigned n, m, k;
  std::vector<std::uint8_t> gate, up, down, quantized;
  std::vector<float> x;
  Device dg, du, dd, dx, qx;
  Operand(unsigned rows, unsigned outputs, unsigned cols, unsigned seed,
          hipStream_t stream, unsigned shift = 0)
      : n(rows),
        m(outputs),
        k(cols),
        dg(std::size_t(m) * (k / 32) * 34, shift, true),
        du(dg.bytes, shift, true),
        dd(std::size_t(2560) * 20 * 34, shift, true),
        dx(std::size_t(n) * k * sizeof(float), 0, true),
        qx(q::Q8TiledBytes(n, k), 0, true) {
    Random rng{seed};
    gate = Weights(m, k, rng);
    up = Weights(m, k, rng);
    down = Weights(2560, 640, rng);
    x.resize(std::size_t(n) * k);
    for (float& v : x)
      v = rng.Value() * 0.75f;
    Upload(dg, gate, stream);
    Upload(du, up, stream);
    Upload(dd, down, stream);
    Upload(dx, x, stream);
    qx.Guard(stream);
    Hip(hipMemsetAsync(qx.data, 0, qx.bytes, stream));
    q::QuantizeQ8Tiled(static_cast<const float*>(dx.data), qx.data, n, k,
                       stream);
    Hip(hipStreamSynchronize(stream));
    quantized = Read(qx, stream);
  }
  void Check(hipStream_t stream) const {
    Require(Read(dg, stream) == gate && Read(du, stream) == up &&
                Read(dd, stream) == down,
            "Immutable encoded weights changed");
    const auto input = Read(dx, stream);
    Require(input.size() == x.size() * sizeof(float) &&
                std::memcmp(input.data(), x.data(), input.size()) == 0,
            "Immutable input changed");
    Require(Read(qx, stream) == quantized, "Immutable quantized input changed");
  }
};

struct Outputs {
  Device gate, up, half, down;
  Outputs(unsigned n, unsigned m, unsigned shift = 0)
      : gate(std::size_t(n) * m * 4),
        up(gate.bytes),
        half(std::size_t(n) * m * 2, shift, true),
        down(std::size_t(n) * 2560 * 4) {}
  void Poison(hipStream_t stream) {
    for (Device* d : {&gate, &up, &half, &down}) {
      d->Guard(stream);
      Hip(hipMemsetAsync(d->data, 0xff, d->bytes, stream));
    }
  }
};

static void Run(const Operand& p, Outputs& out, bool candidate, bool cycle,
                hipStream_t stream) {
  if (candidate) {
    if (p.m == 640 && p.k == 2560 && p.n >= 96) {
      Require(q::SharedQ8PairHalf(p.dg.data, p.du.data, p.qx.data,
                                  static_cast<__half*>(out.half.data), p.n, p.m,
                                  p.k, stream),
              "Pair dispatch failed");
    } else {
      hipLaunchKernelGGL((q::SharedQ8PairKernel<128, 128, 2, 4, 2>),
                         dim3((p.n + 127) / 128, (p.m + 63) / 64), dim3(256), 0,
                         stream, p.dg.data, p.du.data, p.qx.data,
                         static_cast<__half*>(out.half.data), p.n, p.m, p.k);
    }
  } else {
    for (bool up : {false, true}) {
      // Literal production specialization for the new wave-pair comparison.
      hipLaunchKernelGGL((q::W8A8BlockedWmmaGEMMKernel<128, 128, 2, 4, 2>),
                         dim3((p.n + 127) / 128, (p.m + 127) / 128), dim3(256),
                         0, stream, up ? p.du.data : p.dg.data, p.qx.data,
                         static_cast<float*>(up ? out.up.data : out.gate.data),
                         p.n, p.m, p.k);
    }
    q::SwigluHalf(static_cast<const float*>(out.gate.data),
                  static_cast<const float*>(out.up.data),
                  static_cast<__half*>(out.half.data), std::size_t(p.n) * p.m,
                  stream);
  }
  if (cycle) {
    Require(p.m == 640, "Unsupported down input width");
    Require(q::DenseF16Gemm(
                p.dd.data, static_cast<const __half*>(out.half.data),
                static_cast<float*>(out.down.data), p.n, 2560, 640, stream),
            "Down dispatch failed");
  }
  Hip(hipGetLastError());
}

static bool Compare(const std::string& id, const Device& a, const Device& b,
                    bool half, hipStream_t stream) {
  const auto x = Read(a, stream), y = Read(b, stream);
  Require(x.size() == y.size(), "Mismatched output sizes");
  const std::size_t width = half ? 2 : 4;
  for (const auto* bytes : {&x, &y}) {
    for (std::size_t offset = 0; offset < bytes->size(); offset += width) {
      float value;
      if (half) {
        __half v;
        std::memcpy(&v, bytes->data() + offset, 2);
        value = __half2float(v);
      } else {
        std::memcpy(&value, bytes->data() + offset, 4);
      }
      Require(std::isfinite(value), "Unwritten or nonfinite output");
    }
  }
  for (const auto& item :
       {std::make_pair("parent", &x), std::make_pair("candidate", &y)}) {
    std::ofstream f(id + "-" + item.first + ".bin", std::ios::binary);
    f.write(reinterpret_cast<const char*>(item.second->data()),
            item.second->size());
    Require(bool(f), "Output write failed");
  }
  std::cout << "{\"type\":\"comparison\",\"id\":\"" << id
            << "\",\"bytes\":" << x.size() << ",\"half\":" << half
            << ",\"exact\":" << (x == y) << ",\"parent_sha256\":\"" << Hash(x)
            << "\",\"candidate_sha256\":\"" << Hash(y) << "\"}\n";
  return x == y;
}

static bool Oracle(const Operand& p, const Outputs& output, hipStream_t stream,
                   const std::string& id) {
  const auto act = Read(p.qx, stream), observed = Read(output.half, stream);
  double squared = 0, reference_squared = 0, maximum = 0, reference_maximum = 0;
  const unsigned nb = p.k / 32;
  for (unsigned sample = 0; sample < 64; ++sample) {
    const unsigned t = (sample * 37u) % p.n, row = (sample * 43u) % p.m;
    double dots[2]{};
    for (unsigned arm = 0; arm < 2; ++arm) {
      const auto& weights = arm ? p.up : p.gate;
      for (unsigned kb = 0; kb < nb; ++kb) {
        const auto* w = weights.data() + (std::size_t(row) * nb + kb) * 34;
        __half dh;
        std::memcpy(&dh, w, 2);
        const auto* tile = act.data() + (std::size_t(t / 16) * nb + kb) * 576;
        float dx;
        std::memcpy(&dx, tile + 512 + (t % 16) * 4, 4);
        int dot = 0;
        for (unsigned i = 0; i < 32; ++i) {
          std::int8_t qw, qx;
          std::memcpy(&qw, w + 2 + i, 1);
          std::memcpy(&qx, tile + (i / 16) * 256 + (t % 16) * 16 + i % 16, 1);
          dot += int(qw) * int(qx);
        }
        dots[arm] += double(__half2float(dh)) * double(dx) * dot;
      }
    }
    const double reference = dots[0] / (1.0 + std::exp(-dots[0])) * dots[1];
    __half value;
    std::memcpy(&value, observed.data() + (std::size_t(t) * p.m + row) * 2, 2);
    const double delta = double(__half2float(value)) - reference;
    squared += delta * delta;
    reference_squared += reference * reference;
    maximum = std::max(maximum, std::abs(delta));
    reference_maximum = std::max(reference_maximum, std::abs(reference));
  }
  const double relative =
      std::sqrt(squared / std::max(reference_squared, 1e-24));
  const double scaled = maximum / std::max(reference_maximum, 1e-12);
  const bool pass = relative <= 0.002 && scaled <= 0.002;
  std::cout << "{\"type\":\"oracle\",\"id\":\"" << id
            << "\",\"samples\":64,\"relative_rms\":" << relative
            << ",\"scaled_error\":" << scaled
            << ",\"limit\":0.002,\"pass\":" << pass << "}\n";
  return pass;
}

static bool CheckCase(const Operand& p, hipStream_t stream,
                      const std::string& id, unsigned shift = 0) {
  Outputs parent(p.n, p.m), candidate(p.n, p.m, shift);
  const auto tiled = Read(p.qx, stream);
  const bool cycle = p.m == 640;
  parent.Poison(stream);
  candidate.Poison(stream);
  Run(p, parent, false, cycle, stream);
  Run(p, candidate, true, cycle, stream);
  Hip(hipStreamSynchronize(stream));
  bool pass = Compare(id + "-half", parent.half, candidate.half, true, stream);
  if (cycle)
    pass = Compare(id + "-down", parent.down, candidate.down, false, stream) &&
           pass;
  pass = Oracle(p, candidate, stream, id) && pass;
  for (const auto* out : {&parent, &candidate})
    for (const auto* buf : {&out->gate, &out->up, &out->half, &out->down})
      buf->CheckGuards(stream);
  p.Check(stream);
  Require(tiled == Read(p.qx, stream), "Quantized input changed");
  return pass;
}

static bool Timing(const std::vector<std::unique_ptr<Operand>>& rotation,
                   hipStream_t stream) {
  Outputs parent(2048, 640), candidate(2048, 640);
  parent.Poison(stream);
  candidate.Poison(stream);
  hipEvent_t start{}, end{};
  Hip(hipEventCreate(&start));
  Hip(hipEventCreate(&end));
  for (bool cycle : {false, true}) {
    for (int sample = -2; sample < 5; ++sample) {
      for (int order = 0; order < 2; ++order) {
        const bool newer = ((sample + 2 + order) % 2) != 0;
        Hip(hipEventRecord(start, stream));
        for (const auto& p : rotation)
          Run(*p, newer ? candidate : parent, newer, cycle, stream);
        Hip(hipEventRecord(end, stream));
        Hip(hipEventSynchronize(end));
        float ms;
        Hip(hipEventElapsedTime(&ms, start, end));
        std::cout << "{\"type\":\"timing\",\"cycle\":" << cycle
                  << ",\"sample\":" << sample << ",\"order\":" << order
                  << ",\"candidate\":" << newer
                  << ",\"rotations\":" << rotation.size()
                  << ",\"microseconds\":"
                  << (double(ms) * 1000.0 / rotation.size()) << "}\n";
      }
    }
  }
  Hip(hipEventDestroy(start));
  Hip(hipEventDestroy(end));
  const bool half =
      Compare("timing-final-half", parent.half, candidate.half, true, stream);
  return Compare("timing-final-down", parent.down, candidate.down, false,
                 stream) &&
         half;
}

int main() {
  try {
    std::cout << std::setprecision(12) << std::boolalpha;
    hipStream_t stream;
    Hip(hipStreamCreateWithFlags(&stream, hipStreamNonBlocking));
    bool pass = true;
    unsigned cases = 0;
    for (unsigned m : {1u, 15u, 17u, 63u, 65u, 127u, 129u}) {
      Operand p(17, m, 96, 700 + m, stream, 2);
      pass = CheckCase(p, stream, "tail-" + std::to_string(m), 2) && pass;
      ++cases;
    }
    for (unsigned n : {96u, 127u, 128u, 129u, 255u, 1025u}) {
      Operand p(n, 640, 2560, 900 + n, stream);
      pass = CheckCase(p, stream, "rows-" + std::to_string(n)) && pass;
      ++cases;
    }
    std::vector<std::unique_ptr<Operand>> rotation;
    for (unsigned r = 0; r < 11; ++r) {
      rotation.push_back(
          std::make_unique<Operand>(2048, 640, 2560, 1200 + r, stream));
      pass =
          CheckCase(*rotation.back(), stream, "rotate-" + std::to_string(r)) &&
          pass;
      ++cases;
    }
    Require(!q::SharedQ8PairHalf(nullptr, nullptr, nullptr, nullptr, 2048, 640,
                                 2560, stream),
            "Null dispatch accepted");
    Require(!q::SharedQ8PairHalf(rotation[0]->dg.data, rotation[0]->du.data,
                                 rotation[0]->qx.data,
                                 static_cast<__half*>(rotation[0]->dx.data), 95,
                                 640, 2560, stream),
            "Unsupported rows accepted");
    std::size_t weight_bytes = 0, pair_bytes = 0;
    for (const auto& p : rotation)
      weight_bytes += p->dg.bytes + p->du.bytes + p->dd.bytes;
    for (const auto& p : rotation)
      pair_bytes += p->dg.bytes + p->du.bytes;
    Require(pair_bytes > 32 * 1024 * 1024, "Pair weight rotation fits cache");
    pass = Timing(rotation, stream) && pass;
    for (const auto& p : rotation)
      p->Check(stream);
    Hip(hipStreamDestroy(stream));
    std::cout
        << "{\"type\":\"complete\",\"cases\":" << cases
        << ",\"rotated_weight_bytes\":" << weight_bytes
        << ",\"rotated_pair_weight_bytes\":" << pair_bytes
        << ",\"numeric_pass\":" << pass
        << ",\"guards_pass\":true,\"required_outputs_finite_written\":true}\n";
    return pass ? 0 : 1;
  } catch (const std::exception& e) {
    std::cerr << e.what() << '\n';
    return 2;
  }
}
