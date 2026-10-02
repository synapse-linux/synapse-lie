// SPDX-License-Identifier: MIT
// Independent scalar formulas over small synthetic encoded tensors, not CPU
// model forward.
#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/mmq/qfn_mmq.h"
#include <algorithm>
#include <bit>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <hip/hip_fp16.h>
#include <hip/hip_runtime.h>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

static constexpr std::uint64_t grid[256] = {
#include "iq2-grid.inc"
};

void Check(bool value, const char *why) {
  if (!value)
    throw std::runtime_error(why);
}
void Hip(hipError_t status) {
  Check(status == hipSuccess, hipGetErrorString(status));
}
struct Device {
  void *data{};
  explicit Device(std::size_t bytes) { Hip(hipMalloc(&data, bytes)); }
  ~Device() {
    if (data)
      (void)hipFree(data);
  }
  Device(const Device &) = delete;
  Device &operator=(const Device &) = delete;
};

struct Weights {
  std::vector<unsigned char> bytes;
  std::vector<float> values;
};
Weights Make(int type, int experts, int rows, int k, int seed) {
  const int stride = type == 16 ? 66 : 84;
  Weights w{std::vector<unsigned char>(std::size_t(experts) * rows * (k / 256) *
                                       stride),
            std::vector<float>(std::size_t(experts) * rows * k)};
  for (int row = 0; row < experts * rows; ++row) {
    for (int block = 0; block < k / 256; ++block) {
      auto *dst =
          w.bytes.data() + (std::size_t(row) * (k / 256) + block) * stride;
      auto *val = w.values.data() + std::size_t(row) * k + block * 256;
      const __half dh = __float2half(0.00319f * (1 + (row + seed) % 3));
      const float d = __half2float(dh);
      if (type == 16) {
        std::memcpy(dst, &dh, 2);
        for (int group = 0; group < 8; ++group) {
          const unsigned scale = (group + block + row + seed) % 16;
          std::uint32_t signs = scale << 28;
          for (int sub = 0; sub < 4; ++sub) {
            const unsigned code =
                (row * 13 + block * 17 + group * 19 + sub * 23 + seed) % 256;
            const unsigned sign7 = (row + block * 13 + sub * 17 + seed) % 128;
            const unsigned sign8 = sign7 | ((std::popcount(sign7) & 1) << 7);
            dst[2 + group * 8 + sub] = static_cast<unsigned char>(code);
            signs |= sign7 << (7 * sub);
            for (int lane = 0; lane < 8; ++lane) {
              const float magnitude = float((grid[code] >> (8 * lane)) & 255);
              val[group * 32 + sub * 8 + lane] =
                  d * (2 * scale + 1) * 0.125f * magnitude *
                  ((sign8 & (1u << lane)) ? -1.f : 1.f);
            }
          }
          std::memcpy(dst + 2 + group * 8 + 4, &signs, 4);
        }
      } else {
        const __half mh = __float2half(0.00271f * (1 + (row + seed) % 2));
        const float minimum = __half2float(mh);
        std::memcpy(dst + 80, &dh, 2);
        std::memcpy(dst + 82, &mh, 2);
        for (int group = 0; group < 16; ++group)
          dst[group] = static_cast<unsigned char>(((group + seed) % 16) << 4 |
                                                  ((row + group + 3) % 16));
        for (int i = 0; i < 256; ++i) {
          const unsigned q = (i * 7 + row + block + seed) % 4;
          dst[16 + (i / 128) * 32 + i % 32] |= q << (2 * ((i % 128) / 32));
          const unsigned sc = dst[i / 16];
          val[i] = d * (sc & 15) * q - minimum * (sc >> 4);
        }
      }
    }
  }
  return w;
}

void Compare(const std::vector<float> &got, const std::vector<double> &expected,
             const std::string &label) {
  double err = 0, ref = 0, maximum = 0, peak = 0;
  for (std::size_t i = 0; i < got.size(); ++i) {
    Check(std::isfinite(got[i]), "non-finite operator output");
    const double delta = double(got[i]) - expected[i];
    err += delta * delta;
    ref += expected[i] * expected[i];
    maximum = std::max(maximum, std::abs(delta));
    peak = std::max(peak, std::abs(expected[i]));
  }
  const double rrms = std::sqrt(err / std::max(ref, 1e-30));
  const double scaled_max = maximum / std::max(peak, 1e-20);
  std::cout << label << " rrms=" << rrms << " scaled_max=" << scaled_max
            << '\n';
  Check(rrms <= 0.002 && scaled_max <= 0.002,
        "independent operator tolerance exceeded");
}

