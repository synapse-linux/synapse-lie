// SPDX-License-Identifier: MIT
#include "src/core/gguf_reader.hpp"
#include "src/core/quant/ggml_dequant.hpp"
#include "src/models/qwen38_flash_next/weights.hpp"
#include <cassert>
#include <cstring>
#include <iostream>
#include <limits>
#include <vector>

using gufo::core::GgmlType;
namespace qfn = gufo::models::qwen38_flash_next;

// One small synthetic tensor. No model file or tensor forward is accessed.
std::vector<unsigned char> Fixture(unsigned type, std::uint64_t cols,
                                   std::size_t bytes) {
  std::vector<unsigned char> data;
  const auto pod = [&]<class T>(T value) {
    const auto pos = data.size();
    data.resize(pos + sizeof(T));
    std::memcpy(data.data() + pos, &value, sizeof(T));
  };
  pod(std::uint32_t{0x46554747});
  pod(std::uint32_t{3});
  pod(std::uint64_t{1});
  pod(std::uint64_t{0});
  pod(std::uint64_t{1});
  data.push_back('w');
  pod(std::uint32_t{1});
  pod(cols);
  pod(std::uint32_t{type});
  pod(std::uint64_t{0});
  data.resize((data.size() + 31) / 32 * 32 + bytes);
  return data;
}

int main() {
  struct Case {
    unsigned type;
    std::uint64_t cols;
    std::size_t bytes;
  };
  for (auto c : {Case{39, 32, 17}, Case{16, 256, 66}, Case{10, 768, 252},
                 Case{12, 256, 144}, Case{8, 32, 34}}) {
    auto bytes = Fixture(c.type, c.cols, c.bytes);
    std::string error;
    auto reader =
        gufo::core::GgufReader::OpenMemory(bytes.data(), bytes.size(), &error);
    assert(reader && error.empty());
    assert(reader->FindTensor("w")->size_bytes == c.bytes);
    bytes.pop_back();
    assert(!gufo::core::GgufReader::OpenMemory(bytes.data(), bytes.size(),
                                               &error));
  }
  for (auto cols : {std::uint64_t{0}, std::uint64_t{31},
                    std::numeric_limits<std::uint64_t>::max()}) {
    auto bytes = Fixture(39, cols, 32);
    std::string error;
    assert(!gufo::core::GgufReader::OpenMemory(bytes.data(), bytes.size(),
                                               &error));
  }
  auto unknown = Fixture(40, 32, 128);
  std::string error;
  assert(!gufo::core::GgufReader::OpenMemory(unknown.data(), unknown.size(),
                                             &error));
  qfn::TensorRef t;
  t.type = GgmlType::kQ2_K;
  t.cols = 768;
  t.rows = 2560;
  t.experts = 512;
  assert(t.RowBytes() == 252 && t.SizeBytes() == 330301440);
  t.cols = 640;
  assert(t.RowBytes() == 0);
  t.type = GgmlType::kIQ2_XXS;
  t.cols = 2560;
  t.rows = 640;
  assert(t.RowBytes() == 660 && t.SizeBytes() == 216268800);
  assert(gufo::quant::QuantizedRowBytes(GgmlType::kMXFP4, 640) == 340);
  std::cout << "PASS synthetic Q2 storage geometry; no model inference\n";
}
