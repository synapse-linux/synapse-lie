// SPDX-License-Identifier: MIT
// New persistent Q8-derived F16 mirror candidate versus literal retained numerical
// control. Synthetic operators only; model throughput uses the separate frozen
// tester.
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
namespace gufo::models::qwen38_flash_next::rocm {
#include "experiments/q2-q8-k16-phases-control.inc"
}
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
  explicit Device(std::size_t size) : bytes(size) {
    Hip(hipMalloc(&storage, bytes + 2 * guard));
    data = static_cast<std::uint8_t*>(storage) + guard;
  }
  void Guard(hipStream_t stream) {
    Hip(hipMemsetAsync(storage, 0xA7, guard, stream));
    Hip(hipMemsetAsync(static_cast<std::uint8_t*>(data) + bytes, 0xA7, guard,
                       stream));
  }
  void CheckGuards(hipStream_t stream) const {
    std::array<std::uint8_t, 2 * guard> got{};
    Hip(hipMemcpyAsync(got.data(), storage, guard, hipMemcpyDeviceToHost,
                       stream));
    Hip(hipMemcpyAsync(got.data() + guard,
                       static_cast<const std::uint8_t*>(data) + bytes, guard,
                       hipMemcpyDeviceToHost, stream));
    Hip(hipStreamSynchronize(stream));
    for (auto byte : got)
      Require(byte == 0xA7, "Corrupted device guard");
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
struct Inputs {
  unsigned n, m, k;
  bool ssm;
  bool attention{};
  std::vector<float> qgamma, kgamma;
  std::vector<std::uint32_t> position;
  std::vector<__half> activation;
  std::vector<std::uint8_t> weights;
  std::vector<float> convolution, history;
  Device x, conv, past, qg, kg, pos;
  std::array<std::unique_ptr<Device>, 3> w;
  std::array<std::string, 3> w_sha, mirror_sha;
  std::array<std::unique_ptr<Device>, 3> mirror;
  Inputs(unsigned rows, unsigned output, unsigned inner, bool fused,
         hipStream_t stream)
      : n(rows),
        m(output),
        k(inner),
        ssm(fused),
        qgamma(256),
        kgamma(256),
        position(1, 0),
        activation(std::size_t(n) * k),
        weights(std::size_t(m) * (k / 32) * 34),
        convolution(10240 * 4),
        history(10240 * 3),
        x(activation.size() * 2),
        conv(convolution.size() * 4),
        past(history.size() * 4),
        qg(qgamma.size() * 4),
        kg(kgamma.size() * 4),
        pos(position.size() * 4) {
    Random rng;
    for (auto& a : activation)
      a = __float2half_rn(rng.Value() * .125f);
    for (auto& a : convolution)
      a = rng.Value() * .03125f;
    for (auto& a : history)
      a = rng.Value() * .03125f;
    for (unsigned i = 0; i < 256; ++i) {
      qgamma[i] = 1.0f + rng.Value() * .25f;
      kgamma[i] = 1.0f + rng.Value() * .125f;
    }
    Upload(qg, qgamma, stream);
    Upload(kg, kgamma, stream);
    Upload(pos, position, stream);
    Upload(x, activation, stream);
    Upload(conv, convolution, stream);
    Upload(past, history, stream);
    for (unsigned rotation = 0; rotation < 3; ++rotation) {
      for (std::size_t offset = 0; offset < weights.size(); offset += 34) {
        const __half scale = __float2half_rn(
            (offset / 34) % 23 == 0 ? 0.0f : .002f + .0001f * rotation);
        std::memcpy(weights.data() + offset, &scale, 2);
        for (unsigned code = 0; code < 32; ++code)
          weights[offset + 2 + code] = std::uint8_t(rng.Next() >> 24);
      }
      w[rotation] = std::make_unique<Device>(weights.size());
      Upload(*w[rotation], weights, stream);
      w_sha[rotation] = Hash(weights);
      mirror[rotation] = std::make_unique<Device>(std::size_t(m) * k * 2);
      mirror[rotation]->Guard(stream);
      Hip(hipMemsetAsync(mirror[rotation]->data, 0xFF, mirror[rotation]->bytes, stream));
      Require(q::ConvertQ8Mirror(w[rotation]->data, mirror[rotation]->data,
                               std::size_t(m) * k, stream), "Mirror conversion launch failed");
      Hip(hipStreamSynchronize(stream));
      mirror_sha[rotation] = Hash(Read(*mirror[rotation], stream));
    }
  }
  void Unchanged(hipStream_t stream) {
    for (unsigned i = 0; i < 3; ++i)
      Require(Hash(Read(*w[i], stream)) == w_sha[i], "Q8 weights changed");
    for (unsigned i = 0; i < 3; ++i)
      Require(Hash(Read(*mirror[i], stream)) == mirror_sha[i], "F16 mirror changed");
    auto got = Read(qg, stream);
    Require(std::memcmp(got.data(), qgamma.data(), got.size()) == 0,
            "Query gamma changed");
    got = Read(kg, stream);
    Require(std::memcmp(got.data(), kgamma.data(), got.size()) == 0,
            "Key gamma changed");
    got = Read(pos, stream);
    Require(std::memcmp(got.data(), position.data(), got.size()) == 0,
            "Position changed");
    got = Read(x, stream);
    Require(std::memcmp(got.data(), activation.data(), got.size()) == 0,
            "F16 activations changed");
    got = Read(conv, stream);
    Require(std::memcmp(got.data(), convolution.data(), got.size()) == 0,
            "Convolution weights changed");
    got = Read(past, stream);
    Require(std::memcmp(got.data(), history.data(), got.size()) == 0,
            "Convolution history changed");
  }
};
struct State {
  Device out, convolved, query, gate, keys, values;
  State(unsigned n, unsigned m)
      : out(std::size_t(n) * m * 4),
        convolved(std::size_t(n) * 10240 * 4),
        query(std::size_t(n) * 6144 * 4),
        gate(std::size_t(n) * 6144 * 4),
        keys(std::size_t(n) * 512 * 2),
        values(std::size_t(n) * 512 * 2) {}
  void Clear(hipStream_t stream) {
    for (auto* buffer : {&out, &convolved, &query, &gate, &keys, &values}) {
      buffer->Guard(stream);
      Hip(hipMemsetAsync(buffer->data, 0xFF, buffer->bytes, stream));
    }
    // A missing store must not look like an exact zero in both paths.
    Hip(hipMemsetAsync(out.data, 0xFF, out.bytes, stream));
    Hip(hipMemsetAsync(convolved.data, 0xFF, convolved.bytes, stream));
  }
};
static void Launch(bool candidate, Inputs& inputs, State& state, unsigned index,
                   hipStream_t stream) {
  const void* w = candidate ? inputs.mirror[index]->data : inputs.w[index]->data;
  const auto* x = static_cast<const __half*>(inputs.x.data);
  auto* out = static_cast<float*>(state.out.data);
  const dim3 grid((inputs.n + 127) / 128, (inputs.m + 255) / 256);
  if (inputs.attention) {
    const q::AttentionProjectionOutput output{
        static_cast<const float*>(inputs.qg.data),
        static_cast<const float*>(inputs.kg.data),
        static_cast<float*>(state.query.data),
        static_cast<float*>(state.gate.data),
        static_cast<__half*>(state.keys.data),
        static_cast<__half*>(state.values.data),
        static_cast<const std::uint32_t*>(inputs.pos.data),
        10000000.0f,
        1e-6f,
        nullptr};
    if (candidate)
      hipLaunchKernelGGL(
          (q::DenseF16GEMMKernel<256, 128, 2, 8, 1, 1, false, false, true, true, false, true>),
          grid, dim3(256), 0, stream, w, x, nullptr, inputs.n, inputs.m,
          inputs.k, nullptr, nullptr, nullptr, nullptr, nullptr, output);
    else
      hipLaunchKernelGGL((q::DenseQ8K16ControlKernel<256, 128, 2, 8, 1, 1,
                                                     false, false, true>),
                         grid, dim3(256), 0, stream, w, x, nullptr, inputs.n,
                         inputs.m, inputs.k, nullptr, nullptr, nullptr, nullptr,
                         nullptr, output);
  } else if (inputs.ssm) {
    if (candidate)
      hipLaunchKernelGGL(
          (q::DenseF16GEMMKernel<256, 128, 2, 8, 1, 1, false, true, false, true, false, true>), grid,
          dim3(256), 0, stream, w, x, out, inputs.n, inputs.m, inputs.k,
          nullptr, nullptr, nullptr,
          static_cast<const float*>(inputs.conv.data),
          static_cast<float*>(state.convolved.data));
    else
      hipLaunchKernelGGL(
          (q::DenseQ8K16ControlKernel<256, 128, 2, 8, 1, 1, false, true>), grid,
          dim3(256), 0, stream, w, x, out, inputs.n, inputs.m, inputs.k,
          nullptr, nullptr, nullptr,
          static_cast<const float*>(inputs.conv.data),
          static_cast<float*>(state.convolved.data));
    hipLaunchKernelGGL(
        q::SsmConvBoundaryKernel,
        dim3(q::Blocks(10240), (inputs.n + 31) / 32, 3), dim3(256), 0, stream,
        out, static_cast<const float*>(inputs.conv.data),
        static_cast<const float*>(inputs.past.data),
        static_cast<float*>(state.convolved.data), inputs.n, 10240, inputs.m);
  } else {
    if (candidate)
      hipLaunchKernelGGL((q::DenseF16GEMMKernel<256, 128, 2, 8, 1, 1, false, false, false, true, false, true>), grid,
                         dim3(256), 0, stream, w, x, out, inputs.n, inputs.m,
                         inputs.k);
    else
      hipLaunchKernelGGL((q::DenseQ8K16ControlKernel<256, 128, 2, 8, 1>), grid,
                         dim3(256), 0, stream, w, x, out, inputs.n, inputs.m,
                         inputs.k);
  }
  Hip(hipGetLastError());
}
static bool Pair(const Device& first, const Device& second, hipStream_t stream,
                 const char* shape, unsigned rotation, const char* field,
                 unsigned tokens, unsigned rows, bool raw_projection,
                 bool half_output = false) {
  const auto a = Read(first, stream), b = Read(second, stream);
  Require(a.size() == b.size(), "Output size changed");
  std::size_t changed = 0, nonfinite = 0, unwritten = 0;
  std::size_t required = 0, expected_unused = 0, unexpected_unused = 0;
  const unsigned element_bytes = half_output ? 2 : 4;
  for (std::size_t i = 0; i < a.size(); i += element_bytes) {
    const std::size_t token = (i / element_bytes) / rows,
                      channel = (i / element_bytes) % rows;
    const bool live = !raw_projection || channel >= 10240 || token % 32 < 3 ||
                      token % 32 >= 29 || token + 3 >= tokens;
    required += live;
    expected_unused += !live;
    std::uint32_t xa = 0, xb = 0;
    std::memcpy(&xa, a.data() + i, element_bytes);
    std::memcpy(&xb, b.data() + i, element_bytes);
    float x, y;
    if (half_output) {
      x = __half2float(
          __builtin_bit_cast(__half, static_cast<std::uint16_t>(xa)));
      y = __half2float(
          __builtin_bit_cast(__half, static_cast<std::uint16_t>(xb)));
    } else {
      std::memcpy(&x, &xa, 4);
      std::memcpy(&y, &xb, 4);
    }
    const std::uint32_t poison = half_output ? 0xFFFFU : 0xFFFFFFFFU;
    nonfinite += live && (!std::isfinite(x) || !std::isfinite(y));
    unwritten += live && (xa == poison || xb == poison);
    unexpected_unused += !live && (xa != poison || xb != poison);
    changed += xa != xb;
  }
  std::cout << "{\"event\":\"q8_mirror_replay\",\"shape\":\"" << shape
            << "\",\"rotation\":" << rotation << ",\"field\":\"" << field
            << "\",\"bytes\":" << a.size() << ",\"changed_values\":" << changed
            << ",\"nonfinite_values\":" << nonfinite
            << ",\"unwritten_values\":" << unwritten
            << ",\"required_values\":" << required
            << ",\"expected_unused_values\":" << expected_unused
            << ",\"unexpected_unused_values\":" << unexpected_unused
            << ",\"guards_exact\":true"
            << ",\"reference_sha256\":\"" << Hash(a)
            << "\",\"candidate_sha256\":\"" << Hash(b) << "\",\"exact\":"
            << (changed == 0 && nonfinite == 0 && unwritten == 0 &&
                        unexpected_unused == 0
                    ? "true"
                    : "false")
            << "}\n";
  if (changed || nonfinite || unwritten || unexpected_unused) {
    const std::string prefix = std::string("results/q8-mirror-") + shape +
                               "-" + std::to_string(rotation) + "-" + field;
    for (const auto& entry :
         {std::pair<const char*, const std::vector<std::uint8_t>*>("reference",
                                                                   &a),
          std::pair<const char*, const std::vector<std::uint8_t>*>("candidate",
                                                                   &b)}) {
      std::ofstream file(prefix + "-" + entry.first + ".bin", std::ios::binary);
      Require(bool(file), "Cannot retain rejected output");
      file.write(reinterpret_cast<const char*>(entry.second->data()),
                 entry.second->size());
      Require(bool(file), "Cannot finish rejected output");
    }
  }
  Require(unwritten == 0 && unexpected_unused == 0, "Missing or unexpected output store");
  return changed == 0 && nonfinite == 0 && unwritten == 0 &&
         unexpected_unused == 0;
}
static bool Case(const char* label, unsigned n, unsigned m, unsigned k,
                 bool ssm, bool bench, hipStream_t stream,
                 bool attention = false) {
  Inputs in(n, m, k, ssm, stream);
  in.attention = attention;
  State reference(n, m), candidate(n, m);
  bool pass = true;
  for (unsigned index = 0; index < 3; ++index) {
    reference.Clear(stream);
    candidate.Clear(stream);
    Launch(false, in, reference, index, stream);
    Launch(true, in, candidate, index, stream);
    Hip(hipStreamSynchronize(stream));
    if (attention) {
      pass = Pair(reference.query, candidate.query, stream, label, index,
                  "query", n, 6144, false) &&
             pass;
      pass = Pair(reference.gate, candidate.gate, stream, label, index, "gate",
                  n, 6144, false) &&
             pass;
      pass = Pair(reference.keys, candidate.keys, stream, label, index, "keys",
                  n, 512, false, true) &&
             pass;
      pass = Pair(reference.values, candidate.values, stream, label, index,
                  "values", n, 512, false, true) &&
             pass;
    } else {
      pass = Pair(reference.out, candidate.out, stream, label, index,
                  "projection", n, m, ssm) &&
             pass;
      if (ssm)
        pass = Pair(reference.convolved, candidate.convolved, stream, label,
                    index, "convolution", n, 10240, false) &&
               pass;
    }
  }
  if (bench) {
    Require(in.weights.size() * 3 > 32u * 1024 * 1024,
            "Q8 weight rotation does not exceed MALL");
    hipEvent_t start{}, end{};
    Hip(hipEventCreate(&start));
    Hip(hipEventCreate(&end));
    for (unsigned rep = 0; rep < 7; ++rep) {
      for (unsigned order = 0; order < 2; ++order) {
        const bool is_candidate = ((rep + order) % 2) != 0;
        auto& state = is_candidate ? candidate : reference;
        Hip(hipEventRecord(start, stream));
        for (unsigned i = 0; i < 3; ++i)
          Launch(is_candidate, in, state, i, stream);
        Hip(hipEventRecord(end, stream));
        Hip(hipEventSynchronize(end));
        float ms{};
        Hip(hipEventElapsedTime(&ms, start, end));
        std::cout << "{\"event\":\"q8_mirror_timing\",\"shape\":\"" << label
                  << "\",\"rep\":" << rep << ",\"order\":" << order
                  << ",\"candidate\":" << (is_candidate ? "true" : "false")
                  << ",\"warmup\":" << (rep < 2 ? "true" : "false")
                  << ",\"tokens\":" << n << ",\"output_rows\":" << m
                  << ",\"inner\":" << k << ",\"iterations\":3,\"weight_bytes\":"
                  << in.weights.size() * 3
                  << ",\"mirror_weight_bytes\":" << in.mirror[0]->bytes * 3
                  << ",\"us_per_iteration\":" << double(ms) * 1000 / 3 << "}\n";
      }
    }
    Hip(hipEventDestroy(end));
    Hip(hipEventDestroy(start));
  }
  in.Unchanged(stream);
  return pass;
}

// Independent integer IEEE binary16 rounding of signed integer code * scale.
// Scales cover both signs and every finite half encoding with abs(scale)<=128.
// No host floating arithmetic and no CPU model forward. Native Q8 adds +0 in
// its half FMA, so an exact zero is +0, including negative scale zero.
static std::uint16_t ExactProduct(std::uint16_t scale, int code) {
  const unsigned absolute = scale & 0x7FFFU;
  if (code == 0 || absolute == 0) return 0;
  const unsigned exp = absolute >> 10, frac = absolute & 1023U;
  unsigned magnitude = (exp ? 1024U + frac : frac) * unsigned(code < 0 ? -code : code);
  const unsigned sign = ((scale >> 15) ^ unsigned(code < 0)) << 15;
  const int exponent = exp ? int(exp) - 25 : -24;
  const unsigned top = 31U - unsigned(__builtin_clz(magnitude));
  int unbiased = int(top) + exponent;
  if (unbiased < -14) return std::uint16_t(sign | magnitude);
  unsigned mantissa;
  if (top <= 10) mantissa = magnitude << (10 - top);
  else {
    const unsigned shift = top - 10, mask = (1U << shift) - 1U;
    mantissa = magnitude >> shift;
    const unsigned remainder = magnitude & mask, halfway = 1U << (shift - 1);
    mantissa += remainder > halfway || (remainder == halfway && (mantissa & 1U));
  }
  if (mantissa == 2048) { mantissa = 1024; ++unbiased; }
  Require(unbiased <= 15, "Format oracle overflow");
  return std::uint16_t(sign | unsigned(unbiased + 15) << 10 | (mantissa & 1023U));
}
static bool Format(hipStream_t stream) {
  constexpr std::size_t scales = (0x5800U + 1U) * 2U;
  constexpr std::size_t elements = scales * 256U;
  std::vector<std::uint8_t> encoded(scales * 8U * 34U);
  std::vector<std::uint16_t> expected(elements);
  for (unsigned sign = 0; sign < 2; ++sign) {
    for (unsigned absolute = 0; absolute <= 0x5800U; ++absolute) {
      const unsigned index = sign * (0x5800U + 1U) + absolute;
      const std::uint16_t d = std::uint16_t(absolute | sign << 15);
      for (unsigned block = 0; block < 8; ++block) {
        const auto offset = (std::size_t(index) * 8U + block) * 34U;
        std::memcpy(encoded.data() + offset, &d, 2);
        for (unsigned i = 0; i < 32; ++i) {
          const unsigned bits = block * 32 + i;
          encoded[offset + 2 + i] = std::uint8_t(bits);
          expected[std::size_t(index) * 256 + bits] = ExactProduct(d, bits < 128 ? int(bits) : int(bits) - 256);
        }
      }
    }
  }
  Device w(encoded.size()), out(elements * 2U);
  Upload(w, encoded, stream);
  out.Guard(stream);
  Hip(hipMemsetAsync(out.data, 0xFF, out.bytes, stream));
  hipEvent_t begin{}, end{};
  Hip(hipEventCreate(&begin)); Hip(hipEventCreate(&end));
  Hip(hipEventRecord(begin, stream));
  Require(q::ConvertQ8Mirror(w.data, out.data, elements, stream), "Format conversion launch failed");
  Hip(hipEventRecord(end, stream)); Hip(hipEventSynchronize(end));
  float elapsed{}; Hip(hipEventElapsedTime(&elapsed, begin, end));
  Hip(hipEventDestroy(end)); Hip(hipEventDestroy(begin));
  auto got = Read(out, stream);
  std::vector<std::uint8_t> oracle(expected.size() * 2U);
  std::memcpy(oracle.data(), expected.data(), oracle.size());
  std::size_t changed = 0, poison = 0;
  for (std::size_t i = 0; i < expected.size(); ++i) {
    std::uint16_t value; std::memcpy(&value, got.data() + 2U * i, 2);
    changed += value != expected[i]; poison += value == 0xFFFFU;
  }
  for (const auto& entry : {std::pair<const char*, const std::vector<std::uint8_t>*>("candidate", &got),
                            std::pair<const char*, const std::vector<std::uint8_t>*>("integer-reference", &oracle)}) {
    std::ofstream file(std::string("results/q8-mirror-format-") + entry.first + ".bin", std::ios::binary);
    Require(bool(file), "Cannot retain format output");
    file.write(reinterpret_cast<const char*>(entry.second->data()), entry.second->size());
    Require(bool(file), "Cannot finish format output");
  }
  Require(Hash(Read(w, stream)) == Hash(encoded), "Format Q8 weights changed");
  std::cout << "{\"event\":\"q8_mirror_format\",\"scales\":" << scales
            << ",\"code_scale_combinations\":" << elements << ",\"changed_values\":" << changed
            << ",\"unwritten_values\":" << poison << ",\"guards_exact\":true,\"conversion_ms\":" << elapsed
            << ",\"candidate_sha256\":\"" << Hash(got) << "\",\"integer_reference_sha256\":\"" << Hash(oracle)
            << "\",\"exact\":" << (changed == 0 && poison == 0) << "}\n";
  Require(poison == 0, "Unwritten mirror format output");
  return changed == 0;
}

int main() {
  try {
    std::cout << std::boolalpha << std::defaultfloat << std::setprecision(12);
    hipStream_t stream{};
    Hip(hipStreamCreateWithFlags(&stream, hipStreamNonBlocking));
    bool pass = Format(stream);
    for (unsigned n : {1u, 15u, 17u, 129u, 1025u}) {
      const std::string name = "ragged" + std::to_string(n);
      pass = Case(name.c_str(), n, 257, 96, false, false, stream) && pass;
    }
    pass = Case("ssm1024", 1024, 16384, 2560, true, false, stream) && pass;
    pass = Case("ssm1025", 1025, 16384, 2560, true, false, stream) && pass;
    pass = Case("ssm1057", 1057, 16384, 2560, true, false, stream) && pass;
    pass = Case("ssm2048", 2048, 16384, 2560, true, true, stream) && pass;
    pass = Case("output2048", 2048, 2560, 6144, false, true, stream) && pass;
    pass =
        Case("attention1025", 1025, 13312, 2560, false, false, stream, true) &&
        pass;
    pass =
        Case("attention2048", 2048, 13312, 2560, false, true, stream, true) &&
        pass;
    Hip(hipStreamSynchronize(stream));
    Hip(hipStreamDestroy(stream));
    std::cout << "{\"event\":\"q8_mirror_complete\",\"numerical_pass\":"
              << pass
              << ",\"timing_retained\":true,\"model_inference\":false}\n";
    return pass ? 0 : 1;
  } catch (const std::exception& ex) {
    std::cerr << "FAIL: " << ex.what() << '\n';
    return 1;
  }
}
