// SPDX-License-Identifier: MIT
// Opaque typed key/value storage and comparisons only; ordered policy is C17.
#ifndef LIE_GUFO_COMPOSITION_CACHE_HPP
#define LIE_GUFO_COMPOSITION_CACHE_HPP
#include "lie/ordered_cache.h"
#include <functional>
#include <memory>
#include <stdexcept>
namespace lie_gufo {
inline void composition_cache_check(lie_ordered_cache_status rc) {
  if (rc == LIE_ORDERED_CACHE_OK) return;
  if (rc == LIE_ORDERED_CACHE_RESOURCE) throw std::bad_alloc();
  throw std::runtime_error("JSON Schema: invalid C17 composition cache");
}
template<class Key, class T> class CompositionCache {
  using Value = std::shared_ptr<const T>;
  lie_ordered_cache *cache_ = nullptr;
  template<class U> static lie_ordered_cache_status retain(
      void *, const void *p, void **out) noexcept {
    try { *out = new U(*static_cast<const U *>(p)); return LIE_ORDERED_CACHE_OK; }
    catch (const std::bad_alloc &) { return LIE_ORDERED_CACHE_RESOURCE; }
    catch (...) { return LIE_ORDERED_CACHE_CALLBACK; }
  }
  template<class U> static void release(void *, void *p) noexcept { delete static_cast<U *>(p); }
  static lie_ordered_cache_status compare(void *, const void *a, const void *b, int *out) noexcept {
    try {
      const auto &left = *static_cast<const Key *>(a), &right = *static_cast<const Key *>(b);
      const std::less<Key> less;
      *out = less(left, right) ? -1 : less(right, left) ? 1 : 0;
      return LIE_ORDERED_CACHE_OK;
    } catch (...) { return LIE_ORDERED_CACHE_CALLBACK; }
  }
  static lie_ordered_cache_status copy(void *, const void *p, void *out) noexcept {
    *static_cast<Value *>(out) = *static_cast<const Value *>(p);
    return LIE_ORDERED_CACHE_OK;
  }
public:
  CompositionCache() {
    lie_ordered_cache_description d;
    lie_ordered_cache_description_init(&d);
    d.keys = {nullptr, retain<Key>, release<Key>, compare};
    d.values = {nullptr, retain<Value>, release<Value>, copy};
    composition_cache_check(lie_ordered_cache_create(&d, &cache_));
  }
  ~CompositionCache() { lie_ordered_cache_release(cache_); }
  CompositionCache(const CompositionCache &) = delete;
  CompositionCache &operator=(const CompositionCache &) = delete;
  Value get(const Key &key) {
    Value out;
    bool found = false;
    composition_cache_check(lie_ordered_cache_get(cache_, &key, &out, &found));
    return out;
  }
  Value put(const Key &key, Value value) {
    Value out;
    composition_cache_check(lie_ordered_cache_put(cache_, &key, &value, &out));
    return out;
  }
};
} // namespace lie_gufo
#endif
