// SPDX-License-Identifier: MIT
// One wave per scaled activation row versus literal retained1573 packing.
// Synthetic operator timing; original-weight model timing is separate.
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <bit>
#include <algorithm>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "src/core/crypto/sha256.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
namespace gufo::models::qwen38_flash_next::rocm {
#include "experiments/q2-scaled-wave-pack-control.inc"
}
namespace q = gufo::models::qwen38_flash_next::rocm;

static void Require(bool condition, const char *message) {
  if (!condition)
    throw std::runtime_error(message);
}
static void Hip(hipError_t status) {
  if (status != hipSuccess)
    throw std::runtime_error(hipGetErrorString(status));
}
struct Device {
  void *data{};
  std::size_t bytes;
  explicit Device(std::size_t size) : bytes(size) {
    Hip(hipMalloc(&data, size ? size : 4));
  }
  Device(const Device &) = delete;
  Device &operator=(const Device &) = delete;
  ~Device() { (void)hipFree(data); }
};
template <class T>
static void Upload(Device &device, const std::vector<T> &host,
                   hipStream_t stream) {
  Require(device.bytes == host.size() * sizeof(T), "Upload size differs");
  if (device.bytes)
    Hip(hipMemcpyAsync(device.data, host.data(), device.bytes,
                       hipMemcpyHostToDevice, stream));
  Hip(hipStreamSynchronize(stream));
}
static std::vector<std::uint8_t> Read(const Device &device,
                                      hipStream_t stream) {
  std::vector<std::uint8_t> result(device.bytes);
  if (device.bytes)
    Hip(hipMemcpyAsync(result.data(), device.data, device.bytes,
                       hipMemcpyDeviceToHost, stream));
  Hip(hipStreamSynchronize(stream));
  return result;
}
static std::string Hash(const std::vector<std::uint8_t> &bytes) {
  return gufo::crypto::Sha256Hex(bytes);
}
struct Random {
  std::uint32_t state{901};
  std::uint32_t Next() {
    state = state * 1664525u + 1013904223u;
    return state;
  }
};
struct Output {
  std::size_t count;
  bool half;
  std::size_t offset;
  Device device;
  Output(std::size_t n, bool h, std::size_t prefix = 64)
      : count(n), half(h), offset(prefix),
        device(n * (h ? 2 : 4) + prefix + 64) {}
  void *Data() { return static_cast<std::uint8_t *>(device.data) + offset; }
  void Poison(hipStream_t stream) {
    std::vector<std::uint8_t> bytes(device.bytes, 0xa5);
    for (std::size_t i = 0; i < count; ++i) {
      const std::uint32_t pattern = half ? 0x7e55u : 0x7fc0beefu;
      std::memcpy(bytes.data() + offset + i * (half ? 2 : 4), &pattern,
                  half ? 2 : 4);
    }
    Upload(device, bytes, stream);
  }
  std::vector<std::uint8_t> Checked(hipStream_t stream) {
    auto bytes = Read(device, stream);
    for (std::size_t i = 0; i < offset; ++i)
      Require(bytes[i] == 0xa5,
              "Output leading guard changed; refusing further device work");
    for (std::size_t i = 0; i < 64; ++i)
      Require(bytes[bytes.size() - 1 - i] == 0xa5,
              "Output guard changed; refusing further device work");
    for (std::size_t i = 0; i < count; ++i) {
      std::uint32_t bits = 0;
      std::memcpy(&bits, bytes.data() + offset + i * (half ? 2 : 4),
                  half ? 2 : 4);
      Require(bits != (half ? 0x7e55u : 0x7fc0beefu),
              "Required output unwritten; refusing further device work");
    }
    return bytes;
  }
};

static void Save(const std::string &name,
                 const std::vector<std::uint8_t> &bytes) {
  std::ofstream f("results/" + name + ".bin", std::ios::binary);
  f.write(reinterpret_cast<const char *>(bytes.data()), bytes.size());
  Require(bool(f), "Failed to preserve changed output");
}

