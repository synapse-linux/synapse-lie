// SPDX-License-Identifier: MIT
// UnicodeSet storage/property/identity and input/error translation only.
#ifndef LIE_GUFO_GRAMMAR_REGEX_PARSE_HPP
#define LIE_GUFO_GRAMMAR_REGEX_PARSE_HPP
#include "gufo_grammar_regex_compile.hpp"
#include "lie/grammar_regex_parse.h"
#include <exception>
#include <unicode/unistr.h>
namespace lie_gufo {
class RegexParser {
public:
  RegexParser(RegexExpressions &expressions, std::string_view input)
      : expressions_(expressions), text_(icu::UnicodeString::fromUTF8(input)),
        bytes_(input.size()) {
    if (bytes_ > 16384)
      throw std::invalid_argument("JSON Schema: regex exceeds 16384 bytes");
    units_.reserve(static_cast<size_t>(text_.length()));
    for (int32_t i = 0; i < text_.length(); ++i)
      units_.push_back(static_cast<uint16_t>(text_.charAt(i)));
  }
  uint32_t Parse() {
    lie_regex_parser_description d;
    lie_regex_parser_description_init(&d);
    const lie_regex_unicode_sets sets{this,     Range,       Property,   Add,
                                      AddRange, RemoveRange, Complement, Info,
                                      Publish,  Boundary,    Release};
    uint32_t out;
    lie_regex_parse_error error{};
    const auto rc =
        lie_regex_parse_utf16(expressions_.Compiler(), units_.data(),
                              units_.size(), bytes_, &sets, &d, &out, &error);
    if (exception_)
      std::rethrow_exception(exception_);
    if (rc == LIE_REGEX_PARSE_RESOURCE)
      throw std::bad_alloc();
    if (rc == LIE_REGEX_PARSE_COMPILER)
      regex_compile_check(error.compiler_status);
    if (rc != LIE_REGEX_PARSE_OK)
      throw std::invalid_argument("JSON Schema: " +
                                  std::string(lie_regex_parse_reason(rc)));
    return out;
  }

private:
  template <class Function>
  static lie_regex_compile_status Guard(void *ctx, Function call) noexcept {
    try {
      call();
      return LIE_REGEX_COMPILE_OK;
    } catch (const std::bad_alloc &) {
      return LIE_REGEX_COMPILE_RESOURCE;
    } catch (...) {
      static_cast<RegexParser *>(ctx)->exception_ = std::current_exception();
      return LIE_REGEX_COMPILE_INVALID;
    }
  }
  static lie_regex_compile_status Range(void *ctx, int32_t first, int32_t last,
                                        void **out) noexcept {
    return Guard(ctx, [&] { *out = new icu::UnicodeSet(first, last); });
  }
  static lie_regex_compile_status Property(void *ctx, const char *text,
                                           size_t n, void **out) noexcept {
    lie_regex_compile_status result = LIE_REGEX_COMPILE_OK;
    const auto guarded = Guard(ctx, [&] {
      UErrorCode error = U_ZERO_ERROR;
      auto set = std::make_unique<icu::UnicodeSet>(
          icu::UnicodeString::fromUTF8(
              icu::StringPiece(text, static_cast<int32_t>(n))),
          0, nullptr, error);
      if (U_FAILURE(error)) {
        result = error == U_MEMORY_ALLOCATION_ERROR ? LIE_REGEX_COMPILE_RESOURCE
                                                    : LIE_REGEX_COMPILE_INVALID;
        return;
      }
      *out = set.release();
    });
    return guarded == LIE_REGEX_COMPILE_OK ? result : guarded;
  }
  static lie_regex_compile_status Add(void *ctx, void *dst,
                                      const void *src) noexcept {
    return Guard(ctx, [&] {
      static_cast<icu::UnicodeSet *>(dst)->addAll(
          *static_cast<const icu::UnicodeSet *>(src));
    });
  }
  static lie_regex_compile_status AddRange(void *ctx, void *dst, int32_t first,
                                           int32_t last) noexcept {
    return Guard(
        ctx, [&] { static_cast<icu::UnicodeSet *>(dst)->add(first, last); });
  }
  static lie_regex_compile_status
  RemoveRange(void *ctx, void *dst, int32_t first, int32_t last) noexcept {
    return Guard(
        ctx, [&] { static_cast<icu::UnicodeSet *>(dst)->remove(first, last); });
  }
  static lie_regex_compile_status Complement(void *ctx, void *dst) noexcept {
    return Guard(ctx,
                 [&] { static_cast<icu::UnicodeSet *>(dst)->complement(); });
  }
  static lie_regex_compile_status
  Info(void *ctx, const void *set, uint64_t *size, int32_t *first) noexcept {
    return Guard(ctx, [&] {
      auto s = static_cast<const icu::UnicodeSet *>(set);
      *size = static_cast<uint64_t>(s->size());
      *first = s->charAt(0);
    });
  }
  static lie_regex_compile_status Publish(void *ctx, const void *set,
                                          uint32_t *out) noexcept {
    return Guard(ctx, [&] {
      *out = static_cast<RegexParser *>(ctx)->expressions_.Chars(
          *static_cast<const icu::UnicodeSet *>(set));
    });
  }
  static lie_regex_compile_status Boundary(void *ctx, bool positive,
                                           uint32_t *out) noexcept {
    return Guard(ctx, [&] {
      *out = static_cast<RegexParser *>(ctx)->expressions_.Boundary(positive);
    });
  }
  static void Release(void *, void *set) noexcept {
    delete static_cast<icu::UnicodeSet *>(set);
  }
  RegexExpressions &expressions_;
  icu::UnicodeString text_;
  size_t bytes_;
  std::vector<uint16_t> units_;
  std::exception_ptr exception_;
};
} // namespace lie_gufo
#endif
