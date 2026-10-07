// SPDX-License-Identifier: MIT
// Synthetic equal-effective-weight Q8_0/Q5_0 dense decode comparison.
#include "qfn_mmq_prelude.h"
namespace qfn_mmq {
#include "mmvq.hpp"
#include "unary.hpp"
#include "vecdotq.hpp"
#include "experiments/q2-decode-q8-control.inc"
#include "experiments/q2-decode-q5-dense.inc"
}
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
#include "src/core/crypto/sha256.hpp"
#include "q2_decode_q8_oracle_rows.hpp"

namespace q = qfn_mmq;
static void Require(bool ok, const char* message) {
  if (!ok) throw std::runtime_error(message);
}
static void Hip(hipError_t error) {
  if (error != hipSuccess) throw std::runtime_error(hipGetErrorString(error));
}
struct Device {
  void* storage{};
  void* data{};
  size_t bytes;
  explicit Device(size_t n) : bytes(n) {
    Hip(hipMalloc(&storage, n + 128));
    data = static_cast<uint8_t*>(storage) + 64;
    Hip(hipMemset(storage, 0xa7, 64));
    Hip(hipMemset(static_cast<uint8_t*>(data) + n, 0xa7, 64));
  }
  ~Device() { if (storage) { const auto ignored = hipFree(storage); (void)ignored; } }
  Device(const Device&) = delete;
  Device& operator=(const Device&) = delete;
  void Clear() { Hip(hipMemset(data, 0xff, bytes)); }
  std::vector<uint8_t> Read() const {
    std::array<uint8_t, 128> guards{};
    Hip(hipMemcpy(guards.data(), storage, 64, hipMemcpyDeviceToHost));
    Hip(hipMemcpy(guards.data() + 64, static_cast<const uint8_t*>(data) + bytes,
                  64, hipMemcpyDeviceToHost));
    Require(std::all_of(guards.begin(), guards.end(),
                        [](auto x) { return x == 0xa7; }), "Device guard changed");
    std::vector<uint8_t> out(bytes);
    Hip(hipMemcpy(out.data(), data, bytes, hipMemcpyDeviceToHost));
    return out;
  }
};
static std::string Hash(const Device& d) { return gufo::crypto::Sha256Hex(d.Read()); }

