// SPDX-License-Identifier: MIT
// Source-pinned syntax/refusal/full state and finite-prefix witnesses; NO
// MODEL.
#include "src/core/json_schema_regex.hpp"
#include <cstdio>
#include <string>
#include <vector>
using gufo::sampling::JsonSchemaRegex;
int main() {
  std::vector<std::string> patterns = {
      "",
      "^$",
      "a|",
      "|a",
      "(?:a?)?",
      "(?=a|b)[ab]{1,3}(?!c)",
      "(?:\\b|\\B){0,3}",
      "(?:^|$){2,3}",
      "(?=a){0,2}",
      "(?!a){1,2}",
      "[a-z-]",
      "[-a]",
      "[a\\-z]",
      "[\\d]",
      "[^\\D]",
      "\\w",
      "\\W",
      "\\s",
      "\\S",
      "\\p{L}",
      "\\P{L}",
      "[\\p{RGI_Emoji}]",
      "[^\\p{RGI_Emoji}]",
      "[\\p{RGI_Emoji}-\\p{RGI_Emoji}]",
      "é😀",
      "\\u00e9\\uD83D\\uDE00",
      "\\u{1f600}",
      "\\x61\\cB\\0\\n\\r\\t\\f\\v",
      "\\^\\$\\\\\\.\\*\\+\\?\\(\\)\\[\\]\\{\\}\\|\\/",
      "[\\b]",
      "[ ]",
      ".",
      "\\uDC00",
      "[\\uD800-\\uDFFF]",
      "a{0}",
      "a{1,}",
      "a{0,4294967294}",
      "a{4294967295}",
      "a{1,0}",
      "a{}",
      "a{,3}",
      "a{3x}",
      "a{3",
      "[",
      "[a",
      "[a-",
      "[z-a]",
      "[\\w-a]",
      "(",
      ")",
      "a)",
      "(?",
      "(?<a)",
      "(?i)a",
      "\\",
      "\\1",
      "\\01",
      "\\c0",
      "\\u{}",
      "\\u{110000}",
      "\\u{",
      "\\uZZZZ",
      "\\uD800",
      "\\uD800x",
      "\\uD800\\x0000",
      "\\uD800\\u0041",
      "\\xZ0",
      "\\p",
      "\\pL",
      "\\p{",
      "\\p{}",
      "\\p{not-a-property}",
      "\\p{" + std::string(129, 'a') + "}",
      "(?:\\b)*",
      "(?:^){33}",
      "*",
      "+",
      "?",
      "{",
      "}",
      "[a-b-c]",
      std::string(32, '(') + "a" + std::string(32, ')'),
      std::string(33, '(') + "a" + std::string(33, ')'),
      std::string(16384, 'a'),
      std::string(16385, 'a'),
      std::string("a\0b", 3),
      std::string("\\\0", 2),
      std::string("\xc0\x80", 2),
      std::string("\xed\xa0\x80", 3),
      std::string("\xf4\x90\x80\x80", 4)};
  uint32_t random = 0x42135;
  const std::string alphabet = "ab[]()|*+?{}^$\\0123,-=!:";
  for (size_t i = 0; i < 2048; ++i) {
    std::string p;
    for (size_t n = 0; n < i % 23; ++n) {
      random ^= random << 13;
      random ^= random >> 17;
      random ^= random << 5;
      p += alphabet[random % alphabet.size()];
    }
    patterns.push_back(std::move(p));
  }
  size_t compiled = 0, refused = 0, prefixes = 0, transitions = 0;
  for (size_t i = 0; i < patterns.size(); ++i)
    for (uint32_t maximum : {0u, 1u, 8u}) {
      std::printf("pattern=%zu maximum=%u bytes=", i, maximum);
      for (unsigned char c : patterns[i])
        std::printf("%02x", unsigned(c));
      std::printf("\n");
      std::shared_ptr<const JsonSchemaRegex> r;
      try {
        std::vector<std::string> conditions{patterns[i]};
        r = JsonSchemaRegex::Compile(conditions, maximum);
      } catch (const std::exception &e) {
        std::printf("refusal=%s\n", e.what());
        ++refused;
        continue;
      }
      ++compiled;
      std::printf("suffix=%u\n", r->MaximumSuffix());
      for (size_t length = 0; length <= 4; ++length) {
        size_t count = 1;
        for (size_t n = 0; n < length; ++n)
          count *= 3;
        for (size_t word = 0; word < count; ++word) {
          uint32_t state = r->Start();
          size_t v = word;
          for (size_t n = 0; n < length; ++n) {
            state = r->Advance(state, uint32_t("ab?"[v % 3]));
            v /= 3;
          }
          std::printf("prefix=%zu,%zu state=%u accepted=%d\n", length, word,
                      state, r->Accepting(state));
          ++prefixes;
          for (uint32_t cp :
               {0u, 9u, 10u, 13u, 32u, 48u, 65u, 95u, 97u, 98u, 99u, 0xe9u,
                0x391u, 0x2028u, 0xd7ffu, 0xe000u, 0x1f600u, 0x10ffffu}) {
            std::printf("next=%u,%u\n", cp, r->Advance(state, cp));
            ++transitions;
          }
          for (uint32_t lo : {0u, 1u, 3u, 31u, 1000000u})
            std::printf("finish=%u,%d advance=%d\n", lo,
                        r->CanFinish(state, lo, lo + 2),
                        r->CanAdvance(state, 0, 0x10ffff, lo, lo + 2));
        }
      }
    }
  std::printf("PATTERNS=%zu COMPILED=%zu REFUSED=%zu PREFIXES=%zu "
              "TRANSITIONS=%zu COMPLETE_PARSER_HOST_NOT_INFERENCE\n",
              patterns.size(), compiled, refused, prefixes, transitions);
}