// Independent IEEE round-to-nearest-even oracle, using integer bit operations.
// NaN payloads are compared against the original device path separately.
static std::uint16_t HalfBits(float x) {
  const auto u = std::bit_cast<std::uint32_t>(x);
  const unsigned sign = (u >> 16) & 0x8000, exp = (u >> 23) & 255;
  const unsigned frac = u & 0x7fffff;
  if (exp == 255)
    return sign | 0x7c00 | (frac ? 0x200 : 0);
  const int power = static_cast<int>(exp) - 127;
  if (power > 15)
    return sign | 0x7c00;
  if (power < -25)
    return sign;
  const unsigned shift = power >= -14 ? 13 : unsigned(-power - 1);
  const unsigned significand = power >= -14 ? frac : (frac | 0x800000);
  unsigned bits = significand >> shift;
  const unsigned remainder = significand & ((1u << shift) - 1);
  const unsigned halfway = 1u << (shift - 1);
  if (power >= -14)
    bits |= unsigned(power + 15) << 10;
  bits += remainder > halfway || (remainder == halfway && (bits & 1));
  return sign | bits;
}
static float FromHalf(std::uint16_t h) {
  const unsigned exp = (h >> 10) & 31, frac = h & 1023;
  if (exp == 0) {
    const float value = std::ldexp(float(frac), -24);
    return std::bit_cast<float>(std::bit_cast<std::uint32_t>(value) |
                                (std::uint32_t(h & 0x8000) << 16));
  }
  return std::bit_cast<float>((std::uint32_t(h & 0x8000) << 16) |
                              ((exp == 31 ? 255u : exp + 112u) << 23) |
                              (frac << 13));
}

