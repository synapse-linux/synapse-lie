// SPDX-License-Identifier: MIT
// Private value/exception facade; request snapshot storage and copies are C17.
#ifndef LIE_GUFO_GRAMMAR_STATE_HPP
#define LIE_GUFO_GRAMMAR_STATE_HPP
#include "lie/grammar.h"
#include <compare>
#include <cstddef>
#include <iterator>
#include <new>
#include <span>
#include <stdexcept>
#include <string_view>
#include <utility>
namespace lie_gufo {
class RequestGrammarState {
  lie_grammar_state *state_ = nullptr;
  explicit RequestGrammarState(lie_grammar_state *state) noexcept : state_(state) {}
  static lie_grammar_state *duplicate(const lie_grammar_state *state) {
    if (!state) return nullptr;
    lie_grammar_state *copy = nullptr;
    const auto rc = lie_grammar_state_duplicate(state, &copy);
    if (rc == LIE_GRAMMAR_RESOURCE) throw std::bad_alloc();
    if (rc != LIE_GRAMMAR_OK)
      throw std::logic_error("invalid C17 grammar snapshot copy");
    return copy;
  }
public:
  struct Frame {
    std::span<const uint32_t> symbols;
    std::string_view lexeme;
  };
  class Iterator {
    const RequestGrammarState *owner_ = nullptr;
    size_t index_ = 0;
  public:
    using value_type = Frame;
    using difference_type = std::ptrdiff_t;
    using iterator_category = std::input_iterator_tag;
    Iterator() = default;
    Iterator(const RequestGrammarState *owner, size_t index) noexcept
      : owner_(owner), index_(index) {}
    Frame operator*() const { return (*owner_)[index_]; }
    Iterator &operator++() noexcept { ++index_; return *this; }
    Iterator operator++(int) noexcept { auto old = *this; ++*this; return old; }
    bool operator==(const Iterator &) const = default;
  };
  RequestGrammarState() = default;
  ~RequestGrammarState() { lie_grammar_state_release(state_); }
  RequestGrammarState(const RequestGrammarState &other)
    : state_(duplicate(other.state_)) {}
  RequestGrammarState(RequestGrammarState &&other) noexcept
    : state_(std::exchange(other.state_, nullptr)) {}
  RequestGrammarState &operator=(const RequestGrammarState &other) {
    if (this != &other) { RequestGrammarState staging(other); swap(staging); }
    return *this;
  }
  RequestGrammarState &operator=(RequestGrammarState &&other) noexcept {
    if (this != &other) {
      lie_grammar_state_release(state_);
      state_ = std::exchange(other.state_, nullptr);
    }
    return *this;
  }
  // Transfer exactly one independently owned C snapshot; no payload projection.
  static RequestGrammarState adopt(lie_grammar_state *state) noexcept {
    return RequestGrammarState(state);
  }
  const lie_grammar_state *native() const noexcept { return state_; }
  size_t size() const noexcept { return lie_grammar_state_count(state_); }
  bool empty() const noexcept { return size() == 0; }
  void clear() noexcept { lie_grammar_state_release(state_); state_ = nullptr; }
  void swap(RequestGrammarState &other) noexcept { std::swap(state_, other.state_); }
  Frame operator[](size_t index) const {
    lie_grammar_frame f{};
    if (lie_grammar_state_frame(state_, index, &f) != LIE_GRAMMAR_OK)
      throw std::out_of_range("invalid C17 grammar snapshot frame");
    return {{f.symbols, f.symbol_count},
            {f.lexeme_bytes ? reinterpret_cast<const char *>(f.lexeme) : "", f.lexeme_bytes}};
  }
  Frame at(size_t index) const { return (*this)[index]; }
  Iterator begin() const noexcept { return {this, 0}; }
  Iterator end() const noexcept { return {this, size()}; }
  std::strong_ordering operator<=>(const RequestGrammarState &other) const noexcept {
    // Default/moved-from and actual zero-frame snapshots represent the same
    // dead prefix in the provider's value contract. The C API keeps NULL distinct.
    if (empty() && other.empty()) return std::strong_ordering::equal;
    const auto c = lie_grammar_state_compare(state_, other.state_);
    return c < 0 ? std::strong_ordering::less : c > 0 ? std::strong_ordering::greater
                                                        : std::strong_ordering::equal;
  }
  bool operator==(const RequestGrammarState &other) const noexcept {
    return (*this <=> other) == std::strong_ordering::equal;
  }
};
} // namespace lie_gufo
#endif
