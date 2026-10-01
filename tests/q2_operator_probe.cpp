// SPDX-License-Identifier: MIT
// Tiny synthetic operator oracle, NOT a model forward or full format
// qualification. IQ2 uses grid index zero (eight magnitudes of 8), all
// sign/scale fields varied. Format facts: independently pinned Gufo MMQ
// ggml-common.h / VENDOR.md.
#include "qfn_mmq.h"
#include "src/models/qwen38_flash_next/kernels/rocm/q2_routed.h"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <vector>

using Bytes = std::vector<uint8_t>;
static void require(bool yes, const char *why) {
  if (!yes)
    throw std::runtime_error(why);
}
static void hc(hipError_t e) {
  if (e != hipSuccess)
    throw std::runtime_error(hipGetErrorString(e));
}
static unsigned u16(const uint8_t *p) { return p[0] | unsigned(p[1]) << 8; }
static uint32_t u32(const uint8_t *p) {
  return u16(p) | uint32_t(u16(p + 2)) << 16;
}
static void put16(uint8_t *p, unsigned v) {
  p[0] = v;
  p[1] = v >> 8;
}
static void put32(uint8_t *p, uint32_t v) {
  put16(p, v);
  put16(p + 2, v >> 16);
}
static double power_half(const uint8_t *p) {
  const unsigned bits = u16(p);
  require((bits & 0x83ffu) == 0 && (bits >> 10) > 0 && (bits >> 10) < 31,
          "fixture requires positive normal power-of-two half");
  return std::ldexp(1.0, int(bits >> 10) - 15);
}
static unsigned parity(unsigned x) {
  unsigned p = 0;
  for (; x; x >>= 1)
    p ^= x & 1;
  return p;
}
static double value(int type, const uint8_t *b, unsigned j) {
  if (type == LIE_IQ2_XXS) {
    const uint8_t *group = b + 2 + (j / 32) * 8;
    require(group[(j % 32) / 8] == 0,
            "IQ2 oracle covers grid-zero fixtures only");
    const uint32_t fields = u32(group + 4);
    const unsigned signs7 = (fields >> (7 * ((j % 32) / 8))) & 127;
    const unsigned signs = signs7 | parity(signs7) << 7;
    const int sign = (signs >> (j % 8)) & 1 ? -1 : 1;
    // grid=8 cancels the format's /8; independent scalar dequantization.
    return sign * power_half(b) * (2 * (fields >> 28) + 1);
  }
  const unsigned group = j / 128, within = j % 128;
  const unsigned sc = b[group * 8 + within / 16];
  const unsigned q =
      (b[16 + group * 32 + within % 32] >> (2 * (within / 32))) & 3;
  return power_half(b + 80) * (sc & 15) * q - power_half(b + 82) * (sc >> 4);
}
static Bytes weights(int type, int m, int k, int experts, unsigned salt) {
  const size_t block = type == LIE_IQ2_XXS ? 66 : 84;
  Bytes out(size_t(experts) * m * (k / 256) * block + 4096, 0);
  for (size_t i = 0; i < (out.size() - 4096) / block; ++i) {
    auto *b = out.data() + i * block;
    if (type == LIE_IQ2_XXS) {
      put16(b, (5 + (i + salt) % 3) << 10); // 2^-10 .. 2^-8
      for (unsigned g = 0; g < 8; ++g) {
        uint32_t fields = uint32_t((g + i + salt) % 16) << 28;
        for (unsigned v = 0; v < 4; ++v)
          fields |= uint32_t((i * 13 + g * 7 + v + salt) % 128) << (7 * v);
        put32(b + 2 + g * 8 + 4, fields);
      }
    } else {
      for (unsigned j = 0; j < 16; ++j)
        b[j] = uint8_t(i * 19 + j * 17 + salt);
      for (unsigned j = 0; j < 64; ++j)
        b[16 + j] = uint8_t(i * 13 + j * 29 + salt);
      put16(b + 80, 6 << 10); // 2^-9
      put16(b + 82, 5 << 10); // 2^-10
    }
  }
  return out;
}
static float source_value(int row, int col) {
  const int q = col % 32 == 0 ? 127 : ((col * 19 + row * 7) % 253 - 126);
  return row % 3 == 2 ? 0.0f : q / 128.0f;
}
static void cpu_oracle() {
  require(source_value(0, 0) != 0.0f,
          "one-row case must exercise nonzero arithmetic");
  for (int k = 0; k < 2560; ++k)
    require(source_value(2, k) == 0.0f, "zero input-row fixture");
  uint8_t b[84]{};
  put16(b, 5 << 10);
  for (unsigned j = 0; j < 256; ++j)
    require(value(LIE_IQ2_XXS, b, j) == std::ldexp(1.0, -10),
            "IQ2 unit-scale golden");
  put32(b + 6, 0xf0000001u);
  require(value(LIE_IQ2_XXS, b, 0) == -31.0 / 1024 &&
              value(LIE_IQ2_XXS, b, 7) == -31.0 / 1024 &&
              value(LIE_IQ2_XXS, b, 8) == 31.0 / 1024,
          "IQ2 sign parity golden");
  std::memset(b, 0, sizeof b);
  std::memset(b, 0x32, 16);
  std::memset(b + 16, 0xff, 64);
  put16(b + 80, 6 << 10);
  put16(b + 82, 5 << 10);
  for (unsigned j = 0; j < 256; ++j)
    require(value(LIE_Q2_K, b, j) == 9.0 / 1024, "Q2 affine golden");
  std::puts("Q2_SYNTHETIC_SCALAR_FIXTURE_GOLDENS_PASS_NOT_GPU_QUALIFICATION");
}
struct Arena {
  std::vector<void *> ptrs;
  template <typename T> T *alloc(size_t count) {
    void *p = nullptr;
    hc(hipMalloc(&p, count * sizeof(T)));
    ptrs.push_back(p);
    return static_cast<T *>(p);
  }
  void release() {
    for (auto p : ptrs)
      hc(hipFree(p));
    ptrs.clear();
  }
  // On failure, the top-level handler drains once and exits; no unsafe
  // destructor retry.
};
static void one_case(lie_q2_workspace &ws, int type, int tiled, int gated,
                     int rows, int m, hipStream_t stream) {
  const int logical = type == LIE_Q2_K ? 640 : 2560;
  const int physical = type == LIE_Q2_K ? 768 : 2560;
  const int used = type == LIE_Q2_K ? 1 : 3, experts = 4;
  const bool pair = type == LIE_IQ2_XXS;
  const size_t count = size_t(rows) * used * m, guard = 64;
  const auto a = weights(type, m, physical, experts, 1);
  const auto b = weights(type, m, physical, experts, 33);
  std::vector<float> x(size_t(rows) * logical), expected(count),
      expected_b(count);
  std::vector<int32_t> ids(size_t(rows) * used);
  for (int r = 0; r < rows; ++r) {
    for (int k = 0; k < logical; ++k) {
      x[size_t(r) * logical + k] = source_value(r, k);
    }
    for (int u = 0; u < used; ++u)
      ids[r * used + u] =
          (r + u) % 11 == 7 ? -1 : (r % 2 == 0 ? 1 : u % experts);
  }
  const size_t block = type == LIE_Q2_K ? 84 : 66,
               row_bytes = physical / 256 * block;
  for (int r = 0; r < rows; ++r)
    for (int u = 0; u < used; ++u)
      for (int y = 0; y < m; ++y) {
        const int expert = ids[r * used + u];
        double sum = 0, up = 0;
        if (expert >= 0)
          for (int k = 0; k < logical; ++k) {
            size_t off =
                (size_t(expert) * m + y) * row_bytes + (k / 256) * block;
            sum += value(type, a.data() + off, k % 256) *
                   x[size_t(r) * logical + k];
            if (pair)
              up += value(type, b.data() + off, k % 256) *
                    x[size_t(r) * logical + k];
          }
        const size_t at = (size_t(r) * used + u) * m + y;
        expected[at] = gated ? (sum / (1 + std::exp(-sum))) * up : sum;
        expected_b[at] = up;
      }
  Arena mem;
  auto *wa = mem.alloc<uint8_t>(a.size()), *wb = mem.alloc<uint8_t>(b.size());
  auto *dx = mem.alloc<float>(x.size()); // ends at the last LOGICAL row
  auto *di = mem.alloc<int32_t>(ids.size());
  auto *o = mem.alloc<float>(count + 2 * guard),
       *ob = mem.alloc<float>(count + 2 * guard);
  hc(hipMemcpyAsync(wa, a.data(), a.size(), hipMemcpyHostToDevice, stream));
  hc(hipMemcpyAsync(wb, b.data(), b.size(), hipMemcpyHostToDevice, stream));
  hc(hipMemcpyAsync(dx, x.data(), x.size() * sizeof(float),
                    hipMemcpyHostToDevice, stream));
  hc(hipMemcpyAsync(di, ids.data(), ids.size() * sizeof(int32_t),
                    hipMemcpyHostToDevice, stream));
  hc(hipMemsetAsync(ws.storage, 0x7b, ws.plan.total_bytes, stream));
  hc(hipMemsetAsync(o, 0x5a, (count + 2 * guard) * sizeof(float), stream));
  hc(hipMemsetAsync(ob, 0x5a, (count + 2 * guard) * sizeof(float), stream));
  std::printf("{\"event\":\"begin\",\"type\":%d,\"tiled\":%d,\"gated\":%d,"
              "\"rows\":%d,\"m\":%d}\n",
              type, tiled, gated, rows, m);
  std::fflush(stdout);
  require(lie_q2_project(&ws, type, tiled, gated, wa, pair ? wb : nullptr, dx,
                         di, o + guard, pair && !gated ? ob + guard : nullptr,
                         m, logical, physical, rows, used, 0, tiled ? 16 : 0,
                         stream) == 0,
          "operator launch failed; no retry");
  hc(hipStreamSynchronize(stream));
  std::vector<float> got(count + 2 * guard), got_b(count + 2 * guard);
  hc(hipMemcpy(got.data(), o, got.size() * sizeof(float),
               hipMemcpyDeviceToHost));
  hc(hipMemcpy(got_b.data(), ob, got_b.size() * sizeof(float),
               hipMemcpyDeviceToHost));
  double max_error = 0;
  for (size_t j = 0; j < count; ++j)
    for (int p = 0; p < (pair && !gated ? 2 : 1); ++p) {
      double actual = (p ? got_b : got)[guard + j],
             ref = (p ? expected_b : expected)[j];
      const double error = std::abs(actual - ref);
      max_error = std::max(max_error, error);
      // Fixed before GPU execution; exact source quantization uses power-of-two
      // scales.
      require(std::isfinite(actual) &&
                  error <= 0.0002 + 0.00004 * std::abs(ref),
              "scalar operator mismatch");
    }
  for (const auto *v : {&got, &got_b})
    for (size_t j = 0; j < guard; ++j) {
      uint32_t first, last;
      std::memcpy(&first, &(*v)[j], 4);
      std::memcpy(&last, &(*v)[guard + count + j], 4);
      require(first == 0x5a5a5a5a && last == 0x5a5a5a5a,
              "output guard corruption");
    }
  if (type == LIE_Q2_K) {
    const size_t qb = size_t(rows) * 1024 * 36 / 32;
    Bytes q(qb);
    hc(hipMemcpy(q.data(), ws.storage, q.size(), hipMemcpyDeviceToHost));
    for (int r = 0; r < rows; ++r) {
      const int columns = tiled ? 8 : 32, begin = tiled ? 5 : 20,
                bytes = tiled ? 144 : 36;
      for (int c = begin; c < columns; ++c) {
        size_t at = size_t(tiled ? c * rows + r : r * columns + c) * bytes;
        for (int j = 0; j < bytes; ++j)
          require(q[at + j] == 0, "nonzero Q2 quantized padding");
      }
    }
  }
  mem.release();
  std::printf("{\"event\":\"pass\",\"max_absolute_error\":%.9g}\n", max_error);
  std::fflush(stdout);
}
int main(int argc, char **argv) {
  bool gpu = false;
  try {
    require(argc == 2,
            "Usage: q2-operator-probe --cpu-oracle | --gpu-synthetic (GPU "
            "requires external coordinated lease)");
    if (std::strcmp(argv[1], "--cpu-oracle") == 0) {
      cpu_oracle();
      return 0;
    }
    require(std::strcmp(argv[1], "--gpu-synthetic") == 0,
            "unsupported probe mode");
    // NOT an admission implementation: the invoking supervisor must own leases.
    cpu_oracle();
    gpu = true;
    require(qfn_mmq_init(0) == 0, "HIP initialization failed");
    hipStream_t stream{};
    hc(hipStreamCreate(&stream));
    Arena mem;
    lie_q2_workspace ws{};
    require(lie_q2_plan_make(33, 4, 3, &ws.plan), "workspace plan failed");
    ws.storage = mem.alloc<uint8_t>(ws.plan.total_bytes);
    require(lie_q2_workspace_prepare(&ws) == 0, "workspace preparation failed");
    for (int rows : {1, 2, 3, 8, 9, 32, 33})
      for (int m : {3, 17}) {
        for (int type : {LIE_IQ2_XXS, LIE_Q2_K})
          for (int tiled : {0, 1})
            one_case(ws, type, tiled, 0, rows, m, stream);
        if (rows <= 8)
          one_case(ws, LIE_IQ2_XXS, 0, 1, rows, m, stream);
      }
    hc(hipStreamSynchronize(stream));
    mem.release();
    hc(hipStreamDestroy(stream));
    std::puts("Q2_SYNTHETIC_OPERATOR_CASES_PASS_NOT_MODEL_QUALIFICATION");
    return 0;
  } catch (const std::exception &e) {
    std::fprintf(stderr, "FAILED: %s\n", e.what());
    if (gpu && hipDeviceSynchronize() != hipSuccess)
      std::_Exit(70);
    return 1;
  }
}
