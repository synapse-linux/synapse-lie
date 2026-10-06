// SPDX-License-Identifier: MIT
// New SSM resident-fence composition versus literal retained numerical
// control. Synthetic operators only; model throughput uses the separate frozen
// tester.
#include <algorithm>
#include <array>
#include <chrono>
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
#include "experiments/q2-ssm-resident-fence-draft.inc"
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
      hipFree(storage);
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
  std::vector<__half> activation;
  std::vector<std::uint8_t> weights;
  std::vector<float> convolution, history;
  Device x, conv, past;
  std::array<std::unique_ptr<Device>, 3> w;
  std::array<std::string, 3> w_sha;
  Inputs(unsigned rows, unsigned output, unsigned inner, bool fused,
         hipStream_t stream)
      : n(rows),
        m(output),
        k(inner),
        ssm(fused),
        activation(std::size_t(n) * k),
        weights(std::size_t(m) * (k / 32) * 34),
        convolution(10240 * 4),
        history(10240 * 3),
        x(activation.size() * 2),
        conv(convolution.size() * 4),
        past(history.size() * 4) {
    Random rng;
    for (auto& a : activation)
      a = __float2half_rn(rng.Value() * .125f);
    for (auto& a : convolution)
      a = rng.Value() * .03125f;
    for (auto& a : history)
      a = rng.Value() * .03125f;
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
    }
  }
  void Unchanged(hipStream_t stream) {
    for (unsigned i = 0; i < 3; ++i)
      Require(Hash(Read(*w[i], stream)) == w_sha[i], "Q8 weights changed");
    auto got = Read(x, stream);
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
  Device out, convolved;
  State(unsigned n, unsigned m)
      : out(std::size_t(n) * m * 4), convolved(std::size_t(n) * 10240 * 4) {}
  void Clear(hipStream_t stream) {
    out.Guard(stream);
    convolved.Guard(stream);
    // A missing store must not look like an exact zero in both paths.
    Hip(hipMemsetAsync(out.data, 0xFF, out.bytes, stream));
    Hip(hipMemsetAsync(convolved.data, 0xFF, convolved.bytes, stream));
  }
};
static void Launch(bool candidate, Inputs& inputs, State& state, unsigned index,
                   hipStream_t stream) {
  const void* w = inputs.w[index]->data;
  const auto* x = static_cast<const __half*>(inputs.x.data);
  auto* out = static_cast<float*>(state.out.data);
  auto call = candidate ? q::DenseSsmResidentFence : q::DenseF16SsmGemm;
  const bool good = call(w, x, static_cast<const float*>(inputs.conv.data),
                         static_cast<const float*>(inputs.past.data), out,
                         static_cast<float*>(state.convolved.data), inputs.n,
                         inputs.m, inputs.k, 10240, 4, stream);
  Require(good, "Q8 dispatch refused");
  Hip(hipGetLastError());
}
static bool Pair(const Device& first, const Device& second, hipStream_t stream,
                 const char* shape, unsigned rotation, const char* field,
                 unsigned tokens, unsigned rows, bool raw_projection) {
  const auto a = Read(first, stream), b = Read(second, stream);
  Require(a.size() == b.size(), "Output size changed");
  std::size_t changed = 0, nonfinite = 0, unwritten = 0;
  std::size_t required = 0, expected_unused = 0, unexpected_unused = 0;
  for (std::size_t i = 0; i < a.size(); i += 4) {
    float x, y;
    std::memcpy(&x, a.data() + i, 4);
    std::memcpy(&y, b.data() + i, 4);
    // Match the production fused SSM contract: the interior raw QKV is
    // consumed in LDS; only boundary rows and non-convolved channels are live.
    const std::size_t token = (i / 4) / rows, channel = (i / 4) % rows;
    const bool live = !raw_projection || channel >= 10240 || token % 32 < 3 ||
                      token % 32 >= 29 || token + 3 >= tokens;
    required += live;
    expected_unused += !live;
    nonfinite += live && (!std::isfinite(x) || !std::isfinite(y));
    std::uint32_t xa, xb;
    std::memcpy(&xa, a.data() + i, 4);
    std::memcpy(&xb, b.data() + i, 4);
    unwritten += live && (xa == 0xFFFFFFFFU || xb == 0xFFFFFFFFU);
    unexpected_unused += !live && (xa != 0xFFFFFFFFU || xb != 0xFFFFFFFFU);
    changed += xa != xb;
  }
  std::cout << "{\"event\":\"ssm_resident_replay\",\"shape\":\"" << shape
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
  const bool representative =
      rotation == 0 &&
      (std::string(shape).find("-timed-") == std::string::npos ||
       std::string(shape).find("-timed-r0") != std::string::npos);
  if (representative &&
      (changed || nonfinite || unwritten || unexpected_unused)) {
    const std::string prefix = std::string("results/ssm-resident-") + shape +
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
  Require(nonfinite == 0 && unwritten == 0 && unexpected_unused == 0,
          "Unsafe or incomplete SSM output");
  return changed == 0;
}
#include "experiments/q2-ssm-resident-oracle.inc"

static bool Case(const char* label, unsigned n, unsigned m, unsigned k,
                 bool ssm, bool bench, hipStream_t stream) {
  Inputs in(n, m, k, ssm, stream);
  State reference(n, m), candidate(n, m);
  bool pass = true;
  for (unsigned index = 0; index < 3; ++index) {
    reference.Clear(stream);
    candidate.Clear(stream);
    Launch(false, in, reference, index, stream);
    Launch(true, in, candidate, index, stream);
    Hip(hipStreamSynchronize(stream));
    pass = Pair(reference.out, candidate.out, stream, label, index,
                "projection", n, m, ssm) &&
           pass;
    if (ssm)
      pass = Pair(reference.convolved, candidate.convolved, stream, label,
                  index, "convolution", n, 10240, false) &&
             pass;
    pass = Oracle(in, reference, index, stream, label, "reference") && pass;
    pass = Oracle(in, candidate, index, stream, label, "candidate") && pass;
  }
  if (bench) {
    Require(in.weights.size() * 3 > 32u * 1024 * 1024,
            "Q8 weight rotation does not exceed MALL");
    // Distinct destinations keep every timed weight rotation inspectable.
    std::array<std::vector<std::unique_ptr<State>>, 2> timed;
    for (auto& arm : timed)
      for (unsigned rotation = 0; rotation < 3; ++rotation)
        arm.push_back(std::make_unique<State>(n, m));
    hipEvent_t start{}, end{};
    Hip(hipEventCreate(&start));
    Hip(hipEventCreate(&end));
    for (unsigned rep = 0; rep < 7; ++rep) {
      const std::string timed_label =
          std::string(label) + "-timed-r" + std::to_string(rep);
      for (unsigned order = 0; order < 2; ++order) {
        const bool is_candidate = ((rep + order) % 2) != 0;
        auto& states = timed[is_candidate];
        for (auto& state : states)
          state->Clear(stream);
        Hip(hipStreamSynchronize(stream));
        const auto begun = std::chrono::steady_clock::now();
        Hip(hipEventRecord(start, stream));
        for (unsigned i = 0; i < 3; ++i)
          Launch(is_candidate, in, *states[i], i, stream);
        Hip(hipEventRecord(end, stream));
        Hip(hipEventSynchronize(end));
        const double wall = std::chrono::duration<double, std::micro>(
                                std::chrono::steady_clock::now() - begun)
                                .count() /
                            3;
        float ms{};
        Hip(hipEventElapsedTime(&ms, start, end));
        const bool valid = std::isfinite(ms) && ms > 0;
        std::cout << "{\"event\":\"ssm_resident_timing\",\"shape\":\"" << label
                  << "\",\"rep\":" << rep << ",\"order\":" << order
                  << ",\"candidate\":" << is_candidate
                  << ",\"warmup\":" << (rep < 2) << ",\"tokens\":" << n
                  << ",\"output_rows\":" << m << ",\"inner\":" << k
                  << ",\"iterations\":3,\"weight_bytes\":"
                  << in.weights.size() * 3 << ",\"gpu_event_valid\":" << valid
                  << ",\"gpu_event_us\":";
        if (std::isfinite(ms))
          std::cout << double(ms) * 1000 / 3;
        else
          std::cout << "null";
        std::cout << ",\"completed_wall_us\":" << wall << "}\n";
        for (unsigned rotation = 0; rotation < 3; ++rotation) {
          // Read all required values and guards before this state is reused.
          const auto check = [&](const Device& device, unsigned rows,
                                 bool raw) {
            const auto bytes = Read(device, stream);
            for (std::size_t i = 0; i < bytes.size() / 4; ++i) {
              const std::size_t token = i / rows, channel = i % rows;
              const bool live = !raw || channel >= 10240 || token % 32 < 3 ||
                                token % 32 >= 29 || token + 3 >= n;
              float value;
              std::uint32_t bits;
              std::memcpy(&value, bytes.data() + i * 4, 4);
              std::memcpy(&bits, bytes.data() + i * 4, 4);
              Require(live ? std::isfinite(value) && bits != 0xffffffffu
                           : bits == 0xffffffffu,
                      "Actual timed SSM destination is unsafe or incomplete");
            }
          };
          check(states[rotation]->out, m, true);
          check(states[rotation]->convolved, 10240, false);
          pass = Oracle(in, *states[rotation], rotation, stream,
                        timed_label.c_str(),
                        is_candidate ? "candidate" : "reference") &&
                 pass;
        }
      }
      // Compare these actual destinations, before either arm can overwrite
      // them.
      for (unsigned rotation = 0; rotation < 3; ++rotation) {
        pass = Pair(timed[0][rotation]->out, timed[1][rotation]->out, stream,
                    timed_label.c_str(), rotation, "projection", n, m, true) &&
               pass;
        pass = Pair(timed[0][rotation]->convolved,
                    timed[1][rotation]->convolved, stream, timed_label.c_str(),
                    rotation, "convolution", n, 10240, false) &&
               pass;
      }
    }
    Hip(hipEventDestroy(end));
    Hip(hipEventDestroy(start));
  }
  in.Unchanged(stream);
  std::cout << "{\"event\":\"ssm_resident_case\",\"shape\":\"" << label
            << "\",\"guards_finite_written\":true,\"inputs_unchanged\":true}\n";
  return pass;
}
// Resource API values are theoretical launch limits, not measured active waves.
static void Resources() {
  int device = 0;
  Hip(hipGetDevice(&device));
  hipDeviceProp_t properties{};
  Hip(hipGetDeviceProperties(&properties, device));
  for (unsigned candidate = 0; candidate < 2; ++candidate) {
    const void* kernel =
        candidate
            ? reinterpret_cast<const void*>(
                  q::DenseSsmResidentFenceKernel<128, 128, 2, 4, 2, 1, false,
                                                 true>)
            : reinterpret_cast<const void*>(
                  q::DenseF16GEMMKernel<256, 128, 2, 8, 1, 1, false, true>);
    hipFuncAttributes attributes{};
    int blocks = 0;
    Hip(hipFuncGetAttributes(&attributes, kernel));
    Hip(hipOccupancyMaxActiveBlocksPerMultiprocessor(&blocks, kernel, 256, 0));
    std::cout << "{\"event\":\"ssm_resident_resources\",\"candidate\":"
              << bool(candidate)
              << ",\"shared_bytes\":" << attributes.sharedSizeBytes
              << ",\"local_bytes\":" << attributes.localSizeBytes
              << ",\"registers\":" << attributes.numRegs
              << ",\"max_blocks_per_multiprocessor\":" << blocks
              << ",\"device_shared_bytes_per_multiprocessor\":"
              << properties.sharedMemPerMultiprocessor
              << ",\"measured_active_blocks\":false}\n";
  }
}
int main() {
  try {
    std::cout << std::boolalpha << std::defaultfloat << std::setprecision(12);
    Resources();
    hipStream_t stream{};
    Hip(hipStreamCreateWithFlags(&stream, hipStreamNonBlocking));
    bool pass = Case("ssm1024", 1024, 16384, 2560, true, false, stream);
    pass = Case("ssm1025", 1025, 16384, 2560, true, false, stream) && pass;
    pass = Case("ssm1057", 1057, 16384, 2560, true, false, stream) && pass;
    pass = Case("ssm2048", 2048, 16384, 2560, true, true, stream) && pass;
    pass = Case("ssm2049", 2049, 16384, 2560, true, false, stream) && pass;
    Hip(hipStreamSynchronize(stream));
    Hip(hipStreamDestroy(stream));
    std::cout << "{\"event\":\"ssm_resident_complete\",\"numerical_pass\":"
              << pass
              << ",\"timing_retained\":true,\"safe_completion\":true,\"model_"
                 "inference\":false}\n";
    return pass ? 0 : 1;
  } catch (const std::exception& ex) {
    std::cerr << "FAIL: " << ex.what() << '\n';
    return 2;
  }
}
