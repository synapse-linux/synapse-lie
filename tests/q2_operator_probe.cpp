// SPDX-License-Identifier: MIT
// Synthetic operator oracles, NOT model forward or full-model qualification.
// Licensed IQ2 codebook data are generated from pinned Gufo/llama.cpp; scalar
// decoding/dot expressions below are independently written test code.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

#include "q2_iq2_grid.inc"
#include "qfn_mmq.h"
#include "src/models/qwen38_flash_next/kernels/rocm/q2_routed.h"

using Bytes = std::vector<uint8_t>;
static void require(bool yes, const char* why) {
  if (!yes)
    throw std::runtime_error(why);
}
static void hc(hipError_t e) {
  if (e != hipSuccess)
    throw std::runtime_error(hipGetErrorString(e));
}
static unsigned u16(const uint8_t* p) {
  return p[0] | unsigned(p[1]) << 8;
}
static uint32_t u32(const uint8_t* p) {
  return u16(p) | uint32_t(u16(p + 2)) << 16;
}
static void put16(uint8_t* p, unsigned v) {
  p[0] = v;
  p[1] = v >> 8;
}
static void put32(uint8_t* p, uint32_t v) {
  put16(p, v);
  put16(p + 2, v >> 16);
}
static double half_value(const uint8_t* p) {
  const unsigned b = u16(p), exp = (b >> 10) & 31;
  require(exp > 0 && exp < 31, "fixture requires normal finite half");
  return (b & 0x8000 ? -1 : 1) *
         std::ldexp(double(1024 + (b & 1023)), int(exp) - 25);
}
static unsigned parity(unsigned x) {
  unsigned p = 0;
  for (; x; x >>= 1)
    p ^= x & 1;
  return p;
}
static double value(int type, const uint8_t* b, unsigned j) {
  if (type == LIE_IQ2_XXS) {
    const uint8_t* g = b + 2 + (j / 32) * 8;
    const uint32_t f = u32(g + 4);
    const unsigned s7 = (f >> (7 * ((j % 32) / 8))) & 127;
    const unsigned signs = s7 | parity(s7) << 7;
    const int sign = (signs >> (j % 8)) & 1 ? -1 : 1;
    const unsigned grid =
        (oracle_iq2_grid[g[(j % 32) / 8]] >> (8 * (j % 8))) & 255;
    return sign * half_value(b) * (2 * (f >> 28) + 1) * grid / 8.0;
  }
  const unsigned group = j / 128, within = j % 128;
  const unsigned sc = b[group * 8 + within / 16];
  const unsigned q =
      (b[16 + group * 32 + within % 32] >> (2 * (within / 32))) & 3;
  return half_value(b + 80) * (sc & 15) * q - half_value(b + 82) * (sc >> 4);
}
// Pattern 0 retains the first 64 grid-zero fixtures. Pattern 1 traverses the
// codebook and half mantissas. Pattern 2 isolates fractional /8 IQ2 arithmetic.
static Bytes weights(int type, int m, int k, int experts, unsigned salt,
                     int pattern) {
  const size_t block = type == LIE_IQ2_XXS ? 66 : 84;
  Bytes out(size_t(experts) * m * (k / 256) * block + 4096, 0);
  for (size_t i = 0; i < (out.size() - 4096) / block; ++i) {
    auto* b = out.data() + i * block;
    if (type == LIE_IQ2_XXS) {
      put16(b, pattern == 2 ? 5 << 10
                            : ((5 + (i + salt) % 3) << 10) |
                                  (pattern ? (i * 37 + salt) % 1024 : 0));
      for (unsigned g = 0; g < 8; ++g) {
        uint32_t fields =
            pattern == 2 ? 0 : uint32_t((g + i + salt) % 16) << 28;
        for (unsigned v = 0; v < 4; ++v) {
          if (pattern != 2)
            fields |= uint32_t((i * 13 + g * 7 + v + salt) % 128) << (7 * v);
          b[2 + g * 8 + v] = pattern == 2 ? 2
                             : pattern ? (i * 13 + g * 31 + v * 7 + salt) % 256
                                       : 0;
        }
        put32(b + 2 + g * 8 + 4, fields);
      }
    } else {
      for (unsigned j = 0; j < 16; ++j)
        b[j] = uint8_t(i * 19 + j * 17 + salt);
      for (unsigned j = 0; j < 64; ++j)
        b[16 + j] = uint8_t(i * 13 + j * 29 + salt);
      put16(b + 80, (6 << 10) | (pattern ? (i * 37 + salt) % 1024 : 0));
      put16(b + 82, (5 << 10) | (pattern ? (i * 11 + salt) % 1024 : 0));
    }
  }
  return out;
}
static float source_value(int row, int col, int pattern) {
  if (pattern == 2)
    return col == 0 ? 127.0f : 0.0f;
  const int q = col % 32 == 0 ? 127 : ((col * 19 + row * 7) % 253 - 126);
  return row % 3 == 2 ? 0.0f : q / 128.0f;
}
static void cpu_oracle() {
  require(source_value(0, 0, 0) != 0, "one-row fixture must be nonzero");
  uint8_t b[84]{};
  put16(b, 5 << 10);
  for (unsigned j = 0; j < 256; ++j)
    require(value(LIE_IQ2_XXS, b, j) == 1.0 / 1024, "IQ2 grid-zero golden");
  put32(b + 6, 0xf0000001u);
  require(value(LIE_IQ2_XXS, b, 0) == -31.0 / 1024 &&
              value(LIE_IQ2_XXS, b, 7) == -31.0 / 1024 &&
              value(LIE_IQ2_XXS, b, 8) == 31.0 / 1024,
          "IQ2 signs golden");
  std::memset(b, 0, sizeof b);
  put16(b, 5 << 10);
  b[2] = 2;
  require(value(LIE_IQ2_XXS, b, 0) * 127 == 3175.0 / 8192,
          "IQ2 fractional scale golden");
  std::memset(b, 0x32, 16);
  std::memset(b + 16, 0xff, 64);
  put16(b + 80, 6 << 10);
  put16(b + 82, 5 << 10);
  for (unsigned j = 0; j < 256; ++j)
    require(value(LIE_Q2_K, b, j) == 9.0 / 1024, "Q2 affine golden");
  const auto w = weights(LIE_IQ2_XXS, 640, 2560, 2, 1, 1);
  bool seen[256]{};
  for (size_t i = 0; i < (w.size() - 4096) / 66; ++i)
    for (unsigned g = 0; g < 8; ++g)
      for (unsigned v = 0; v < 4; ++v)
        seen[w[i * 66 + 2 + g * 8 + v]] = true;
  for (bool x : seen)
    require(x, "full IQ2 codebook fixture coverage");
  std::puts("Q2_SYNTHETIC_SCALAR_FIXTURE_GOLDENS_PASS_NOT_GPU_QUALIFICATION");
}
struct Case {
  int type, tiled, gated, rows, m, experts, used, tile, pattern;
  bool dirty;
};
static std::vector<Case> extended_cases() {
  std::vector<Case> c{{16, 0, 0, 1, 1, 2, 1, 0, 2, true},
                      {16, 1, 0, 1, 1, 2, 1, 16, 2, false}};
  // Aligned production output shapes and every supported requested tile width.
  for (int t : {0, 16, 32, 48, 64, 80}) {
    c.push_back({16, t != 0, 0, 9, 640, 16, 8, t, 1, true});
    c.push_back({10, t != 0, 0, 33, 2560, 16, 1, t, 1, false});
  }
  for (int rows : {1, 2, 3, 8})
    c.push_back({16, 0, 1, rows, 640, 16, 8, 0, 1, false});
  // Last physical expert, all 512 routing bins, and maximum logical capacity.
  c.push_back({16, 0, 0, 1, 640, 512, 1, 0, 1, true});
  c.push_back({10, 1, 0, 1, 2560, 512, 1, 80, 1, false});
  c.push_back({16, 1, 0, 2048, 3, 512, 32, 80, 1, true});
  c.push_back({10, 1, 0, 65536, 3, 512, 1, 80, 1, false});
  // Smaller work after the maximum: same allocation, stale tails/maps present.
  c.push_back({16, 1, 0, 1, 17, 512, 1, 16, 1, false});
  c.push_back({10, 1, 0, 1, 17, 512, 1, 16, 1, false});
  return c;
}
static void begin(const Case& c, int index) {
  if (index >= 0)
    std::printf(
        "{\"event\":\"begin\",\"case\":%d,\"type\":%d,\"tiled\":%d,"
        "\"gated\":%d,\"rows\":%d,\"m\":%d,\"experts\":%d,\"used\":%d,"
        "\"tile\":%d,\"pattern\":%d,\"dirty\":%s}\n",
        index, c.type, c.tiled, c.gated, c.rows, c.m, c.experts, c.used, c.tile,
        c.pattern, c.dirty ? "true" : "false");
  else
    std::printf(
        "{\"event\":\"begin\",\"type\":%d,\"tiled\":%d,\"gated\":%d,"
        "\"rows\":%d,\"m\":%d}\n",
        c.type, c.tiled, c.gated, c.rows, c.m);
  std::fflush(stdout);
}
struct Arena {
  std::vector<void*> ptrs;
  template<typename T>
  T* alloc(size_t count) {
    void* p = nullptr;
    hc(hipMalloc(&p, count * sizeof(T)));
    ptrs.push_back(p);
    return static_cast<T*>(p);
  }
  void release() {
    for (auto p : ptrs)
      hc(hipFree(p));
    ptrs.clear();
  }
};
static void raw(const std::string& dir, int index, const char* kind,
                const std::vector<float>& data) {
  if (dir.empty())
    return;
  std::string name =
      dir + "/case-" + std::to_string(index) + "." + kind + ".f32";
  FILE* f = std::fopen(name.c_str(), "wbx");
  require(f, "exclusive raw output open failed");
  const bool ok =
      std::fwrite(data.data(), sizeof(float), data.size(), f) == data.size();
  const int rc = std::fclose(f);
  require(ok && rc == 0, "raw output write failed");
}
static void one_case(lie_q2_workspace& ws, const Case& c, hipStream_t stream,
                     int index = -1, const std::string& directory = "") {
  begin(c, index);
  const int logical = c.type == LIE_Q2_K ? 640 : 2560,
            physical = c.type == LIE_Q2_K ? 768 : 2560;
  const bool pair = c.type == LIE_IQ2_XXS;
  const size_t count = size_t(c.rows) * c.used * c.m, guard = 64;
  const auto a = weights(c.type, c.m, physical, c.experts, 1, c.pattern);
  const auto b =
      pair ? weights(c.type, c.m, physical, c.experts, 33, c.pattern) : Bytes{};
  std::vector<float> x(size_t(c.rows) * logical), expected(count),
      expected_b(count);
  std::vector<int32_t> ids(size_t(c.rows) * c.used);
  for (int r = 0; r < c.rows; ++r) {
    for (int k = 0; k < logical; ++k)
      x[size_t(r) * logical + k] = source_value(r, k, c.pattern);
    for (int u = 0; u < c.used; ++u) {
      const int e = c.pattern == 0 ? (r % 2 == 0 ? 1 : u % c.experts)
                    : c.pattern == 2 || r == 0 ? c.experts - 1
                                               : (r * c.used + u) % c.experts;
      ids[r * c.used + u] = (r + u) % 11 == 7 ? -1 : e;
    }
  }
  const size_t block = c.type == LIE_Q2_K ? 84 : 66,
               row_bytes = physical / 256 * block;
  // Cache only referenced experts; fixture CPU math is not a model fallback.
  std::map<int, std::vector<float>> ca, cb;
  for (int expert : ids)
    if (expert >= 0 && !ca.count(expert)) {
      auto& da = ca[expert];
      da.resize(size_t(c.m) * logical);
      auto& db = cb[expert];
      if (pair)
        db.resize(da.size());
      for (int y = 0; y < c.m; ++y)
        for (int k = 0; k < logical; ++k) {
          const size_t off =
              (size_t(expert) * c.m + y) * row_bytes + (k / 256) * block;
          da[size_t(y) * logical + k] = value(c.type, a.data() + off, k % 256);
          if (pair)
            db[size_t(y) * logical + k] =
                value(c.type, b.data() + off, k % 256);
        }
    }
  for (int r = 0; r < c.rows; ++r)
    for (int u = 0; u < c.used; ++u)
      for (int y = 0; y < c.m; ++y) {
        const int e = ids[r * c.used + u];
        double sum = 0, up = 0;
        if (e >= 0) {
          const float* va = ca.at(e).data() + size_t(y) * logical;
          const float* vb =
              pair ? cb.at(e).data() + size_t(y) * logical : nullptr;
          const float* in = x.data() + size_t(r) * logical;
          for (int k = 0; k < logical; ++k) {
            sum += double(va[k]) * in[k];
            if (pair)
              up += double(vb[k]) * in[k];
          }
        }
        const size_t at = (size_t(r) * c.used + u) * c.m + y;
        expected[at] = c.gated ? (sum / (1 + std::exp(-sum))) * up : sum;
        expected_b[at] = up;
      }
  Arena mem;
  auto* wa = mem.alloc<uint8_t>(a.size());
  auto* wb = pair ? mem.alloc<uint8_t>(b.size()) : nullptr;
  auto* dx = mem.alloc<float>(x.size());
  auto* di = mem.alloc<int32_t>(ids.size());
  auto *o = mem.alloc<float>(count + 2 * guard),
       *ob = mem.alloc<float>(count + 2 * guard);
  hc(hipMemcpyAsync(wa, a.data(), a.size(), hipMemcpyHostToDevice, stream));
  if (pair)
    hc(hipMemcpyAsync(wb, b.data(), b.size(), hipMemcpyHostToDevice, stream));
  hc(hipMemcpyAsync(dx, x.data(), x.size() * sizeof(float),
                    hipMemcpyHostToDevice, stream));
  hc(hipMemcpyAsync(di, ids.data(), ids.size() * sizeof(int32_t),
                    hipMemcpyHostToDevice, stream));
  if (c.dirty)
    hc(hipMemsetAsync(ws.storage, 0x7b, ws.plan.total_bytes, stream));
  hc(hipMemsetAsync(o, 0x5a, (count + 2 * guard) * sizeof(float), stream));
  hc(hipMemsetAsync(ob, 0x5a, (count + 2 * guard) * sizeof(float), stream));
  require(
      lie_q2_project(&ws, c.type, c.tiled, c.gated, wa, wb, dx, di, o + guard,
                     pair && !c.gated ? ob + guard : nullptr, c.m, logical,
                     physical, c.rows, c.used, 0, c.tile, stream) == 0,
      "operator launch failed; no retry");
  hc(hipStreamSynchronize(stream));
  std::vector<float> got(count + 2 * guard), got_b(count + 2 * guard);
  hc(hipMemcpy(got.data(), o, got.size() * sizeof(float),
               hipMemcpyDeviceToHost));
  hc(hipMemcpy(got_b.data(), ob, got_b.size() * sizeof(float),
               hipMemcpyDeviceToHost));
  raw(directory, index, "actual", got);
  raw(directory, index, "expected", expected);
  if (pair && !c.gated) {
    raw(directory, index, "actual-b", got_b);
    raw(directory, index, "expected-b", expected_b);
  }
  double max_error = 0;
  for (size_t j = 0; j < count; ++j)
    for (int p = 0; p < (pair && !c.gated ? 2 : 1); ++p) {
      double actual = (p ? got_b : got)[guard + j],
             ref = (p ? expected_b : expected)[j],
             error = std::abs(actual - ref);
      max_error = std::max(max_error, error);
      if (!std::isfinite(actual) || error > 0.0002 + 0.00004 * std::abs(ref)) {
        std::fprintf(stderr,
                     "mismatch case=%d output=%d index=%zu actual=%.17g "
                     "reference=%.17g error=%.17g\n",
                     index, p, j, actual, ref, error);
        throw std::runtime_error("scalar operator mismatch");
      }
    }
  for (const auto* v : {&got, &got_b})
    for (size_t j = 0; j < guard; ++j) {
      uint32_t first, last;
      std::memcpy(&first, &(*v)[j], 4);
      std::memcpy(&last, &(*v)[guard + count + j], 4);
      require(first == 0x5a5a5a5a && last == 0x5a5a5a5a,
              "output guard corruption");
    }
  if (c.type == LIE_Q2_K) {
    Bytes q(size_t(c.rows) * 1024 * 36 / 32);
    hc(hipMemcpy(q.data(), ws.storage, q.size(), hipMemcpyDeviceToHost));
    for (int r = 0; r < c.rows; ++r)
      for (int col = c.tiled ? 5 : 20; col < (c.tiled ? 8 : 32); ++col) {
        const int bytes = c.tiled ? 144 : 36;
        size_t at = size_t(c.tiled ? col * c.rows + r : r * 32 + col) * bytes;
        for (int j = 0; j < bytes; ++j)
          require(q[at + j] == 0, "nonzero Q2 quantized padding");
      }
  }
  mem.release();
  std::printf("{\"event\":\"pass\",\"max_absolute_error\":%.9g}\n", max_error);
  std::fflush(stdout);
}
int main(int argc, char** argv) {
  bool gpu = false;
  try {
    require(argc >= 2,
            "Usage: q2-operator-probe --cpu-oracle | "
            "--list-extended | --gpu-synthetic | --gpu-extended "
            "NEW-RAW-DIR (external GPU leases required)");
    const std::string mode = argv[1];
    if (mode == "--cpu-oracle" && argc == 2) {
      cpu_oracle();
      return 0;
    }
    if (mode == "--list-extended" && argc == 2) {
      int i = 0;
      for (const auto& c : extended_cases())
        begin(c, i++);
      return 0;
    }
    const bool ext = mode == "--gpu-extended";
    require((ext && argc == 3) || (mode == "--gpu-synthetic" && argc == 2),
            "unsupported probe mode");
    std::string directory = ext ? argv[2] : "";
    if (ext)
      require(std::filesystem::create_directory(directory),
              "raw directory already exists");
    cpu_oracle();
    gpu = true;
    require(qfn_mmq_init(0) == 0, "HIP initialization failed");
    hipStream_t stream{};
    hc(hipStreamCreate(&stream));
    Arena mem;
    lie_q2_workspace ws{};
    require(lie_q2_plan_make(ext ? 2048 : 33, ext ? 512 : 4, ext ? 32 : 3,
                             &ws.plan),
            "workspace plan failed");
    ws.storage = mem.alloc<uint8_t>(ws.plan.total_bytes);
    require(lie_q2_workspace_prepare(&ws) == 0, "workspace preparation failed");
    if (ext) {
      int i = 0;
      for (const auto& c : extended_cases())
        one_case(ws, c, stream, i++, directory);
    } else
      for (int rows : {1, 2, 3, 8, 9, 32, 33})
        for (int m : {3, 17}) {
          for (int type : {LIE_IQ2_XXS, LIE_Q2_K})
            for (int tiled : {0, 1})
              one_case(ws,
                       {type, tiled, 0, rows, m, 4, type == LIE_Q2_K ? 1 : 3,
                        tiled ? 16 : 0, 0, true},
                       stream);
          if (rows <= 8)
            one_case(ws, {16, 0, 1, rows, m, 4, 3, 0, 0, true}, stream);
        }
    hc(hipStreamSynchronize(stream));
    mem.release();
    hc(hipStreamDestroy(stream));
    std::puts(ext ? "Q2_EXTENDED_OPERATOR_CASES_PASS_NOT_MODEL_QUALIFICATION"
                  : "Q2_SYNTHETIC_OPERATOR_CASES_PASS_NOT_MODEL_QUALIFICATION");
    return 0;
  } catch (const std::exception& e) {
    std::fprintf(stderr, "FAILED: %s\n", e.what());
    if (gpu && hipDeviceSynchronize() != hipSuccess)
      std::_Exit(70);
    return 1;
  }
}
