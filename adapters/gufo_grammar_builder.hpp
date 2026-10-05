// SPDX-License-Identifier: MIT
// Typed provider table views/storage and exception translation; construction is C17.
#ifndef LIE_GUFO_GRAMMAR_BUILDER_HPP
#define LIE_GUFO_GRAMMAR_BUILDER_HPP
#include "lie/grammar_builder.h"
#include "gufo_grammar.hpp"
namespace lie_gufo {
inline void builder_check(lie_builder_status rc) {
  switch (rc) {
  case LIE_BUILDER_OK: return;
  case LIE_BUILDER_RESOURCE: throw std::bad_alloc();
  case LIE_BUILDER_RULE_LIMIT:
    throw std::invalid_argument("JSON Schema: compiled grammar exceeds the rule limit");
  case LIE_BUILDER_CYCLE:
    throw std::invalid_argument("JSON Schema: reference cycle does not consume input");
  case LIE_BUILDER_EMPTY:
    throw gufo::sampling::JsonSchemaEmpty("JSON Schema: schema has no finite value");
  case LIE_BUILDER_WORK_LIMIT:
    throw std::runtime_error("JSON Schema: construction work limit exceeded");
  default: throw std::invalid_argument("JSON Schema: invalid C17 grammar construction");
  }
}
using Builder = std::unique_ptr<lie_grammar_builder, decltype(&lie_builder_release)>;
inline Builder builder_create() {
  lie_builder_description d; lie_builder_description_init(&d);
  lie_grammar_builder *p = nullptr; builder_check(lie_builder_create(&d, &p));
  return Builder(p, lie_builder_release);
}
inline std::vector<lie_builder_sequence> builder_views(const gufo::sampling::JsonConstraint::Rule &rule) {
  std::vector<lie_builder_sequence> views;
  views.reserve(rule.size());
  for (const auto &s : rule) views.push_back({s.data(), s.size()});
  return views;
}
inline uint32_t builder_new(lie_grammar_builder *b, const gufo::sampling::JsonConstraint::Rule &rule) {
  const auto views = builder_views(rule); uint32_t id = 0;
  builder_check(lie_builder_new(b, views.data(), views.size(), &id)); return id;
}
inline void builder_set(lie_grammar_builder *b, uint32_t id, const gufo::sampling::JsonConstraint::Rule &rule) {
  const auto views = builder_views(rule); builder_check(lie_builder_set(b, id, views.data(), views.size()));
}
// Preserve private templates for the still-transitional reasoning/tool composition.
inline std::shared_ptr<const lie_grammar_program> builder_finish(lie_grammar_builder *b,
    std::vector<gufo::sampling::JsonConstraint::Rule> &rules,
    std::vector<std::bitset<256>> &classes, const Lexemes &lexemes, uint32_t root) {
  lie_grammar_description d;
  builder_check(lie_builder_finish(b, root, lexemes.size(), &d));
  rules.resize(d.rule_count);
  for (size_t i = 0; i < d.rule_count; ++i) {
    const auto r = d.rules[i]; rules[i].resize(r.count);
    for (size_t j = 0; j < r.count; ++j) {
      const auto s = d.sequences[r.offset + j];
      rules[i][j].assign(d.symbols + s.offset, d.symbols + s.offset + s.count);
    }
  }
  classes.resize(d.class_count);
  for (size_t i = 0; i < d.class_count; ++i)
    for (unsigned byte = 0; byte < 256; ++byte)
      classes[i].set(byte, (d.classes[i * 32 + byte / 8] >> (byte % 8)) & 1u);
  d.predicates = {&lexemes, grammar_allows, grammar_predicate_advance, grammar_predicate_canonical};
  lie_grammar_program *p = nullptr; grammar_check(lie_grammar_program_create(&d, &p));
  return std::shared_ptr<const lie_grammar_program>(p, lie_grammar_program_release);
}
} // namespace lie_gufo
#endif