struct Inputs {
  unsigned m, k, banks, iterations;
  bool gated;
  std::vector<q::block_q8_1> x;
  std::array<std::vector<std::vector<q::block_q8_0>>, 2> q8;
  std::array<std::vector<std::vector<q::block_q5_0>>, 2> q5;
  std::array<std::vector<std::unique_ptr<Device>>, 2> q8_device, q5_device;
  std::array<std::vector<std::string>, 2> q8_hash, q5_hash;
  Device x_device;
  std::string x_hash;
  Inputs(unsigned rows, unsigned cols, bool gate, bool tiny, bool timed)
      : m(rows), k(cols), gated(gate), x(k / 32),
        x_device(x.size() * sizeof(x[0])) {
    const size_t blocks = size_t(m) * (k / 32);
    const size_t one_q5 = blocks * sizeof(q::block_q5_0);
    banks = timed ? std::max<size_t>(2, (48 * 1024 * 1024 + one_q5 - 1) / one_q5) : 2;
    Require(banks <= 64, "Unexpected bank budget");
    iterations = timed ? banks * std::max(1u, (64u + banks - 1) / banks) : banks;
    uint32_t rng = 713;
    const auto next = [&]() { rng = rng * 1664525u + 1013904223u; return rng; };
    for (auto& block : x) {
      int sum = 0;
      for (auto& v : block.qs) { v = static_cast<int8_t>(int(next() >> 24) - 128); sum += v; }
      const float scale = tiny ? 0.0000158f : 0.00373f;
      block.ds = __floats2half2_rn(scale, scale * sum);
    }
    Hip(hipMemcpy(x_device.data, x.data(), x_device.bytes, hipMemcpyHostToDevice));
    x_hash = Hash(x_device);
    for (unsigned bank = 0; bank < banks; ++bank) {
      for (unsigned family = 0; family < (gated ? 2u : 1u); ++family) {
        q8[family].emplace_back(blocks);
        q5[family].emplace_back(blocks);
        for (size_t b = 0; b < blocks; ++b) {
          auto& wide = q8[family].back()[b];
          auto& narrow = q5[family].back()[b];
          const auto scale = __float2half_rn(0.000513f * float(1 + next() % 3));
          wide.d = narrow.d = scale;
          std::memset(narrow.qh, 0, sizeof(narrow.qh));
          std::memset(narrow.qs, 0, sizeof(narrow.qs));
          for (unsigned j = 0; j < 32; ++j) {
            const unsigned code = next() >> 27;
            wide.qs[j] = static_cast<int8_t>(int(code) - 16);
            narrow.qh[j / 8] |= uint8_t(((code >> 4) & 1) << (j % 8));
            narrow.qs[j % 16] |= uint8_t((code & 15) << (j < 16 ? 0 : 4));
          }
        }
        const size_t wide_bytes = blocks * sizeof(q::block_q8_0);
        q8_device[family].emplace_back(std::make_unique<Device>(wide_bytes));
        Hip(hipMemcpy(q8_device[family].back()->data, q8[family].back().data(),
                      wide_bytes, hipMemcpyHostToDevice));
        q8_hash[family].push_back(Hash(*q8_device[family].back()));
        q5_device[family].emplace_back(std::make_unique<Device>(one_q5));
        Hip(hipMemcpy(q5_device[family].back()->data, q5[family].back().data(),
                      one_q5, hipMemcpyHostToDevice));
        q5_hash[family].push_back(Hash(*q5_device[family].back()));
      }
    }
  }
  void Unchanged() const {
    Require(Hash(x_device) == x_hash, "Input changed");
    for (unsigned family = 0; family < (gated ? 2u : 1u); ++family)
      for (unsigned bank = 0; bank < banks; ++bank) {
        Require(Hash(*q8_device[family][bank]) == q8_hash[family][bank], "Q8 weights changed");
        Require(Hash(*q5_device[family][bank]) == q5_hash[family][bank], "Q5 weights changed");
      }
  }
};
static void Launch(unsigned arm, const Inputs& in, Device& out,
                   unsigned bank, hipStream_t stream) {
  const auto* x = static_cast<const q::block_q8_1*>(in.x_device.data);
  auto* y = static_cast<float*>(out.data);
  if (arm == 0) {
    const void* w = in.q8_device[0][bank]->data;
    const void* g = in.gated ? in.q8_device[1][bank]->data : nullptr;
    if (in.gated) q::mul_mat_vec_q8<1, true><<<in.m, 32, 0, stream>>>(w, g, x, y, in.k, in.m, in.k / 32);
    else q::mul_mat_vec_q8<1, false><<<in.m, 32, 0, stream>>>(w, nullptr, x, y, in.k, in.m, in.k / 32);
  } else {
    const void* w = in.q5_device[0][bank]->data;
    const void* g = in.gated ? in.q5_device[1][bank]->data : nullptr;
    if (in.gated) q::mul_mat_vec_q5_dense<true><<<in.m, 32, 0, stream>>>(w, g, x, y, in.k, in.m);
    else q::mul_mat_vec_q5_dense<false><<<in.m, 32, 0, stream>>>(w, nullptr, x, y, in.k, in.m);
  }
  Hip(hipGetLastError());
}
static double Oracle(const Inputs& in, const std::vector<uint8_t>& bytes,
                     unsigned bank, unsigned arm) {
  for (size_t i = 0; i < bytes.size(); i += 4) {
    float value; std::memcpy(&value, bytes.data() + i, 4);
    Require(std::isfinite(value), "Nonfinite or unwritten output");
  }
  double error = 0, norm = 0, max_error = 0, peak = 0;
  for (unsigned sample = 0; sample < 64; ++sample) {
    const unsigned row = Q8OracleRow(in.m, sample, bank);
    double dot = 0, gate = 0;
    for (unsigned b = 0; b < in.k / 32; ++b) {
      const auto& x = in.x[b];
      for (unsigned family = 0; family < (in.gated ? 2u : 1u); ++family) {
        const size_t offset = size_t(row) * (in.k / 32) + b;
        const auto& wide = in.q8[family][bank][offset];
        const auto& narrow = in.q5[family][bank][offset];
        int sum = 0;
        for (unsigned j = 0; j < 32; ++j) {
          const unsigned packed = narrow.qs[j % 16] >> (j < 16 ? 0 : 4);
          const int code = int(packed & 15) + 16 * int((narrow.qh[j / 8] >> (j % 8)) & 1);
          const int weight = arm ? code - 16 : int(wide.qs[j]);
          sum += weight * int(x.qs[j]);
        }
        const double scale = __half2float(arm ? narrow.d : wide.d);
        const double value = double(sum) * scale * double(__low2float(x.ds));
        if (family == 0) dot += value; else gate += value;
      }
    }
    const double expected = in.gated ? dot * gate / (1 + std::exp(-gate)) : dot;
    float actual; std::memcpy(&actual, bytes.data() + 4 * row, 4);
    const double delta = actual - expected;
    error += delta * delta; norm += expected * expected;
    max_error = std::max(max_error, std::abs(delta));
    peak = std::max(peak, std::abs(expected));
  }
  const double rms = std::sqrt(error / std::max(norm, 1e-300));
  const double scaled = max_error / std::max(peak, 1e-300);
  Require(rms <= 2e-5 && scaled <= 2e-5, "FP64 oracle mismatch");
  return rms;
}
static bool Case(const char* name, unsigned m, unsigned k, bool gated,
                 bool tiny, bool timed, hipStream_t stream) {
  Inputs in(m, k, gated, tiny, timed);
  std::array<std::vector<std::unique_ptr<Device>>, 2> outputs;
  for (auto& arm : outputs)
    for (unsigned i = 0; i < in.iterations; ++i)
      arm.emplace_back(std::make_unique<Device>(size_t(m) * sizeof(float)));
  hipEvent_t begin{}, end{}; Hip(hipEventCreate(&begin)); Hip(hipEventCreate(&end));
  bool pass = true;
  for (unsigned rep = 0; rep < (timed ? 7u : 1u); ++rep) {
    std::array<std::vector<std::vector<uint8_t>>, 2> all;
    for (unsigned order = 0; order < 2; ++order) {
      const unsigned arm = (rep + order) % 2;
      for (auto& out : outputs[arm]) out->Clear();
      Hip(hipStreamSynchronize(stream));
      const auto start = std::chrono::steady_clock::now();
      Hip(hipEventRecord(begin, stream));
      for (unsigned i = 0; i < in.iterations; ++i)
        Launch(arm, in, *outputs[arm][i], i % in.banks, stream);
      Hip(hipEventRecord(end, stream)); Hip(hipEventSynchronize(end));
      const auto stop = std::chrono::steady_clock::now(); Hip(hipGetLastError());
      float ms = 0; Hip(hipEventElapsedTime(&ms, begin, end));
      if (timed) {
        const size_t bytes = in.banks * in.q8_device[0][0]->bytes;
        std::cout << "{\"event\":\"q5_dense_timing\",\"case\":\"" << name
                  << "\",\"rep\":" << rep << ",\"order\":" << order
                  << ",\"arm\":" << arm << ",\"warmup\":" << (rep < 2)
                  << ",\"iterations\":" << in.iterations
                  << ",\"rotated_weight_bytes_q8\":" << bytes * (1 + gated)
                  << ",\"rotated_weight_bytes_q5\":"
                  << in.banks * in.q5_device[0][0]->bytes * (1 + gated)
                  << ",\"gpu_event_valid\":" << (std::isfinite(ms) && ms > 0)
                  << ",\"gpu_event_us\":";
        if (std::isfinite(ms)) std::cout << double(ms) * 1000 / in.iterations;
        else std::cout << "null";
        std::cout << ",\"completed_wall_us\":"
                  << std::chrono::duration<double, std::micro>(stop - start).count() / in.iterations << "}\n";
      }
      for (unsigned i = 0; i < in.iterations; ++i) {
        all[arm].push_back(outputs[arm][i]->Read());
        const double rms = Oracle(in, all[arm].back(), i % in.banks, arm);
        if (i == 0)
          std::cout << "{\"event\":\"q5_dense_oracle\",\"case\":\"" << name
                    << "\",\"rep\":" << rep << ",\"arm\":" << arm
                    << ",\"relative_rms\":" << rms << ",\"pass\":true}\n";
      }
    }
    for (unsigned i = 0; i < in.iterations; ++i) {
      double error = 0, norm = 0;
      for (size_t j = 0; j < all[0][i].size(); j += 4) {
        float wide, narrow;
        std::memcpy(&wide, all[0][i].data() + j, 4);
        std::memcpy(&narrow, all[1][i].data() + j, 4);
        error += double(wide - narrow) * double(wide - narrow);
        norm += double(wide) * double(wide);
      }
      const double rms = std::sqrt(error / std::max(norm, 1e-300));
      pass = (rms <= 2e-5) && pass;
      if (i == 0)
        std::cout << "{\"event\":\"q5_dense_pair\",\"case\":\"" << name
                  << "\",\"rep\":" << rep << ",\"relative_rms\":" << rms
                  << ",\"pass\":" << (rms <= 2e-5) << "}\n";
    }
  }
  in.Unchanged(); Hip(hipEventDestroy(end)); Hip(hipEventDestroy(begin));
  std::cout << "{\"event\":\"q5_dense_case\",\"case\":\"" << name
            << "\",\"rows\":" << m << ",\"cols\":" << k
            << ",\"banks\":" << in.banks << ",\"pass\":" << pass << "}\n";
  return pass;
}
int main() {
  try {
    std::cout << std::boolalpha << std::defaultfloat << std::setprecision(12);
    hipStream_t stream{}; Hip(hipStreamCreateWithFlags(&stream, hipStreamNonBlocking));
    bool pass = Case("tiny-plain", 31, 256, false, true, false, stream);
    pass = Case("tiny-gated", 35, 288, true, true, false, stream) && pass;
    pass = Case("ssm-in", 16384, 2560, false, false, true, stream) && pass;
    pass = Case("attn-out", 2560, 6144, false, false, true, stream) && pass;
    pass = Case("shared-down", 2560, 640, false, false, true, stream) && pass;
    pass = Case("gated", 640, 2560, true, false, true, stream) && pass;
    Hip(hipStreamSynchronize(stream)); Hip(hipStreamDestroy(stream));
    std::cout << "{\"event\":\"q5_dense_complete\",\"numerical_pass\":" << pass
              << ",\"model_inference\":false}\n";
    return pass ? 0 : 1;
  } catch (const std::exception& e) { std::cerr << "FAIL: " << e.what() << '\n'; return 2; }
}