struct PackedCase {
  unsigned rows;
  std::size_t prefix;
  std::vector<float> values;
  Device input;
  std::string input_hash;
  std::array<std::unique_ptr<Output>, 2> half, inverse;
  PackedCase(unsigned n, unsigned input_offset, unsigned output_offset,
             bool ordinary, hipStream_t stream)
      : rows(n), prefix(input_offset), values(std::size_t(n) * 640),
        input(values.size() * 4 + prefix) {
    Random rng;
    for (unsigned row = 0; row < n; ++row) {
      for (unsigned c = 0; c < 640; ++c) {
        const std::size_t i = std::size_t(row) * 640 + c;
        float value = std::ldexp(
            float(int(rng.Next() >> 16) - 32768) / 16384.0f, int(row % 17) - 8);
        if (!ordinary) {
          switch (row % 9) {
          case 0:
            value = c & 1 ? -0.0f : 0.0f;
            break;
          case 1:
            value = std::bit_cast<float>((rng.Next() & 0x807fffffu) | 1u);
            break;
          case 2:
            value = std::ldexp(value, -116);
            break;
          case 3:
            value = std::ldexp(value, 110);
            break;
          case 4: {
            const auto code = std::uint16_t((i % 0x7bfe) + 1);
            const float tie =
                float((double(FromHalf(code)) + FromHalf(code + 1)) / 2);
            value = c % 3 == 0   ? std::nextafter(tie, 0.0f)
                    : c % 3 == 1 ? tie
                                 : std::nextafter(tie, INFINITY);
            if (c & 1)
              value = -value;
            break;
          }
          case 5:
            value = c & 1 ? -std::numeric_limits<float>::max()
                          : std::numeric_limits<float>::min();
            break;
          case 6:
            value = std::ldexp(value, -24);
            break;
          default:
            break;
          }
        }
        values[i] = value;
      }
    }
    // No readable tail after the final input value.
    std::vector<std::uint8_t> bytes(input.bytes, 0xa5);
    std::memcpy(bytes.data() + prefix, values.data(), values.size() * 4);
    Upload(input, bytes, stream);
    input_hash = Hash(bytes);
    for (unsigned a = 0; a < 2; ++a) {
      half[a] =
          std::make_unique<Output>(values.size(), true, 64 + output_offset);
      inverse[a] = std::make_unique<Output>(rows, false);
    }
  }
  const float *Input() {
    return reinterpret_cast<const float *>(
        static_cast<const std::uint8_t *>(input.data) + prefix);
  }
  void Run(unsigned arm, hipStream_t stream) {
    auto *h = static_cast<__half *>(half[arm]->Data());
    auto *sc = static_cast<float *>(inverse[arm]->Data());
    if (arm) {
      Require(q::PackQ2ScaledRows(Input(), h, sc, rows, 640, stream),
              "Candidate pack dispatch refused");
    } else {
      hipLaunchKernelGGL(q::PackQ2ScaledWaveControlKernel, dim3(rows),
                         dim3(256), 0, stream, Input(), h, sc,
                         std::size_t(640));
    }
    Hip(hipGetLastError());
  }
  bool Check(const std::string &name, hipStream_t stream) {
    std::array<std::vector<std::uint8_t>, 2> halves, scales;
    for (unsigned arm = 0; arm < 2; ++arm) {
      half[arm]->Poison(stream);
      inverse[arm]->Poison(stream);
      Run(arm, stream);
      halves[arm] = half[arm]->Checked(stream);
      scales[arm] = inverse[arm]->Checked(stream);
      Save(name + (arm ? "-candidate-half" : "-parent-half"), halves[arm]);
      Save(name + (arm ? "-candidate-scale" : "-parent-scale"), scales[arm]);
    }
    std::size_t half_errors[2]{}, scale_errors[2]{};
    for (unsigned row = 0; row < rows; ++row) {
      double peak = 0;
      for (unsigned c = 0; c < 640; ++c)
        peak = std::max(peak,
                        std::fabs(double(values[std::size_t(row) * 640 + c])));
      const int shift =
          peak == 0 ? 0 : std::clamp(13 - std::ilogb(peak), -120, 120);
      const float expected_inverse = float(std::ldexp(1.0, -shift));
      for (unsigned a = 0; a < 2; ++a) {
        float observed;
        std::memcpy(&observed, scales[a].data() + inverse[a]->offset + row * 4,
                    4);
        Require(std::isfinite(observed) && observed > 0,
                "Nonfinite/invalid scale; refusing further work");
        scale_errors[a] += std::bit_cast<unsigned>(observed) !=
                           std::bit_cast<unsigned>(expected_inverse);
      }
      for (unsigned c = 0; c < 640; ++c) {
        const auto i = std::size_t(row) * 640 + c;
        // Double ldexp and integer RN-even are independent of device shuffle,
        // F32 exponent construction and HIP half-conversion implementations.
        const float scaled = float(std::ldexp(double(values[i]), shift));
        const auto expected = HalfBits(scaled);
        for (unsigned a = 0; a < 2; ++a) {
          std::uint16_t observed;
          std::memcpy(&observed, halves[a].data() + half[a]->offset + i * 2, 2);
          Require((observed & 0x7c00u) != 0x7c00u,
                  "Nonfinite packed output; refusing further work");
          half_errors[a] += observed != expected;
        }
      }
    }
    Require(Hash(Read(input, stream)) == input_hash, "Input mutated");
    const bool exact_half = halves[0] == halves[1],
               exact_scale = scales[0] == scales[1];
    std::cout << "{\"event\":\"scaled_wave_pack_check\",\"case\":\"" << name
              << "\",\"rows\":" << rows << ",\"input_prefix\":" << prefix
              << ",\"output_prefix\":" << half[0]->offset
              << ",\"half_exact\":" << exact_half
              << ",\"scale_exact\":" << exact_scale
              << ",\"parent_oracle_half_errors\":" << half_errors[0]
              << ",\"candidate_oracle_half_errors\":" << half_errors[1]
              << ",\"parent_oracle_scale_errors\":" << scale_errors[0]
              << ",\"candidate_oracle_scale_errors\":" << scale_errors[1]
              << ",\"parent_half_sha256\":\"" << Hash(halves[0])
              << "\",\"candidate_half_sha256\":\"" << Hash(halves[1])
              << "\",\"parent_scale_sha256\":\"" << Hash(scales[0])
              << "\",\"candidate_scale_sha256\":\"" << Hash(scales[1])
              << "\"}\n";
    return exact_half && exact_scale && !half_errors[0] && !half_errors[1] &&
           !scale_errors[0] && !scale_errors[1];
  }
};

