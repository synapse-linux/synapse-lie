// SPDX-License-Identifier: MIT
// Replay the unchanged independent GPU oracle on retained R3 producer arrays.
// No model forward, production kernel launch or new random input generation.
#include <hip/hip_runtime.h>

#include <cstring>
#include <cstddef>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

extern "C" hipError_t q2_shared_q8_scalar_oracle(const float*, void*,
                                                 std::size_t, std::size_t,
                                                 hipStream_t);

static void Require(bool value, const char* reason) {
  if (!value) throw std::runtime_error(reason);
}
static void Hip(hipError_t status) {
  Require(status == hipSuccess, hipGetErrorString(status));
}
struct Device {
  void* data{};
  explicit Device(std::size_t bytes) { Hip(hipMalloc(&data, bytes)); }
  ~Device() { (void)hipFree(data); }
  Device(const Device&) = delete;
  Device& operator=(const Device&) = delete;
};
struct Stream {
  hipStream_t data{};
  Stream() { Hip(hipStreamCreateWithFlags(&data, hipStreamNonBlocking)); }
  ~Stream() { (void)hipStreamDestroy(data); }
};

static std::vector<unsigned char> Load(const std::string& name, std::size_t size) {
  std::ifstream file("oracle-replay-data/"+name, std::ios::binary);
  std::vector<unsigned char> bytes(size);
  file.read(reinterpret_cast<char*>(bytes.data()), size);
  Require(file.gcount() == static_cast<std::streamsize>(size) &&
              file.peek() == std::char_traits<char>::eof(), "Retained array size differs");
  return bytes;
}
static void Save(const std::string& name, const std::vector<unsigned char>& bytes) {
  std::ofstream file("results/"+name, std::ios::binary);
  file.write(reinterpret_cast<const char*>(bytes.data()), bytes.size());
  Require(bool(file), "Cannot preserve oracle replay output");
}

static bool Case(unsigned n, unsigned pattern) {
  constexpr unsigned k = 2560;
  constexpr std::size_t guard = 32;
  const std::size_t bytes = ((n+15)/16)*(k/32)*576;
  const std::string prefix = "shared-q8-n"+std::to_string(n)+"-p"+std::to_string(pattern);
  const auto input = Load(prefix+"-mixed-reference.bin", std::size_t(n)*k*4);
  const auto expected = Load(prefix+"-q8-reference.bin", bytes);
  const auto old_oracle = Load(prefix+"-independent-q8.bin", bytes);
  std::size_t historical_differences = 0;
  for (std::size_t i = 0; i < bytes; ++i) historical_differences += expected[i] != old_oracle[i];
  std::cout << "{\"event\":\"oracle_historical\",\"n\":" << n
            << ",\"pattern\":" << pattern << ",\"different_bytes\":"
            << historical_differences << "}\n";
  Device x(input.size());
  Hip(hipMemcpy(x.data, input.data(), input.size(), hipMemcpyHostToDevice));
  Stream stream;
  bool ordered_pass = true;
  for (unsigned rep = 0; rep < 8; ++rep) {
    for (unsigned order = 0; order < 2; ++order) {
      const bool ordered = ((rep+order)&1) != 0;
      Device output(bytes+2*guard);
      if (ordered)
        Hip(hipMemsetAsync(output.data, 0xFF, bytes+2*guard, stream.data));
      else
        Hip(hipMemset(output.data, 0xFF, bytes+2*guard));
      auto* destination = static_cast<unsigned char*>(output.data)+guard;
      Hip(q2_shared_q8_scalar_oracle(static_cast<const float*>(x.data),
                                    destination, n, k, stream.data));
      Hip(hipStreamSynchronize(stream.data));
      std::vector<unsigned char> all(bytes+2*guard);
      Hip(hipMemcpy(all.data(), output.data, all.size(), hipMemcpyDeviceToHost));
      for (std::size_t i = 0; i < guard; ++i)
        Require(all[i] == 0xFF && all[guard+bytes+i] == 0xFF, "Output guard changed");
      std::vector<unsigned char> actual(all.begin()+guard, all.end()-guard);
      std::size_t differences = 0;
      for (std::size_t i = 0; i < bytes; ++i) differences += actual[i] != expected[i];
      ordered_pass = ordered_pass && (!ordered || differences == 0);
      const std::string filename = "oracle-n"+std::to_string(n)+"-p"+
          std::to_string(pattern)+"-rep"+std::to_string(rep)+
          (ordered ? "-ordered.bin" : "-legacy.bin");
      Save(filename, actual);
      std::cout << "{\"event\":\"oracle_replay\",\"n\":" << n
                << ",\"pattern\":" << pattern << ",\"rep\":" << rep
                << ",\"order\":" << order << ",\"ordered\":" << (ordered ? "true" : "false")
                << ",\"different_bytes\":" << differences
                << ",\"bytes\":" << bytes << ",\"guard_exact\":true,\"output\":\""
                << filename << "\"}\n";
    }
  }
  std::vector<unsigned char> after(input.size());
  Hip(hipMemcpy(after.data(), x.data, after.size(), hipMemcpyDeviceToHost));
  Require(after == input, "Read-only retained input changed");
  return ordered_pass;
}

int main() {
  try {
    bool pass = true;
    for (const auto [n, pattern] : {std::pair{96u, 0u}, {97u, 1u}, {127u, 2u},
                                    {129u, 0u}, {2048u, 0u}})
      pass = Case(n, pattern) && pass;
    std::cout << (pass ? "PASS" : "FAIL")
              << " ordered independent Q8 saved-array replay; no model inference\n";
    return pass ? 0 : 1;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n'; return 1;
  }
}
