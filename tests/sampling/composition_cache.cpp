// SPDX-License-Identifier: MIT
// Actual pinned reasoning/tool entry points with independent retained-map oracle.
#include "src/core/json.hpp"
#include "src/core/json_constraint.hpp"
#include <array>
#include <cassert>
#include <iostream>
#include <map>
#include <thread>
#include <tuple>
#include <vector>
using gufo::sampling::JsonConstraint;
using Program = std::shared_ptr<const JsonConstraint>;
using Tools = std::vector<JsonConstraint::Tool>;
using Key = std::tuple<Program, Tools, bool, bool>;
static size_t reasoning_cases, tool_cases, prefixes;
static bool accepts(const Program &p, const std::string &text) {
  auto state = p->Start();
  for (unsigned char byte : text) state = p->Advance(state, byte);
  return p->Complete(state);
}
static void witness(const Program &p, const std::string &text) {
  auto state = p->Start();
  for (size_t n = 0; n <= text.size(); ++n) {
    std::cout << n << ':' << state.size() << ',' << p->Complete(state) << ' ';
    ++prefixes;
    if (n < text.size()) state = p->Advance(state, static_cast<unsigned char>(text[n]));
  }
  std::cout << '\n';
}
template<class K> static void oracle(std::map<K, Program> &cache,
    const K &key, const Program &actual, std::vector<Program> &retained) {
  const auto found = cache.find(key);
  if (found != cache.end()) { assert(found->second == actual); return; }
  for (const auto &old : retained) assert(old != actual);
  if (cache.size() == 16) cache.erase(cache.begin());
  cache.emplace(key, actual);
  retained.push_back(actual);
}
int main() {
  std::vector<Program> answers;
  for (unsigned i = 0; i < 32; ++i) {
    auto schema = gufo::json::parse(R"({"type":"object","properties":{},"additionalProperties":false})");
    schema["description"] = gufo::json::Value("composition-identity-" + std::to_string(i));
    answers.push_back(JsonConstraint::Compile(schema, false));
  }
  std::map<Program, Program> reason_cache;
  std::vector<Program> reason_retained;
  for (unsigned step = 0; step < 200; ++step) {
    const auto &answer = answers[(step * 13 + step / 5) % answers.size()];
    const auto actual = JsonConstraint::WithReasoning(answer);
    oracle(reason_cache, answer, actual, reason_retained);
    assert(JsonConstraint::WithReasoning(answer) == actual);
    assert(accepts(actual, "nested<tool_call></think>{}"));
    assert(!accepts(actual, "</think>{\"x\":0}") && !accepts(actual, "thinking only"));
    std::cout << "REASON " << step << '\n';
    witness(actual, "x</thi</think>{}");
    ++reasoning_cases;
  }
  std::vector<Key> keys;
  for (unsigned i = 0; i < 64; ++i) {
    const Program answer = i % 3 ? answers[i % answers.size()] : nullptr;
    Tools tools{{i % 5 ? "first" : "quoted\"\\\n", answers[(i * 7) % answers.size()]}};
    if (i % 2) tools.emplace_back("second", tools[0].second);
    keys.emplace_back(answer, tools, (i & 1) != 0, (i & 2) != 0);
  }
  std::map<Key, Program> tool_cache;
  std::vector<Program> tool_retained;
  for (unsigned step = 0; step < 240; ++step) {
    const auto &key = keys[(step * 17 + step / 5) % keys.size()];
    const auto &[answer, tools, required, parallel] = key;
    const auto actual = JsonConstraint::WithTools(answer, tools, required, parallel);
    oracle(tool_cache, key, actual, tool_retained);
    assert(JsonConstraint::WithTools(answer, tools, required, parallel) == actual);
    const auto call = "<tool_call>{\"name\":" + gufo::json::Value(tools[0].first).dump() + ",\"arguments\":{}}</tool_call>";
    assert(accepts(actual, call));
    assert(accepts(actual, call + call) == parallel);
    assert(accepts(actual, "{}") == !required);
    assert(JsonConstraint::WithTools(answer, {}, required, parallel) == answer);
    std::cout << "TOOLS " << step << " answer=" << bool(answer) << " required=" << required << " parallel=" << parallel << '\n';
    witness(actual, call);
    ++tool_cases;
  }
  // The same published program is shared by concurrent readers/candidate puts.
  const auto answer = answers[0];
  const auto reason = JsonConstraint::WithReasoning(answer);
  const Tools tools{{"concurrent", answers[1]}};
  const auto tool = JsonConstraint::WithTools(answer, tools, true, false);
  std::array<std::thread, 8> workers;
  for (auto &worker : workers) worker = std::thread([&] {
    for (unsigned i = 0; i < 100; ++i) {
      assert(JsonConstraint::WithReasoning(answer) == reason);
      assert(JsonConstraint::WithTools(answer, tools, true, false) == tool);
      assert(accepts(reason, "</think>{}"));
    }
  });
  for (auto &worker : workers) worker.join();
  // A borrowed key/value call can retire, while returned immutable programs live.
  for (const auto &p : reason_retained) assert(accepts(p, "</think>{}"));
  std::cout << "COMPOSITION_CACHE REASON=" << reasoning_cases << " TOOLS=" << tool_cases
            << " PREFIXES=" << prefixes << " CONCURRENT=1600 HOST_NOT_INFERENCE\n";
}
