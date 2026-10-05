// SPDX-License-Identifier: MIT
// Synchronous borrowed input and C17 status-to-exception translation only.
#ifndef LIE_GUFO_GRAMMAR_REGEX_PARSE_HPP
#define LIE_GUFO_GRAMMAR_REGEX_PARSE_HPP
#include "gufo_grammar_regex_compile.hpp"
namespace lie_gufo {
class RegexParser {
public:
  // The pinned call site invokes Parse before the pattern view expires.
  RegexParser(RegexExpressions &expressions, std::string_view input)
      : expressions_(expressions), input_(input) {}
  uint32_t Parse() {
    lie_regex_parser_description d;
    lie_regex_parser_description_init(&d);
    uint32_t out;
    lie_regex_parse_error error{};
    const auto rc = lie_grammar_unicode_parse(
        expressions_.Unicode(), input_.data(), input_.size(), &d, &out, &error);
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
  RegexExpressions &expressions_;
  std::string_view input_;
};
} // namespace lie_gufo
#endif
