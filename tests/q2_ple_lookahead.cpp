// SPDX-License-Identifier: MIT
// Original-weight scheduling A/B, synthetic varied tokens, AR prefill only.
#include <sys/mman.h>
#include <unistd.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <span>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#include "ple_flow.h"
#include "src/core/crypto/sha256.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/executor.hpp"

namespace q = gufo::models::qwen38_flash_next;
using Exec = q::rocm::Executor;
using Clock = std::chrono::steady_clock;
constexpr std::size_t kChunk = 2048, kChunks = 4, kDecode = 32;
constexpr std::size_t kPrompt = kChunk * kChunks;

static void Require(bool good, const std::string &why) {
  if (!good)
    throw std::runtime_error(why);
}
static double Seconds(Clock::time_point start) {
  return std::chrono::duration<double>(Clock::now() - start).count();
}
static void FillTokens(std::span<std::int32_t> tokens, std::uint32_t seed) {
  for (auto &token : tokens) {
    seed ^= seed << 13;
    seed ^= seed >> 17;
    seed ^= seed << 5;
    token = 256 + seed % 100000;
  }
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
static std::vector<std::uint64_t> Pages(std::span<const std::uint32_t> rows,
                                        std::uint64_t offset,
                                        std::size_t bytes) {
  Require(::sysconf(_SC_PAGESIZE) == 4096, "Diagnostic requires 4-KiB pages");
  std::vector<std::uint64_t> pages;
  pages.reserve(rows.size() * 2);
  for (auto row : rows) {
    const auto first = offset + row * bytes;
    pages.push_back(first / 4096);
    pages.push_back((first + bytes - 1) / 4096);
  }
  std::sort(pages.begin(), pages.end());
  pages.erase(std::unique(pages.begin(), pages.end()), pages.end());
  return pages;
}
static std::size_t Resident(const gufo::core::GgufMappedRegion &region,
                            std::span<const std::uint64_t> pages) {
  // Observe only: no deliberate page faults, eviction or advice changes.
  // Every residency check is outside the prefill and decode timers.
  std::size_t resident = 0;
  for (auto page : pages) {
    Require(page * 4096 < region.size, "Page outside mapped file");
    auto *address = const_cast<std::uint8_t *>(
                        static_cast<const std::uint8_t *>(region.data)) +
                    page * 4096;
    unsigned char value = 0;
    Require(::mincore(address, 4096, &value) == 0, "mincore failed");
    resident += value & 1;
  }
  return resident;
}
template <typename T> static std::string Hash(std::span<const T> values) {
  return gufo::crypto::Sha256Hex(
      std::span(reinterpret_cast<const std::uint8_t *>(values.data()),
                values.size_bytes()));
}
template <typename T>
static void Save(const std::string &name, std::span<const T> values) {
  std::ofstream file("results/" + name, std::ios::binary);
  file.write(reinterpret_cast<const char *>(values.data()),
             values.size_bytes());
  Require(bool(file), "Cannot save PLE lookahead evidence");
}
[[noreturn]] static void Undrained() {
  // This process owns its allocations. A failed HIP fence cannot authorize
  // host-buffer reuse or destructor frees; retain the failure and retire it.
  std::fputs("FAIL: prepared HIP input did not drain; retiring owned process\n",
             stderr);
  std::fflush(nullptr);
  std::_Exit(3);
}

struct Buffers {
  std::array<void *, 2> data{};
  std::size_t row_bytes, slot_bytes;
  explicit Buffers(const q::Config &c)
      : row_bytes(kChunk * c.ple_heads * sizeof(std::uint32_t)),
        slot_bytes(row_bytes + kChunk * c.PleEmbeddingDim() * sizeof(float)) {
    for (auto &p : data) {
      if (hipHostMalloc(&p, slot_bytes) != hipSuccess) {
        for (auto old : data)
          if (old)
            (void)hipHostFree(old);
        throw std::runtime_error("Cannot allocate bounded pinned PLE slots");
      }
    }
  }
  ~Buffers() {
    for (auto p : data)
      (void)hipHostFree(p);
  }
  Buffers(const Buffers &) = delete;
  Buffers &operator=(const Buffers &) = delete;
  std::span<std::uint32_t> Rows(void *slot) const {
    return {static_cast<std::uint32_t *>(slot),
            row_bytes / sizeof(std::uint32_t)};
  }
  std::span<float> Embeddings(void *slot) const {
    return {reinterpret_cast<float *>(static_cast<char *>(slot) + row_bytes),
            (slot_bytes - row_bytes) / sizeof(float)};
  }
};

struct Interval {
  double begin{0}, end{0};
};
struct Context {
  const q::Config &config;
  q::NgramTable &table;
  Exec &executor;
  q::rocm::Session &session;
  const Buffers &buffers;
  std::span<const std::int32_t> tokens;
  std::vector<float> &logits;
  Clock::time_point start;
  q::NgramHistory history;
  std::array<Interval, kChunks> prepare_times{}, consume_times{};
  // Written by separate callback threads; inspected only after C flow drains.
  std::string producer_error, consumer_error;

  std::span<const std::int32_t> Tokens(std::size_t chunk) const {
    return tokens.subspan(chunk * kChunk, kChunk);
  }
  static int Prepare(void *opaque, std::size_t chunk, void *slot) {
    auto &c = *static_cast<Context *>(opaque);
    try {
      c.prepare_times[chunk].begin = Seconds(c.start);
      auto rows = c.buffers.Rows(slot);
      q::HashNgramRows(c.config, c.history, c.Tokens(chunk), rows);
      const bool ok = c.table.Read(rows, c.buffers.Embeddings(slot));
      c.prepare_times[chunk].end = Seconds(c.start);
      if (!ok)
        c.producer_error = "PLE producer read failed";
      return ok ? 0 : 1;
    } catch (const std::exception &ex) {
      try {
        c.producer_error = ex.what();
      } catch (...) {
      }
      return 1;
    } catch (...) {
      return 1;
    }
  }
  static int Consume(void *opaque, std::size_t chunk, const void *slot) {
    auto &c = *static_cast<Context *>(opaque);
    bool released = true;
    try {
      c.consume_times[chunk].begin = Seconds(c.start);
      // Const spans are borrowed by the executor; buffer lifetime belongs to C.
      const bool ok = c.executor.ForwardPrepared(
          c.session, c.Tokens(chunk), 1,
          c.logits.data() + chunk * c.config.vocab_size,
          c.buffers.Rows(const_cast<void *>(slot)),
          c.buffers.Embeddings(const_cast<void *>(slot)), &released,
          &c.consumer_error);
      c.consume_times[chunk].end = Seconds(c.start);
      if (!released)
        Undrained();
      return ok ? 0 : 1;
    } catch (const std::exception &ex) {
      if (!released)
        Undrained();
      try {
        c.consumer_error = ex.what();
      } catch (...) {
      }
      return 1;
    } catch (...) {
      if (!released)
        Undrained();
      return 1;
    }
  }
};

static void RejectStale(Exec &exec, q::rocm::Session &session,
                        Context &context) {
  auto rows = context.buffers.Rows(context.buffers.data[0]);
  auto embeddings = context.buffers.Embeddings(context.buffers.data[0]);
  q::NgramHistory history;
  q::HashNgramRows(context.config, history, context.Tokens(0), rows);
  ++rows[0];
  const auto epoch = session.MutationEpoch();
  std::string error;
  bool released = false;
  Require(!exec.ForwardPrepared(session, context.Tokens(0), 0, nullptr, rows,
                                embeddings, &released, &error) &&
              released && session.MutationEpoch() == epoch &&
              !session.position(),
          "Stale PLE rows mutated session or retained input");
  error.clear();
  Require(!exec.ForwardPrepared(session, context.Tokens(0), 0, nullptr,
                                rows.first(rows.size() - 1), embeddings,
                                &released, &error) &&
              released && session.MutationEpoch() == epoch &&
              !session.position(),
          "Malformed PLE input mutated session");
}

int main(int argc, char **argv) {
  try {
    Require(argc == 2 ||
                (argc == 3 && std::string(argv[2]) == "--first-access"),
            "Usage: q2_ple_lookahead MODEL [--first-access]");
    const bool first_access = argc == 3;
    std::cout << std::unitbuf << std::setprecision(12);
    std::string error;
    auto reader = gufo::core::GgufReader::OpenFile(argv[1], &error);
    Require(bool(reader), error);
    auto weights = q::ModelWeights::Bind(*reader, &error);
    Require(bool(weights), error);
    auto device = q::rocm::DeviceModel::Upload(*weights, *reader, nullptr,
                                               nullptr, &error);
    Require(bool(device), error);
    const auto &config = weights->config;
    const auto &tensor = weights->ple_table;
    Require(config.ple_layer >= 0 && config.vocab_size > 100256,
            "Unexpected original PLE model geometry");
    Buffers buffers(config);
    std::vector<std::int32_t> tokens(kPrompt + kDecode);
    FillTokens(tokens, 0x734ec92u);
    if (first_access) {
      Require(tensor.type == gufo::core::GgmlType::kBF16,
              "First-access probe requires original BF16 PLE rows");
      // Warm execution paths on a disjoint padding prompt before assigning
      // first position to either arm. Fresh tables/sessions follow below.
      auto table = q::NgramTable::Open(
          reader->GetMappedRegions()[tensor.shard].file_descriptor,
          tensor.file_offset, tensor.rows, config.ple_head_dim, tensor.type,
          &error);
      Require(bool(table), error);
      Exec::Options options;
      options.max_batch = kChunk;
      auto exec = Exec::Create(*device, table.get(), options, &error);
      Require(bool(exec), error);
      auto session = exec->CreateSession(
          gufo::core::SessionMode::kAutoregressive, kPrompt + kDecode, &error);
      Require(bool(session), error);
      std::vector<std::int32_t> padding(kPrompt + kDecode, 256);
      std::vector<float> logits(config.vocab_size);
      const auto start = Clock::now();
      for (std::size_t chunk = 0; chunk < kChunks; ++chunk)
        Require(
            exec->Forward(*session,
                          std::span(padding).subspan(chunk * kChunk, kChunk), 1,
                          logits.data(), Exec::ForwardMode::kPrefill, &error),
            error);
      for (std::size_t step = 0; step < kDecode; ++step)
        Require(exec->Forward(
                    *session, std::span(padding).subspan(kPrompt + step, 1), 1,
                    logits.data(), Exec::ForwardMode::kDecode, &error),
                error);
      Require(std::all_of(logits.begin(), logits.end(),
                          [](float x) { return std::isfinite(x); }),
              "Non-finite warmup output");
      std::cout << "{\"event\":\"warmup\",\"padding_id\":256,\"seconds\":"
                << Seconds(start) << ",\"finite\":true}\n";
    }
    if (!first_access)
      Save<std::int32_t>("lookahead-input.i32", tokens);
    std::cout << "{\"event\":\"configuration\",\"prompt\":" << kPrompt
              << ",\"chunk\":" << kChunk << ",\"forced_decode\":" << kDecode
              << ",\"slot_bytes\":" << buffers.slot_bytes
              << ",\"reserved_bytes\":"
              << lie_ple_flow_bytes(buffers.slot_bytes) << ",\"input_sha256\":"
              << (first_access ? "null"
                               : "\"" + Hash<std::int32_t>(tokens) + "\"")
              << ",\"global_cache_flush\":false,\"synthetic_tokens\":true"
              << ",\"protocol\":\""
              << (first_access ? "first-access-v1" : "repeated-v1")
              << "\",\"sets\":" << (first_access ? 8 : 1) << "}\n";
    std::vector<float> reference;
    bool exact_all = true;
    // First accesses are retained separately, then rotate all three arms so
    // each occupies every measured order position. No global page eviction.
    const std::vector<std::vector<int>> orders =
        first_access
            ? std::vector<std::vector<int>>{{0, 2}, {2, 0}, {2, 0}, {0, 2},
                                            {0, 2}, {2, 0}, {2, 0}, {0, 2}}
            : std::vector<std::vector<int>>{
                  {0, 1, 2}, {0, 2, 1}, {1, 0, 2}, {2, 1, 0}};
    const std::array<const char *, 3> names{"native", "prepared_serial",
                                            "lookahead"};
    for (std::size_t rep = 0; rep < orders.size(); ++rep) {
      std::vector<std::uint64_t> pages;
      if (first_access) {
        const std::uint32_t seed =
            0xd17a4c39u + std::uint32_t(rep) * 0x09e3779bu;
        FillTokens(tokens, seed);
        reference.clear();
        Save<std::int32_t>(
            "first-access-set-" + std::to_string(rep) + "-input.i32", tokens);
        std::vector<std::uint32_t> rows(kPrompt * config.ple_heads);
        q::NgramHistory history;
        q::HashNgramRows(config, history, std::span(tokens).first(kPrompt),
                         rows);
        pages = Pages(rows, tensor.file_offset,
                      config.ple_head_dim * sizeof(std::uint16_t));
        std::cout << "{\"event\":\"input\",\"rep\":" << rep
                  << ",\"seed\":" << seed << ",\"first_mode\":\""
                  << names[orders[rep][0]] << "\",\"input_sha256\":\""
                  << Hash<std::int32_t>(tokens) << "\",\"rows_sha256\":\""
                  << Hash<std::uint32_t>(rows) << "\"}\n";
      }
      std::size_t order_position = 0;
      for (const auto mode : orders[rep]) {
        std::this_thread::sleep_for(std::chrono::seconds(5));
        auto table = q::NgramTable::Open(
            reader->GetMappedRegions()[tensor.shard].file_descriptor,
            tensor.file_offset, tensor.rows, config.ple_head_dim, tensor.type,
            &error);
        Require(bool(table), error);
        Exec::Options options;
        options.max_batch = kChunk;
        auto exec = Exec::Create(*device, table.get(), options, &error);
        Require(bool(exec), error);
        auto session =
            exec->CreateSession(gufo::core::SessionMode::kAutoregressive,
                                kPrompt + kDecode, &error);
        Require(bool(session), error);
        std::vector<float> logits((kChunks + kDecode) * config.vocab_size);
        Context context{config, *table,       *exec, *session, buffers, tokens,
                        logits, Clock::now(), {},    {},       {},      {},
                        {}};
        if (rep == 0 && mode == 0)
          RejectStale(*exec, *session, context);
        lie_ple_flow_stats stats{};
        const lie_ple_flow_options flow_options{
            kChunks,
            buffers.slot_bytes,
            lie_ple_flow_bytes(buffers.slot_bytes),
            {buffers.data[0], buffers.data[1]},
            &context,
            mode == 2,
            Context::Prepare,
            Context::Consume};
        lie_ple_flow *flow =
            mode ? lie_ple_flow_create(&flow_options) : nullptr;
        Require(!mode || flow, "Cannot admit bounded PLE flow");
        const auto resident_before =
            first_access
                ? Resident(reader->GetMappedRegions()[tensor.shard], pages)
                : 0;
        const auto read_before = first_access ? ReadBytes() : 0;
        context.start = Clock::now();
        bool good = true;
        if (mode == 0) {
          for (std::size_t chunk = 0; chunk < kChunks && good; ++chunk) {
            context.consume_times[chunk].begin = Seconds(context.start);
            good = exec->Forward(*session, context.Tokens(chunk), 1,
                                 logits.data() + chunk * config.vocab_size,
                                 Exec::ForwardMode::kPrefill, &error);
            context.consume_times[chunk].end = Seconds(context.start);
          }
        } else {
          good = lie_ple_flow_run(flow, &stats) == LIE_PLE_OK;
        }
        const double prefill_seconds = Seconds(context.start);
        const auto read_after = first_access ? ReadBytes() : 0;
        if (!good && !mode &&
            hipStreamSynchronize(exec->stream()) != hipSuccess)
          Undrained();
        if (flow)
          Require(lie_ple_flow_destroy(flow) == LIE_PLE_OK,
                  "Flow did not retire");
        std::cout << "{\"event\":\"prefill\",\"mode\":\"" << names[mode]
                  << "\",\"rep\":" << rep << ",\"first_access_observation\":"
                  << ((first_access ? order_position == 0 : rep == 0) ? "true"
                                                                      : "false")
                  << ",\"order_position\":" << order_position++
                  << ",\"seconds\":" << prefill_seconds
                  << ",\"tokens_per_second\":" << kPrompt / prefill_seconds
                  << ",\"good\":" << (good ? "true" : "false")
                  << ",\"flow_status\":" << stats.status
                  << ",\"prepared\":" << stats.prepared
                  << ",\"consumed\":" << stats.consumed
                  << ",\"prepare_ns\":" << stats.prepare_ns
                  << ",\"consume_ns\":" << stats.consume_ns
                  << ",\"consumer_wait_ns\":" << stats.consumer_wait_ns
                  << ",\"peak_owned_slots\":" << stats.peak_owned_slots
                  << "}\n";
        Require(good, error + context.producer_error + context.consumer_error);
        Require(session->position() == kPrompt, "Prefill position differs");
        if (first_access) {
          Require(read_after >= read_before, "Process read counter decreased");
          std::cout << "{\"event\":\"io\",\"mode\":\"" << names[mode]
                    << "\",\"rep\":" << rep
                    << ",\"requested_pages\":" << pages.size()
                    << ",\"resident_before\":" << resident_before
                    << ",\"resident_after\":"
                    << Resident(reader->GetMappedRegions()[tensor.shard], pages)
                    << ",\"process_read_bytes\":" << read_after - read_before
                    << "}\n";
        }
        for (std::size_t chunk = 0; chunk < kChunks; ++chunk) {
          std::cout << "{\"event\":\"interval\",\"mode\":\"" << names[mode]
                    << "\",\"rep\":" << rep << ",\"chunk\":" << chunk
                    << ",\"prepare_begin\":"
                    << context.prepare_times[chunk].begin
                    << ",\"prepare_end\":" << context.prepare_times[chunk].end
                    << ",\"consume_begin\":"
                    << context.consume_times[chunk].begin
                    << ",\"consume_end\":" << context.consume_times[chunk].end
                    << "}\n";
        }
        double decode_seconds = 0;
        for (std::size_t step = 0; step < kDecode; ++step) {
          const auto begin = Clock::now();
          Require(exec->Forward(
                      *session, std::span(tokens).subspan(kPrompt + step, 1), 1,
                      logits.data() + (kChunks + step) * config.vocab_size,
                      Exec::ForwardMode::kDecode, &error),
                  error);
          decode_seconds += Seconds(begin);
        }
        bool finite =
            std::all_of(logits.begin(), logits.end(),
                        [](float value) { return std::isfinite(value); });
        if (reference.empty()) {
          reference = logits;
          Save<float>(first_access ? "first-access-set-" + std::to_string(rep) +
                                         "-reference-all.f32"
                                   : "lookahead-native-all.f32",
                      reference);
        }
        const bool exact = !std::memcmp(reference.data(), logits.data(),
                                        logits.size() * sizeof(float));
        exact_all = exact_all && exact && finite;
        const auto prefix =
            std::string(names[mode]) + "-" + std::to_string(rep);
        Save<float>(prefix + "-prefill.f32",
                    std::span(logits).subspan((kChunks - 1) * config.vocab_size,
                                              config.vocab_size));
        Save<float>(prefix + "-last.f32",
                    std::span(logits).last(config.vocab_size));
        std::cout << "{\"event\":\"comparison\",\"mode\":\"" << names[mode]
                  << "\",\"rep\":" << rep
                  << ",\"all_exact\":" << (exact ? "true" : "false")
                  << ",\"finite\":" << (finite ? "true" : "false")
                  << ",\"decode_seconds\":" << decode_seconds
                  << ",\"output_sha256\":\"" << Hash<float>(logits) << "\"}\n";
        for (std::size_t row = 0; row < kChunks + kDecode; ++row)
          std::cout << "{\"event\":\"frontier\",\"mode\":\"" << names[mode]
                    << "\",\"rep\":" << rep << ",\"row\":" << row
                    << ",\"sha256\":\""
                    << Hash<float>(std::span(logits).subspan(
                           row * config.vocab_size, config.vocab_size))
                    << "\"}\n";
        if (rep == orders.size() - 1 && mode == 0) {
          // Real in-flight cancellation, after at least one layer admission.
          auto cancelled =
              exec->CreateSession(gufo::core::SessionMode::kAutoregressive,
                                  kPrompt + kDecode, &error);
          Require(bool(cancelled), error);
          Context probe{
              config,       *table, *exec, *cancelled, buffers, tokens, logits,
              Clock::now(), {},     {},    {},         {},      {}};
          Require(!Context::Prepare(&probe, 0, buffers.data[0]),
                  probe.producer_error);
          unsigned checks = 0;
          cancelled->SetCancellationCheck([&] { return ++checks >= 3; });
          bool released = true;
          bool ok = exec->ForwardPrepared(
              *cancelled, probe.Tokens(0), 1, logits.data(),
              buffers.Rows(buffers.data[0]),
              buffers.Embeddings(buffers.data[0]), &released, &error);
          if (!released)
            Undrained();
          Require(!ok && cancelled->Cancelled() && checks >= 3,
                  "In-flight prepared cancellation was not observed");
          std::cout << "{\"event\":\"cancellation\",\"input_released\":true,"
                       "\"checks\":"
                    << checks << "}\n";
        }
      }
    }
    std::cout << "{\"event\":\"complete\",\"all_exact\":"
              << (exact_all ? "true" : "false")
              << ",\"full_context_acceptance\":false}\n";
    return exact_all ? 0 : 1;
  } catch (const std::exception &ex) {
    std::cerr << "FAIL: " << ex.what() << '\n';
    return 1;
  }
}
