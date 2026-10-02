// SPDX-License-Identifier: MIT
// Original-row I/O only. No model upload, GPU launch or CPU model forward.
#include "q2_ple_io.hpp"

#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#include <algorithm>
#include <array>
#include <bit>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <span>
#include <stdexcept>
#include <string>
#include <vector>

#include "q2_ple_diag.hpp"
#include "src/core/crypto/sha256.hpp"
#include "src/models/qwen38_flash_next/ngram.hpp"
#include "src/models/qwen38_flash_next/weights.hpp"

namespace q = gufo::models::qwen38_flash_next;
using Clock = std::chrono::steady_clock;
static void Require(bool value, const std::string& why) {
  if (!value)
    throw std::runtime_error(why);
}
template<typename T>
static std::string Hash(std::span<const T> values) {
  return gufo::crypto::Sha256Hex(
      std::span(reinterpret_cast<const std::uint8_t*>(values.data()),
                values.size_bytes()));
}
static std::uint64_t ReadBytes() {
  std::ifstream stream("/proc/self/io");
  std::string key;
  std::uint64_t value;
  while (stream >> key >> value)
    if (key == "read_bytes:")
      return value;
  throw std::runtime_error("Process I/O accounting is unavailable");
}
static std::vector<std::int32_t> Tokens(std::uint32_t seed) {
  std::vector<std::int32_t> tokens(2048);
  for (auto& token : tokens) {
    seed ^= seed << 13;
    seed ^= seed >> 17;
    seed ^= seed << 5;
    token = 256 + seed % 100000;
  }
  return tokens;
}
static std::vector<std::uint64_t> Pages(std::span<const std::uint32_t> rows,
                                        std::uint64_t offset,
                                        std::size_t bytes) {
  Require(::sysconf(_SC_PAGESIZE) == 4096, "Diagnostic requires 4-KiB pages");
  std::vector<std::uint64_t> pages;
  for (auto row : rows) {
    const auto first = offset + row * bytes;
    pages.push_back(first / 4096);
    pages.push_back((first + bytes - 1) / 4096);
  }
  std::sort(pages.begin(), pages.end());
  pages.erase(std::unique(pages.begin(), pages.end()), pages.end());
  return pages;
}
static std::size_t Resident(const gufo::core::GgufMappedRegion& region,
                            std::span<const std::uint64_t> pages) {
  // Read-only residency observation, outside all gather timers. No page faults
  // are intentionally requested and no shared cache eviction is performed.
  std::size_t resident = 0;
  for (auto page : pages) {
    Require(page * 4096 < region.size, "Page outside mapped file");
    auto* address = const_cast<std::uint8_t*>(
                        static_cast<const std::uint8_t*>(region.data)) +
                    page * 4096;
    unsigned char value = 0;
    Require(::mincore(address, 4096, &value) == 0, "mincore failed");
    resident += value & 1;
  }
  return resident;
}

static void Fixture() {
  struct File {
    std::array<char, 64> path{};
    int fd{-1};
    File() {
      std::strcpy(path.data(), "/tmp/lie-q2-ple-io-XXXXXX");
      fd = ::mkstemp(path.data());
      Require(fd >= 0, "Cannot create private fixture");
    }
    ~File() {
      if (fd >= 0) {
        ::close(fd);
        ::unlink(path.data());
      }
    }
  } file;
  constexpr std::uint32_t dim = 160, count = 65537;
  const std::array<std::uint32_t, 8> rows{0,     17,    16384, 32768,
                                          49152, 65536, 0,     65536};
  Require(::ftruncate(file.fd, std::uint64_t(count) * dim * 2) == 0,
          "Cannot size fixture");
  for (auto row : rows) {
    std::array<std::uint16_t, dim> encoded;
    for (std::size_t i = 0; i < dim; ++i)
      encoded[i] = 0x3f00 + (row / 16384 + i) % 128;
    Require(::pwrite(file.fd, encoded.data(), sizeof(encoded),
                     std::uint64_t(row) * sizeof(encoded)) == sizeof(encoded),
            "Cannot write private fixture");
  }
  for (int advice : {POSIX_FADV_NORMAL, POSIX_FADV_RANDOM}) {
    for (std::size_t budget : {8u * 1024 * 1024, 32u * 1024 * 1024}) {
      q2pleio::advice = advice;
      q2pleio::bf16_cache_budget = budget;
      std::string error;
      auto table = q::NgramTable::Open(file.fd, 0, count, dim,
                                       gufo::core::GgmlType::kBF16, &error);
      Require(bool(table), error);
      Require(q2pleio::advice_result == 0, "Descriptor advice failed");
      Require(
          q2ple::cache_slots == (budget == 8u * 1024 * 1024 ? 16384 : 65536),
          "Unexpected cache capacity");
      std::vector<float> out(rows.size() * dim + 16, -1234.5F);
      for (int rep = 0; rep < 5; ++rep) {
        q2ple::Reset();
        Require(table->StartRead(rows, std::span(out).first(rows.size() * dim)),
                "Cannot start fixture gather");
        Require(!table->StartRead(rows, out), "Overlapping gather must fail");
        Require(table->WaitRead(), "Fixture gather failed");
        for (std::size_t r = 0; r < rows.size(); ++r)
          for (std::size_t i = 0; i < dim; ++i) {
            const float expected =
                0.5F + float((rows[r] / 16384 + i) % 128) / 256.0F;
            Require(out[r * dim + i] == expected,
                    "Independent BF16 row oracle differs");
          }
        Require(std::all_of(out.end() - 16, out.end(),
                            [](float x) { return x == -1234.5F; }),
                "Output guard changed");
      }
      const std::array<std::uint32_t, 1> invalid{count};
      Require(!table->Read(invalid, out), "Out-of-range row accepted");
      Require(table->StartRead(rows, out), "Cannot start destructor-wait case");
      table.reset();  // Owned output stays alive while the table joins readers.
    }
  }
  std::cout << "PASS: PLE descriptor advice, cache capacity, row oracle, "
               "guards and lifetime\n";
}