struct Down {
  std::vector<std::int32_t> bounds, slots, tiles;
  std::unique_ptr<Device> bd, sd, td;
  Device weights;
  std::array<Output, 2> output;
  std::array<std::string, 4> immutable;
  Down(hipStream_t stream)
      : bounds(513), weights(std::size_t(512) * 2560 * 3 * 84),
        output{Output(std::size_t(20480) * 2560, true),
               Output(std::size_t(20480) * 2560, true)} {
    // Every expert has40 live slots inside its48 padded rows, including holes.
    for (unsigned e = 0; e <= 512; ++e)
      bounds[e] = e * 48;
    slots.assign(512 * 48, -1);
    for (unsigned s = 0; s < 20480; ++s)
      slots[(s % 512) * 48 + s / 512] = s;
    for (unsigned e = 0; e < 512; ++e)
      tiles.push_back(e);
    bd = std::make_unique<Device>(bounds.size() * 4);
    sd = std::make_unique<Device>(slots.size() * 4);
    td = std::make_unique<Device>(tiles.size() * 4);
    Upload(*bd, bounds, stream);
    Upload(*sd, slots, stream);
    Upload(*td, tiles, stream);
    Random rng;
    std::vector<std::uint8_t> encoded(weights.bytes);
    for (std::size_t i = 0; i < encoded.size(); i += 84) {
      for (unsigned j = 0; j < 80; ++j)
        encoded[i + j] = rng.Next() >> 24;
      const __half d = __float2half_rn(0.00125f),
                   minimum = __float2half_rn(0.00075f);
      std::memcpy(encoded.data() + i + 80, &d, 2);
      std::memcpy(encoded.data() + i + 82, &minimum, 2);
    }
    Upload(weights, encoded, stream);
    unsigned i = 0;
    for (Device *d : {bd.get(), sd.get(), td.get(), &weights})
      immutable[i++] = Hash(Read(*d, stream));
  }
  void Run(unsigned arm, PackedCase &pack, hipStream_t stream) {
    Require(q::RoutedQ2ScaledHalfGemm(
                weights.data,
                static_cast<const __half *>(pack.half[arm]->Data()),
                static_cast<const float *>(pack.inverse[arm]->Data()),
                static_cast<const std::int32_t *>(td->data), tiles.size(), 48,
                static_cast<const std::int32_t *>(bd->data),
                static_cast<const std::int32_t *>(sd->data),
                static_cast<__half *>(output[arm].Data()), 2560, 640, stream),
            "Unchanged down dispatch refused");
  }
  bool Check(PackedCase &pack, hipStream_t stream, const std::string &label) {
    std::array<std::vector<std::uint8_t>, 2> bytes;
    for (unsigned arm = 0; arm < 2; ++arm) {
      output[arm].Poison(stream);
      pack.Run(arm, stream);
      Run(arm, pack, stream);
      bytes[arm] = output[arm].Checked(stream);
      for (std::size_t i = 0; i < output[arm].count; ++i) {
        std::uint16_t h;
        std::memcpy(&h, bytes[arm].data() + output[arm].offset + i * 2, 2);
        Require((h & 0x7c00u) != 0x7c00u,
                "Nonfinite down output; refusing further work");
      }
      Save(label + (arm ? "-candidate-down" : "-parent-down"), bytes[arm]);
    }
    unsigned i = 0;
    for (Device *d : {bd.get(), sd.get(), td.get(), &weights})
      Require(Hash(Read(*d, stream)) == immutable[i++], "Down input mutated");
    const bool exact = bytes[0] == bytes[1];
    std::cout << "{\"event\":\"scaled_wave_down_check\",\"case\":\"" << label
              << "\",\"exact\":" << exact << ",\"parent_sha256\":\""
              << Hash(bytes[0]) << "\",\"candidate_sha256\":\""
              << Hash(bytes[1]) << "\"}\n";
    return exact;
  }
};