void Case(int type, int tokens, bool tiled, bool tiny) {
  const int rows = 5, experts = 512, used = 2;
  const int k = type == 16 ? 2560 : 768;
  const int logical = type == 16 ? 2560 : 640;
  const int slots = tokens * used;
  auto w = Make(type, experts, rows, k, 3),
       up = Make(type, experts, rows, k, 11);
  std::vector<float> x(std::size_t(tokens) * logical);
  const float scale = tiny ? std::ldexp(1.f, -14) : std::ldexp(1.f, -8);
  for (std::size_t i = 0; i < x.size(); ++i)
    x[i] = float(i % 32 == 0 ? 127 : int((i * 17 + 31) % 251) - 125) * scale;
  std::vector<std::int32_t> ids(slots);
  for (int t = 0; t < tokens; ++t) {
    ids[t * used] = 0;
    ids[t * used + 1] = 511;
  }
  Device wd(w.bytes.size() + 4096), ud(up.bytes.size() + 4096);
  Device xd(x.size() * sizeof(float)), id(ids.size() * sizeof(std::int32_t));
  Device yd(std::size_t(slots) * rows * sizeof(float)),
      zd(std::size_t(slots) * rows * sizeof(float));
  Hip(hipMemset(wd.data, 0, w.bytes.size() + 4096));
  Hip(hipMemset(ud.data, 0, up.bytes.size() + 4096));
  Hip(hipMemcpy(wd.data, w.bytes.data(), w.bytes.size(),
                hipMemcpyHostToDevice));
  Hip(hipMemcpy(ud.data, up.bytes.data(), up.bytes.size(),
                hipMemcpyHostToDevice));
  Hip(hipMemcpy(xd.data, x.data(), x.size() * sizeof(float),
                hipMemcpyHostToDevice));
  Hip(hipMemcpy(id.data, ids.data(), ids.size() * sizeof(std::int32_t),
                hipMemcpyHostToDevice));
  const auto *xp = static_cast<float *>(xd.data);
  const auto *ip = static_cast<std::int32_t *>(id.data);
  auto *y = static_cast<float *>(yd.data);
  auto *z = static_cast<float *>(zd.data);
  int rc;
  const bool gated = type == 16 && !tiled && tokens <= 8;
  if (gated)
    rc = qfn_mmq_moe_gated_vec(type, wd.data, ud.data, xp, ip, y, rows, k,
                               tokens, experts, used, nullptr);
  else if (!tiled)
    rc = qfn_mmq_moe_vec(type, wd.data, xp, ip, y, rows, k, tokens, experts,
                         used, nullptr, nullptr, nullptr, logical);
  else if (type == 16)
    rc = qfn_mmq_iq2_xxs_moe_raw(wd.data, xp, ip, y, rows, k, tokens, experts,
                                 used, nullptr, ud.data, z);
  else
    rc = qfn_mmq_q2_K_moe_raw(wd.data, xp, ip, y, rows, k, tokens, experts,
                              used, nullptr, logical);
  Check(rc == 0, "routed launch failed");
  Hip(hipDeviceSynchronize());
  std::vector<float> got(std::size_t(slots) * rows), other(got.size());
  Hip(hipMemcpy(got.data(), yd.data, got.size() * sizeof(float),
                hipMemcpyDeviceToHost));
  if (type == 16 && tiled)
    Hip(hipMemcpy(other.data(), zd.data, other.size() * sizeof(float),
                  hipMemcpyDeviceToHost));
  std::vector<double> ref(got.size()), ref_up(got.size());
  for (int t = 0; t < tokens; ++t)
    for (int u = 0; u < used; ++u)
      for (int row = 0; row < rows; ++row) {
        double a = 0, b = 0;
        for (int j = 0; j < logical; ++j) {
          const auto wi = (std::size_t(ids[t * used + u]) * rows + row) * k + j;
          a += double(x[std::size_t(t) * logical + j]) * w.values[wi];
          b += double(x[std::size_t(t) * logical + j]) * up.values[wi];
        }
        const auto i = (std::size_t(t) * used + u) * rows + row;
        ref[i] = gated ? a / (1 + std::exp(-a)) * b : a;
        ref_up[i] = b;
      }
  const auto name = std::to_string(type) + "/" + std::to_string(tokens) +
                    (tiled ? "/PP" : "/TG") + (tiny ? "/small" : "/normal");
  Compare(got, ref, name);
  if (type == 16 && tiled)
    Compare(other, ref_up, name + "/paired-up");
}

int main() {
  try {
    Check(qfn_mmq_init(0) == 0, "HIP init failed");
    for (int type : {16, 10})
      for (int tokens : {1, 3, 8, 9, 33})
        for (bool tiny : {false, true})
          Case(type, tokens, tokens > 8, tiny);
    // Every finite half value, including subnormals and signed zero, widens
    // exactly.
    std::vector<std::uint16_t> bits(65536);
    for (unsigned i = 0; i < bits.size(); ++i)
      bits[i] = i;
    Device h(bits.size() * 2), f(bits.size() * 4);
    Hip(hipMemcpy(h.data, bits.data(), bits.size() * 2, hipMemcpyHostToDevice));
    gufo::models::qwen38_flash_next::rocm::WidenHalf(
        static_cast<const __half *>(h.data), static_cast<float *>(f.data),
        bits.size(), nullptr);
    Hip(hipDeviceSynchronize());
    std::vector<float> got(bits.size());
    Hip(hipMemcpy(got.data(), f.data, bits.size() * 4, hipMemcpyDeviceToHost));
    for (unsigned i = 0; i < bits.size(); ++i) {
      __half x;
      std::memcpy(&x, &bits[i], 2);
      if ((i & 0x7c00) != 0x7c00)
        Check(std::bit_cast<std::uint32_t>(got[i]) ==
                  std::bit_cast<std::uint32_t>(__half2float(x)),
              "HC widening changed a finite half");
    }
    std::cout
        << "PASS Q2 independent synthetic operators; no model inference\n";
  } catch (const std::exception &ex) {
    std::cerr << ex.what() << '\n';
    return 1;
  }
}
