// SPDX-License-Identifier: MIT
// Actual pinned Compile entry point, independent retained-identity oracle.
#include "src/core/json.hpp"
#include "src/core/json_constraint.hpp"
#include <array>
#include <cassert>
#include <iostream>
#include <map>
#include <thread>
#include <vector>
using gufo::json::Value;
using gufo::sampling::JsonConstraint;
using Program = std::shared_ptr<const JsonConstraint>;
static bool accepts(const Program &p, const std::string &text) {
  auto state = p->Start();
  for (unsigned char byte : text)
    state = p->Advance(state, byte);
  return p->Complete(state);
}
int main() {
  std::map<std::string, Program> oracle;
  std::vector<Program> retained;
  for (unsigned step = 0; step < 360; ++step) {
    const unsigned id = (step * 13 + step / 9) % 48;
    const bool strict = (step % 5) == 0;
    auto schema = gufo::json::parse(
        R"({"type":"object","properties":{},"additionalProperties":false})");
    schema["description"] = Value(std::string("cache-") + std::to_string(id));
    const std::string key =
        std::string(strict ? "strict:" : "schema:") + schema.dump();
    auto prior = oracle.find(key);
    const bool hit = prior != oracle.end();
    auto actual = JsonConstraint::Compile(schema, strict);
    if (hit)
      assert(actual == prior->second);
    else {
      for (const auto &old : retained)
        assert(actual != old);
      if (oracle.size() == 16)
        oracle.erase(oracle.begin());
      oracle.emplace(key, actual);
      retained.push_back(actual);
    }
    assert(accepts(actual, "{}") && !accepts(actual, "{\"unknown\":0}"));
    assert(JsonConstraint::Compile(schema, strict) == actual);
    std::cout << "compile " << step << " variant=" << id << " strict=" << strict
              << " hit=" << hit << " entries=" << oracle.size()
              << " accept=1 reject=1 same=1\n";
  }
  auto schema = gufo::json::parse(
      R"({"type":"object","properties":{},"additionalProperties":false,"description":"shared-thread-program"})");
  auto shared = JsonConstraint::Compile(schema, false);
  std::array<Program, 8> programs;
  std::array<std::thread, 8> threads;
  for (size_t i = 0; i < threads.size(); ++i)
    threads[i] = std::thread([&, i] {
      for (unsigned n = 0; n < 200; ++n) {
        programs[i] = JsonConstraint::Compile(schema, false);
        assert(programs[i] == shared);
        assert(accepts(programs[i], "{}"));
      }
    });
  for (auto &thread : threads)
    thread.join();
  for (const auto &p : programs)
    assert(p == shared);
  std::cout << "concurrent retained_identity=1 operations=1600\n";
  schema["description"] = Value(std::string(2u * 1024u * 1024u, 'x'));
  bool refused = false;
  try {
    (void)JsonConstraint::Compile(schema, false);
  } catch (const std::invalid_argument &e) {
    refused = true;
    std::cout << "limit " << e.what() << '\n';
  }
  assert(refused);
  assert(
      JsonConstraint::Compile(
          gufo::json::parse(
              R"({"type":"object","properties":{},"additionalProperties":false,"description":"shared-thread-program"})"),
          false) == shared);
  std::cout << "Compiled-schema cache: PASS HOST NOT-INFERENCE\n";
}
