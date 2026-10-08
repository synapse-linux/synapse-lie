// SPDX-License-Identifier: MIT
// Source-pinned full DFA/Unicode and refusal witnesses. HOST NOT-INFERENCE.
#include "src/core/json_schema_regex.hpp"
#include <array>
#include <cstdio>
#include <set>
#include <string>
#include <vector>
using gufo::sampling::JsonSchemaRegex;
struct Case {
  std::vector<std::string> patterns;
  bool all_scalars;
};
int main() {
  const std::vector<Case> cases = {
      {{}, true},
      {{"^a$"}, true},
      {{"^(a|é|😀)$"}, true},
      {{"^\\p{L}$"}, true},
      {{"^[^\\w\\s]$"}, true},
      {{"\\bcat\\b"}, true},
      {{"(?=ab)a.*"}, true},
      {{"^a*$", "^(?!aa$).*"}, true},
      {{"^(a?){2,4}$"}, false},
      {{"^(ab){1,3}$"}, false},
      {{"^(a|b|)$"}, false},
      {{"^(?:a|ab)*$"}, false},
      {{"a$"}, false},
      {{"^a"}, false},
      {{"\\Bcat\\B"}, false},
      {{"^(?=a|b)(?!aa)[ab]{1,4}$"}, false},
      {{"^(?:\\b|\\B){1,3}a$"}, false},
      {{"^\\p{Greek}{1,3}$", "^\\P{N}+$"}, false},
      {{"^[\\u{1f600}-\\u{1f64f}]{1,2}$"}, false},
      {{"^[\\u0000-\\u007f]{0,2}$"}, false},
      {{"^.$"}, false},
      {{"^[\\s\\S]$"}, false},
      {{"^[\\d\\D]$"}, false},
      {{"^[]$"}, false},
      {{"^(a?)*$"}, false},
      {{"^a{1,7}?$"}, false},
      {{"["}, false},
      {{"(?<=a)b"}, false},
      {{"a{4,2}"}, false},
      {{"\\uD800"}, false},
      {{std::string(33, '(') + "a" + std::string(33, ')')}, false}};
  const std::array<uint32_t, 32> probes = {
      0,      9,       10,      13,      32,      48,      57,       65,
      90,     95,      97,      98,      99,      116,     122,      127,
      0xe9,   0x391,   0x3b1,   0x2000,  0x2028,  0x2029,  0xd7ff,   0xe000,
      0xffff, 0x10000, 0x1f600, 0x1f601, 0x1f64f, 0x1f650, 0x10fffe, 0x10ffff};
  size_t compilations = 0, refusals = 0, states = 0, scalar_queries = 0,
         finish_queries = 0;
  for (size_t ci = 0; ci < cases.size(); ++ci)
    for (uint32_t maximum : {0u, 1u, 4u, 32u}) {
      std::printf("case=%zu maximum=%u\n", ci, maximum);
      std::shared_ptr<const JsonSchemaRegex> r;
      try {
        r = JsonSchemaRegex::Compile(cases[ci].patterns, maximum);
      } catch (const std::exception &e) {
        std::printf("refusal=%s\n", e.what());
        ++refusals;
        continue;
      }
      ++compilations;
      std::printf("suffix=%u start=%u\n", r->MaximumSuffix(), r->Start());
      std::vector<uint32_t> queue{r->Start()};
      std::set<uint32_t> seen{r->Start()};
      for (size_t i = 0; i < queue.size(); ++i) {
        const uint32_t s = queue[i];
        ++states;
        std::printf("state=%u accepting=%d\n", s, r->Accepting(s));
        const auto enqueue = [&](uint32_t next) {
          if (next != JsonSchemaRegex::kDead && seen.insert(next).second)
            queue.push_back(next);
        };
        if (cases[ci].all_scalars) {
          uint32_t first = 0, previous = JsonSchemaRegex::kDead;
          for (uint32_t cp = 0; cp <= 0x110000; ++cp) {
            if (cp >= 0xd800 && cp <= 0xdfff)
              continue;
            const uint32_t next = cp == 0x110000 ? 0 : r->Advance(s, cp);
            if (cp == 0x110000 || (cp && next != previous) || cp == 0xe000) {
              const uint32_t last = cp == 0xe000 ? 0xd7ff : cp - 1;
              std::printf("range=%u,%u next=%u\n", first, last, previous);
              first = cp;
            }
            if (cp < 0x110000) {
              if (!cp || next != previous || cp == 0xe000)
                enqueue(next);
              previous = next;
              ++scalar_queries;
            }
          }
        } else
          for (uint32_t cp : probes) {
            const uint32_t next = r->Advance(s, cp);
            std::printf("cp=%u next=%u\n", cp, next);
            enqueue(next);
          }
        for (uint32_t minimum : {0u, 1u, 2u, 4u, 31u, 1000000u})
          for (uint32_t extra : {0u, 1u, 5u}) {
            std::printf("finish=%u,%u,%d\n", minimum, minimum + extra,
                        r->CanFinish(s, minimum, minimum + extra));
            for (const auto bounds : {std::array<uint32_t, 2>{0, 0x10ffff},
                                      {48, 57},
                                      {97, 122},
                                      {0x1f600, 0x1f64f},
                                      {0xd800, 0xdfff}})
              std::printf("advance=%u,%u,%u,%u,%d\n", bounds[0], bounds[1],
                          minimum, minimum + extra,
                          r->CanAdvance(s, bounds[0], bounds[1], minimum,
                                        minimum + extra));
            ++finish_queries;
          }
      }
      // Invalid published-state queries retain the provider's dead semantics.
      std::printf("invalid=%d,%d,%u\n", r->Accepting(UINT32_MAX),
                  r->CanFinish(UINT32_MAX, 0, 1), r->Advance(UINT32_MAX, 'a'));
    }
  std::printf("COMPILATIONS=%zu REFUSALS=%zu STATES=%zu SCALAR_QUERIES=%zu "
              "FINISH_QUERIES=%zu COMPLETE_COMPILER_HOST_NOT_INFERENCE\n",
              compilations, refusals, states, scalar_queries, finish_queries);
}
