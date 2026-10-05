// SPDX-License-Identifier: MIT
// ICU set/parser and exception translation; expression/derivative/DFA
// algorithms are C17.
#ifndef LIE_GUFO_GRAMMAR_REGEX_COMPILE_HPP
#define LIE_GUFO_GRAMMAR_REGEX_COMPILE_HPP
#include "gufo_grammar_regex.hpp"
#include "lie/grammar_regex_compile.h"
#include <algorithm>
#include <unicode/uniset.h>
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
  std::vector<icu::UnicodeSet> classes;
  explicit RegexExpressions(uint32_t maximum) {
    lie_regex_compiler_description d;
    lie_regex_compiler_description_init(&d);
    d.maximum_length = maximum;
    lie_regex_compiler *raw = nullptr;
    regex_compile_check(lie_regex_compiler_create(&d, &raw));
    compiler_.reset(raw);
    lie_regex_bases bases{};
    regex_compile_check(lie_regex_compiler_bases(raw, &bases));
    empty = bases.empty;
    epsilon = bases.epsilon;
    start = bases.start;
    any = bases.any;
    all = bases.all;
    icu::UnicodeSet scalars(0, 0x10ffff);
    scalars.remove(0xd800, 0xdfff);
    classes.push_back(std::move(scalars));
  }
  uint32_t Chars(icu::UnicodeSet set) {
    set.remove(0xd800, 0xdfff);
    if (set.isEmpty())
      return empty;
    auto found = std::ranges::find(classes, set);
    uint32_t id = static_cast<uint32_t>(found - classes.begin());
    if (found == classes.end()) {
      std::vector<lie_unicode_range> ranges;
      for (int32_t i = 0; i < set.getRangeCount(); ++i)
        ranges.push_back({static_cast<uint32_t>(set.getRangeStart(i)),
                          static_cast<uint32_t>(set.getRangeEnd(i))});
      uint32_t copied;
      regex_compile_check(lie_regex_class_add(compiler_.get(), ranges.data(),
                                              ranges.size(), &copied));
      if (copied != id)
        throw std::logic_error("C17 regex class translation mismatch");
      classes.push_back(std::move(set));
    }
    uint32_t out;
    regex_compile_check(lie_regex_chars(compiler_.get(), id, &out));
    return out;
  }
  uint32_t Boundary(bool positive) {
    icu::UnicodeSet words('a', 'z');
    words.add('A', 'Z').add('0', '9').add('_');
    (void)Chars(std::move(words));
    uint32_t out;
    regex_compile_check(lie_regex_boundary(compiler_.get(), positive, &out));
    return out;
  }
  uint32_t Not(uint32_t child) {
    uint32_t out;
    regex_compile_check(lie_regex_not(compiler_.get(), child, &out));
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
    regex_compile_check(lie_regex_combine(compiler_.get(), operation,
                                          parts.data(), parts.size(), &out));
    return out;
  }
  uint32_t Repeat(uint32_t child, uint32_t low, uint32_t high) {
    uint32_t out;
    regex_compile_check(
        lie_regex_repeat(compiler_.get(), child, low, high, &out));
    return out;
  }
  bool Nullable(uint32_t id, bool at_start, bool previous = false,
                bool next = false) const {
    bool out;
    regex_compile_check(lie_regex_nullable(compiler_.get(), id, at_start,
                                           previous, next, &out));
    return out;
  }
  uint32_t Derive(uint32_t id, UChar32 cp, bool at_start, bool previous) {
    uint32_t out;
    regex_compile_check(lie_regex_derive(compiler_.get(), id,
                                         static_cast<uint32_t>(cp), at_start,
                                         previous, &out));
    return out;
  }
  std::shared_ptr<const lie_regex_program> Seal(uint32_t root) {
    lie_regex_program *out = nullptr;
    regex_compile_check(lie_regex_seal(compiler_.get(), root, &out));
    return std::shared_ptr<const lie_regex_program>(out, lie_regex_release);
  }
  lie_regex_compiler *Compiler() const { return compiler_.get(); }

private:
  std::unique_ptr<lie_regex_compiler, decltype(&lie_regex_compiler_release)>
      compiler_{nullptr, lie_regex_compiler_release};
};
} // namespace lie_gufo
#endif
