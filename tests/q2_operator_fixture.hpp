// SPDX-License-Identifier: MIT
#pragma once
// Independent scalar formulas over small synthetic encoded tensors, not CPU
// model forward.
#include <algorithm>
#include <bit>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
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
  auto filename = label;
  std::replace(filename.begin(), filename.end(), '/', '-');
  std::ofstream evidence("results/operator-" + filename + ".f32",
                         std::ios::binary);
  evidence.write(reinterpret_cast<const char *>(got.data()),
                 static_cast<std::streamsize>(got.size() * sizeof(float)));
  Check(bool(evidence), "Cannot save operator frontier");
}
