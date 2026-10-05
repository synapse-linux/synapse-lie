// SPDX-License-Identifier: MIT
// Immutable table/state/predicate and error translation only; runtime is C17.
#ifndef LIE_GUFO_GRAMMAR_HPP
#define LIE_GUFO_GRAMMAR_HPP
#include "lie/grammar.h"
#include "src/core/json_constraint.hpp"
#include <cstring>
#include <limits>
#include <memory>
#include <span>
#include <stdexcept>
namespace lie_gufo {
inline void grammar_check(lie_grammar_status rc) {
  switch (rc) {
  case LIE_GRAMMAR_OK: return;
  case LIE_GRAMMAR_RESOURCE: throw std::bad_alloc();
  case LIE_GRAMMAR_STACK_LIMIT:
    throw std::runtime_error("JSON grammar stack limit exceeded");
  case LIE_GRAMMAR_STATE_LIMIT:
  case LIE_GRAMMAR_WORK_LIMIT:
    throw std::runtime_error("JSON grammar state limit exceeded");
  case LIE_GRAMMAR_PREDICATE:
    throw std::runtime_error("JSON grammar primitive predicate failed");
  default: throw std::invalid_argument("invalid C17 JSON grammar input");
  }
}
using Lexemes = std::vector<std::shared_ptr<const gufo::sampling::JsonSchemaLexeme>>;
inline bool grammar_allows(const void *ctx, uint32_t id, uint8_t byte) noexcept {
  return static_cast<const Lexemes *>(ctx)->at(id)->AllowsByte(byte);
}
inline lie_grammar_status grammar_predicate_advance(
    const void *ctx, uint32_t id, const uint8_t *input, size_t bytes, uint8_t byte,
    uint8_t *output, size_t capacity, size_t *length, bool *prefix,
    bool *complete) noexcept {
  try {
    std::string value;
    if (bytes)
      value.assign(reinterpret_cast<const char *>(input), bytes);
    const auto match = static_cast<const Lexemes *>(ctx)->at(id)->Advance(value, byte);
    if (value.size() > capacity)
      return LIE_GRAMMAR_RESOURCE;
    if (!value.empty())
      std::memcpy(output, value.data(), value.size());
    *length = value.size();
    *prefix = match.prefix;
    *complete = match.complete;
    return LIE_GRAMMAR_OK;
  } catch (const std::bad_alloc &) {
    return LIE_GRAMMAR_RESOURCE;
  } catch (...) {
    return LIE_GRAMMAR_PREDICATE;
  }
}
inline lie_grammar_status grammar_predicate_canonical(
    const void *ctx, uint32_t id, uint8_t *output, size_t *length, size_t capacity,
    size_t token_bytes) noexcept {
  try {
    std::string value;
    if (*length)
      value.assign(reinterpret_cast<const char *>(output), *length);
    static_cast<const Lexemes *>(ctx)->at(id)->CanonicalMaskState(value, token_bytes);
    if (value.size() > capacity)
      return LIE_GRAMMAR_RESOURCE;
    if (!value.empty())
      std::memcpy(output, value.data(), value.size());
    *length = value.size();
    return LIE_GRAMMAR_OK;
  } catch (const std::bad_alloc &) {
    return LIE_GRAMMAR_RESOURCE;
  } catch (...) {
    return LIE_GRAMMAR_PREDICATE;
  }
}
inline uint32_t grammar_offset(size_t n) {
  if (n > UINT32_MAX)
    throw std::invalid_argument("JSON grammar table limit exceeded");
  return static_cast<uint32_t>(n);
}
inline std::shared_ptr<const lie_grammar_program> grammar_program(
    std::span<const gufo::sampling::JsonConstraint::Rule> source_rules,
    std::span<const std::bitset<256>> source_classes, const Lexemes &lexemes,
    uint32_t root) {
  std::vector<lie_grammar_range> rules, sequences;
  std::vector<uint32_t> symbols;
  std::vector<uint8_t> classes;
  for (const auto &rule : source_rules) {
    rules.push_back({grammar_offset(sequences.size()), grammar_offset(rule.size())});
    for (const auto &sequence : rule) {
      sequences.push_back({grammar_offset(symbols.size()), grammar_offset(sequence.size())});
      symbols.insert(symbols.end(), sequence.begin(), sequence.end());
    }
  }
  classes.resize(source_classes.size() * 32);
  for (size_t i = 0; i < source_classes.size(); ++i)
    for (unsigned byte = 0; byte < 256; ++byte)
      if (source_classes[i].test(byte))
        classes[i * 32 + byte / 8] |= 1u << (byte % 8);
  lie_grammar_description d;
  lie_grammar_description_init(&d);
  d.root = root;
  d.rules = rules.data(); d.rule_count = rules.size();
  d.sequences = sequences.data(); d.sequence_count = sequences.size();
  d.symbols = symbols.data(); d.symbol_count = symbols.size();
  d.classes = classes.data(); d.class_count = source_classes.size();
  d.lexeme_count = lexemes.size();
  // Context is immutable and owned by the containing provider grammar.
  d.predicates = {&lexemes, grammar_allows,
                  grammar_predicate_advance, grammar_predicate_canonical};
  lie_grammar_program *p = nullptr;
  grammar_check(lie_grammar_program_create(&d, &p));
  return std::shared_ptr<const lie_grammar_program>(p, lie_grammar_program_release);
}
using GrammarState = std::unique_ptr<lie_grammar_state, decltype(&lie_grammar_state_release)>;
inline lie_grammar_status
grammar_snapshot_read(const void *ctx, size_t index,
                      lie_grammar_frame *out) noexcept {
  const auto &f =
      (*static_cast<const gufo::sampling::JsonConstraint::State *>(ctx))[index];
  *out = {f.symbols.data(), f.symbols.size(),
          reinterpret_cast<const uint8_t *>(f.lexeme.data()), f.lexeme.size()};
  return LIE_GRAMMAR_OK;
}
inline lie_grammar_status grammar_snapshot_prepare(void *ctx,
                                                   size_t count) noexcept {
  try {
    static_cast<gufo::sampling::JsonConstraint::State *>(ctx)->resize(count);
    return LIE_GRAMMAR_OK;
  } catch (const std::bad_alloc &) {
    return LIE_GRAMMAR_RESOURCE;
  } catch (...) {
    return LIE_GRAMMAR_INVALID;
  }
}
inline lie_grammar_status
grammar_snapshot_write(void *ctx, size_t index, size_t symbols, size_t bytes,
                       lie_grammar_writable_frame *out) noexcept {
  try {
    auto &f =
        (*static_cast<gufo::sampling::JsonConstraint::State *>(ctx))[index];
    f.symbols.resize(symbols);
    f.lexeme.resize(bytes);
    *out = {f.symbols.data(), f.symbols.size(),
            reinterpret_cast<uint8_t *>(f.lexeme.data()), f.lexeme.size()};
    return LIE_GRAMMAR_OK;
  } catch (const std::bad_alloc &) {
    return LIE_GRAMMAR_RESOURCE;
  } catch (...) {
    return LIE_GRAMMAR_INVALID;
  }
}
inline GrammarState
grammar_import(const lie_grammar_program *p,
               const gufo::sampling::JsonConstraint::State &source) {
  const lie_grammar_snapshot_reader reader{
      LIE_GRAMMAR_SNAPSHOT_ABI, sizeof(lie_grammar_snapshot_reader), &source,
      source.size(), grammar_snapshot_read};
  lie_grammar_state *state = nullptr;
  grammar_check(lie_grammar_state_read(p, &reader, &state));
  return GrammarState(state, lie_grammar_state_release);
}
inline gufo::sampling::JsonConstraint::State
grammar_export(const lie_grammar_state *s) {
  gufo::sampling::JsonConstraint::State staging;
  const lie_grammar_snapshot_writer writer{
      LIE_GRAMMAR_SNAPSHOT_ABI, sizeof(lie_grammar_snapshot_writer), &staging,
      grammar_snapshot_prepare, grammar_snapshot_write};
  grammar_check(lie_grammar_state_write(s, &writer));
  return staging;
}
inline gufo::sampling::JsonConstraint::State grammar_run(
    const lie_grammar_program *p, const gufo::sampling::JsonConstraint::State &source,
    unsigned operation, uint8_t byte = 0, size_t token_bytes = 0) {
  if (!p)
    throw std::logic_error("C17 JSON grammar program was not sealed");
  lie_grammar_state *raw = nullptr;
  lie_grammar_status rc;
  if (operation == 0)
    rc = lie_grammar_start(p, &raw);
  else {
    auto input = grammar_import(p, source);
    rc = operation == 1 ? lie_grammar_advance(p, input.get(), byte, &raw)
       : operation == 2 ? lie_grammar_canonical(p, input.get(), token_bytes, &raw)
                        : lie_grammar_expand(p, input.get(), &raw);
  }
  grammar_check(rc);
  GrammarState owned(raw, lie_grammar_state_release);
  return grammar_export(owned.get());
}
inline bool grammar_complete(const lie_grammar_program *p,
                              const gufo::sampling::JsonConstraint::State &source) {
  auto input = grammar_import(p, source);
  return lie_grammar_complete(input.get());
}
inline std::vector<float> grammar_mask(std::span<const float> logits,
    std::span<const uint32_t> ids, std::span<const uint8_t> mask) {
  std::vector<float> output(logits.size());
  grammar_check(lie_grammar_mask_logits(logits.data(), logits.size(),
      ids.empty() ? nullptr : ids.data(), ids.size(), mask.data(), mask.size(),
      output.data(), output.size()));
  return output;
}
} // namespace lie_gufo
#endif
