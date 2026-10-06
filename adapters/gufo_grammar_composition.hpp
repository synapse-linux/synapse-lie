// SPDX-License-Identifier: MIT
// Typed immutable storage/predicate import and status translation only.
#ifndef LIE_GUFO_GRAMMAR_COMPOSITION_HPP
#define LIE_GUFO_GRAMMAR_COMPOSITION_HPP
#include "lie/grammar_composition.h"
#include "gufo_grammar.hpp"
namespace lie_gufo {
inline void composition_check(lie_composition_status rc) {
  if (rc == LIE_COMPOSITION_OK) return;
  if (rc == LIE_COMPOSITION_RESOURCE) throw std::bad_alloc();
  if (rc == LIE_COMPOSITION_TABLE_LIMIT || rc == LIE_COMPOSITION_WORK_LIMIT)
    throw std::invalid_argument("JSON Schema: combined tool grammar exceeds its resource budget");
  throw std::invalid_argument("invalid C17 grammar composition input");
}
using Composition = std::unique_ptr<lie_grammar_composition,
                                    decltype(&lie_composition_release)>;
struct CompositionSource {
  const lie_grammar_program *program;
  const Lexemes *lexemes;
};
template<class Rules, class Classes>
inline std::shared_ptr<const lie_grammar_program> composition_finish(
    const Composition &source, std::span<const CompositionSource> imports,
    Rules &rules, Classes &classes, Lexemes &lexemes, uint32_t &root,
    bool &stop) {
  lie_composition_view view;
  composition_check(lie_composition_describe(source.get(), &view));
  const auto &d = view.grammar;
  Rules staged_rules(d.rule_count);
  for (size_t i = 0; i < d.rule_count; ++i) {
    const auto range = d.rules[i];
    auto &rule = staged_rules[i];
    rule.reserve(range.count);
    for (size_t j = 0; j < range.count; ++j) {
      const auto seq = d.sequences[range.offset + j];
      rule.emplace_back();
      if (seq.count) rule.back().assign(d.symbols + seq.offset,
                                       d.symbols + seq.offset + seq.count);
    }
  }
  Classes staged_classes(d.class_count);
  for (size_t i = 0; i < d.class_count; ++i)
    for (unsigned b = 0; b < 256; ++b)
      if (d.classes[i * 32 + b / 8] & (1u << (b % 8))) staged_classes[i].set(b);
  Lexemes staged_lexemes;
  staged_lexemes.reserve(d.lexeme_count);
  for (size_t i = 0; i < d.lexeme_count; ++i) {
    const auto origin = view.lexemes[i];
    const Lexemes *owner = nullptr;
    for (const auto &entry : imports)
      if (entry.program == origin.program) { owner = entry.lexemes; break; }
    if (!owner || origin.index >= owner->size())
      throw std::logic_error("C17 grammar composition lost a predicate owner");
    staged_lexemes.push_back((*owner)[origin.index]);
  }
  rules = std::move(staged_rules); classes = std::move(staged_classes);
  lexemes = std::move(staged_lexemes); root = d.root;
  stop = view.stop_only_when_complete;
  auto bound = d;
#if LIE_C17_SAMPLING
  bound.predicates = lexemes.predicates();
#else
  bound.predicates = {&lexemes, grammar_allows,
                      grammar_predicate_advance, grammar_predicate_canonical};
#endif
  lie_grammar_program *program = nullptr;
  grammar_check(lie_grammar_program_create(&bound, &program));
  return std::shared_ptr<const lie_grammar_program>(program, lie_grammar_program_release);
}
}
#endif
