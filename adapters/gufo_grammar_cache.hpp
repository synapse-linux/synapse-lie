// SPDX-License-Identifier: MIT
// Typed opaque-handle ownership/error translation only; cache policy is C17.
#ifndef LIE_GUFO_GRAMMAR_CACHE_HPP
#define LIE_GUFO_GRAMMAR_CACHE_HPP
#include "lie/grammar_cache.h"
#include <memory>
#include <stdexcept>
#include <string_view>
namespace lie_gufo {
inline void grammar_cache_check(lie_grammar_cache_status rc) {
  if (rc == LIE_GRAMMAR_CACHE_OK)
    return;
  if (rc == LIE_GRAMMAR_CACHE_RESOURCE)
    throw std::bad_alloc();
  if (rc == LIE_GRAMMAR_CACHE_KEY_LIMIT)
    throw std::invalid_argument("JSON Schema: maximum schema size is 2 MiB");
  throw std::runtime_error("JSON Schema: invalid C17 compilation cache");
}
template <class T> class GrammarCache {
  using Value = std::shared_ptr<const T>;
  lie_grammar_cache *cache_ = nullptr;
  static lie_grammar_cache_status retain(void *, const void *p,
                                         void **out) noexcept {
    try {
      *out = new Value(*static_cast<const Value *>(p));
      return LIE_GRAMMAR_CACHE_OK;
    } catch (...) {
      return LIE_GRAMMAR_CACHE_RESOURCE;
    }
  }
  static void release(void *, void *p) noexcept {
    delete static_cast<Value *>(p);
  }
  static lie_grammar_cache_status copy(void *, const void *p,
                                       void *out) noexcept {
    *static_cast<Value *>(out) = *static_cast<const Value *>(p);
    return LIE_GRAMMAR_CACHE_OK;
  }

public:
  GrammarCache() {
    lie_grammar_cache_description d;
    lie_grammar_cache_description_init(&d);
    d.values = {nullptr, retain, release, copy};
    grammar_cache_check(lie_grammar_cache_create(&d, &cache_));
  }
  ~GrammarCache() { lie_grammar_cache_release(cache_); }
  GrammarCache(const GrammarCache &) = delete;
  GrammarCache &operator=(const GrammarCache &) = delete;
  Value get(std::string_view key) {
    Value out;
    bool found = false;
    grammar_cache_check(lie_grammar_cache_get(
        cache_, reinterpret_cast<const uint8_t *>(key.data()), key.size(), &out,
        &found));
    return out;
  }
  Value put(std::string_view key, Value value) {
    Value out;
    grammar_cache_check(lie_grammar_cache_put(
        cache_, reinterpret_cast<const uint8_t *>(key.data()), key.size(),
        &value, &out));
    return out;
  }
};
} // namespace lie_gufo
#endif
