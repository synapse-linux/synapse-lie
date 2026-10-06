// SPDX-License-Identifier: MIT
// Fixed Q2 down contract versus the literal retained half-output parent.
// Synthetic guarded operator checks, separate from original-weight inference.
#include <array>
#include <cmath>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
#include "experiments/q2_iq2_tail16_routes.inc"
#include "src/core/crypto/sha256.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
namespace gufo::models::qwen38_flash_next::rocm {
#include "experiments/q2-down-register-palette-control.inc"
}
namespace q = gufo::models::qwen38_flash_next::rocm;

static void Require(bool value, const char* message) {
  if (!value) throw std::runtime_error(message);
}
static void Hip(hipError_t value) {
  if (value != hipSuccess) throw std::runtime_error(hipGetErrorString(value));
}
struct Device {
  void* data{};
  std::size_t bytes;
  unsigned output_prefix{64};
  explicit Device(std::size_t size) : bytes(size) {
    Hip(hipMalloc(&data, size ? size : 4));
  }
  Device(const Device&) = delete;
  Device& operator=(const Device&) = delete;
  ~Device() { hipFree(data); }
};
template<class T>
static void Upload(Device& out, const std::vector<T>& in, hipStream_t stream) {
  Require(out.bytes == in.size() * sizeof(T), "Upload size differs");
  if (out.bytes) Hip(hipMemcpyAsync(out.data, in.data(), out.bytes,
                                  hipMemcpyHostToDevice, stream));
  Hip(hipStreamSynchronize(stream));
}
static std::vector<std::uint8_t> Read(const Device& in, hipStream_t stream) {
  std::vector<std::uint8_t> out(in.bytes);
  if (in.bytes) Hip(hipMemcpyAsync(out.data(), in.data, in.bytes,
                                 hipMemcpyDeviceToHost, stream));
  Hip(hipStreamSynchronize(stream));
  return out;
}
static std::string Hash(const std::vector<std::uint8_t>& in) {
  return gufo::crypto::Sha256Hex(in);
}
struct Random {
  std::uint32_t state{901};
  std::uint32_t Next() { return state = state * 1664525u + 1013904223u; }
};
struct Inputs {
  unsigned n, m, k, experts, used, width, nonempty{};
  std::vector<__half> activation;
  std::vector<float> inverse;
  std::vector<std::int32_t> bounds, slots, tiles;
  std::vector<std::uint8_t> encoded;
  std::array<std::unique_ptr<Device>, 3> weights;
  std::array<std::string, 3> weight_hash;
  Device x, scale;
  std::unique_ptr<Device> bd, sd, td;