static void Time(PackedCase &pack, Down &down, hipStream_t stream) {
  hipEvent_t begin{}, end{};
  Hip(hipEventCreate(&begin));
  Hip(hipEventCreate(&end));
  Require(pack.input.bytes > 32u * 1024 * 1024 &&
              down.weights.bytes > 32u * 1024 * 1024,
          "Production working sets must exceed MALL independently");
  for (unsigned cycle = 0; cycle < 2; ++cycle) {
    const unsigned iterations = cycle ? 3 : 8;
    for (unsigned rep = 0; rep < 7; ++rep) {
      for (unsigned order = 0; order < 2; ++order) {
        const unsigned arm = (rep + order) % 2;
        Hip(hipEventRecord(begin, stream));
        for (unsigned i = 0; i < iterations; ++i) {
          pack.Run(arm, stream);
          if (cycle)
            down.Run(arm, pack, stream);
        }
        Hip(hipEventRecord(end, stream));
        Hip(hipEventSynchronize(end));
        float ms{};
        Hip(hipEventElapsedTime(&ms, begin, end));
        std::cout << "{\"event\":\"scaled_wave_pack_timing\",\"scope\":\""
                  << (cycle ? "pack_down" : "pack") << "\",\"rep\":" << rep
                  << ",\"order\":" << order << ",\"candidate\":" << bool(arm)
                  << ",\"warmup\":" << (rep < 2)
                  << ",\"iterations\":" << iterations
                  << ",\"input_bytes\":" << pack.input.bytes
                  << ",\"weight_bytes\":" << (cycle ? down.weights.bytes : 0)
                  << ",\"us_per_iteration\":" << double(ms) * 1000 / iterations
                  << "}\n";
      }
    }
  }
  Hip(hipEventDestroy(end));
  Hip(hipEventDestroy(begin));
}

int main() {
  try {
    std::cout << std::boolalpha << std::defaultfloat << std::setprecision(12);
    hipStream_t stream{};
    Hip(hipStreamCreateWithFlags(&stream, hipStreamNonBlocking));
    bool pass = true;
    for (unsigned rows :
         {1u, 7u, 8u, 9u, 15u, 16u, 17u, 31u, 33u, 97u, 257u, 1025u}) {
      for (unsigned offset : {0u, 1u}) {
        PackedCase input(rows, offset * 4, offset * 2, false, stream);
        pass = input.Check("rows-" + std::to_string(rows) + "-offset-" +
                               std::to_string(offset),
                           stream) &&
               pass;
      }
    }
    PackedCase pack(20480, 0, 0, true, stream);
    Require(!q::PackQ2ScaledRows(
                nullptr, static_cast<__half *>(pack.half[0]->Data()),
                static_cast<float *>(pack.inverse[0]->Data()), 1, 640, stream),
            "Null input accepted");
    Require(!q::PackQ2ScaledRows(pack.Input(), nullptr,
                                 static_cast<float *>(pack.inverse[0]->Data()),
                                 1, 640, stream),
            "Null output accepted");
    Require(!q::PackQ2ScaledRows(pack.Input(),
                                 static_cast<__half *>(pack.half[0]->Data()),
                                 nullptr, 1, 640, stream),
            "Null scales accepted");
    for (auto [rows, cols] :
         {std::pair<unsigned, unsigned>{0, 640}, {1, 639}, {1, 641}})
      Require(!q::PackQ2ScaledRows(
                  pack.Input(), static_cast<__half *>(pack.half[0]->Data()),
                  static_cast<float *>(pack.inverse[0]->Data()), rows, cols,
                  stream),
              "Unsupported shape accepted");
    pass = pack.Check("production", stream) && pass;
    Down down(stream);
    pass = down.Check(pack, stream, "before-timing") && pass;
    Time(pack, down, stream);
    pass = down.Check(pack, stream, "after-timing") && pass;
    Require(Hash(Read(pack.input, stream)) == pack.input_hash,
            "Packing input mutated during timing");
    Hip(hipStreamSynchronize(stream));
    Hip(hipStreamDestroy(stream));
    std::cout << "{\"event\":\"scaled_wave_pack_complete\",\"numerical_pass\":"
              << pass
              << ",\"timings_retained\":true,\"model_inference\":false}\n";
    return pass ? 0 : 1;
  } catch (const std::exception &e) {
    std::cerr << e.what() << '\n';
    return 2;
  }
}
