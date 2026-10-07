// SPDX-License-Identifier: MIT
// Offline replay of captured GPU rows, or visibly separate synthetic fixtures.
// No model forward/device use. Complete probability/draw witnesses compare the
// pinned original, C17 and OFF samplers; a separate long-double math oracle
// checks the post-filter mass rather than trusting agreement alone.
#include "src/core/json.hpp"
#include "src/core/sampling.hpp"
#include "src/models/qwen38_flash_next/mtp_sampling.hpp"
#include "../../tools/sampling-capture-format.h"
#include <algorithm>
#include <bit>
#include <cerrno>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <limits>
#include <memory>
#include <openssl/evp.h>
#include <span>
#include <stdexcept>
#include <string>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>

namespace {
using gufo::json::Value;
using namespace gufo::sampling;
constexpr size_t max_vocab = 1048576, max_line = 262144;
void require(bool valid, const char *message) {
  if (!valid) throw std::runtime_error(message);
}
struct FD {
  int fd;
  explicit FD(int value) : fd(value) { require(fd >= 0, "capture file open failed"); }
  ~FD() { if (fd >= 0) close(fd); }
  FD(const FD &) = delete;
  FD &operator=(const FD &) = delete;
};
struct CloseFile {
  void operator()(FILE *file) const noexcept { if (file) std::fclose(file); }
};
const Value &field(const Value &v, const char *name) {
  const auto *p = v.find(name); require(p, "capture field missing"); return *p;
}
std::string string(const Value &v, const char *name) {
  const auto &p = field(v, name); require(p.is_string(), "capture string type invalid"); return p.str();
}
double real(const Value &v, const char *name) {
  const auto &p = field(v, name); require(p.is_number(), "capture number type invalid");
  const double n = p.as_double(); require(std::isfinite(n), "capture number nonfinite"); return n;
}
size_t integer(const Value &v, const char *name, size_t high) {
  const double n = real(v, name);
  require(n >= 0 && n <= static_cast<double>(high) && std::floor(n) == n, "capture integer out of range");
  return static_cast<size_t>(n);
}
bool boolean(const Value &v, const char *name) {
  const auto &p = field(v, name); require(p.is_bool(), "capture boolean type invalid"); return p.as_bool();
}
std::vector<TokenId> tokens(const Value &v, const char *name, size_t maximum, size_t vocab) {
  const auto &p = field(v, name); require(p.is_array(), "capture token array type invalid");
  require(!p.items().empty() && p.items().size() <= maximum, "capture token array length invalid");
  std::vector<TokenId> result;
  for (const auto &item : p.items()) {
    require(item.is_number(), "capture token type invalid"); const double n = item.as_double();
    require(std::isfinite(n) && n >= 0 && n < static_cast<double>(vocab) && std::floor(n) == n,
            "capture token outside vocabulary");
    result.push_back(static_cast<TokenId>(n));
  }
  return result;
}
void keys(const Value &v, std::initializer_list<const char *> names) {
  require(v.is_object() && v.members().size() == names.size(), "capture object fields invalid");
  for (const auto *name : names) (void)field(v, name);
}
SamplingConfig config(const Value &v, unsigned profile) {
  keys(v, {"temperature", "top_p", "top_k", "min_p", "frequency_penalty", "presence_penalty", "seed"});
  const double temperatures[] = {0, 1, 1, .7, 1, 2};
  const double minps[] = {0, .05, 0, .05, .05, .2};
  require(real(v, "temperature") == temperatures[profile] && real(v, "top_p") == (profile == 3 ? .9 : 1) &&
          real(v, "min_p") == minps[profile] && integer(v, "top_k", 32) == (profile == 2 || profile == 4 ? 32u : 0u) &&
          real(v, "frequency_penalty") == (profile == 4 ? .4 : profile == 5 ? -.3 : 0) &&
          real(v, "presence_penalty") == (profile == 4 ? .2 : profile == 5 ? -.1 : 0) &&
          integer(v, "seed", 123) == 123, "capture frozen generation identity mismatch");
  SamplingConfig c;
  c.temperature = static_cast<float>(real(v, "temperature")); c.top_p = static_cast<float>(real(v, "top_p"));
  c.top_k = static_cast<int32_t>(integer(v, "top_k", 32)); c.min_p = static_cast<float>(real(v, "min_p"));
  c.frequency_penalty = static_cast<float>(real(v, "frequency_penalty"));
  c.presence_penalty = static_cast<float>(real(v, "presence_penalty")); c.seed = 123;
  return c;
}
std::vector<float> row_file(int directory, const Value &metadata, unsigned profile, unsigned step, size_t vocab) {
  const std::string expected = "profile-" + std::to_string(profile) + "-row-" + std::to_string(step) + ".f32le";
  require(string(metadata, "file") == expected && integer(metadata, "bytes", max_vocab * 4) == vocab * 4,
          "capture row path/length mismatch");
  struct stat before{}, stat{};
  require(!fstatat(directory, expected.c_str(), &before, AT_SYMLINK_NOFOLLOW) &&
          S_ISREG(before.st_mode) && before.st_size == static_cast<off_t>(vocab * 4),
          "capture row is not a complete regular file");
  FD file(openat(directory, expected.c_str(), O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK));
  require(!fstat(file.fd, &stat) && S_ISREG(stat.st_mode) && stat.st_size == before.st_size &&
          stat.st_ino == before.st_ino && stat.st_dev == before.st_dev,
          "capture row is not a complete regular file");
  std::vector<float> result(vocab); auto *bytes = reinterpret_cast<unsigned char *>(result.data());
  for (size_t at = 0; at < vocab * 4;) {
    const ssize_t n = read(file.fd, bytes + at, vocab * 4 - at);
    if (n < 0 && errno == EINTR) continue;
    require(n > 0, "capture row read failed"); at += static_cast<size_t>(n);
  }
  unsigned char digest[32]; unsigned n = 0; char hex[65];
  require(EVP_Digest(bytes, vocab * 4, digest, &n, EVP_sha256(), nullptr) && n == 32, "row digest failed");
  for (unsigned i = 0; i < n; ++i) std::snprintf(hex + i * 2, 3, "%02x", digest[i]);
  require(string(metadata, "sha256") == hex, "capture row SHA256 mismatch");
  for (float value : result) require(std::isfinite(value), "capture raw row nonfinite");
  return result;
}
using Piece = ConstraintVocabulary::Piece;
std::vector<Piece> vocabulary_file(int directory, const Value &metadata) {
  keys(metadata, {"event", "file", "sha256", "bytes", "tokens"});
  const size_t bytes = integer(metadata, "bytes", LIE_CAPTURE_VOCAB_BYTES_MAX);
  const size_t count = integer(metadata, "tokens", max_vocab);
  require(count && bytes >= 12 && string(metadata, "file") == LIE_CAPTURE_VOCAB_FILE,
          "capture vocabulary path/length invalid");
  struct stat before{}, after{};
  require(!fstatat(directory, LIE_CAPTURE_VOCAB_FILE, &before, AT_SYMLINK_NOFOLLOW) &&
          S_ISREG(before.st_mode) && before.st_size == static_cast<off_t>(bytes),
          "capture vocabulary is not a complete regular file");
  FD file(openat(directory, LIE_CAPTURE_VOCAB_FILE, O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK));
  require(!fstat(file.fd, &after) && S_ISREG(after.st_mode) && after.st_size == before.st_size &&
          after.st_ino == before.st_ino && after.st_dev == before.st_dev,
          "capture vocabulary is not a complete regular file");
  std::vector<unsigned char> data(bytes);
  for (size_t at = 0; at < bytes;) {
    const ssize_t n = read(file.fd, data.data() + at, bytes - at);
    if (n < 0 && errno == EINTR) continue;
    require(n > 0, "capture vocabulary read failed"); at += static_cast<size_t>(n);
  }
  require(!fstat(file.fd, &after) && after.st_size == before.st_size,
          "capture vocabulary changed during read");
  unsigned char digest[32]; unsigned n = 0; char hash[65];
  require(EVP_Digest(data.data(), bytes, digest, &n, EVP_sha256(), nullptr) && n == 32,
          "capture vocabulary digest failed");
  for (unsigned i = 0; i < n; ++i) std::snprintf(hash + i * 2, 3, "%02x", digest[i]);
  require(string(metadata, "sha256") == hash, "capture vocabulary SHA256 mismatch");
  require(!std::memcmp(data.data(), LIE_CAPTURE_VOCAB_MAGIC, 8), "capture vocabulary magic mismatch");
  size_t at = 8;
  auto word = [&] {
    require(at <= bytes && bytes - at >= 4, "capture vocabulary record truncated");
    const uint32_t value = data[at] | (uint32_t(data[at + 1]) << 8) |
        (uint32_t(data[at + 2]) << 16) | (uint32_t(data[at + 3]) << 24); at += 4; return value;
  };
  require(word() == count, "capture vocabulary count mismatch");
  std::vector<Piece> result; result.reserve(count); bool has_stop = false;
  for (size_t token = 0; token < count; ++token) {
    const size_t length = word(); const uint32_t stop = word();
    require(length <= LIE_CAPTURE_PIECE_BYTES_MAX && length <= bytes - at && stop <= 1,
            "capture vocabulary piece/stop invalid");
    result.push_back({std::string(reinterpret_cast<const char *>(data.data() + at), length), stop != 0});
    at += length; has_stop |= stop != 0;
  }
  require(at == bytes && has_stop, "capture vocabulary trailing data or no stop token");
  return result;
}
std::shared_ptr<const TokenConstraint> tool_constraint(const Value &metadata,
                                                     const std::vector<Piece> &pieces) {
  keys(metadata, {"format", "required", "parallel", "name", "parameters_json", "definition_json"});
  require(string(metadata, "format") == "json_object" && boolean(metadata, "required") &&
          !boolean(metadata, "parallel") && string(metadata, "name") == LIE_CAPTURE_TOOL_NAME &&
          string(metadata, "parameters_json") == LIE_CAPTURE_TOOL_PARAMETERS &&
          string(metadata, "definition_json") == LIE_CAPTURE_TOOL_DEFINITION,
          "capture frozen tool constraint mismatch");
  auto constraint = std::make_shared<TokenConstraint>();
  constraint->grammar = JsonConstraint::WithTools(JsonConstraint::Object(),
      {{LIE_CAPTURE_TOOL_NAME, JsonConstraint::Compile(gufo::json::parse(LIE_CAPTURE_TOOL_PARAMETERS), true)}}, true, false);
  constraint->vocabulary = std::make_shared<ConstraintVocabulary>(pieces.size(),
      [&pieces](uint32_t token) { return pieces.at(token); });
  return constraint;
}
std::vector<uint8_t> direct_allowed(const JsonConstraint &grammar,
                                   const JsonConstraint::State &state,
                                   const std::vector<Piece> &pieces) {
  // Independent byte-by-byte membership for every token, without using the
  // production vocabulary trie, mask cache, canonicalization or Accept helper.
  // The frozen format binds a nonparallel required call with a structured
  // answer: in this mode only stop tokens are allowed once the call completes.
  const bool complete = grammar.Complete(state); std::vector<uint8_t> mask(pieces.size());
  for (size_t token = 0; token < pieces.size(); ++token) {
    const auto &piece = pieces[token];
    if (complete) { mask[token] = piece.stop; continue; }
    if (piece.stop || piece.text.empty()) continue;
    auto next = state;
    for (unsigned char byte : piece.text) {
      next = grammar.Advance(next, byte); if (next.empty()) break;
    }
    mask[token] = !next.empty();
  }
  return mask;
}
void completed_tool(const Value &metadata, const std::string &output) {
  constexpr std::string_view begin = "<tool_call>", end = "</tool_call>";
  require(output.starts_with(begin) && output.ends_with(end) && output.size() > begin.size() + end.size(),
          "captured required call framing invalid");
  auto call = gufo::json::parse(std::string_view(output).substr(begin.size(), output.size() - begin.size() - end.size()));
  keys(call, {"name", "arguments"}); keys(metadata, {"name", "arguments"});
  require(string(call, "name") == LIE_CAPTURE_TOOL_NAME && string(metadata, "name") == LIE_CAPTURE_TOOL_NAME,
          "captured required call name invalid");
  const auto &arguments = field(call, "arguments"), &saved = field(metadata, "arguments");
  keys(arguments, {"order", "size"}); keys(saved, {"order", "size"});
  const auto order = string(arguments, "order"); const auto size = integer(arguments, "size", 9);
  require((order == "LIFO" || order == "FIFO") && string(saved, "order") == order &&
          integer(saved, "size", 9) == size, "captured required call arguments/schema mismatch");
  std::printf("tool=%s order=%s size=%zu semantic_match=%d\n", LIE_CAPTURE_TOOL_NAME, order.c_str(), size,
              order == "LIFO" && size == 3);
}
struct Mass { TokenId token; long double value; };
std::vector<Mass> math_distribution(std::span<const float> row, const SamplingConfig &c,
                                  const std::vector<uint32_t> &generated,
                                  std::span<const uint8_t> allowed = {}) {
  std::vector<Mass> ranked; ranked.reserve(row.size());
  // Independent full ranking and long-double arithmetic. No production heap,
  // candidate-selection, normalization, history or sampling helper is called.
  for (size_t i = 0; i < row.size(); ++i) {
    if (!allowed.empty() && !allowed[i]) continue;
    long double value = row[i]; value -= static_cast<long double>(c.frequency_penalty) * generated[i];
    if (generated[i]) value -= c.presence_penalty;
    ranked.push_back({static_cast<TokenId>(i), value});
  }
  require(!ranked.empty(), "independent oracle has no allowed finite token");
  std::sort(ranked.begin(), ranked.end(), [](Mass a, Mass b) {
    return a.value == b.value ? a.token < b.token : a.value > b.value;
  });
  if (c.temperature == 0) return {{ranked.front().token, 1}};
  if (c.top_k > 0 && static_cast<size_t>(c.top_k) < ranked.size()) ranked.resize(c.top_k);
  const long double maximum = ranked.front().value;
  if (c.top_p < 1) {
    long double total = 0, cumulative = 0;
    for (auto p : ranked) total += std::exp((p.value - maximum) / c.temperature);
    size_t used = 0;
    do { cumulative += std::exp((ranked[used++].value - maximum) / c.temperature); }
    while (used < ranked.size() && cumulative < static_cast<long double>(c.top_p) * total);
    ranked.resize(used);
  }
  if (c.min_p > 0) {
    const long double threshold = maximum + static_cast<long double>(c.temperature) * std::log(static_cast<long double>(c.min_p));
    auto end = std::find_if(ranked.begin(), ranked.end(), [threshold](Mass p) { return p.value < threshold; });
    ranked.erase(end, ranked.end());
  }
  require(!ranked.empty(), "independent math filter removed all candidates");
  long double total = 0;
  for (auto &p : ranked) { p.value = std::exp((p.value - maximum) / c.temperature); total += p.value; }
  for (auto &p : ranked) p.value /= total;
  std::erase_if(ranked, [](Mass p) { return static_cast<double>(p.value) == 0; });
  return ranked;
}
void check_mass(const SamplingDistribution &distribution, const std::vector<Mass> &oracle, size_t vocab) {
  std::vector<long double> expected(vocab, 0);
  for (auto p : oracle) expected[p.token] = p.value;
  require(distribution.entries().size() == oracle.size(), "independent math support count differs");
  long double total = 0;
  for (auto p : distribution.entries()) {
    require(p.token < vocab && expected[p.token] > 0 && std::isfinite(p.value) && p.value > 0,
            "distribution has duplicate/outside-support/nonfinite mass");
    const long double difference = std::fabs(static_cast<long double>(p.value) - expected[p.token]);
    require(difference <= 5e-14L + 5e-12L * expected[p.token], "distribution differs from independent long-double mass");
    total += p.value; expected[p.token] = 0;
  }
  require(std::fabs(total - 1) <= 5e-12L, "distribution mass does not sum to one");
}
double uniform(uint64_t &state) {
  uint64_t x = state ? state : UINT64_C(0x9e3779b97f4a7c15);
  x ^= x >> 12; x ^= x << 25; x ^= x >> 27; state = x;
  return static_cast<double>((x * UINT64_C(0x2545f4914f6cdd1d)) >> 11) * 0x1p-53;
}
TokenId draw(std::span<const Probability> mass, uint64_t &state) {
  require(!mass.empty(), "independent draw has no mass");
  if (mass.size() == 1) return mass.front().token;
  double remaining = uniform(state);
  for (auto p : mass) { remaining -= p.value; if (remaining < 0) return p.token; }
  return mass.back().token;
}
void residual(const SamplingDistribution &p) {
  if (p.entries().size() < 2) { std::puts("residual=singleton-target"); return; }
  // A unit proposal on the first candidate forces correction after rejection.
  // The target's other candidates have mass outside that proposal's support.
  const TokenId qid = p.entries().front().token; const float qvalue = 1;
  std::vector<Probability> expected; double total = 0;
  for (auto entry : p.entries()) if (entry.token != qid) {
    expected.push_back(entry); total += entry.value;
  }
  for (auto &entry : expected) entry.value /= total;
  for (uint64_t seed = 0; seed < 8; ++seed) {
    uint64_t actual_rng = seed, expected_rng = seed;
    const auto token = p.SampleResidual({&qid, 1}, {&qvalue, 1}, &actual_rng);
    require(token == draw(expected, expected_rng) && actual_rng == expected_rng,
            "independent forced residual draw/RNG differs");
    std::printf("residual=%u rng=%llu\n", token, static_cast<unsigned long long>(actual_rng));
  }
}
#include "mtp_replay.hpp"
int replay(const char *path, bool allow_synthetic) {
  FD directory(open(path, O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW));
  struct stat before{}, stat{};
  require(!fstatat(directory.fd, "capture.jsonl", &before, AT_SYMLINK_NOFOLLOW) &&
          S_ISREG(before.st_mode) && before.st_size <= 128 * 1024 * 1024,
          "capture metadata file invalid or oversized");
  FD metadata(openat(directory.fd, "capture.jsonl", O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK));
  require(!fstat(metadata.fd, &stat) && S_ISREG(stat.st_mode) && stat.st_size == before.st_size &&
          stat.st_ino == before.st_ino && stat.st_dev == before.st_dev,
          "capture metadata file invalid or oversized");
  FILE *file = fdopen(metadata.fd, "r"); require(file, "metadata stream open failed"); metadata.fd = -1;
  std::unique_ptr<FILE, CloseFile> stream(file);
  std::vector<char> line(max_line + 2);
  bool identity = false, complete = false, tools = false, stopped = false;
  unsigned profile = 0, step = 0, budget = 0, row_count = 0;
  size_t vocab = 0; std::vector<TokenId> prompt, accepted; std::vector<uint32_t> generated;
  std::unique_ptr<SamplerState> sampler; uint64_t expected_rng = 123;
  SamplingConfig current;
  std::vector<Piece> pieces; JsonConstraint::State grammar_state; std::string output;
  while (std::fgets(line.data(), static_cast<int>(line.size()), file)) {
    const size_t bytes = std::strlen(line.data());
    require(bytes && bytes <= max_line && line[bytes - 1] == '\n', "capture JSON line oversized, truncated or contains NUL");
    auto v = gufo::json::parse(std::string_view(line.data(), bytes));
    require(!complete, "capture data after completion"); const auto kind = string(v, "event");
    if (!identity) {
      if (kind == "identity" && string(v, "schema") == "synapse-lie.sampling-capture.v3")
        return replay_mtp(directory.fd, file, v, allow_synthetic);
      require(before.st_size <= 16 * 1024 * 1024, "AR capture metadata oversized");
      keys(v, {"event", "schema", "program", "build_id", "engine", "source_pin", "dense_sampling", "synthetic",
               "classification", "scope", "row_encoding", "decode_mode", "eos_policy", "context", "prefill_chunk", "profiles", "tokens_per_profile"});
      tools = string(v, "schema") == "synapse-lie.sampling-capture.v2";
      require(kind == "identity" && (tools || string(v, "schema") == "synapse-lie.sampling-capture.v1") &&
              string(v, "program") == "lie-sampling-capture" && integer(v, "profiles", 6) == 6 &&
              string(v, "row_encoding") == "IEEE754-F32-little-endian" && string(v, "decode_mode") == "ar" &&
              integer(v, "context", 8192) == 8192 && integer(v, "prefill_chunk", 2048) == 2048,
              "capture identity mismatch");
      const bool synthetic = boolean(v, "synthetic");
      require(!synthetic || allow_synthetic, "synthetic capture requires explicit --allow-synthetic");
      require(string(v, "classification") == (synthetic ? "NOT-INFERENCE" : "ORIGINAL-WEIGHT-ROW-CAPTURE"),
              "capture classification mismatch");
      require(string(v, "eos_policy") == (tools ? "stop; un-emitted EOS is captured without position advance" :
          "ignore; EOS remains an ordinary sampled token"), "capture EOS policy mismatch");
      budget = static_cast<unsigned>(integer(v, "tokens_per_profile", 128)); require(budget, "empty capture budget");
      std::printf("classification=%s scope=%s\n",
                  synthetic ? "NOT-INFERENCE" : "CAPTURE-DECLARED-ORIGINAL-WEIGHTS-REQUIRE-SUPERVISOR-PROVENANCE",
                  tools ? "required-function-AR-mask/filter/draw/complete-call;not-MTP-controller/performance" :
                  "unconstrained-AR-filter/draw/residual;not-MTP-controller/quality/performance");
      identity = true; continue;
    }
    if (kind == "vocabulary") {
      require(tools && pieces.empty() && profile == 0 && !sampler, "capture vocabulary ordering invalid");
      pieces = vocabulary_file(directory.fd, v);
      std::printf("vocabulary=%zu sha256=%s\n", pieces.size(), string(v, "sha256").c_str());
    } else if (kind == "profile_begin") {
      if (tools) keys(v, {"event", "profile", "name", "vocab", "generation", "prompt_ids", "constraint"});
      else keys(v, {"event", "profile", "name", "vocab", "generation", "prompt_ids"});
      require(!sampler && profile < 6 && integer(v, "profile", 5) == profile, "capture profile ordering invalid");
      const char *names[] = {"greedy", "ds4-temperature1-minp", "top-k", "nucleus-minp",
                             "generated-penalties", "temperature2-negative-penalties"};
      require(string(v, "name") == names[profile], "capture profile name mismatch");
      vocab = integer(v, "vocab", max_vocab); require(vocab, "empty capture vocabulary");
      current = config(field(v, "generation"), profile); prompt = tokens(v, "prompt_ids", 8192 - budget, vocab);
      if (tools) {
        require(vocab == pieces.size(), "capture required vocabulary missing or inconsistent");
        current.constraint = tool_constraint(field(v, "constraint"), pieces);
        grammar_state = current.constraint->grammar->Start(); output.clear();
      }
      sampler = std::make_unique<SamplerState>(current, prompt); generated.assign(vocab, 0);
      accepted.clear(); step = 0; expected_rng = 123; stopped = false;
    } else if (kind == "row") {
      if (tools) keys(v, {"event", "profile", "step", "file", "sha256", "bytes", "token", "position", "emitted", "stop"});
      else keys(v, {"event", "profile", "step", "file", "sha256", "bytes", "token", "position"});
      const bool terminal = tools && boolean(v, "stop");
      const size_t emitted = tools ? integer(v, "emitted", 1) : 1;
      require(sampler && !stopped && step < budget && terminal != bool(emitted) &&
              integer(v, "profile", 5) == profile && integer(v, "step", 127) == step &&
              integer(v, "position", 8192) == prompt.size() + accepted.size() + emitted,
              "capture row frontier invalid");
      auto logits = row_file(directory.fd, v, profile, step, vocab);
      std::vector<uint8_t> allowed;
      if (tools) {
        allowed = direct_allowed(*current.constraint->grammar, grammar_state, pieces);
        require(*current.constraint->Allowed(grammar_state) == allowed, "independent full token mask differs");
      }
      const auto distribution = sampler->Distribution(logits);
      check_mass(distribution, math_distribution(logits, current, generated, allowed), vocab);
      std::printf("profile=%u step=%u sha256=%s\n", profile, step, string(v, "sha256").c_str());
      if (tools) { std::fputs("allowed=", stdout); for (auto bit : allowed) std::printf("%u", unsigned(bit)); std::putchar('\n'); }
      for (auto p : distribution.entries()) std::printf("p=%u:%a\n", p.token, p.value);
      const auto independent = draw(distribution.entries(), expected_rng), actual = sampler->Sample(logits);
      require(actual == independent && sampler->rng_state() == expected_rng,
              "captured live token, replay draw or independent RNG differs");
      if (terminal) require(field(v, "token").is_null() && actual < pieces.size() && pieces[actual].stop &&
          current.constraint->grammar->Complete(grammar_state), "captured premature or malformed stop");
      else require(actual == integer(v, "token", vocab - 1), "captured live token, replay draw or independent RNG differs");
      std::printf("draw=%u rng=%llu\n", actual, static_cast<unsigned long long>(sampler->rng_state()));
      residual(distribution);
      if (terminal) stopped = true;
      else {
        if (tools) {
          const auto &piece = pieces.at(actual);
          require(!piece.stop && !piece.text.empty() && piece.text.find('\0') == std::string::npos &&
              piece.text.size() <= LIE_CAPTURE_OUTPUT_BYTES_MAX - output.size(), "captured emitted tool piece invalid");
          output += piece.text;
          for (unsigned char byte : piece.text) grammar_state = current.constraint->grammar->Advance(grammar_state, byte);
          require(!grammar_state.empty(), "captured emitted tool token breaks independent grammar state");
        }
        sampler->Accept(actual); ++generated[actual]; accepted.push_back(actual);
      }
      ++step; ++row_count;
    } else if (kind == "profile_complete") {
      if (tools) keys(v, {"event", "profile", "rows", "output_ids", "tool_call"});
      else keys(v, {"event", "profile", "rows", "output_ids"});
      require(sampler && (tools ? stopped && step <= budget : step == budget) &&
              integer(v, "profile", 5) == profile && integer(v, "rows", 128) == step &&
              tokens(v, "output_ids", budget, vocab) == accepted, "capture completed profile mismatch");
      if (tools) completed_tool(field(v, "tool_call"), output);
      sampler.reset(); ++profile;
    } else if (kind == "complete") {
      keys(v, {"event", "exit_code", "profiles", "rows"});
      require(!sampler && profile == 6 && integer(v, "exit_code", 0) == 0 && integer(v, "profiles", 6) == 6 &&
              integer(v, "rows", 768) == row_count && (tools ? row_count <= 6 * budget : row_count == 6 * budget),
              "capture incomplete aggregate");
      complete = true;
    } else throw std::runtime_error("capture failure or unknown event; no acceptance");
  }
  require(!std::ferror(file) && complete, "capture terminal record missing or read failed");
  std::printf("ROWS=%u COMPLETE_OFFLINE_WITNESSES_NOT_FULL_ACCEPTANCE\n", row_count);
  return std::ferror(stdout) ? 1 : 0;
}
}
int main(int argc, char **argv) {
  static_assert(sizeof(float) == 4 && std::numeric_limits<float>::is_iec559 && std::endian::native == std::endian::little);
  const bool synthetic = argc == 4 && !std::strcmp(argv[3], "--allow-synthetic");
  if ((argc != 3 && !synthetic) || std::strcmp(argv[1], "--capture")) {
    std::fputs("Usage: sampling-replay --capture DIRECTORY [--allow-synthetic]\n", stderr); return 2;
  }
  try { return replay(argv[2], synthetic); }
  catch (const std::exception &error) { std::fprintf(stderr, "Sampling replay: %s\n", error.what()); return 1; }
}
