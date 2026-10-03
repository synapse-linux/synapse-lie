// SPDX-License-Identifier: MIT
// Synthetic conversion/consumer experiment; no model forward or serving claim.
#include <algorithm>
#include <bit>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <hip/hip_runtime.h>
#include <iostream>
#include <stdexcept>
#include <string>
#include <sys/mman.h>
#include <unistd.h>
#include <vector>

#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hpp"
namespace q = gufo::models::qwen38_flash_next::rocm;

static void Check(bool ok, const char *why) {
  if (!ok)
    throw std::runtime_error(why);
}
static void Hip(hipError_t code) {
  Check(code == hipSuccess, hipGetErrorString(code));
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
struct Events {
  hipEvent_t begin{}, end{};
  Events() {
    Hip(hipEventCreate(&begin));
    const auto code = hipEventCreate(&end);
    if (code != hipSuccess) {
      (void)hipEventDestroy(begin);
      Hip(code);
    }
  }
  ~Events() {
    (void)hipEventDestroy(end);
    (void)hipEventDestroy(begin);
  }
};
static std::uint32_t Next(std::uint32_t &state) {
  state ^= state << 13;
  state ^= state >> 17;
  state ^= state << 5;
  return state;
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
static std::vector<float> Inputs() {
  std::vector<float> values;
  for (unsigned h = 0; h < 65536; ++h)
    values.push_back(FromHalf(h));
  // Every adjacent positive finite half interval and both sides of its tie.
  for (unsigned h = 0; h < 0x7bff; ++h) {
    const float tie =
        float((double(FromHalf(h)) + double(FromHalf(h + 1))) / 2);
    for (float x :
         {std::nextafter(tie, 0.0f), tie, std::nextafter(tie, INFINITY)}) {
      values.push_back(x);
      values.push_back(-x);
    }
  }
  for (float x : {65519.99609375f, 65520.0f, 65520.00390625f}) {
    values.push_back(x);
    values.push_back(-x);
  }
  std::uint32_t state = 617;
  for (unsigned i = 0; i < 65536; ++i)
    values.push_back(std::bit_cast<float>(Next(state)));
  return values;
}
static void Narrow(bool vector, const float *x, __half *y, std::size_t size) {
  if (vector)
    Check(q::NarrowF16Vector(x, y, size, nullptr), "Vector launch failed");
  else if (size) {
    q::NarrowActivations(x, y, false, size, nullptr);
    Hip(hipGetLastError());
  }
}
static void ConversionCase(const std::vector<float> &input, std::size_t count,
                           unsigned input_offset, unsigned output_offset) {
  constexpr std::size_t guard = 32;
  constexpr std::uint16_t sentinel = 0x55aa;
  std::vector<float> storage(count + input_offset, 0.25f);
  std::copy_n(input.begin(), count, storage.begin() + input_offset);
  // Exact requested allocation ends at the final input; no vector tail padding.
  Device xd(storage.size() * sizeof(float));
  Hip(hipMemcpy(xd.data, storage.data(), storage.size() * 4,
                hipMemcpyHostToDevice));
  const auto offset = guard + output_offset;
  std::vector<std::uint16_t> output(offset + count + guard, sentinel), control;
  Device yd(output.size() * 2);
  for (bool vector : {false, true}) {
    std::fill(output.begin(), output.end(), sentinel);
    Hip(hipMemcpy(yd.data, output.data(), output.size() * 2,
                  hipMemcpyHostToDevice));
    Narrow(vector, static_cast<const float *>(xd.data) + input_offset,
           static_cast<__half *>(yd.data) + offset, count);
    Hip(hipDeviceSynchronize());
    Hip(hipMemcpy(output.data(), yd.data, output.size() * 2,
                  hipMemcpyDeviceToHost));
    for (std::size_t i = 0; i < output.size(); ++i) {
      if (i < offset || i >= offset + count)
        Check(output[i] == sentinel, "Output guard changed");
      else {
        const float x = input[i - offset];
        const auto u = std::bit_cast<std::uint32_t>(x);
        if ((u & 0x7fffffff) > 0x7f800000)
          Check((output[i] & 0x7c00) == 0x7c00 && (output[i] & 1023),
                "NaN lost");
        else
          Check(output[i] == HalfBits(x), "Independent conversion mismatch");
      }
    }
    if (!vector)
      control = output;
    else
      Check(output == control, "Conversion differs from original device route");
  }
  std::vector<float> after(storage.size());
  Hip(hipMemcpy(after.data(), xd.data, after.size() * 4,
                hipMemcpyDeviceToHost));
  Check(std::memcmp(after.data(), storage.data(), after.size() * 4) == 0,
        "Input changed");
  std::cout << "{\"event\":\"narrow_conversion\",\"count\":" << count
            << ",\"input_offset\":" << input_offset
            << ",\"output_offset\":" << output_offset
            << ",\"exact\":true,\"independent_oracle\":true}\n";
}

// Read-only registered file mapping, like the model's mapped weight route.
// Synthetic contents are deterministic; this is not original-weight evidence.
struct Weights {
  void *host{MAP_FAILED}, *device{};
  std::size_t bytes;
  int fd{-1};
  bool registered{};
  Weights(unsigned m, unsigned k, unsigned copies)
      : bytes(std::size_t(m) * k * copies * 2) {
    char path[] = "results/narrow-weights-XXXXXX";
    try {
      fd = mkstemp(path);
      Check(fd >= 0, "Cannot create synthetic weights");
      Check(unlink(path) == 0, "Cannot unlink private weight file");
      Check(ftruncate(fd, bytes) == 0, "Cannot size synthetic weights");
      host = mmap(nullptr, bytes, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
      Check(host != MAP_FAILED, "Cannot map synthetic weights");
      auto *values = static_cast<std::uint16_t *>(host);
      std::uint32_t state = 761;
      for (std::size_t i = 0; i < bytes / 2; ++i)
        values[i] = HalfBits(float(int(Next(state) % 129) - 64) / 2048.0f);
      Check(msync(host, bytes, MS_SYNC) == 0, "Cannot flush synthetic weights");
      Check(mprotect(host, bytes, PROT_READ) == 0,
            "Cannot protect synthetic weights");
      Hip(hipHostRegister(host, bytes,
                          hipHostRegisterMapped | hipHostRegisterReadOnly));
      registered = true;
      Hip(hipHostGetDevicePointer(&device, host, 0));
    } catch (...) {
      Release();
      throw;
    }
  }
  void Release() {
    if (registered)
      (void)hipHostUnregister(host);
    if (host != MAP_FAILED)
      (void)munmap(host, bytes);
    if (fd >= 0)
      (void)close(fd);
  }
  ~Weights() { Release(); }
  Weights(const Weights &) = delete;
  Weights &operator=(const Weights &) = delete;
};

static void Bench(unsigned m, unsigned k) {
  constexpr unsigned n = 2048, copies = 4, launches = 8;
  const auto size = std::size_t(n) * k, out_size = std::size_t(n) * m;
  Device input(size * copies * 4), half(size * copies * 2),
      output(out_size * copies * 4);
  Weights weights(m, k, copies);
  std::vector<float> host(size * copies);
  std::uint32_t state = 349;
  for (float &x : host)
    x = float(int(Next(state) % 65537) - 32768) / 32749.0f;
  Hip(hipMemcpy(input.data, host.data(), host.size() * 4,
                hipMemcpyHostToDevice));
  auto launch = [&](bool vector, bool consumer, unsigned index) {
    const auto copy = index % copies;
    auto *converted = static_cast<__half *>(half.data) + copy * size;
    Narrow(vector, static_cast<const float *>(input.data) + copy * size,
           converted, size);
    if (consumer)
      Check(q::UnquantizedF16Gemm(
                static_cast<const __half *>(weights.device) +
                    std::size_t(copy) * m * k,
                converted, static_cast<float *>(output.data) + copy * out_size,
                n, m, k, nullptr),
            "Consumer launch failed");
    Hip(hipGetLastError());
  };
  // Validate every converted value and every consumer result before timing.
  std::vector<float> control(out_size * copies), result(control.size());
  std::vector<std::uint16_t> converted(size * copies);
  for (bool vector : {false, true}) {
    for (unsigned i = 0; i < copies; ++i)
      launch(vector, true, i);
    Hip(hipDeviceSynchronize());
    Hip(hipMemcpy(converted.data(), half.data, converted.size() * 2,
                  hipMemcpyDeviceToHost));
    for (std::size_t i = 0; i < converted.size(); ++i)
      Check(converted[i] == HalfBits(host[i]),
            "Shaped conversion oracle mismatch");
    Hip(hipMemcpy(result.data(), output.data, result.size() * 4,
                  hipMemcpyDeviceToHost));
    for (float x : result)
      Check(std::isfinite(x), "Nonfinite consumer output");
    if (!vector)
      control = result;
    else
      Check(std::memcmp(control.data(), result.data(), result.size() * 4) == 0,
            "Full consumer output changed");
  }
  // Independent original input/weight FP64 dots; same existing 2e-5 HC bound.
  const auto *w = static_cast<const std::uint16_t *>(weights.host);
  double error2 = 0, norm2 = 0, peak = 0, maximum = 0;
  for (unsigned sample = 0; sample < 128; ++sample) {
    const unsigned copy = sample % copies, token = (sample * 797u) % n,
                   row = (sample * 173u) % m;
    double expected = 0;
    for (unsigned j = 0; j < k; ++j)
      expected +=
          double(FromHalf(w[(std::size_t(copy) * m + row) * k + j])) *
          FromHalf(HalfBits(host[(std::size_t(copy) * n + token) * k + j]));
    const double delta =
        double(control[(std::size_t(copy) * n + token) * m + row]) - expected;
    error2 += delta * delta;
    norm2 += expected * expected;
    peak = std::max(peak, std::abs(expected));
    maximum = std::max(maximum, std::abs(delta));
  }
  const double rms = std::sqrt(error2 / std::max(norm2, 1e-60));
  const double scaled = maximum / std::max(peak, 1e-30);
  std::cout << "{\"event\":\"narrow_consumer_check\",\"m\":" << m
            << ",\"k\":" << k << ",\"n\":" << n << ",\"copies\":" << copies
            << ",\"exact_values\":" << control.size()
            << ",\"oracle_samples\":128,\"relative_rms\":" << rms
            << ",\"error_over_peak\":" << scaled << "}\n";
  Check(rms <= 0.00002 && scaled <= 0.00002,
        "Independent consumer tolerance exceeded");
  Events events;
  for (bool consumer : {false, true}) {
    for (bool vector : {false, true})
      for (unsigned i = 0; i < copies; ++i)
        launch(vector, consumer, i);
    Hip(hipDeviceSynchronize());
    for (unsigned rep = 0; rep < 5; ++rep) {
      for (unsigned arm = 0; arm < 2; ++arm) {
        const bool vector = (arm + rep) % 2;
        Hip(hipEventRecord(events.begin, nullptr));
        for (unsigned i = 0; i < launches; ++i)
          launch(vector, consumer, i);
        Hip(hipEventRecord(events.end, nullptr));
        Hip(hipEventSynchronize(events.end));
        float ms = 0;
        Hip(hipEventElapsedTime(&ms, events.begin, events.end));
        std::cout << "{\"event\":\"narrow_timing\",\"scope\":\""
                  << (consumer ? "conversion_and_consumer" : "conversion_only")
                  << "\",\"vector\":" << (vector ? "true" : "false")
                  << ",\"m\":" << m << ",\"k\":" << k << ",\"n\":" << n
                  << ",\"rep\":" << rep << ",\"launches\":" << launches
                  << ",\"copies\":" << copies
                  << ",\"activation_bytes\":" << size * copies * 6
                  << ",\"mapped_weight_bytes\":" << weights.bytes
                  << ",\"us_per_cycle\":" << ms * 1000.0 / launches << "}\n";
      }
    }
  }
}

int main() {
  try {
    std::cout << std::unitbuf;
    std::cout.precision(12);
    Hip(hipSetDevice(0));
    Check(q::NarrowF16Vector(nullptr, nullptr, 0, nullptr),
          "Empty conversion rejected");
    Device dummy(16);
    auto *f = static_cast<float *>(dummy.data);
    auto *h = static_cast<__half *>(dummy.data);
    Hip(hipMemset(dummy.data, 0x5a, 16));
    Check(q::NarrowF16Vector(f, h, 0, nullptr),
          "Empty buffer conversion rejected");
    Check(!q::NarrowF16Vector(nullptr, h, 1, nullptr), "Null input accepted");
    Check(!q::NarrowF16Vector(f, nullptr, 1, nullptr), "Null output accepted");
    Check(
        !q::NarrowF16Vector(f, h, std::size_t{0xffffffffu} * 256 + 1, nullptr),
        "Oversized launch accepted");
    Hip(hipGetLastError());
    std::uint8_t sentinel[16];
    Hip(hipMemcpy(sentinel, dummy.data, 16, hipMemcpyDeviceToHost));
    for (auto b : sentinel)
      Check(b == 0x5a, "Refused launch mutated output");
    const auto inputs = Inputs();
    unsigned cases = 0;
    for (unsigned count :
         {1u, 2u, 3u, 4u, 5u, 255u, 256u, 257u, 1023u, 1024u, 1025u})
      for (unsigned a = 0; a < 4; ++a)
        for (unsigned b = 0; b < 4; ++b) {
          ConversionCase(inputs, count, a, b);
          ++cases;
        }
    for (unsigned a = 0; a < 4; ++a)
      for (unsigned b = 0; b < 4; ++b) {
        ConversionCase(inputs, inputs.size(), a, b);
        ++cases;
      }
    Bench(320, 10240);
    Bench(513, 2560);
    std::cout << "{\"event\":\"narrow_summary\",\"conversion_cases\":" << cases
              << ",\"special_input_values\":" << inputs.size()
              << ",\"consumer_shapes\":2}\n";
    return 0;
  } catch (const std::exception &e) {
    std::cerr << "FAIL: " << e.what() << '\n';
    return 1;
  }
}
