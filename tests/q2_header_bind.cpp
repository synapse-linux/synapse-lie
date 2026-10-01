// SPDX-License-Identifier: MIT
// Actual-header-derived host binding probe, NOT-INFERENCE / NOT-MODEL-LOAD.
// Only a bounded saved header is read. All declared tensor payload addresses
// refer to an anonymous PROT_NONE virtual region; no tensor values are present.
#include "src/models/qwen38_flash_next/weights.hpp"
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <unistd.h>

#include <charconv>
#include <cstring>
#include <iostream>
#include <stdexcept>

#ifdef LIE_Q2_MODEL_TEST_PLAN
#include "q2_model_memory.h"
int lie_q2_model_plan_from_reader(const gufo::core::GgufReader&,
                                 lie_q2_test_memory*, std::string*);
#endif

namespace q = gufo::models::qwen38_flash_next;
using gufo::core::GgmlType;
static void require(bool ok, const std::string &why) {
  if (!ok)
    throw std::runtime_error(why);
}
static std::uint64_t number(const char *s) {
  std::uint64_t n = 0;
  const auto end = s + std::strlen(s);
  const auto result = std::from_chars(s, end, n);
  require(result.ec == std::errc{} && result.ptr == end,
          "invalid decimal argument");
  return n;
}
struct Mapping {
  void *address = MAP_FAILED;
  std::size_t length = 0;
  ~Mapping() {
    if (address != MAP_FAILED)
      munmap(address, length);
  }
};
struct File {
  int fd = -1;
  ~File() {
    if (fd >= 0)
      close(fd);
  }
};
int main(int argc, char **argv) {
  try {
    require(
        argc == 4,
        "Usage: q2-header-bind SAVED-HEADER DECLARED-FILE-BYTES DATA-START");
    const rlimit no_core{0, 0};
    require(setrlimit(RLIMIT_CORE, &no_core) == 0, "core limit");
    const auto file_bytes = number(argv[2]), data_start = number(argv[3]);
    File f{open(argv[1], O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK)};
    require(f.fd >= 0, "header open failed");
    struct stat st{};
    require(fstat(f.fd, &st) == 0 && S_ISREG(st.st_mode) && st.st_size > 0 &&
                st.st_size <= 24 * 1024 * 1024,
            "bounded regular saved header required");
    const auto header_bytes = static_cast<std::size_t>(st.st_size);
    require(data_start >= header_bytes &&
                data_start - header_bytes < 1024 * 1024 &&
                data_start < file_bytes &&
                file_bytes <= 256ull * 1024 * 1024 * 1024,
            "header/file extent bounds");
    const auto page_result = sysconf(_SC_PAGESIZE);
    require(page_result > 0, "page size");
    const auto page = static_cast<std::size_t>(page_result);
    // Shift the logical file base so the declared data region starts on an OS
    // page boundary. Even the FIRST payload byte is inaccessible.
    const auto shift = (page - data_start % page) % page;
    Mapping mapping;
    mapping.length = file_bytes + shift;
    mapping.address = mmap(nullptr, mapping.length, PROT_NONE,
                           MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
    require(mapping.address != MAP_FAILED,
            "virtual reservation failed (not RAM-fit evidence)");
    const auto readable = static_cast<std::size_t>(data_start + shift);
    require(mprotect(mapping.address, readable, PROT_READ | PROT_WRITE) == 0,
            "header protection setup");
    auto *base = static_cast<std::uint8_t *>(mapping.address) + shift;
    std::size_t done = 0;
    while (done < header_bytes) {
      const auto n = read(f.fd, base + done, header_bytes - done);
      require(n > 0, "saved header read failed");
      done += static_cast<std::size_t>(n);
    }
    require(mprotect(mapping.address, readable, PROT_READ) == 0,
            "read-only header setup");
    std::string error;
    auto reader = gufo::core::GgufReader::OpenMemory(base, file_bytes, &error);
    require(reader != nullptr, "reader refused actual saved header: " + error);
    require(reader->GetAlignment() == 32 &&
                data_start == (header_bytes + 31) / 32 * 32,
            "data boundary must match parsed header alignment");
    auto weights = q::ModelWeights::Bind(*reader, &error);
    require(weights.has_value(),
            "binder refused actual saved header: " + error);
    require(reader->GetTensorCount() == 1256 && weights->layers.size() == 48 &&
                weights->config.expert_ff == 640,
            "actual Q2 architecture identity");
    for (const auto &layer : weights->layers) {
      require(layer.ffn_gate_exps.type == GgmlType::kIQ2_XXS &&
                  layer.ffn_up_exps.type == GgmlType::kIQ2_XXS &&
                  layer.ffn_down_exps.type == GgmlType::kQ2_K,
              "Q2 routed formats");
      const auto &down = layer.ffn_down_exps;
      require(down.cols == 768 && down.rows == 2560 && down.experts == 512 &&
                  down.RowBytes() == 252 && down.SizeBytes() == 330301440,
              "physical Q2 strides");
      require(down.Expert(1) - down.Expert(0) == 645120, "Q2 expert stride");
      require(layer.hc_attn.inject.type == GgmlType::kF16 &&
                  layer.hc_ffn.inject.type == GgmlType::kF16,
              "actual F16 inject");
    }
    require(weights->ple_table.type == GgmlType::kBF16 &&
                weights->ple_table.SizeBytes() == 102400491520ull,
            "actual PLE view");
#ifdef LIE_Q2_MODEL_TEST_PLAN
    lie_q2_test_memory plan{};
    require(lie_q2_model_plan_from_reader(*reader, &plan, &error) != 0,
            "first-test memory plan refused saved header: " + error);
    require(!lie_q2_test_memory_active(), "planning must not enable allocation");
    std::cout << "{\"state\":\"Q2_SAVED_HEADER_TEST_PLAN_NOT_RESIDENT_FIT\","
              << "\"ple_addressed\":" << plan.ple_addressed
              << ",\"weight_upper\":" << plan.weight_upper
              << ",\"allocation_limit\":" << plan.allocation_limit
              << ",\"host_allowance\":" << plan.host_allowance
              << ",\"system_reserve\":" << plan.system_reserve
              << ",\"required_available\":" << plan.required_available << "}\n";
#endif
    // Reader/weights are destroyed before Mapping. No model forward exists
    // here.
    std::cout << "{\"state\":\"ACTUAL_Q2_HEADER_BINDING_PASS_NOT_MODEL_LOAD_OR_"
                 "INFERENCE\","
              << "\"header_bytes\":" << header_bytes
              << ",\"tensor_count\":1256,\"trunk_layers\":48,"
              << "\"logical_down_input\":640,\"physical_down_input\":768,"
              << "\"row_bytes\":252,\"expert_bytes\":645120,\"payload_"
                 "protected\":true,"
              << "\"tensor_values_present\":false,\"gpu_execution\":false,"
                 "\"memory_fit_assessed\":false}\n";
    return 0;
  } catch (const std::exception &e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
}
