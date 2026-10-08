// SPDX-License-Identifier: MIT
// Copied DFA table and exception glue; no derivative or graph runtime algorithm.
#ifndef LIE_GUFO_GRAMMAR_REGEX_HPP
#define LIE_GUFO_GRAMMAR_REGEX_HPP
#include "lie/grammar_regex.h"
#include <memory>
#include <stdexcept>
#include <vector>
namespace lie_gufo {
inline void regex_check(lie_regex_status rc) {
  if (rc == LIE_REGEX_OK) return;
  if (rc == LIE_REGEX_RESOURCE) throw std::bad_alloc();
  if (rc == LIE_REGEX_WORK_LIMIT) throw std::runtime_error("JSON Schema: regex work limit exceeded");
  throw std::out_of_range("invalid C17 JSON regex state or table");
}
template<class Graph>
inline std::shared_ptr<const lie_regex_program> regex_program(const Graph &graph) {
  std::vector<lie_grammar_range> classes;
  std::vector<lie_unicode_range> ranges;
  std::vector<uint8_t> accepting;
  std::vector<uint32_t> next;
  for (const auto &set : graph.alphabet) {
    classes.push_back({static_cast<uint32_t>(ranges.size()),static_cast<uint32_t>(set.getRangeCount())});
    for (int32_t i = 0; i < set.getRangeCount(); ++i)
      ranges.push_back({static_cast<uint32_t>(set.getRangeStart(i)),static_cast<uint32_t>(set.getRangeEnd(i))});
  }
  for (const auto &s : graph.states) {
    accepting.push_back(s.accepting);
    next.insert(next.end(),s.next.begin(),s.next.end());
  }
  lie_regex_description d; lie_regex_description_init(&d);
  d.classes = classes.data(); d.class_count = classes.size();
  d.ranges = ranges.data(); d.range_count = ranges.size();
  d.accepting = accepting.data(); d.state_count = accepting.size(); d.transitions = next.data();
  lie_regex_program *p = nullptr; regex_check(lie_regex_create(&d,&p));
  return std::shared_ptr<const lie_regex_program>(p,lie_regex_release);
}
inline bool regex_accepting(const lie_regex_program *p, uint32_t state) {
  bool out; regex_check(lie_regex_accepting(p,state,&out)); return out;
}
inline uint32_t regex_advance(const lie_regex_program *p, uint32_t state, uint32_t cp) {
  uint32_t out; regex_check(lie_regex_advance(p,state,cp,&out)); return out;
}
inline bool regex_finish(const lie_regex_program *p, uint32_t state, uint32_t min, uint32_t max) {
  bool out; regex_check(lie_regex_can_finish(p,state,min,max,&out)); return out;
}
inline bool regex_can_advance(const lie_regex_program *p, uint32_t state, uint32_t first,
  uint32_t last, uint32_t min, uint32_t max) {
  bool out; regex_check(lie_regex_can_advance(p,state,first,last,min,max,&out)); return out;
}
} // namespace lie_gufo
#endif