  Inputs(unsigned tokens, unsigned output, unsigned inner, unsigned active,
         unsigned top, unsigned tile, hipStream_t stream,
         const std::uint32_t* captured = nullptr)
      : n(tokens),
        m(output),
        k(inner),
        experts(active),
        used(top),
        width(tile),
        activation(std::size_t(n) * used * k),
        inverse(std::size_t(n) * used),
        bounds(experts + 1),
        encoded(std::size_t(experts) * m * ((k + 255) / 256) * 84),
        x(activation.size() * 2),
        scale(inverse.size() * 4) {
    Require(k % 64 == 0 && used <= experts, "Invalid Q2 shape");
    Random rng;
    for (std::size_t i = 0; i < activation.size(); ++i) {
      const float magnitude = i % 97 == 0 ? 8192.0f : 16.0f;
      const float value = i % 37 == 0   ? -0.0f
                          : i % 41 == 0 ? 0.0000001f
                                        : float(int(rng.Next() >> 16) - 32768) /
                                              32768 * magnitude;
      activation[i] = __float2half_rn(value);
    }
    for (std::size_t i = 0; i < inverse.size(); ++i)
      inverse[i] = i % 101 == 0 ? -0.0f : std::ldexp(i % 3 == 0 ? -1.25f : 1.0f, int(i % 23) - 30);
    Upload(x, activation, stream);
    Upload(scale, inverse, stream);
    std::vector<unsigned> counts(experts), cursor(experts);
    if (captured) {
      Require(n == 2048 && experts == 512 && used == 10, "Captured shape changed");
      unsigned total = 0;
      for (unsigned e = 0; e < experts; ++e) {
        counts[e] = captured[e];
        Require(counts[e] <= n, "Captured expert count exceeds tokens");
        total += counts[e];
      }
      Require(total == n * used, "Captured route total changed");
    } else {
      for (unsigned slot = 0; slot < n * used; ++slot) ++counts[slot % experts];
    }
    for (unsigned e = 0; e < experts; ++e)
      {
        nonempty += counts[e] != 0;
        bounds[e + 1] = bounds[e] + ((counts[e] + 15) / 16) * 16;
      }
    slots.assign(bounds.back(), -1);
    if (captured) {
      unsigned slot = 0;
      for (unsigned e = 0; e < experts; ++e)
        for (unsigned row = 0; row < counts[e]; ++row)
          slots[unsigned(bounds[e]) + row] = std::int32_t(slot++);
      Require(slot == n * used, "Captured slots incomplete");
    } else {
      for (unsigned slot = 0; slot < n * used; ++slot) {
        const unsigned e = slot % experts;
        slots[unsigned(bounds[e]) + cursor[e]++] = std::int32_t(slot);
      }
    }
    for (unsigned e = 0; e < experts; ++e)
      for (unsigned j = 0; j < (counts[e] + 15) / 16 * 16; j += width)
        tiles.push_back(std::int32_t(e | (j / width) << 16));
    bd = std::make_unique<Device>(bounds.size() * 4);
    sd = std::make_unique<Device>(slots.size() * 4);
    td = std::make_unique<Device>(tiles.size() * 4);
    Upload(*bd, bounds, stream);
    Upload(*sd, slots, stream);
    Upload(*td, tiles, stream);
    for (unsigned rotation = 0; rotation < 3; ++rotation) {
      for (std::size_t block = 0; block < encoded.size(); block += 84) {
        for (unsigned i = 0; i < 80; ++i)
          encoded[block + i] = std::uint8_t(rng.Next() >> 24);
        const auto index = block / 84 + rotation;
        const float value = index % 29 == 0   ? 0.0f
                            : index % 31 == 0 ? -0.0000001f
                            : index % 43 == 0 ? -0.00125f
                                              : 0.00125f;
        const __half d = __float2half_rn(value),
                     minimum = __float2half_rn(value * 0.75f);
        std::memcpy(encoded.data() + block + 80, &d, 2);
        std::memcpy(encoded.data() + block + 82, &minimum, 2);
      }
      weights[rotation] = std::make_unique<Device>(encoded.size());
      Upload(*weights[rotation], encoded, stream);
      weight_hash[rotation] = Hash(encoded);
    }
  }
  void Unchanged(hipStream_t stream) {
    for (unsigned r = 0; r < 3; ++r)
      Require(Hash(Read(*weights[r], stream)) == weight_hash[r],
              "Weights changed");
    for (const auto& pair :
         {std::pair<const Device*, const void*>{bd.get(), bounds.data()},
          std::pair<const Device*, const void*>{sd.get(), slots.data()},
          std::pair<const Device*, const void*>{td.get(), tiles.data()}}) {
      const auto bytes = Read(*pair.first, stream);
      Require(std::memcmp(bytes.data(), pair.second, bytes.size()) == 0,
              "Routing input changed");
    }
    for (const auto& pair :
         {std::pair<const Device*, const void*>{&x, activation.data()},
          std::pair<const Device*, const void*>{&scale, inverse.data()}}) {
      const auto bytes = Read(*pair.first, stream);
      Require(std::memcmp(bytes.data(), pair.second, bytes.size()) == 0,
              "Input changed");
    }
  }
};

