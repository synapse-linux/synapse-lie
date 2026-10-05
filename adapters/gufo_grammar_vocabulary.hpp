// SPDX-License-Identifier: MIT
// Piece/state/snapshot/exception translation only; trie and cache policy are C17.
#ifndef LIE_GUFO_GRAMMAR_VOCABULARY_HPP
#define LIE_GUFO_GRAMMAR_VOCABULARY_HPP
#include "gufo_grammar.hpp"
#include "lie/grammar_vocabulary.h"
namespace lie_gufo {
inline void vocabulary_check(lie_grammar_status rc) {
  if (rc == LIE_GRAMMAR_NO_TOKEN)
    throw std::runtime_error("JSON constraint has no valid token");
  if (rc == LIE_GRAMMAR_VOCABULARY_LIMIT)
    throw std::invalid_argument("constraint token trie exceeds its node limit");
  if (rc == LIE_GRAMMAR_MASK_WORK_LIMIT)
    throw std::runtime_error("JSON token mask work limit exceeded");
  grammar_check(rc);
}
inline bool vocabulary_cacheable(const void *context, const lie_grammar_state *s) noexcept {
  const auto &lexemes = *static_cast<const Lexemes *>(context);
  for (size_t i = 0; i < lie_grammar_state_count(s); ++i) {
    lie_grammar_frame f{};
    if (lie_grammar_state_frame(s, i, &f) != LIE_GRAMMAR_OK) return false;
    if (f.symbol_count && (f.symbols[f.symbol_count - 1] & LIE_GRAMMAR_LEXEME)) {
      const auto id = f.symbols[f.symbol_count - 1] & ~LIE_GRAMMAR_LEXEME;
      if (id >= lexemes.size() || !lexemes[id]->CacheTransitions()) return false;
    }
  }
  return true;
}
inline std::shared_ptr<const lie_grammar_vocabulary> vocabulary_program(
    std::span<const gufo::sampling::ConstraintVocabulary::Piece> input) {
  std::vector<lie_token_piece> pieces;
  pieces.reserve(input.size());
  for (const auto &p : input)
    pieces.push_back({reinterpret_cast<const uint8_t *>(p.text.data()),p.text.size(),p.stop});
  lie_vocabulary_description d; lie_vocabulary_description_init(&d);
  d.pieces = pieces.data(); d.count = pieces.size();
  lie_grammar_vocabulary *v = nullptr;
  vocabulary_check(lie_vocabulary_create(&d,&v));
  return std::shared_ptr<const lie_grammar_vocabulary>(v,lie_vocabulary_release);
}
inline std::vector<uint8_t> vocabulary_mask(const lie_grammar_vocabulary *v,
  const lie_grammar_program *p, const lie_grammar_state *state,
  const Lexemes &lexemes, bool stop_only) {
  lie_vocabulary_query q; lie_vocabulary_query_init(&q);
  q.context = &lexemes; q.cache_transitions = vocabulary_cacheable;
  std::vector<uint8_t> out(lie_vocabulary_size(v));
  vocabulary_check(lie_vocabulary_allowed(v,p,state,stop_only,&q,out.data(),out.size(),nullptr));
  return out;
}
using MaskSnapshot = std::shared_ptr<const std::vector<uint8_t>>;
inline void mask_snapshot_release(void *, void *payload) noexcept {
  delete static_cast<MaskSnapshot *>(payload);
}
inline std::shared_ptr<lie_grammar_mask_cache> mask_cache(const lie_grammar_program *p) {
  lie_grammar_mask_cache *c = nullptr;
  grammar_check(lie_mask_cache_create(p,16,{},mask_snapshot_release,nullptr,&c));
  return std::shared_ptr<lie_grammar_mask_cache>(c,lie_mask_cache_release);
}
} // namespace lie_gufo
#endif
