// SPDX-License-Identifier: MIT
// Actual private shared_ptr glue: hit allocation and holder OOM/lifetime gates.
#include "gufo_grammar_cache.hpp"
#include <atomic>
#include <cassert>
#include <cstdlib>
#include <iostream>
#include <new>
#include <string>
static std::atomic<bool> refuse_new{false};
void *operator new(std::size_t bytes) {
  if (refuse_new.load())
    throw std::bad_alloc();
  if (void *p = std::malloc(bytes ? bytes : 1))
    return p;
  throw std::bad_alloc();
}
void operator delete(void *p) noexcept { std::free(p); }
void operator delete(void *p, std::size_t) noexcept { std::free(p); }
struct Value {
  int id;
};
int main() {
  std::weak_ptr<const Value> weak;
  std::shared_ptr<const Value> retained;
  {
    lie_gufo::GrammarCache<Value> cache;
    for (unsigned i = 0; i < 16; ++i) {
      auto value = std::make_shared<const Value>(Value{int(i)});
      const auto key = std::string("a") + std::to_string(100 + i);
      assert(cache.put(key, value) == value);
      if (!i) {
        weak = value;
        retained = value;
      }
    }
    auto incoming = std::make_shared<const Value>(Value{99});
    refuse_new = true;
    assert(cache.get("a100") == retained);
    assert(!cache.get("missing"));
    bool refused = false;
    try {
      (void)cache.put("zz", incoming);
    } catch (const std::bad_alloc &) {
      refused = true;
    }
    refuse_new = false;
    assert(refused && cache.get("a100") == retained && !cache.get("zz"));
    assert(cache.put("zz", incoming) == incoming);
    assert(!cache.get("a100") && !weak.expired() && retained->id == 0);
    retained.reset();
    assert(weak.expired());
    weak = incoming;
    assert(cache.put("zz", std::make_shared<const Value>(Value{100})) ==
           incoming);
    incoming.reset();
    assert(!weak.expired());
  }
  assert(weak.expired());
  std::cout << "Private compiled-schema cache glue: PASS; "
               "allocation_free_hit=1 holder_refusal=1 retained_eviction=1 "
               "retirement=1 HOST NOT-INFERENCE\n";
}
