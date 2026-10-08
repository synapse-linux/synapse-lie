// SPDX-License-Identifier: MIT
// Private GPU gate for the in-memory Q8_0 -> Q5_0 decode overlay.
#include "qfn_mmq_prelude.h"
namespace qfn_mmq {
#include "common.hpp"
#include "qfn_mmq.h"
}

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <vector>

namespace q = qfn_mmq;

static void Check(bool good, const char* message) {
  if (!good) throw std::runtime_error(message);
}
static void Hip(hipError_t result) {
  if (result != hipSuccess) throw std::runtime_error(hipGetErrorString(result));
}

struct Guarded {
  void* base{};
  void* data{};
  size_t bytes{};
  explicit Guarded(size_t count) : bytes(count) {
    Hip(hipMalloc(&base, count + 128));
    data = static_cast<uint8_t*>(base) + 64;
    Hip(hipMemset(base, 0x7c, 64));
    Hip(hipMemset(static_cast<uint8_t*>(data) + count, 0x7c, 64));
  }
  ~Guarded() { if (base) (void)hipFree(base); }
  Guarded(const Guarded&) = delete;
  Guarded& operator=(const Guarded&) = delete;
  std::vector<uint8_t> Read() const {
    std::array<uint8_t, 128> guard{};
    Hip(hipMemcpy(guard.data(), base, 64, hipMemcpyDeviceToHost));
    Hip(hipMemcpy(guard.data() + 64,
                  static_cast<const uint8_t*>(data) + bytes, 64,
                  hipMemcpyDeviceToHost));
    Check(std::all_of(guard.begin(), guard.end(),
                      [](uint8_t value) { return value == 0x7c; }),
          "overlay buffer guard changed");
    std::vector<uint8_t> output(bytes);
    Hip(hipMemcpy(output.data(), data, bytes, hipMemcpyDeviceToHost));
    return output;
  }
};

int main() {
  try {
    constexpr int rows = 257;
    constexpr int cols = 2560;
    constexpr size_t blocks = size_t(rows) * cols / 32;
    std::vector<q::block_q8_0> input(blocks);
    std::vector<q::block_q8_1> activations(cols / 32);
    uint32_t state = 0x7b67b4a1u;
    const auto next = [&]() { state = state * 1664525u + 1013904223u; return state; };
    for (size_t b = 0; b < blocks; ++b) {
      float scale = 0.00037f * float(1 + b % 7);
      if (b % 113 == 0) scale = 0;
      if (b % 127 == 0) scale = -scale;
      input[b].d = __float2half_rn(scale);
      for (auto& code : input[b].qs)
        code = static_cast<int8_t>(int(next() >> 24) - 128);
    }
    for (auto& block : activations) {
      int sum = 0;
      for (auto& code : block.qs) {
        code = static_cast<int8_t>(int(next() >> 24) - 128);
        sum += code;
      }
      const float scale = 0.0037f;
      block.ds = __floats2half2_rn(scale, scale * float(sum));
    }
    Guarded wide(input.size() * sizeof(input[0]));
    Guarded narrow(blocks * sizeof(q::block_q5_0));
    Guarded x(activations.size() * sizeof(activations[0]));
    Guarded y(size_t(rows) * sizeof(float));
    Hip(hipMemcpy(wide.data, input.data(), wide.bytes, hipMemcpyHostToDevice));
    Hip(hipMemcpy(x.data, activations.data(), x.bytes, hipMemcpyHostToDevice));
    Hip(hipMemset(narrow.data, 0xff, narrow.bytes));
    Hip(hipMemset(y.data, 0xff, y.bytes));
    Check(q::qfn_mmq_q8_0_to_q5_0_overlay(wide.data, narrow.data,
                                           blocks, nullptr) == 0,
          "overlay conversion launch failed");
    Check(q::qfn_mmq_q5_0_dense_vec_preq(narrow.data, nullptr, x.data,
                                         static_cast<float*>(y.data), rows,
                                         1, cols, nullptr) == 0,
          "overlay decode launch failed");
    Hip(hipDeviceSynchronize());
    Check(std::memcmp(wide.Read().data(), input.data(), wide.bytes) == 0,
          "Q8 source changed");
    const auto encoded = narrow.Read();
    const auto decoded = y.Read();
    double weight_error = 0, weight_energy = 0;
    double output_error = 0, output_energy = 0;
    double max_scaled_error = 0, peak = 0;
    for (size_t b = 0; b < blocks; ++b) {
      q::block_q5_0 block{};
      std::memcpy(&block, encoded.data() + b * sizeof(block), sizeof(block));
      const double d8 = __half2float(input[b].d);
      const double d5 = __half2float(block.d);
      Check(std::isfinite(d5) && d5 >= 0, "invalid Q5 scale");
      for (int j = 0; j < 32; ++j) {
        const unsigned low = (block.qs[j & 15] >> (j < 16 ? 0 : 4)) & 15u;
        const unsigned high = (block.qh[j / 8] >> (j % 8)) & 1u;
        const int signed_code = int(low | (high << 4)) - 16;
        const double original = d8 * input[b].qs[j];
        const double candidate = d5 * signed_code;
        weight_error += (candidate - original) * (candidate - original);
        weight_energy += original * original;
      }
    }
    for (int row = 0; row < rows; ++row) {
      double reference = 0;
      for (int kb = 0; kb < cols / 32; ++kb) {
        const size_t b = size_t(row) * (cols / 32) + kb;
        q::block_q5_0 block{};
        std::memcpy(&block, encoded.data() + b * sizeof(block), sizeof(block));
        const auto& activation = activations[kb];
        int unsigned_dot = 0;
        for (int j = 0; j < 32; ++j) {
          const unsigned low = (block.qs[j & 15] >> (j < 16 ? 0 : 4)) & 15u;
          const unsigned high = (block.qh[j / 8] >> (j % 8)) & 1u;
          unsigned_dot += int(low | (high << 4)) * int(activation.qs[j]);
        }
        reference += double(__half2float(block.d)) *
            (double(unsigned_dot) * __low2float(activation.ds) -
             16.0 * __high2float(activation.ds));
      }
      float actual{};
      std::memcpy(&actual, decoded.data() + size_t(row) * sizeof(float),
                  sizeof(float));
      Check(std::isfinite(actual), "nonfinite or unwritten Q5 output");
      const double error = double(actual) - reference;
      output_error += error * error;
      output_energy += reference * reference;
      max_scaled_error = std::max(max_scaled_error, std::abs(error));
      peak = std::max(peak, std::abs(reference));
    }
    const double weight_rms = std::sqrt(weight_error / weight_energy);
    const double output_rms = std::sqrt(output_error / output_energy);
    const double maximum = max_scaled_error / peak;
    Check(weight_rms < 0.08 && output_rms < 2e-5 && maximum < 2e-5,
          "Q5 overlay precision gate failed");
    std::cout << std::setprecision(12)
              << "{\"event\":\"q5_overlay_conversion\",\"rows\":" << rows
              << ",\"cols\":" << cols << ",\"blocks\":" << blocks
              << ",\"weight_relative_rms\":" << weight_rms
              << ",\"decode_oracle_relative_rms\":" << output_rms
              << ",\"decode_oracle_max_scaled_error\":" << maximum
              << ",\"pass\":true}\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 2;
  }
}
