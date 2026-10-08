// SPDX-License-Identifier: MIT
// Complete ordered states and token-stop decisions at actual pinned entry points.
#include "src/core/json.hpp"
#include "src/core/json_constraint.hpp"
#include <cassert>
#include <iomanip>
#include <iostream>
using gufo::sampling::JsonConstraint;
using Program = std::shared_ptr<const JsonConstraint>;
static size_t cases, prefixes;
static void witness(const Program &p, const std::string &text) {
  const gufo::sampling::ConstraintVocabulary vocabulary(259, [](uint32_t id) {
    const std::string piece = id < 256 ? std::string(1, static_cast<char>(id))
        : id == 256 ? "<tool_call>" : id == 257 ? "</think>" : "";
    return gufo::sampling::ConstraintVocabulary::Piece{piece, id == 258};
  });
  auto state = p->Start();
  for (size_t i = 0; i <= text.size(); ++i) {
    std::cout << i << ':' << p->Complete(state) << '[';
    for (const auto &frame : state) {
      std::cout << '(';
      for (auto symbol : frame.symbols) std::cout << symbol << ',';
      std::cout << ';';
      for (unsigned char byte : frame.lexeme) std::cout << unsigned(byte) << ',';
      std::cout << ')';
    }
    std::cout << ']';
    try {
      for (auto allowed : vocabulary.Allowed(*p, state)) std::cout << unsigned(allowed);
    } catch (const std::runtime_error &error) {
      // Dead prefixes intentionally have no admissible token. Preserve this
      // declared refusal as part of the complete witness; rethrow other faults.
      if (std::string_view(error.what()) != "JSON constraint has no valid token") throw;
      std::cout << "NO_TOKEN";
    }
    std::cout << '\n'; ++prefixes;
    if (i < text.size()) state = p->Advance(state, static_cast<unsigned char>(text[i]));
  }
  ++cases;
}
int main() {
  const auto answer = JsonConstraint::Compile(gufo::json::parse(R"({"type":"object","properties":{"s":{"type":"string","enum":["A"]}},"required":["s"],"additionalProperties":false})"), false);
  const auto object = JsonConstraint::Compile(gufo::json::parse(R"({"type":"object","properties":{"x":{"type":"integer","minimum":1,"maximum":2}},"required":["x"],"additionalProperties":false})"), false);
  const auto string = JsonConstraint::Compile(gufo::json::parse(R"({"type":"object","properties":{"s":{"type":"string","minLength":1,"maxLength":3}},"required":["s"],"additionalProperties":false})"), false);
  for (const auto &base : {answer, object, string}) {
    const auto reason = JsonConstraint::WithReasoning(base);
    for (const auto &text : {"x</thi</think>{\"s\":\"A\"}", "</think>{\"x\":2}", "</think>{\"s\":\"abc\"}", "</think>{\"s\":\"abcd\"}"})
      witness(reason, text);
    witness(JsonConstraint::WithReasoning(reason), "</think>x</think>{\"s\":\"A\"}");
  }
  for (unsigned mode = 0; mode < 8; ++mode) {
    const bool plain = mode & 1, required = mode & 2, parallel = mode & 4;
    const JsonConstraint::Tool tools[] = {{"same", answer}, {"object", object}, {"again", object}, {"text", string}};
    const auto composed = JsonConstraint::WithTools(plain ? nullptr : answer,
        {std::begin(tools), std::end(tools)}, required, parallel);
    const std::string call = "<tool_call>{\"name\":\"object\",\"arguments\":{\"x\":1}}</tool_call>";
    for (const auto &text : {call, call + call, std::string("{\"s\":\"A\"}"), "prefix" + call,
                            call + "tail", std::string("<tool_call>{\"name\":\"same\",\"arguments\":{\"s\":\"B\"}}</tool_call>")})
      witness(composed, text);
    witness(JsonConstraint::WithReasoning(composed), "thought</think>" + call);
  }
  for (unsigned byte = 0; byte < 256; ++byte) {
    const std::string name(1, static_cast<char>(byte));
    const auto composed = JsonConstraint::WithTools(answer, {{name, string}}, true, false);
    witness(composed, "<tool_call>{\"name\":" + gufo::json::Value(name).dump() + ",\"arguments\":{\"s\":\"B\"}}</tool_call>");
  }
  std::cout << "COMPOSITION CASES=" << cases << " PREFIXES=" << prefixes << " HOST_NOT_INFERENCE\n";
}