template<unsigned BN>
static void LaunchWidth(bool candidate, Inputs& in, Device& out, unsigned rotation,
                        hipStream_t stream) {
  const auto* tiles = static_cast<const std::int32_t*>(in.td->data);
  const auto* bounds = static_cast<const std::int32_t*>(in.bd->data);
  const auto* slots = static_cast<const std::int32_t*>(in.sd->data);
  auto* output = reinterpret_cast<__half*>(static_cast<std::uint8_t*>(out.data) + out.output_prefix);
  if (candidate) {
    Require(q::RoutedQ2ScaledHalfGemm(in.weights[rotation]->data,
        static_cast<const __half*>(in.x.data), static_cast<const float*>(in.scale.data),
        tiles, in.tiles.size(), BN, bounds, slots, output, in.m, in.k, stream),
        "Production Q2 down fixed contract dispatch rejected");
  } else {
    hipLaunchKernelGGL((q::RoutedQ2RegisterPaletteControlKernel<q::WeightType::kQ2_K,
        128, BN, 2, false, false, true>), dim3((in.m + 127) / 128, in.tiles.size()),
        dim3(256), 0, stream, in.weights[rotation]->data,
        static_cast<const __half*>(in.x.data), tiles, bounds, slots, slots, nullptr,
        reinterpret_cast<float*>(output), nullptr, in.m, in.k, in.scale.data);
  }
  Hip(hipGetLastError());
}
static void Launch(bool candidate, Inputs& in, Device& out, unsigned rotation,
                   hipStream_t stream) {
  switch (in.width) {
    case 16: LaunchWidth<16>(candidate, in, out, rotation, stream); break;
    case 48: LaunchWidth<48>(candidate, in, out, rotation, stream); break;
    case 64: LaunchWidth<64>(candidate, in, out, rotation, stream); break;
    default: Require(false, "Unsupported Q2 width");
  }
}
static bool Case(const std::string& label, unsigned n, unsigned m, unsigned k,
                 unsigned experts, unsigned used, unsigned width, bool bench,
                 hipStream_t stream, const std::uint32_t* captured = nullptr, unsigned prefix = 64) {
  Inputs in(n, m, k, experts, used, width, stream, captured);
  std::cout << "{\"event\":\"down_fixed_contract_map\",\"case\":\"" << label
      << "\",\"tile_rows\":" << width << ",\"tile_count\":" << in.tiles.size()
      << ",\"expert_capacity\":" << experts << ",\"nonempty_experts\":" << in.nonempty
      << ",\"padded_rows\":" << in.bounds.back() << ",\"maps_exact\":true}\n";
  const std::size_t bytes = std::size_t(n) * used * m * 2 + prefix + 64;
  Device reference(bytes), candidate(bytes);
  reference.output_prefix = candidate.output_prefix = prefix;
  std::vector<std::uint8_t> last_reference, last_candidate;
  bool pass = true;
  for (unsigned r = 0; r < 3; ++r) {
    std::vector<std::uint8_t> poison(bytes, 0xa5);
    const std::uint16_t unwritten_half = 0x7e55U;
    for (std::size_t i = prefix; i < bytes - 64; i += 2)
      std::memcpy(poison.data() + i, &unwritten_half, 2);
    Upload(reference, poison, stream); Upload(candidate, poison, stream);
    Launch(false, in, reference, r, stream); Launch(true, in, candidate, r, stream);
    const auto a = Read(reference, stream), b = Read(candidate, stream);
    if (r == 2) { last_reference = a; last_candidate = b; }
    std::size_t changed = 0, nonfinite = 0, unwritten = 0;
    bool guards = true;
    for (std::size_t i = 0; i < bytes; i += 2) {
      std::uint16_t av, bv;
      std::memcpy(&av, a.data() + i, 2); std::memcpy(&bv, b.data() + i, 2);
      if (i < prefix || i >= bytes - 64) {
        guards = guards && av == 0xa5a5U && bv == 0xa5a5U;
      } else {
        changed += av != bv;
        unwritten += av == 0x7e55U || bv == 0x7e55U;
        nonfinite += (av & 0x7c00U) == 0x7c00U || (bv & 0x7c00U) == 0x7c00U;
      }
    }
    const bool exact = !changed && !nonfinite && !unwritten && guards;
    pass = pass && exact;
    std::cout << "{\"event\":\"down_fixed_contract_replay\",\"case\":\"" << label
        << "\",\"rotation\":" << r << ",\"packed\":false,\"bytes\":" << bytes
        << ",\"changed_values\":" << changed << ",\"nonfinite_values\":" << nonfinite
        << ",\"unwritten_values\":" << unwritten << ",\"guards_exact\":" << guards
        << ",\"exact\":" << exact << ",\"reference_sha256\":\"" << Hash(a)
        << "\",\"candidate_sha256\":\"" << Hash(b) << "\",\"weight_sha256\":\""
        << in.weight_hash[r] << "\",\"weight_repeat_sha256\":\"" << in.weight_hash[r] << "\"}\n";
    if (!exact) {
      for (unsigned arm = 0; arm < 2; ++arm) {
        const auto& values = arm ? b : a;
        const auto file = "results/" + label + "-" + std::to_string(r) +
            (arm ? "-candidate.bin" : "-reference.bin");
        std::ofstream saved(file, std::ios::binary);
        saved.write(reinterpret_cast<const char*>(values.data()), values.size());
        Require(bool(saved), "Failed to preserve changed output");
      }
    }
    Require(guards, "Q2 down output guard changed; refusing further device work");
    Require(!unwritten, "Q2 down output unwritten; refusing further device work");
  }
  if (bench) {
    Require(in.encoded.size() * 3 > 32u * 1024 * 1024, "Weight rotation below MALL");
    hipEvent_t begin{}, end{};
    Hip(hipEventCreate(&begin)); Hip(hipEventCreate(&end));
    for (unsigned rep = 0; rep < 7; ++rep) {
      for (unsigned order = 0; order < 2; ++order) {
        const bool is_candidate = (rep + order) % 2;
        auto& output = is_candidate ? candidate : reference;
        Hip(hipStreamSynchronize(stream));
        const auto wall_begin = std::chrono::steady_clock::now();
        Hip(hipEventRecord(begin, stream));
        for (unsigned r = 0; r < 3; ++r) Launch(is_candidate, in, output, r, stream);
        Hip(hipEventRecord(end, stream)); Hip(hipEventSynchronize(end));
        Hip(hipStreamSynchronize(stream));
        const double wall_us = std::chrono::duration<double, std::micro>(
            std::chrono::steady_clock::now() - wall_begin).count() / 3.0;
        float ms{}; Hip(hipEventElapsedTime(&ms, begin, end));
        const bool valid = std::isfinite(ms) && ms > 0.0f;
        std::uint32_t hip_bits{}; std::memcpy(&hip_bits, &ms, 4);
        std::cout << "{\"event\":\"down_fixed_contract_timing\",\"case\":\"" << label
            << "\",\"rep\":" << rep << ",\"order\":" << order
            << ",\"candidate\":" << is_candidate << ",\"warmup\":" << (rep < 2)
            << ",\"tokens\":" << n << ",\"output_rows\":" << m << ",\"inner\":" << k
            << ",\"expert_capacity\":" << experts << ",\"tile_rows\":" << width
            << ",\"iterations\":3,\"weight_bytes\":" << in.encoded.size() * 3
            << ",\"hip_us_per_iteration\":";
        if (std::isfinite(ms)) std::cout << double(ms) * 1000 / 3;
        else std::cout << "null";
        std::cout << ",\"hip_valid\":" << valid << ",\"hip_raw_bits\":" << hip_bits
            << ",\"us_per_iteration\":" << wall_us << "}\n";
      }
    }
    const auto timed_reference = Read(reference, stream), timed_candidate = Read(candidate, stream);
    if (timed_reference != last_reference || timed_candidate != last_candidate) {
      for (const auto& saved : std::array<std::pair<const char*, const std::vector<std::uint8_t>*>, 4>{{
               {"reference-before", &last_reference}, {"candidate-before", &last_candidate},
               {"reference-after", &timed_reference}, {"candidate-after", &timed_candidate}}}) {
        std::ofstream output("results/" + label + "-" + saved.first + ".bin", std::ios::binary);
        output.write(reinterpret_cast<const char*>(saved.second->data()), saved.second->size());
        Require(bool(output), "Failed to preserve timed output difference");
      }
    }
    Require(timed_reference == last_reference && timed_candidate == last_candidate,
            "Timed output differs from its complete replay buffer");
    std::cout << "{\"event\":\"down_fixed_contract_post_timing\",\"case\":\"" << label
        << "\",\"rotation\":2,\"bytes\":" << bytes
        << ",\"reference_sha256\":\"" << Hash(timed_reference)
        << "\",\"candidate_sha256\":\"" << Hash(timed_candidate) << "\"}\n";
    Hip(hipEventDestroy(end)); Hip(hipEventDestroy(begin));
  }
  in.Unchanged(stream);
  return pass;
}
int main() {
  try {
    std::cout << std::boolalpha << std::defaultfloat << std::setprecision(12);
    hipStream_t stream{}; Hip(hipStreamCreateWithFlags(&stream, hipStreamNonBlocking));
    bool pass = true;
    for (unsigned n : {1u, 16u, 17u, 49u, 65u, 129u, 144u, 145u, 257u})
      for (unsigned m : {1u, 65u, 2560u})
        pass = Case("edge-n" + std::to_string(n) + "-m" + std::to_string(m),
                    n, m, 640, 1, 1, 48, false, stream) && pass;
    for (unsigned width : {16u,64u})
      for (unsigned n : {65u,145u})
        for (unsigned m : {65u,2560u})
          pass = Case("control-w"+std::to_string(width)+"-n"+std::to_string(n)+"-m"+std::to_string(m),
                      n,m,640,1,1,width,false,stream) && pass;
    for (unsigned width : {16u,48u,64u})
      pass = Case("unaligned4-w" + std::to_string(width), 65, 2560, 640,
                  1, 1, width, false, stream, nullptr, 68) && pass;
    pass = Case("uniform-e160-w48",2048,2560,640,160,10,48,true,stream) && pass;
    pass = Case("control-e512-w64",2048,2560,640,512,10,64,true,stream) && pass;
    pass = Case("uniform-e512-w48",2048,2560,640,512,10,48,false,stream) && pass;
    pass = Case("real-layer0",2048,2560,640,512,10,48,true,stream,kLayer0Counts) && pass;
    pass = Case("real-layer3",2048,2560,640,512,10,48,true,stream,kLayer3Counts) && pass;
    pass = Case("real-layer22",2048,2560,640,512,10,48,true,stream,kLayer22Counts) && pass;
    Hip(hipStreamSynchronize(stream)); Hip(hipStreamDestroy(stream));
    std::cout << "{\"event\":\"down_fixed_contract_complete\",\"numerical_pass\":" << pass
        << ",\"timing_retained\":true,\"model_inference\":false}\n";
    return pass ? 0 : 1;
  } catch (const std::exception& error) {
    std::cerr << "FAIL: " << error.what() << '\n'; return 2;
  }
}
