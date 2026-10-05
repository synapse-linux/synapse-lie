// SPDX-License-Identifier: MIT
// C17 context RAII and exception/enum translation only.
#ifndef LIE_GUFO_GRAMMAR_REGEX_COMPILE_HPP
#define LIE_GUFO_GRAMMAR_REGEX_COMPILE_HPP
#include "gufo_grammar_regex.hpp"
#include "lie/grammar_unicode.h"
namespace lie_gufo {
inline void regex_compile_check(lie_regex_compile_status rc) {
  const char *reason = nullptr;
  switch (rc) {
  case LIE_REGEX_COMPILE_OK:
    return;
  case LIE_REGEX_COMPILE_RESOURCE:
    throw std::bad_alloc();
  case LIE_REGEX_COMPILE_EXPRESSION_LIMIT:
    reason = "regex expression budget exceeded";
    break;
  case LIE_REGEX_COMPILE_DERIVATIVE_LIMIT:
    reason = "regex derivative budget exceeded";
    break;
  case LIE_REGEX_COMPILE_STATE_LIMIT:
    reason = "compiled regex exceeds the state budget";
    break;
  case LIE_REGEX_COMPILE_REPETITION:
    reason = "invalid regex repetition";
    break;
  case LIE_REGEX_COMPILE_CLASS_LIMIT:
    reason = "regex character-class budget exceeded";
    break;
  case LIE_REGEX_COMPILE_WORK_LIMIT:
    reason = "regex work limit exceeded";
    break;
  default:
    reason = "invalid C17 regex compiler input";
    break;
  }
  throw std::invalid_argument("JSON Schema: " + std::string(reason));
}
class RegexExpressions {
public:
  uint32_t empty{}, epsilon{}, start{}, any{}, all{UINT32_MAX};
  explicit RegexExpressions(uint32_t maximum) {
    lie_grammar_unicode_description d;
    lie_grammar_unicode_description_init(&d);
    d.compiler.maximum_length = maximum;
    lie_grammar_unicode *raw = nullptr;
    regex_compile_check(lie_grammar_unicode_create(&d, &raw));
    unicode_.reset(raw);
    lie_regex_bases bases{};
    regex_compile_check(lie_regex_compiler_bases(Compiler(), &bases));
    empty = bases.empty;
    epsilon = bases.epsilon;
    start = bases.start;
    any = bases.any;
    all = bases.all;
  }
  uint32_t Not(uint32_t child) {
    uint32_t out;
    regex_compile_check(lie_regex_not(Compiler(), child, &out));
    return out;
  }
  template <class Kind>
  uint32_t Combine(Kind kind, std::vector<uint32_t> parts) {
    const auto value = static_cast<unsigned>(kind);
    // Pinned enum Kind: Or=5,And=6,Concat=8. This is enum translation only.
    if (value != 5 && value != 6 && value != 8)
      throw std::invalid_argument("invalid regex operation translation");
    const auto operation = value == 5   ? LIE_REGEX_UNION
                           : value == 6 ? LIE_REGEX_INTERSECTION
                                        : LIE_REGEX_CONCATENATION;
    uint32_t out;
    regex_compile_check(lie_regex_combine(Compiler(), operation, parts.data(),
                                          parts.size(), &out));
    return out;
  }
  uint32_t Repeat(uint32_t child, uint32_t low, uint32_t high) {
    uint32_t out;
    regex_compile_check(lie_regex_repeat(Compiler(), child, low, high, &out));
    return out;
  }
  bool Nullable(uint32_t id, bool at_start, bool previous = false,
                bool next = false) const {
    bool out;
    regex_compile_check(
        lie_regex_nullable(Compiler(), id, at_start, previous, next, &out));
    return out;
  }
  uint32_t Derive(uint32_t id, int32_t cp, bool at_start, bool previous) {
    uint32_t out;
    regex_compile_check(lie_regex_derive(
        Compiler(), id, static_cast<uint32_t>(cp), at_start, previous, &out));
    return out;
  }
  std::shared_ptr<const lie_regex_program> Seal(uint32_t root) {
    lie_regex_program *out = nullptr;
    regex_compile_check(lie_regex_seal(Compiler(), root, &out));
    return std::shared_ptr<const lie_regex_program>(out, lie_regex_release);
  }
  lie_regex_compiler *Compiler() const {
    return lie_grammar_unicode_compiler(unicode_.get());
  }
  lie_grammar_unicode *Unicode() const { return unicode_.get(); }

private:
  std::unique_ptr<lie_grammar_unicode, decltype(&lie_grammar_unicode_release)>
      unicode_{nullptr, lie_grammar_unicode_release};
};
} // namespace lie_gufo
#endif
