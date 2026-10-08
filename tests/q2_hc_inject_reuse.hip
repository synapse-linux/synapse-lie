// SPDX-License-Identifier: MIT
// Guarded complete HC mix/injection cycles; synthetic operands, no model.
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
#include <vector>
#include "src/core/crypto/sha256.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
namespace gufo::models::qwen38_flash_next::rocm {
#include "experiments/q2-hc-inject-reuse-draft-v3.inc"
}
namespace q = gufo::models::qwen38_flash_next::rocm;
constexpr unsigned kHidden = 2560, kRank = 320, kStreams = 4;
static void Require(bool ok, const char* message) {
  if (!ok) throw std::runtime_error(message);
}
static void Hip(hipError_t error) {
  if (error != hipSuccess) throw std::runtime_error(hipGetErrorString(error));
}
struct Device {
  void* data{};
  std::size_t bytes;
  explicit Device(std::size_t count) : bytes(count) {
    Hip(hipMalloc(&data, count ? count : 4));
  }
  Device(const Device&) = delete;
  Device& operator=(const Device&) = delete;
  ~Device() { hipFree(data); }
};
template<class T>
static void Upload(Device& destination, const std::vector<T>& source,
                   hipStream_t stream) {
  Require(destination.bytes == source.size() * sizeof(T), "Upload extent differs");
  if (destination.bytes)
    Hip(hipMemcpyAsync(destination.data, source.data(), destination.bytes,
                       hipMemcpyHostToDevice, stream));
  Hip(hipStreamSynchronize(stream));
}
static std::vector<std::uint8_t> Read(const Device& source, hipStream_t stream) {
  std::vector<std::uint8_t> data(source.bytes);
  if (source.bytes)
    Hip(hipMemcpyAsync(data.data(), source.data, source.bytes,
                       hipMemcpyDeviceToHost, stream));
  Hip(hipStreamSynchronize(stream));
  return data;
}
static std::string Hash(const std::vector<std::uint8_t>& data) {
  return gufo::crypto::Sha256Hex(data);
}
struct Random {
  std::uint32_t value{1901};
  float Next(float scale) {
    value = value * 1664525u + 1013904223u;
    return float(int(value >> 16) - 32768) / 32768.0f * scale;
  }
};
struct Guarded {
  std::size_t payload;
  Device storage;
  explicit Guarded(std::size_t bytes) : payload(bytes), storage(bytes + 128) {}
  void* Data() { return static_cast<std::uint8_t*>(storage.data) + 64; }
  void Reset(unsigned element_bytes, hipStream_t stream) {
    std::vector<std::uint8_t> bytes(storage.bytes, 0xa5);
    const std::uint32_t f32 = 0x7fc12345;
    const std::uint16_t f16 = 0x7e55;
    for (std::size_t i = 64; i < 64 + payload; i += element_bytes) {
      if (element_bytes == 4) std::memcpy(bytes.data() + i, &f32, 4);
      else if (element_bytes == 2) std::memcpy(bytes.data() + i, &f16, 2);
    }
    Upload(storage, bytes, stream);
  }
  std::vector<std::uint8_t> Checked(hipStream_t stream, unsigned element_bytes,
                                  bool written = true) {
    auto bytes = Read(storage, stream);
    for (std::size_t i = 0; i < bytes.size(); ++i)
      if (i < 64 || i >= 64 + payload)
        Require(bytes[i] == 0xa5, "HC output guard changed; stop device work");
    if (written && element_bytes > 1) {
      for (std::size_t i = 64; i < 64 + payload; i += element_bytes) {
        if (element_bytes == 4) {
          std::uint32_t v; std::memcpy(&v, bytes.data() + i, 4);
          Require(v != 0x7fc12345, "HC output unwritten; stop device work");
        } else {
          std::uint16_t v; std::memcpy(&v, bytes.data() + i, 2);
          Require(v != 0x7e55, "HC half output unwritten; stop device work");
        }
      }
    }
    return bytes;
  }
};
static std::size_t Nonfinite(const std::vector<std::uint8_t>& bytes, unsigned width) {
  std::size_t count = 0;
  for (std::size_t i = 64; i + 64 < bytes.size(); i += width) {
    if (width == 4) {
      std::uint32_t v; std::memcpy(&v, bytes.data() + i, 4);
      count += (v & 0x7f800000) == 0x7f800000;
    } else if (width == 2) {
      std::uint16_t v; std::memcpy(&v, bytes.data() + i, 2);
      count += (v & 0x7c00) == 0x7c00;
    }
  }
  return count;
}
struct Inputs {
  unsigned n, rotations;
  std::vector<float> normalized, residual, scales, gamma, coefficients;
  std::vector<__half> low_rank;
  Device xn, res, sc, gm, iw, low;
  std::vector<std::unique_ptr<Device>> up;
  std::vector<std::string> up_hash;
  std::array<std::string, 6> input_hash;
  Inputs(unsigned tokens, unsigned pattern, unsigned count, hipStream_t stream)
      : n(tokens), rotations(count), normalized(std::size_t(n) * 4 * kHidden),
        residual(normalized.size()), scales(std::size_t(n) * 4), gamma(4 * kHidden),
        coefficients(4 * 4 * kHidden), low_rank(std::size_t(n) * kRank),
        xn(normalized.size() * 4), res(residual.size() * 4), sc(scales.size() * 4),
        gm(gamma.size() * 4), iw(coefficients.size() * 4), low(low_rank.size() * 2) {
    Random random;
    const float magnitude = pattern == 1 ? 0.0001f : 0.5f;
    for (std::size_t i = 0; i < normalized.size(); ++i) {
      normalized[i] = i % 41 == 0 ? -0.0f : random.Next(magnitude);
      residual[i] = i % 43 == 0 ? 0.0f : random.Next(magnitude);
    }
    for (std::size_t i = 0; i < scales.size(); ++i) scales[i] = 0.8f + random.Next(0.25f);
    for (std::size_t i = 0; i < gamma.size(); ++i) gamma[i] = 1.0f + random.Next(0.5f);
    for (auto& value : coefficients) value = random.Next(0.0625f);
    for (auto& value : low_rank) value = __float2half_rn(random.Next(0.03125f));
    Upload(xn, normalized, stream); Upload(res, residual, stream);
    Upload(sc, scales, stream); Upload(gm, gamma, stream);
    Upload(iw, coefficients, stream); Upload(low, low_rank, stream);
    unsigned idx = 0;
    for (const Device* buffer : {&xn, &res, &sc, &gm, &iw, &low})
      input_hash[idx++] = Hash(Read(*buffer, stream));
    for (unsigned r = 0; r < rotations; ++r) {
      std::vector<__half> weights(4 * kHidden * kRank);
      for (auto& value : weights) value = __float2half_rn(random.Next(0.03125f));
      up.push_back(std::make_unique<Device>(weights.size() * 2));
      Upload(*up.back(), weights, stream); up_hash.push_back(Hash(Read(*up.back(), stream)));
    }
  }
  void Unchanged(hipStream_t stream) {
    unsigned idx = 0;
    for (const Device* buffer : {&xn, &res, &sc, &gm, &iw, &low})
      Require(Hash(Read(*buffer, stream)) == input_hash[idx++], "HC input mutated");
    for (unsigned r = 0; r < rotations; ++r)
      Require(Hash(Read(*up[r], stream)) == up_hash[r], "HC weights mutated");
  }
};
struct Outputs {
  Guarded mixed, half, q8, inject, dots;
  explicit Outputs(unsigned n)
      : mixed(std::size_t(n) * kHidden * 4), half(std::size_t(n) * kHidden * 2),
        q8(q::Q8TiledBytes(n, kHidden)),
        inject(std::size_t(n) * 4 * q::HcInjectPartsVec4(kHidden) * 4),
        dots(std::size_t(n) * kHidden * 4) {}
  void Reset(hipStream_t stream) {
    mixed.Reset(4, stream); half.Reset(2, stream); q8.Reset(1, stream);
    inject.Reset(4, stream); dots.Reset(4, stream);
  }
};
static void Launch(bool candidate, unsigned mode, Inputs& in, Outputs& out,
                   unsigned rotation, bool half, hipStream_t stream) {
  const auto* w = in.up[rotation]->data;
  const auto* low = static_cast<const __half*>(in.low.data);
  const auto* xn = static_cast<const float*>(in.xn.data);
  const auto* iw = static_cast<const float*>(in.iw.data);
  auto* mixed = static_cast<float*>(out.mixed.Data());
  auto* narrowed = half ? static_cast<__half*>(out.half.Data()) : nullptr;
  auto* inject = static_cast<float*>(out.inject.Data());
  bool ok;
  if (mode == 2) {
    const auto* res = static_cast<const float*>(in.res.data);
    const auto* sc = static_cast<const float*>(in.sc.data);
    const auto* gm = static_cast<const float*>(in.gm.data);
    ok = candidate
        ? q::HcInjectReuseLdsDraftDeferred(w, low, res, sc, gm, iw, mixed, narrowed,
              static_cast<float*>(out.dots.Data()), out.dots.payload, inject, in.n, stream)
        : q::HcMixDeferredNorm(w, low, res, iw, mixed, narrowed, inject, in.n,
              kHidden, kRank, stream, sc, gm);
  } else if (candidate) {
    ok = q::HcInjectReuseLdsDraftRaw(w, low, xn, iw, mixed, narrowed,
        mode == 1 ? out.q8.Data() : nullptr, static_cast<float*>(out.dots.Data()),
        out.dots.payload, inject, in.n, stream);
  } else if (mode == 1) {
    ok = q::HcMixRawQ8F16Gemm(w, low, xn, iw, mixed, narrowed, out.q8.Data(), inject,
                            in.n, kHidden, kRank, stream);
  } else {
    ok = q::HcMixRawF16Gemm(w, low, xn, iw, mixed, narrowed, inject, in.n,
                          kHidden, kRank, stream);
  }
  Require(ok, "Complete HC cycle dispatch rejected"); Hip(hipGetLastError());
}
static bool Compare(const std::string& label, const std::string& field, unsigned rotation,
                    Guarded& reference, Guarded& candidate, unsigned width,
                    hipStream_t stream, bool written = true) {
  const auto a = reference.Checked(stream, width, written);
  const auto b = candidate.Checked(stream, width, written);
  const std::size_t nonfinite = written && width > 1 ? Nonfinite(a, width) + Nonfinite(b, width) : 0;
  const bool exact = a == b && nonfinite == 0;
  std::cout << "{\"event\":\"hc_reuse_replay\",\"case\":\"" << label
      << "\",\"field\":\"" << field << "\",\"rotation\":" << rotation
      << ",\"bytes\":" << reference.payload << ",\"exact\":" << exact
      << ",\"guards_exact\":true,\"finite_written_checked\":" << (written && width > 1)
      << ",\"nonfinite_values\":" << nonfinite
      << ",\"reference_sha256\":\"" << Hash(a) << "\",\"candidate_sha256\":\""
      << Hash(b) << "\"}\n";
  if (!exact) {
    for (unsigned arm = 0; arm < 2; ++arm) {
      const auto& data = arm ? b : a;
      std::ofstream file("results/" + label + "-" + field + "-" +
          std::to_string(rotation) + (arm ? "-candidate.bin" : "-reference.bin"), std::ios::binary);
      file.write(reinterpret_cast<const char*>(data.data()), data.size());
      Require(bool(file), "Failed to preserve HC numerical difference");
    }
  }
  return exact;
}
static bool Q8Live(Guarded& out, unsigned n, hipStream_t stream) {
  const auto bytes = out.Checked(stream, 1);
  bool pass = true;
  for (unsigned tt = 0; tt < ((n + 127) / 128) * 8; ++tt)
    for (unsigned kb = 0; kb < kHidden / 32; ++kb)
      for (unsigned token = 0; token < 16; ++token) {
        const std::size_t base = 64 + (std::size_t(tt) * (kHidden / 32) + kb) * 576;
        if (tt * 16 + token < n) {
          std::uint32_t scale; std::memcpy(&scale, bytes.data() + base + 512 + token * 4, 4);
          Require(scale != 0xa5a5a5a5, "HC Q8 scale unwritten");
          pass = pass && (scale & 0x7f800000) != 0x7f800000;
        } else {
          for (unsigned i = 0; i < 32; ++i)
            Require(bytes[base + (i / 16) * 256 + token * 16 + i % 16] == 0xa5,
                    "HC Q8 padding mutated");
          for (unsigned i = 0; i < 4; ++i)
            Require(bytes[base + 512 + token * 4 + i] == 0xa5, "HC Q8 scale padding mutated");
        }
      }
  return pass;
}
static bool Case(unsigned n, unsigned mode, unsigned pattern, bool half,
                 bool timed, hipStream_t stream) {
  const std::string label = "n" + std::to_string(n) + "-m" + std::to_string(mode) +
      "-p" + std::to_string(pattern) + (half ? "-half" : "-nohalf");
  Inputs in(n, pattern, timed ? 6 : 1, stream);
  Outputs reference(n), candidate(n);
  bool pass = true;
  for (unsigned rotation = 0; rotation < in.rotations; ++rotation) {
    reference.Reset(stream); candidate.Reset(stream);
    Launch(false, mode, in, reference, rotation, half, stream);
    Launch(true, mode, in, candidate, rotation, half, stream);
    pass = Compare(label, "mixed", rotation, reference.mixed, candidate.mixed, 4, stream) && pass;
    pass = Compare(label, "half", rotation, reference.half, candidate.half, 2, stream, half) && pass;
    pass = Compare(label, "inject", rotation, reference.inject, candidate.inject, 4, stream) && pass;
    if (mode == 1) {
      const bool reference_q8 = Q8Live(reference.q8, n, stream);
      const bool candidate_q8 = Q8Live(candidate.q8, n, stream);
      const bool q8_pass = reference_q8 && candidate_q8;
      pass = q8_pass && pass;
      std::cout << "{\"event\":\"hc_reuse_q8_live\",\"case\":\"" << label
          << "\",\"rotation\":" << rotation << ",\"finite_scales_padding_exact\":" << q8_pass << "}\n";
      pass = Compare(label, "q8", rotation, reference.q8, candidate.q8, 1, stream) && pass;
    }
    const auto dots = candidate.dots.Checked(stream, 4);
    const std::size_t dot_nonfinite = Nonfinite(dots, 4);
    pass = dot_nonfinite == 0 && pass;
    std::cout << "{\"event\":\"hc_reuse_scratch\",\"case\":\"" << label
        << "\",\"rotation\":" << rotation << ",\"bytes\":" << candidate.dots.payload
        << ",\"guarded_written\":true,\"nonfinite_values\":" << dot_nonfinite
        << ",\"sha256\":\"" << Hash(dots) << "\"}\n";
  }
  if (timed) {
    const std::size_t rotating_bytes = in.up[0]->bytes * in.rotations;
    Require(rotating_bytes > 32u * 1024 * 1024, "HC rotating weights below MALL");
    hipEvent_t begin{}, end{}; Hip(hipEventCreate(&begin)); Hip(hipEventCreate(&end));
    for (unsigned rep = 0; rep < 7; ++rep)
      for (unsigned order = 0; order < 2; ++order) {
        const bool variant = (rep + order) % 2;
        auto& out = variant ? candidate : reference;
        Hip(hipStreamSynchronize(stream));
        const auto start = std::chrono::steady_clock::now();
        Hip(hipEventRecord(begin, stream));
        for (unsigned rotation = 0; rotation < in.rotations; ++rotation)
          Launch(variant, mode, in, out, rotation, half, stream);
        Hip(hipEventRecord(end, stream)); Hip(hipEventSynchronize(end));
        Hip(hipStreamSynchronize(stream));
        const auto finish = std::chrono::steady_clock::now();
        float milliseconds = -1.0f; Hip(hipEventElapsedTime(&milliseconds, begin, end));
        const double wall_us = std::chrono::duration<double, std::micro>(finish - start).count() / in.rotations;
        Require(std::isfinite(wall_us) && wall_us > 0, "HC monotonic timer invalid");
        const bool hip_valid = std::isfinite(milliseconds) && milliseconds > 0;
        std::cout << "{\"event\":\"hc_reuse_timing\",\"case\":\"" << label
            << "\",\"rep\":" << rep << ",\"order\":" << order << ",\"candidate\":" << variant
            << ",\"warmup\":" << (rep < 2) << ",\"iterations\":" << in.rotations
            << ",\"rotating_weight_bytes\":" << rotating_bytes << ",\"wall_us_per_cycle\":" << wall_us
            << ",\"hip_ms_raw\":";
        if (std::isfinite(milliseconds)) std::cout << milliseconds;
        else std::cout << "null";
        std::uint32_t hip_bits; std::memcpy(&hip_bits, &milliseconds, 4);
        std::cout << ",\"hip_ms_raw_bits\":" << hip_bits << ",\"hip_timer_valid\":" << hip_valid
            << ",\"scope\":\"complete mix/injection incl event submission and terminal sync; copies/setup outside\"}\n";
      }
    Hip(hipEventDestroy(end)); Hip(hipEventDestroy(begin));
    // Recheck complete output after both warmed alternating arms.
    pass = Compare(label, "post-mixed", 5, reference.mixed, candidate.mixed, 4, stream) && pass;
    pass = Compare(label, "post-inject", 5, reference.inject, candidate.inject, 4, stream) && pass;
    pass = Compare(label, "post-half", 5, reference.half, candidate.half, 2, stream) && pass;
    pass = Nonfinite(candidate.dots.Checked(stream, 4), 4) == 0 && pass;
    if (mode == 1) {
      const bool reference_q8 = Q8Live(reference.q8, n, stream);
      const bool candidate_q8 = Q8Live(candidate.q8, n, stream);
      pass = reference_q8 && candidate_q8 && pass;
      pass = Compare(label, "post-q8", 5, reference.q8, candidate.q8, 1, stream) && pass;
    }
  }
  in.Unchanged(stream);
  return pass;
}
int main() {
  try {
    std::cout << std::boolalpha << std::setprecision(12);
    hipStream_t stream{}; Hip(hipStreamCreateWithFlags(&stream, hipStreamNonBlocking));
    bool pass = true;
    for (unsigned n : {96u, 97u, 127u, 128u, 129u, 257u})
      for (unsigned mode = 0; mode < 3; ++mode)
        for (unsigned pattern = 0; pattern < 2; ++pattern)
          pass = Case(n, mode, pattern, true, false, stream) && pass;
    for (unsigned mode = 0; mode < 3; ++mode) {
      pass = Case(129, mode, 0, false, false, stream) && pass;
      pass = Case(2048, mode, 0, true, true, stream) && pass;
    }
    Hip(hipStreamSynchronize(stream)); Hip(hipStreamDestroy(stream));
    std::cout << "{\"event\":\"hc_reuse_complete\",\"numerical_pass\":" << pass
        << ",\"timing_retained\":true,\"model_inference\":false}\n";
    return pass ? 0 : 1;
  } catch (const std::exception& error) {
    std::cerr << "FAIL: " << error.what() << '\n'; return 2;
  }
}
