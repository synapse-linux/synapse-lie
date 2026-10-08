// SPDX-License-Identifier: MIT
// Original-weight PLE diagnostics, not a throughput or quality acceptance test.
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <span>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#include "q2_ple_diag.hpp"
#include "src/core/crypto/sha256.hpp"
#include "src/models/qwen/chat_template.hpp"
#include "src/models/qwen/tokenizer.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/executor.hpp"

namespace q = gufo::models::qwen38_flash_next;
namespace tok = gufo::tokenization;
using Clock = std::chrono::steady_clock;
using Exec = q::rocm::Executor;

static void Require(bool good, const std::string& why) {
  if (!good)
    throw std::runtime_error(why);
}
static double Seconds(Clock::time_point start) {
  return std::chrono::duration<double>(Clock::now() - start).count();
}
template<typename T>
static std::string Hash(std::span<const T> values) {
  return gufo::crypto::Sha256Hex(
      std::span(reinterpret_cast<const std::uint8_t*>(values.data()),
                values.size_bytes()));
}
template<typename T>
static void Save(const std::string& name, std::span<const T> values) {
  std::ofstream file("results/" + name, std::ios::binary);
  file.write(reinterpret_cast<const char*>(values.data()), values.size_bytes());
  Require(bool(file), "Cannot save diagnostic evidence");
}
static std::vector<std::int32_t> Padding(const tok::QwenTokenizer& tokenizer,
                                         std::size_t target) {
  std::size_t lo = 0, hi = target * 2;
  while (lo <= hi) {
    const auto n = lo + (hi - lo) / 2;
    std::string text = "Ignore this padding data:\n";
    for (std::size_t i = 0; i < n; ++i)
      text += "x ";
    text +=
        "\nCount from 1 to 200, separated by commas. Output only the numbers.";
    tok::ChatTemplateOptions options;
    options.enable_thinking = false;
    std::string error;
    const std::vector<tok::ChatMessage> messages{{tok::ChatRole::kUser, text}};
    auto ids = tok::QwenChatTemplate::RenderAndTokenize(tokenizer, messages,
                                                        options, &error);
    Require(bool(ids), error);
    if (ids->size() == target)
      return {ids->begin(), ids->end()};
    if (ids->size() < target)
      lo = n + 1;
    else {
      if (n == 0)
        break;
      hi = n - 1;
    }
  }
  throw std::runtime_error("Cannot construct exact physical prompt length");
}
static std::vector<std::int32_t> Varied(std::size_t size) {
  // Deterministic ordinary token IDs, explicitly synthetic, no special tokens.
  std::uint32_t state = 0x38f1a5u;
  std::vector<std::int32_t> ids(size);
  for (auto& id : ids) {
    state ^= state << 13;
    state ^= state >> 17;
    state ^= state << 5;
    id = 256 + state % 100000;
  }
  return ids;
}
static void CheckStats(const q2ple::Snapshot& stats) {
  Require(stats[q2ple::cache_hits] + stats[q2ple::io_rows] ==
              stats[q2ple::unique_rows],
          "PLE unique-row accounting differs");
  Require(stats[q2ple::unique_rows] <= stats[q2ple::rows],
          "PLE row accounting differs");
}

