#pragma once
// SPDX-License-Identifier: MIT
// Shared guarded buffer and independent half-conversion helpers for expert
// ordering. Synthetic operator timing; original-weight model timing is
// separate.
#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "src/core/crypto/sha256.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
namespace q = gufo::models::qwen38_flash_next::rocm;

static void Require(bool condition, const char* message) {
  if (!condition)
    throw std::runtime_error(message);
}
static void Hip(hipError_t status) {
  if (status != hipSuccess)
    throw std::runtime_error(hipGetErrorString(status));
}
struct Device {
  void* data{};
  std::size_t bytes;
  explicit Device(std::size_t size) : bytes(size) {
    Hip(hipMalloc(&data, size ? size : 4));
  }
  Device(const Device&) = delete;
  Device& operator=(const Device&) = delete;
  ~Device() { (void)hipFree(data); }
};
template<class T>
static void Upload(Device& device, const std::vector<T>& host,
                   hipStream_t stream) {
  Require(device.bytes == host.size() * sizeof(T), "Upload size differs");
  if (device.bytes)
    Hip(hipMemcpyAsync(device.data, host.data(), device.bytes,
                       hipMemcpyHostToDevice, stream));
  Hip(hipStreamSynchronize(stream));
}
static std::vector<std::uint8_t> Read(const Device& device,
                                      hipStream_t stream) {
  std::vector<std::uint8_t> result(device.bytes);
  if (device.bytes)
    Hip(hipMemcpyAsync(result.data(), device.data, device.bytes,
                       hipMemcpyDeviceToHost, stream));
  Hip(hipStreamSynchronize(stream));
  return result;
}
static std::string Hash(const std::vector<std::uint8_t>& bytes) {
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
      : count(n),
        half(h),
        offset(prefix),
        device(n * (h ? 2 : 4) + prefix + 64) {}
  void* Data() { return static_cast<std::uint8_t*>(device.data) + offset; }
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

static void Save(const std::string& name,
                 const std::vector<std::uint8_t>& bytes) {
  std::ofstream f("results/" + name + ".bin", std::ios::binary);
  f.write(reinterpret_cast<const char*>(bytes.data()), bytes.size());
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
