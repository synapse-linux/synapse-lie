// SPDX-License-Identifier: MIT
// GPU-only direct-executor qualification. This is not a serving frontend.
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <span>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#include "src/core/crypto/sha256.hpp"
#include "src/models/qwen/chat_template.hpp"
#include "src/models/qwen/tokenizer.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/executor.hpp"

namespace q = gufo::models::qwen38_flash_next;
namespace tok = gufo::tokenization;
using Clock = std::chrono::steady_clock;
using Exec = q::rocm::Executor;
void Q2ProfileMarker(int phase);

static void Require(bool good, const std::string &why) {
  if (!good)
    throw std::runtime_error(why);
}
static double Seconds(Clock::time_point start) {
  return std::chrono::duration<double>(Clock::now() - start).count();
}
static std::string Json(const std::string &s) {
  std::string out = "\"";
  constexpr char hex[] = "0123456789abcdef";
  for (unsigned char c : s) {
    if (c == '"' || c == '\\') {
      out += '\\';
      out += char(c);
    } else if (c < 32) {
      out += "\\u00";
      out += hex[c >> 4];
      out += hex[c & 15];
    } else
      out += char(c);
  }
  return out + '"';
}
template <class T>
static void Save(const std::string &name, std::span<const T> v) {
  std::ofstream f("results/" + name, std::ios::binary);
  f.write(reinterpret_cast<const char *>(v.data()),
          std::streamsize(v.size_bytes()));
  Require(bool(f), "Cannot save evidence");
}
static std::uint32_t Argmax(const std::vector<float> &logits) {
  for (float x : logits)
    Require(std::isfinite(x), "Non-finite logit frontier");
  return std::uint32_t(std::max_element(logits.begin(), logits.end()) -
                       logits.begin());
}
static std::vector<std::int32_t> Prompt(const tok::QwenTokenizer &tokenizer,
                                        const std::string &text) {
  std::string error;
  tok::ChatTemplateOptions options;
  options.enable_thinking = false;
  const std::vector<tok::ChatMessage> messages{{tok::ChatRole::kUser, text}};
  auto ids = tok::QwenChatTemplate::RenderAndTokenize(tokenizer, messages,
                                                      options, &error);
  Require(bool(ids), error);
  return {ids->begin(), ids->end()};
}
static std::vector<std::int32_t>
SizedPrompt(const tok::QwenTokenizer &tokenizer, std::size_t target) {
  std::size_t lo = 0, hi = target * 2;
  while (lo <= hi) {
    const auto n = lo + (hi - lo) / 2;
    std::string text = "Ignore this padding data:\n";
    for (std::size_t i = 0; i < n; ++i)
      text += "x ";
    text +=
        "\nCount from 1 to 200, separated by commas. Output only the numbers.";
    auto ids = Prompt(tokenizer, text);
    if (ids.size() == target)
      return ids;
    if (ids.size() < target)
      lo = n + 1;
    else {
      if (n == 0)
        break;
      hi = n - 1;
    }
  }
  throw std::runtime_error("Cannot construct exact physical prompt length");
}

