// SPDX-License-Identifier: MIT
// CPU fixture: cached rows survive colliding disk misses within one gather.
#include "src/models/qwen38_flash_next/ngram.hpp"

#include <fcntl.h>
#include <unistd.h>

#include <array>
#include <atomic>
#include <bit>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <span>
#include <vector>

namespace {
constexpr std::uint32_t kDim = 160, kCold = 1024, kWarm = 128, kHigh = 65536;
constexpr off_t kOffset = 4096 + 90;
constexpr float kGuard = -12345.0f;
constexpr std::array<int, 16> kIQ4{-127, -104, -83, -65, -49, -35, -22, -10,
                                   1,    13,   25,  38,  53,  69,  89,  113};
std::atomic<std::size_t> calls{0}, high_calls{0};
off_t high_offset = 0;

void Require(bool condition, const char *message) {
  if (!condition) {
    std::fprintf(stderr, "FAIL: %s\n", message);
    std::exit(1);
  }
}

float Expected(std::uint32_t row, std::uint32_t col, bool iq4) {
  // Colliding low/high IDs must contain different values: checking only low
  // row bits would hide a wrong cache-key match in this fixture.
  row += 7 * (row >> 16) + 3 * (row >> 8);
  if (!iq4) {
    return static_cast<float>(static_cast<int>((row * 17 + col * 3) % 128) -
                              64);
  }
  const auto block = col / 32, lane = col % 32;
  const auto index = lane < 16 ? (row + block * 3 + lane) % 16
                               : (row + block * 5 + lane - 16 + 7) % 16;
  return static_cast<float>(kIQ4[index]);
}

void WriteRows(int fd, std::uint32_t first, std::uint32_t count, bool iq4) {
  const std::size_t row_bytes = iq4 ? 90 : 320;
  std::vector<std::uint8_t> bytes(count * row_bytes);
  for (std::uint32_t r = 0; r < count; ++r) {
    auto *dst = bytes.data() + r * row_bytes;
    if (iq4) {
      const auto seed =
          first + r + 7 * ((first + r) >> 16) + 3 * ((first + r) >> 8);
      for (std::uint32_t block = 0; block < 5; ++block) {
        dst[block * 18] = 0;
        dst[block * 18 + 1] = 0x3c; // Independent IEEE half +1 scale.
        for (std::uint32_t j = 0; j < 16; ++j) {
          dst[block * 18 + 2 + j] = ((seed + block * 3 + j) % 16) |
                                    (((seed + block * 5 + j + 7) % 16) << 4);
        }
      }
    } else {
      for (std::uint32_t col = 0; col < kDim; ++col) {
        const auto bits = static_cast<std::uint16_t>(
            std::bit_cast<std::uint32_t>(Expected(first + r, col, false)) >>
            16);
        std::memcpy(dst + col * 2, &bits, sizeof(bits));
      }
    }
  }
  Require(
      ::pwrite(fd, bytes.data(), bytes.size(), kOffset + first * row_bytes) ==
          static_cast<ssize_t>(bytes.size()),
      "write private fixture rows");
}

void CheckRows(std::span<const std::uint32_t> rows,
               const std::vector<float> &out, bool iq4) {
  Require(out.front() == kGuard && out.back() == kGuard, "output guards");
  for (std::size_t i = 0; i < rows.size(); ++i) {
    for (std::uint32_t col = 0; col < kDim; ++col) {
      Require(out[1 + i * kDim + col] == Expected(rows[i], col, iq4),
              "independent decoded row and duplicate order");
    }
  }
}

void Exercise(bool iq4, bool require_cache_first) {
  namespace q = gufo::models::qwen38_flash_next;
  using gufo::core::GgmlType;
  for (std::uint32_t r = 0; r < kWarm; ++r) {
    Require(Expected(r, 0, iq4) != Expected(kHigh + r, 0, iq4),
            "colliding fixture rows must have distinct data");
  }
  char name[] = "/tmp/lie-ple-cache-first-XXXXXX";
  const int fd = ::mkstemp(name);
  Require(fd >= 0, "create private fixture");
  Require(::unlink(name) == 0, "unlink private fixture");
  const std::size_t row_bytes = iq4 ? 90 : 320;
  high_offset = kOffset + kHigh * row_bytes;
  Require(::ftruncate(fd, kOffset + (kHigh + kWarm) * row_bytes) == 0,
          "size sparse private fixture");
  WriteRows(fd, 0, kCold, iq4);
  WriteRows(fd, kHigh, kWarm, iq4);
  auto table = q::NgramTable::Open(fd, kOffset, kHigh + kWarm, kDim,
                                   iq4 ? GgmlType::kIQ4_NL : GgmlType::kBF16);
  Require(table != nullptr, "open private PLE table");
  std::vector<std::uint32_t> warm;
  for (std::uint32_t r = 0; r < kWarm; ++r) {
    warm.push_back(kHigh + r);
  }
  std::vector<float> warm_out(warm.size() * kDim + 2, kGuard);
  Require(table->Read(warm, std::span(warm_out).subspan(1, warm.size() * kDim)),
          "prime distinct high rows");
  CheckRows(warm, warm_out, iq4);

  // The high rows alias the earliest cold rows at both production capacities.
  // Interleave input order, add duplicates, and require independent row values.
  std::vector<std::uint32_t> rows;
  for (std::uint32_t r = 0; r < kCold; ++r) {
    rows.push_back(r);
    if (r < kWarm) {
      rows.push_back(kHigh + r);
      rows.push_back(kHigh + r);
      rows.push_back(r);
    }
  }
  calls = 0;
  high_calls = 0;
  std::vector<float> out(rows.size() * kDim + 2, kGuard);
  Require(table->StartRead(rows, std::span(out).subspan(1, rows.size() * kDim)),
          "start mixed colliding gather");
  Require(!table->StartRead({}, {}), "reject overlapping gather");
  Require(table->WaitRead(), "finish mixed colliding gather");
  Require(!table->WaitRead(), "reject second completion");
  CheckRows(rows, out, iq4);
  const auto rereads = high_calls.load();
  std::printf("{\"fixture\":\"ple-cache-first\",\"format\":\"%s\","
              "\"unique_cold_rows\":%u,\"resident_rows\":%u,"
              "\"pread_calls\":%zu,\"resident_pread_calls\":%zu,"
              "\"exact_rows\":true,\"strict\":%s}\n",
              iq4 ? "IQ4_NL" : "BF16", kCold, kWarm, calls.load(), rereads,
              require_cache_first ? "true" : "false");
  Require(!require_cache_first || rereads == 0,
          "no resident row reread during colliding gather");

  // A wholly cached large gather must not read the backing file again.
  rows.clear();
  for (std::uint32_t r = 0; r < kCold; ++r) {
    rows.push_back(r);
  }
  Require(table->Read(rows, std::span(out).subspan(1, rows.size() * kDim)),
          "prime complete low range");
  out.assign(rows.size() * kDim + 2, kGuard);
  calls = 0;
  Require(table->Read(rows, std::span(out).subspan(1, rows.size() * kDim)),
          "repeat complete low range");
  Require(calls == 0, "fully cached large gather performs no pread");
  CheckRows(rows, out, iq4);
  table.reset();
  Require(::close(fd) == 0, "close private fixture");
}
} // namespace

extern "C" ssize_t __real_pread(int, void *, size_t, off_t);
extern "C" ssize_t __wrap_pread(int fd, void *buf, size_t count, off_t offset) {
  calls.fetch_add(1, std::memory_order_relaxed);
  if (offset >= high_offset - 4096) {
    high_calls.fetch_add(1, std::memory_order_relaxed);
  }
  return __real_pread(fd, buf, count, offset);
}

int main(int argc, char **argv) {
  const bool control = argc == 2 && std::strcmp(argv[1], "--control") == 0;
  Require(argc == 1 || control, "expected no arguments or --control");
  Exercise(false, !control);
  Exercise(true, !control);
  return 0;
}
