// SPDX-License-Identifier: MIT
// Full-score comparison for a four-query key-residency experiment.
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
#include "experiments/q2-select-score-group4.inc"

namespace q = gufo::models::qwen38_flash_next::rocm;
static void Require(bool ok, const char* why) {
  if (!ok) throw std::runtime_error(why);
}
static void Hip(hipError_t rc) {
  if (rc != hipSuccess) throw std::runtime_error(hipGetErrorString(rc));
}
struct Device {
  void* base{};
  void* data{};
  std::size_t bytes;
  explicit Device(std::size_t n) : bytes(n) {
    Hip(hipMalloc(&base, n + 128));
    data = static_cast<std::uint8_t*>(base) + 64;
    Hip(hipMemset(base, 0xa7, 64));
    Hip(hipMemset(static_cast<std::uint8_t*>(data) + n, 0xa7, 64));
  }
  ~Device() { if (base) (void)hipFree(base); }
  Device(const Device&) = delete;
  Device& operator=(const Device&) = delete;
  std::vector<std::uint8_t> Read() const {
    std::array<std::uint8_t, 128> guards{};
    Hip(hipMemcpy(guards.data(), base, 64, hipMemcpyDeviceToHost));
    Hip(hipMemcpy(guards.data() + 64,
                  static_cast<const std::uint8_t*>(data) + bytes, 64,
                  hipMemcpyDeviceToHost));
    Require(std::all_of(guards.begin(), guards.end(),
                        [](auto x) { return x == 0xa7; }), "Device guard changed");
    std::vector<std::uint8_t> result(bytes);
    Hip(hipMemcpy(result.data(), data, bytes, hipMemcpyDeviceToHost));
    return result;
  }
};
constexpr unsigned kHeads = 4, kDim = 128, kRatio = 4;
constexpr unsigned kBudget = 512, kPitch = 33440, kMaskWords = 1045;
static float Float(const std::vector<std::uint8_t>& data, std::size_t i) {
  float value;
  std::memcpy(&value, data.data() + i * sizeof(float), sizeof(float));
  return value;
}
static void Launch(bool grouped, const Device& query, const Device& keys,
                   const Device& position, Device& scores,
                   unsigned rows, hipStream_t stream) {
  const dim3 grid((rows + (grouped ? 3 : 0)) / (grouped ? 4 : 1),
                  (kPitch + 255) / 256);
  if (grouped) {
    hipLaunchKernelGGL(q::Q2SelectScoreGroup4Kernel, grid, dim3(256), 0, stream,
        static_cast<const float*>(query.data),
        static_cast<const __half*>(keys.data),
        static_cast<float*>(scores.data), rows,
        static_cast<const unsigned*>(position.data), 0u, kRatio,
        kBudget, kPitch);
  } else {
    hipLaunchKernelGGL(q::SelectScoreKernel, grid, dim3(256), 0, stream,
        static_cast<const float*>(query.data),
        static_cast<const __half*>(keys.data),
        static_cast<float*>(scores.data), rows,
        static_cast<const unsigned*>(position.data), 0u, kRatio,
        kBudget, kPitch);
  }
  Hip(hipGetLastError());
}
static bool Oracle(const std::vector<float>& queries,
                   const std::vector<__half>& keys,
                   const std::vector<std::uint8_t>& output,
                   unsigned rows, unsigned start, const char* name) {
  double worst = 0;
  unsigned samples = 0;
  for (unsigned row : {0u, rows / 2, rows - 1}) {
    const unsigned complete = (start + row + 1) / kRatio;
    if (complete <= kBudget) continue;
    for (unsigned key : {0u, kBudget - 1, complete / 2, complete - 1}) {
      double total = 0;
      for (unsigned head = 0; head < kHeads; ++head) {
        double dot = 0;
        for (unsigned dim = 0; dim < kDim; ++dim)
          dot += double(queries[(std::size_t(row) * kHeads + head) * kDim + dim]) *
                 double(__half2float(keys[std::size_t(key) * kDim + dim]));
        total += std::max(dot, 0.0);
      }
      worst = std::max(worst, std::abs(double(Float(output,
                                             std::size_t(row) * kPitch + key)) - total));
      ++samples;
    }
  }
  const bool pass = samples && worst <= 0.001;
  std::cout << "{\"event\":\"score_oracle\",\"case\":\"" << name
            << "\",\"samples\":" << samples << ",\"max_absolute_error\":"
            << worst << ",\"pass\":" << pass << "}\n";
  return pass;
}
static bool Case(const char* name, unsigned rows, unsigned start,
                 bool timed, hipStream_t stream) {
  Require(rows && start + rows <= 133760, "Case exceeds capacity");
  std::vector<float> queries(std::size_t(rows) * kHeads * kDim);
  std::vector<__half> keys(std::size_t(kPitch) * kDim);
  unsigned rng = 0x517b4d31;
  auto random = [&] {
    rng = rng * 1664525u + 1013904223u;
    return float(int(rng >> 16) - 32768) / 32768.f;
  };
  for (auto& value : queries) value = random() * 0.4f;
  for (auto& value : keys) value = __float2half_rn(random() * 0.5f);
  Device qd(queries.size() * sizeof(float)), kd(keys.size() * sizeof(__half));
  Device pd(sizeof(unsigned)), a(std::size_t(rows) * kPitch * sizeof(float));
  Device b(a.bytes), am(std::size_t(rows) * kMaskWords * sizeof(unsigned));
  Device bm(am.bytes);
  Hip(hipMemcpy(qd.data, queries.data(), qd.bytes, hipMemcpyHostToDevice));
  Hip(hipMemcpy(kd.data, keys.data(), kd.bytes, hipMemcpyHostToDevice));
  Hip(hipMemcpy(pd.data, &start, sizeof(start), hipMemcpyHostToDevice));
  const auto q_before = qd.Read(), k_before = kd.Read(), p_before = pd.Read();
  const std::array<Device*, 2> outputs{&a, &b};
  const std::array<Device*, 2> masks{&am, &bm};
  bool pass = true;
  hipEvent_t begin{}, end{};
  Hip(hipEventCreate(&begin)); Hip(hipEventCreate(&end));
  for (unsigned rep = 0; rep < (timed ? 7u : 1u); ++rep) {
    std::array<std::vector<std::uint8_t>, 2> values;
    std::array<std::vector<std::uint8_t>, 2> mask_values;
    for (unsigned order = 0; order < 2; ++order) {
      const unsigned arm = (rep + order) % 2;
      Device& output = *outputs[arm];
      Hip(hipMemset(output.data, 0xa5, output.bytes));
      Hip(hipDeviceSynchronize());
      const auto t0 = std::chrono::steady_clock::now();
      Hip(hipEventRecord(begin, stream));
      Launch(arm, qd, kd, pd, output, rows, stream);
      Hip(hipEventRecord(end, stream));
      Hip(hipEventSynchronize(end));
      const auto t1 = std::chrono::steady_clock::now();
      float ms = 0; Hip(hipEventElapsedTime(&ms, begin, end));
      if (timed)
        std::cout << "{\"event\":\"score_timing\",\"case\":\"" << name
                  << "\",\"rep\":" << rep << ",\"arm\":" << arm
                  << ",\"order\":" << order << ",\"warmup\":" << (rep < 2)
                  << ",\"rows\":" << rows << ",\"start\":" << start
                  << ",\"gpu_event_valid\":" << (std::isfinite(ms) && ms > 0)
                  << ",\"gpu_event_us\":" << double(ms) * 1000
                  << ",\"completed_wall_us\":"
                  << std::chrono::duration<double, std::micro>(t1 - t0).count()
                  << "}\n";
      values[arm] = output.Read();
      Device& mask = *masks[arm];
      Hip(hipMemset(mask.data, 0xa5, mask.bytes));
      hipLaunchKernelGGL(q::SelectMarkKernel, dim3(rows), dim3(256), 0,
                         stream, static_cast<unsigned*>(mask.data),
                         static_cast<const float*>(output.data),
                         static_cast<const unsigned*>(pd.data), 0u, kRatio,
                         kBudget, kMaskWords, kPitch);
      Hip(hipGetLastError());
      Hip(hipStreamSynchronize(stream));
      mask_values[arm] = mask.Read();
      for (std::size_t i = 0; i < values[arm].size() / sizeof(float); ++i) {
        const unsigned complete = (start + unsigned(i / kPitch) + 1) / kRatio;
        if (complete > kBudget && i % kPitch < complete)
          Require(std::isfinite(Float(values[arm], i)), "Nonfinite score");
      }
      if (rep == 0) pass = Oracle(queries, keys, values[arm], rows, start, name) && pass;
    }
    const bool exact = values[0] == values[1];
    const bool mask_exact = mask_values[0] == mask_values[1];
    pass = exact && mask_exact && pass;
    std::cout << "{\"event\":\"score_pair\",\"case\":\"" << name
              << "\",\"rep\":" << rep << ",\"bytes\":" << a.bytes
              << ",\"exact\":" << exact
              << ",\"mask_exact\":" << mask_exact << "}\n";
    if (!exact) {
      for (std::size_t i = 0; i < values[0].size() / 4; ++i)
        if (std::memcmp(values[0].data() + i * 4, values[1].data() + i * 4, 4)) {
          std::cerr << "First mismatch score slot " << i << "\n";
          break;
        }
    }
  }
  Require(qd.Read() == q_before && kd.Read() == k_before && pd.Read() == p_before,
          "Score input changed");
  Hip(hipEventDestroy(begin)); Hip(hipEventDestroy(end));
  return pass;
}
int main() {
  std::cout << std::boolalpha << std::setprecision(17);
  try {
    hipStream_t stream{}; Hip(hipStreamCreateWithFlags(&stream, hipStreamNonBlocking));
    bool pass = true;
    pass = Case("full32", 2048, 28672, true, stream) && pass;
    pass = Case("full128", 2048, 126976, true, stream) && pass;
    pass = Case("tail128", 1901, 129024, false, stream) && pass;
    pass = Case("budget", 8, 2044, false, stream) && pass;
    Hip(hipStreamDestroy(stream));
    std::cout << "{\"event\":\"complete\",\"pass\":" << pass
              << ",\"model_inference\":false}\n";
    return pass ? 0 : 1;
  } catch (const std::exception& e) {
    std::cerr << e.what() << '\n';
    return 2;
  }
}
