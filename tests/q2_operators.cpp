// SPDX-License-Identifier: MIT
#include "q2_operator_fixture.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/mmq/qfn_mmq.h"

void Case(int type, int tokens, bool tiled, bool tiny, int rows = 5,
          int tile_cols = 0) {
  const int experts = 512, used = 2;
  qfn_mmq_set_routed_tile_cols(tile_cols);
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
                    (tiled ? "/PP" : "/TG") + (tiny ? "/small" : "/normal") +
                    "/rows" + std::to_string(rows) + "/tile" +
                    std::to_string(tile_cols);
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
    // The scheduling-only Q2 candidate must retain exact outputs at every
    // routed width reachable on gfx1151, including aligned and ragged rows.
    for (int tile : {16, 32, 48, 64, 80})
      for (bool tiny : {false, true}) {
        Case(10, 17, true, tiny, 64, tile);
        Case(10, 65, true, tiny, 65, tile);
      }
    qfn_mmq_set_routed_tile_cols(0);
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