int main(int argc, char** argv) {
  try {
    Require(argc == 2, "Usage: q2_ple MODEL");
    std::cout << std::unitbuf << std::setprecision(12);
    std::string error;
    auto reader = gufo::core::GgufReader::OpenFile(argv[1], &error);
    Require(bool(reader), error);
    auto weights = q::ModelWeights::Bind(*reader, &error);
    Require(bool(weights), error);
    auto tokenizer = tok::QwenTokenizer::CreateFromGguf(*reader, &error);
    Require(bool(tokenizer), error);
    const auto& c = weights->config;
    const auto& t = weights->ple_table;
    auto open = [&] {
      auto table = q::NgramTable::Open(
          reader->GetMappedRegions()[t.shard].file_descriptor, t.file_offset,
          t.rows, c.ple_head_dim, t.type, &error);
      Require(bool(table), error);
      return table;
    };
    auto device = q::rocm::DeviceModel::Upload(*weights, *reader, nullptr,
                                               nullptr, &error);
    Require(bool(device), error);
    Exec::Options options;
    options.max_batch = 2048;
    std::vector<float> logits(tokenizer->GetVocabSize());
    const auto padding = Padding(*tokenizer, 2048);
    const auto varied = Varied(8192 + 32);
    for (const std::string label : {"padding", "varied"}) {
      const std::vector<std::int32_t> input =
          label == "padding" ? padding
                             : std::vector<std::int32_t>(varied.begin(),
                                                         varied.begin() + 2048);
      Save<std::int32_t>(label + "-input.i32", input);
      auto table = open();
      std::cout << "{\"event\":\"table\",\"case\":\"" << label
                << "\",\"type\":" << static_cast<int>(t.type)
                << ",\"row_bytes\":" << table->RowBytes()
                << ",\"table_rows\":" << table->Rows()
                << ",\"heads\":" << c.ple_heads
                << ",\"cache_slots\":" << q2ple::cache_slots
                << ",\"cache_bytes\":" << q2ple::cache_bytes
                << ",\"workers\":" << q2ple::workers
                << ",\"direct_io\":" << (q2ple::direct ? "true" : "false")
                << "}\n";
      auto executor = Exec::Create(*device, table.get(), options, &error);
      Require(bool(executor), error);
      for (int rep = 0; rep < 4; ++rep) {
        // No cache eviction or global tuning. Repetitions retain only this
        // table.
        std::this_thread::sleep_for(std::chrono::seconds(5));
        auto session = executor->CreateSession(
            gufo::core::SessionMode::kAutoregressive, 9216, &error);
        Require(bool(session), error);
        auto forward = [&](std::span<const std::int32_t> ids, bool pp,
                           int step) {
          q2ple::Reset();
          const auto start = Clock::now();
          Require(executor->Forward(*session, ids, 1, logits.data(),
                                    pp ? Exec::ForwardMode::kPrefill
                                       : Exec::ForwardMode::kDecode,
                                    &error),
                  error);
          const auto seconds = Seconds(start);
          const auto stats = q2ple::Read();
          CheckStats(stats);
          for (float value : logits)
            Require(std::isfinite(value), "Non-finite frontier");
          const auto digest = Hash<float>(logits);
          if (pp || step == 31)
            Save<float>(label + "-" + std::to_string(rep) +
                            (pp ? "-prefill.f32" : "-last.f32"),
                        logits);
          std::cout << std::defaultfloat << std::setprecision(12)
                    << "{\"event\":\"forward\",\"case\":\"" << label
                    << "\",\"rep\":" << rep << ",\"phase\":\""
                    << (pp ? "prefill" : "decode") << "\",\"step\":" << step
                    << ",\"tokens\":" << ids.size()
                    << ",\"seconds\":" << seconds << ",\"frontier_sha256\":\""
                    << digest << "\",\"ple\":";
          q2ple::Json(std::cout, stats);
          std::cout << "}\n";
        };
        forward(input, true, -1);
        // Same 32 forced IDs for Q2/UD: no semantic/EOS or greedy quality
        // claim.
        for (int step = 0; step < 32; ++step)
          forward(std::span(varied).subspan(8192 + step, 1), false, step);
      }
    }
    // Isolated row-I/O diagnostic: fresh owned cache, cold then three repeats.
    // No GPU forward; 8K gather is intentionally separate from 2K chunking.
    for (std::size_t length : {2048, 8192}) {
      for (const std::string label : {"padding", "varied"}) {
        const auto input = label == "padding"
                               ? Padding(*tokenizer, length)
                               : std::vector<std::int32_t>(
                                     varied.begin(), varied.begin() + length);
        auto table = open();
        std::vector<std::uint32_t> rows(length * c.ple_heads);
        std::vector<float> out(length * c.PleEmbeddingDim());
        std::string first_hash;
        for (int rep = 0; rep < 4; ++rep) {
          q::NgramHistory history;
          q2ple::Reset();
          const auto start = Clock::now();
          q::HashNgramRows(c, history, input, rows);
          Require(table->Read(rows, out), "PLE gather failed");
          const auto seconds = Seconds(start);
          const auto stats = q2ple::Read();
          CheckStats(stats);
          for (float value : out)
            Require(std::isfinite(value), "Non-finite row");
          const auto digest = Hash<float>(out);
          if (rep == 0)
            first_hash = digest;
          Require(first_hash == digest, "Repeated gather differs");
          std::cout << "{\"event\":\"gather\",\"case\":\"" << label
                    << "\",\"rep\":" << rep << ",\"tokens\":" << length
                    << ",\"seconds\":" << seconds << ",\"embedding_sha256\":\""
                    << digest << "\",\"ple\":";
          q2ple::Json(std::cout, stats);
          std::cout << "}\n";
        }
      }
    }
    std::cout << "{\"event\":\"complete\",\"diagnostic_only\":true}\n";
  } catch (const std::exception& ex) {
    std::cerr << "FAIL: " << ex.what() << '\n';
    return 1;
  }
}