int main(int argc, char **argv) {
  try {
    Require(argc == 3, "Usage: q2_model MODEL smoke|bench|bench2k|profile");
    const bool bench2k = std::string(argv[2]) == "bench2k";
    const bool bench = std::string(argv[2]) == "bench" || bench2k;
    const bool profile = std::string(argv[2]) == "profile";
    Require(bench || profile || std::string(argv[2]) == "smoke",
            "Unsupported profile");
    std::cout << std::unitbuf << std::setprecision(10);
    std::string error;
    const auto load_start = Clock::now();
    auto reader = gufo::core::GgufReader::OpenFile(argv[1], &error);
    Require(bool(reader), error);
    auto weights = q::ModelWeights::Bind(*reader, &error);
    Require(bool(weights), error);
    auto tokenizer = tok::QwenTokenizer::CreateFromGguf(*reader, &error);
    Require(bool(tokenizer), error);
    Require(tok::QwenChatTemplate::ValidateGgufTemplate(*reader, &error),
            error);
    const auto &c = weights->config;
    const auto &table = weights->ple_table;
    auto ngram = q::NgramTable::Open(
        reader->GetMappedRegions()[table.shard].file_descriptor,
        table.file_offset, table.rows, c.ple_head_dim, table.type, &error);
    Require(bool(ngram), error);
    std::cout << "{\"event\":\"bound\",\"model\":" << Json(argv[1]) << "}\n";
    auto device = q::rocm::DeviceModel::Upload(*weights, *reader, nullptr,
                                               nullptr, &error);
    Require(bool(device), error);
    Exec::Options options;
    options.max_batch = 2048;
    auto executor = Exec::Create(*device, ngram.get(), options, &error);
    Require(bool(executor), error);
    std::vector<float> logits(tokenizer->GetVocabSize());
    std::cout
        << "{\"event\":\"loaded\",\"seconds\":" << Seconds(load_start)
        << ",\"resident_bytes\":" << device->resident_bytes()
        << ",\"deferred_scratch_bytes\":" << executor->DeferredScratchBytes()
        << ",\"mtp\":false,\"max_context\":9216,\"prefill_chunk\":2048}\n";
    auto sample = [&](const std::string &label,
                      const std::vector<std::int32_t> &input, int rep,
                      int limit) {
      auto session = executor->CreateSession(
          gufo::core::SessionMode::kAutoregressive, 9216, &error);
      Require(bool(session), error);
      const bool trace = profile && label == "profile2048";
      if (trace)
        Q2ProfileMarker(0);
      const auto start = Clock::now();
      for (std::size_t offset = 0; offset < input.size();
           offset += options.max_batch) {
        const auto width =
            std::min<std::size_t>(options.max_batch, input.size() - offset);
        Require(executor->Forward(
                    *session, std::span(input).subspan(offset, width), 1,
                    logits.data(), Exec::ForwardMode::kPrefill, &error),
                error);
      }
      const double pp = Seconds(start);
      if (trace)
        Q2ProfileMarker(1);
      const auto prefix = label + "-" + std::to_string(rep);
      Save<float>(prefix + "-prefill.f32", logits);
      auto next = Argmax(logits);
      std::vector<std::uint32_t> output;
      bool eos = false;
      double tg = 0;
      int steps = 0;
      if (trace)
        Q2ProfileMarker(2);
      while (int(output.size()) < limit) {
        if (tokenizer->IsStopToken(next)) {
          eos = true;
          break;
        }
        output.push_back(next);
        if (int(output.size()) == limit)
          break;
        const std::int32_t token = std::int32_t(next);
        const auto step = Clock::now();
        Require(executor->Forward(*session, std::span(&token, 1), 1,
                                  logits.data(), Exec::ForwardMode::kDecode,
                                  &error),
                error);
        next = Argmax(logits);
        tg += Seconds(step);
        ++steps;
      }
      if (trace)
        Q2ProfileMarker(3);
      Save<float>(prefix + "-last.f32", logits);
      Save<std::uint32_t>(prefix + "-output.u32", output);
      const auto text = tokenizer->Decode(output);
      // Upstream diagnostic code changes the global stream's float precision.
      std::cout << std::defaultfloat << std::setprecision(10)
                << "{\"event\":\"sample\",\"label\":" << Json(label)
                << ",\"rep\":" << rep
                << ",\"warmup\":" << (rep == 0 ? "true" : "false")
                << ",\"prompt_tokens\":" << input.size()
                << ",\"output_tokens\":" << output.size()
                << ",\"decode_steps\":" << steps << ",\"prefill_s\":" << pp
                << ",\"decode_s\":" << tg
                << ",\"prefill_tok_s\":" << input.size() / pp
                << ",\"decode_steps_s\":" << (steps ? steps / tg : 0)
                << ",\"session_bytes\":" << session->AllocatedBytes()
                << ",\"eos\":" << (eos ? "true" : "false")
                << ",\"text\":" << Json(text) << "}\n";
      return text;
    };
    const auto arithmetic =
        Prompt(*tokenizer, "What is 19 + 23? Output only the integer.");
    Save<std::int32_t>("arithmetic-input.i32", arithmetic);
    auto answer = sample("arithmetic", arithmetic, 0, 32);
    answer.erase(std::remove_if(answer.begin(), answer.end(),
                                [](unsigned char x) { return x <= 32; }),
                 answer.end());
    Require(answer == "42", "Arithmetic smoke did not return exactly 42");
    const auto counting = Prompt(
        *tokenizer,
        "Count from 1 to 5 separated by commas. Output only the numbers.");
    Save<std::int32_t>("counting-input.i32", counting);
    answer = sample("counting", counting, 0, 32);
    answer.erase(std::remove_if(answer.begin(), answer.end(),
                                [](unsigned char x) { return x <= 32; }),
                 answer.end());
    Require(answer == "1,2,3,4,5", "Counting smoke returned unexpected output");
    if (profile) {
      const auto input = SizedPrompt(*tokenizer, 2048);
      Save<std::int32_t>("profile2048-input.i32", input);
      sample("warm2048", input, 0, 16);
      sample("profile2048", input, 0, 16);
    } else if (bench) {
      std::vector<std::vector<std::int32_t>> inputs;
      for (std::size_t size : {512, 2048, 8192}) {
        if (bench2k && size != 2048)
          continue;
        const auto input = SizedPrompt(*tokenizer, size);
        const auto label = "pp" + std::to_string(size);
        Save<std::int32_t>(label + "-input.i32", input);
        inputs.push_back(input);
      }
      for (int rep = 0; rep < 4; ++rep) {
        if (bench2k) {
          // Cool between independent requests; never inside PP/TG timing.
          // The external supervisor retains its CPU/GPU thermal stop.
          std::cout << "{\"event\":\"cooldown\",\"seconds\":15,\"before_rep\":"
                    << rep << "}\n";
          std::this_thread::sleep_for(std::chrono::seconds(15));
        }
        for (std::size_t i = 0; i < inputs.size(); ++i) {
          const auto &input = inputs[rep == 2 ? inputs.size() - 1 - i : i];
          sample("pp" + std::to_string(input.size()), input, rep, 128);
        }
      }
    }
#ifdef LIE_Q2_SHARED_FORK
    const auto &fork = executor->SharedForkStats();
    Require(fork.state == LIE_GPU_IDLE && fork.started == fork.joined &&
                fork.drained == 0,
            "Shared branch was not joined cleanly");
    if (bench || profile)
      Require(fork.started > 0, "Shared branch was not exercised");
    std::cout << "{\"event\":\"shared_fork\",\"started\":" << fork.started
              << ",\"joined\":" << fork.joined << ",\"drained\":" << fork.drained
              << ",\"state\":\"idle\"}\n";
#endif
    std::cout << "{\"event\":\"complete\",\"finite_frontiers\":true,\"semantic_"
                 "smoke\":true}\n";
  } catch (const std::exception &e) {
    std::cerr << "FAIL: " << e.what() << '\n';
    return 1;
  }
}
