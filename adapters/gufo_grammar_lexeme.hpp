// SPDX-License-Identifier: MIT
// Included by the pinned header after JsonSchemaEmpty. C owns predicates;
// this compatibility facade supplies private references/strings/exceptions.
#ifndef LIE_GUFO_GRAMMAR_LEXEME_HPP
#define LIE_GUFO_GRAMMAR_LEXEME_HPP
#include "lie/grammar_lexeme.h"
#include <algorithm>
#include <memory>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
namespace lie_gufo {
inline void lexeme_check(lie_lexeme_status rc) {
  using gufo::sampling::JsonSchemaEmpty;
  switch (rc) {
  case LIE_LEXEME_OK: return;
  case LIE_LEXEME_RESOURCE: throw std::bad_alloc();
  case LIE_LEXEME_NUMBER_WORK: throw std::runtime_error("JSON Schema: numeric work limit exceeded");
  case LIE_LEXEME_STRING_WORK: throw std::runtime_error("JSON Schema: regex work limit exceeded");
  case LIE_LEXEME_STRING_STATE: throw std::logic_error("invalid JSON string matcher state");
  case LIE_LEXEME_STRING_PHASE: throw std::logic_error("invalid JSON string matcher phase");
  case LIE_LEXEME_STRING_EMPTY_LENGTH: throw JsonSchemaEmpty("JSON Schema: minLength exceeds maxLength");
  case LIE_LEXEME_STRING_EMPTY_PATTERN: throw JsonSchemaEmpty("JSON Schema: string predicates and lengths have no matching value");
  case LIE_LEXEME_LIMIT: throw std::runtime_error("JSON grammar predicate resource limit exceeded");
  case LIE_LEXEME_SEALED: throw std::logic_error("immutable JSON grammar predicate table");
  default: throw std::invalid_argument("invalid C17 JSON grammar predicate");
  }
}
inline lie_grammar_lexeme *lexeme_whitespace() {
  lie_grammar_lexeme *p = nullptr; lexeme_check(lie_lexeme_whitespace_create(nullptr, &p)); return p;
}
inline lie_grammar_lexeme *lexeme_number(const std::shared_ptr<const lie_number_policy> &policy) {
  lie_grammar_lexeme *p = nullptr; lexeme_check(lie_lexeme_number_create(nullptr, policy.get(), &p)); return p;
}
inline lie_lexeme_match lexeme_match(const lie_grammar_lexeme *p, std::string_view text) {
  lie_lexeme_match m{};
  lexeme_check(lie_lexeme_check(p, reinterpret_cast<const uint8_t *>(text.data()), text.size(), &m));
  return m;
}
inline lie_lexeme_match lexeme_advance(const lie_grammar_lexeme *p, std::string &state, unsigned char b) {
  std::string staged(std::max(state.size() + 1, size_t(LIE_STRING_STATE_BYTES)), '\0');
  size_t n = 0; lie_lexeme_match m{};
  lexeme_check(lie_lexeme_advance(p, reinterpret_cast<const uint8_t *>(state.data()), state.size(), b,
      reinterpret_cast<uint8_t *>(staged.data()), staged.size(), &n, &m));
  staged.resize(n); state = std::move(staged); return m;
}
inline void lexeme_canonical(const lie_grammar_lexeme *p, std::string &state, size_t tokens) {
  lexeme_check(lie_lexeme_canonical(p, reinterpret_cast<uint8_t *>(state.data()), state.size(), tokens));
}
inline bool lexeme_accept_value(const lie_grammar_lexeme *p, const gufo::json::Value &value) {
  if (const auto *number = lie_lexeme_number_policy(p)) {
    if (!value.is_number()) return false;
    const auto text = value.dump(); bool out = false;
    const auto rc = lie_number_accept(number, {text.data(), text.size()}, &out);
    if (rc == LIE_NUMBER_RESOURCE) throw std::bad_alloc();
    if (rc == LIE_NUMBER_WORK_LIMIT) throw std::runtime_error("JSON Schema: numeric work limit exceeded");
    if (rc != LIE_NUMBER_OK) throw std::invalid_argument("JSON Schema: invalid exact-decimal numeric constraint");
    return out;
  }
  return lexeme_match(p, value.dump()).complete;
}
}
namespace gufo::sampling {
class JsonSchemaLexeme {
public:
  struct Match { bool prefix{false}, complete{false}; };
  virtual ~JsonSchemaLexeme() { lie_lexeme_release(c17_); }
  JsonSchemaLexeme(const JsonSchemaLexeme &) = delete;
  JsonSchemaLexeme &operator=(const JsonSchemaLexeme &) = delete;
  bool AllowsByte(unsigned char b) const { return lie_lexeme_allows(c17_, b); }
  virtual Match Check(std::string_view text) const {
    const auto m = lie_gufo::lexeme_match(c17_, text); return {m.prefix, m.complete};
  }
  virtual Match Advance(std::string &state, unsigned char b) const {
    const auto m = lie_gufo::lexeme_advance(c17_, state, b); return {m.prefix, m.complete};
  }
  virtual bool CacheTransitions() const { return lie_lexeme_cache_transitions(c17_); }
  virtual void CanonicalMaskState(std::string &state, size_t tokens) const {
    lie_gufo::lexeme_canonical(c17_, state, tokens);
  }
  virtual bool AcceptValue(const json::Value &value) const {
    return lie_gufo::lexeme_accept_value(c17_, value);
  }
  const lie_grammar_lexeme *C17Lexeme() const noexcept { return c17_; }
  static std::shared_ptr<const JsonSchemaLexeme> String(const json::Value &);
  static std::shared_ptr<const JsonSchemaLexeme> Number(const json::Value &, bool);
  static std::shared_ptr<const JsonSchemaLexeme> Whitespace();
  static json::Value IntersectMultipleOf(const json::Value &, const json::Value &);
  static json::Value Format(std::string_view);
protected:
  explicit JsonSchemaLexeme(lie_grammar_lexeme *p) noexcept : c17_(p) {}
  lie_grammar_lexeme *c17_;
};
}
namespace lie_gufo {
class LexemeView {
  const lie_grammar_lexeme *p_;
public:
  explicit LexemeView(const lie_grammar_lexeme *p) noexcept : p_(p) {}
  const LexemeView *operator->() const noexcept { return this; }
  bool AllowsByte(unsigned char b) const { return lie_lexeme_allows(p_, b); }
  bool CacheTransitions() const { return lie_lexeme_cache_transitions(p_); }
  gufo::sampling::JsonSchemaLexeme::Match Advance(std::string &state, unsigned char b) const {
    const auto m = lexeme_advance(p_, state, b); return {m.prefix, m.complete};
  }
  void CanonicalMaskState(std::string &state, size_t n) const { lexeme_canonical(p_, state, n); }
  const lie_grammar_lexeme *native() const noexcept { return p_; }
  bool AcceptValue(const gufo::json::Value &value) const { return lexeme_accept_value(p_, value); }
};
class LexemeTable {
  lie_lexeme_table *p_ = nullptr;
  explicit LexemeTable(lie_lexeme_table *owned, int) noexcept : p_(owned) {}
public:
  static LexemeTable adopt(lie_lexeme_table *owned) {
    if (!owned) lexeme_check(LIE_LEXEME_INVALID);
    return LexemeTable(owned, 0);
  }
  LexemeTable() { lexeme_check(lie_lexeme_table_create(nullptr, &p_)); }
  ~LexemeTable() { lie_lexeme_table_release(p_); }
  LexemeTable(const LexemeTable &other) {
    lexeme_check(lie_lexeme_table_clone(other.p_, nullptr, &p_));
  }
  LexemeTable &operator=(const LexemeTable &other) {
    if (this != &other) { LexemeTable staged(other); std::swap(p_, staged.p_); }
    return *this;
  }
  LexemeTable(LexemeTable &&other) noexcept : p_(std::exchange(other.p_, nullptr)) {}
  LexemeTable &operator=(LexemeTable &&other) noexcept {
    if (this != &other) { lie_lexeme_table_release(p_); p_ = std::exchange(other.p_, nullptr); }
    return *this;
  }
  size_t size() const noexcept { return lie_lexeme_table_size(p_); }
  void reserve(size_t n) { lexeme_check(lie_lexeme_table_reserve(p_, n)); }
  LexemeView operator[](size_t i) const noexcept { return LexemeView(lie_lexeme_table_at(p_, i)); }
  LexemeView at(size_t i) const {
    if (i >= size()) throw std::out_of_range("JSON grammar predicate index out of range");
    return (*this)[i];
  }
  void push_back(const std::shared_ptr<const gufo::sampling::JsonSchemaLexeme> &p) {
    lexeme_check(lie_lexeme_table_push(p_, p ? p->C17Lexeme() : nullptr));
  }
  void push_back(LexemeView p) { lexeme_check(lie_lexeme_table_push(p_, p.native())); }
  const lie_lexeme_table *native() const noexcept { return p_; }
  lie_grammar_predicates predicates() const {
    lexeme_check(lie_lexeme_table_seal(p_)); return lie_lexeme_table_predicates(p_);
  }
};
}
#endif