int main(int argc, char** argv) {
  try {
    Require(argc == 2, "Usage: q2_ple_io MODEL|--fixture");
    if (std::string(argv[1]) == "--fixture") {
      Fixture();
      return 0;
    }
    std::cout << std::unitbuf << std::setprecision(12);
    std::string error;
    auto reader = gufo::core::GgufReader::OpenFile(argv[1], &error);
    Require(bool(reader), error);
    auto weights = q::ModelWeights::Bind(*reader, &error);
    Require(bool(weights), error);
    const auto& c = weights->config;
    const auto& t = weights->ple_table;
    const auto& region = reader->GetMappedRegions()[t.shard];
    struct stat st{};
    Require(
        ::fstat(region.file_descriptor, &st) == 0 && st.st_uid == ::geteuid(),
        "Residency observation requires ownership of the readable model file");
    std::vector<float> out(2048 * c.PleEmbeddingDim());
    const auto row_bytes = t.type == gufo::core::GgmlType::kBF16
                               ? c.ple_head_dim * 2
                               : c.ple_head_dim / 32 * 18;
    for (const std::string campaign : {"advice", "capacity"}) {
      if (campaign == "capacity" && t.type != gufo::core::GgmlType::kBF16)
        continue;
      const int pairs = campaign == "advice" ? 8 : 4;
      const int reps = campaign == "advice" ? 2 : 4;
      for (int pair = 0; pair < pairs; ++pair) {
        const auto seed = 0x10f0001u + pair * 0x2345u;
        const auto tokens = Tokens(seed);
        q::NgramHistory history;
        std::vector<std::uint32_t> rows(tokens.size() * c.ple_heads);
        q::HashNgramRows(c, history, tokens, rows);
        const auto pages = Pages(rows, t.file_offset, row_bytes);
        const auto input_hash = Hash<std::int32_t>(tokens);
        std::string first_hash;
        for (int position = 0; position < 2; ++position) {
          // ABBA order of first policies across disjoint row sets. Identical
          // second-policy reads prove bytes; resident-page counts expose
          // warming.
          const bool candidate =
              position ^ ((pair % 4 == 1) || (pair % 4 == 2));
          q2pleio::advice = campaign == "advice" && candidate
                                ? POSIX_FADV_RANDOM
                                : POSIX_FADV_NORMAL;
          q2pleio::bf16_cache_budget = campaign == "capacity" && candidate
                                           ? 32u * 1024 * 1024
                                           : 8u * 1024 * 1024;
          auto table =
              q::NgramTable::Open(region.file_descriptor, t.file_offset, t.rows,
                                  c.ple_head_dim, t.type, &error);
          Require(bool(table), error);
          Require(q2pleio::advice_result == 0,
                  "Reader descriptor advice failed");
          for (int rep = 0; rep < reps; ++rep) {
            const auto resident_before = Resident(region, pages);
            q2ple::Reset();
            const auto bytes_before = ReadBytes();
            const auto start = Clock::now();
            Require(table->Read(rows, out), "Original-row gather failed");
            const auto seconds =
                std::chrono::duration<double>(Clock::now() - start).count();
            const auto bytes_after = ReadBytes();
            const auto stats = q2ple::Read();
            Require(stats[q2ple::cache_hits] + stats[q2ple::io_rows] ==
                        stats[q2ple::unique_rows],
                    "Row accounting differs");
            const auto resident_after = Resident(region, pages);
            for (float value : out)
              Require(std::isfinite(value), "Non-finite embedding row");
            const auto digest = Hash<float>(out);
            if (first_hash.empty())
              first_hash = digest;
            Require(first_hash == digest,
                    "Access policy changed embedding bytes");
            std::cout << "{\"event\":\"io\",\"campaign\":\"" << campaign
                      << "\",\"pair\":" << pair << ",\"position\":" << position
                      << ",\"candidate\":" << (candidate ? "true" : "false")
                      << ",\"rep\":" << rep << ",\"seed\":" << seed
                      << ",\"seconds\":" << seconds
                      << ",\"type\":" << static_cast<int>(t.type)
                      << ",\"cache_slots\":" << q2ple::cache_slots
                      << ",\"cache_bytes\":" << q2ple::cache_bytes
                      << ",\"advice\":" << q2pleio::advice
                      << ",\"direct_open\":"
                      << (q2ple::direct ? "true" : "false")
                      << ",\"page_count\":" << pages.size()
                      << ",\"resident_before\":" << resident_before
                      << ",\"resident_after\":" << resident_after
                      << ",\"physical_read_bytes\":"
                      << bytes_after - bytes_before << ",\"input_sha256\":\""
                      << input_hash << "\",\"embedding_sha256\":\"" << digest
                      << "\",\"ple\":";
            q2ple::Json(std::cout, stats);
            std::cout << "}\n";
          }
        }
      }
    }
    std::cout << "{\"event\":\"complete\",\"scope\":\"original_rows_only_no_"
                 "model_forward\"}\n";
  } catch (const std::exception& ex) {
    std::cerr << "FAIL: " << ex.what() << '\n';
    return 1;
  }
}
