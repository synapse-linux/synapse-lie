// SPDX-License-Identifier: MIT
// Complete native-vector/C17 snapshot roundtrips and actual C++ hook refusals.
#include "src/core/json_constraint.hpp"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <new>
#if defined(LIE_TEST_BIAS)
#include "gufo_grammar.hpp"
#endif
static size_t calls, fail_at;
void *operator new(size_t n) {
  if (++calls == fail_at)
    throw std::bad_alloc();
  if (void *p = std::malloc(n ? n : 1))
    return p;
  throw std::bad_alloc();
}
void *operator new[](size_t n) { return ::operator new(n); }
void operator delete(void *p) noexcept { std::free(p); }
void operator delete[](void *p) noexcept { std::free(p); }
void operator delete(void *p, size_t) noexcept { std::free(p); }
void operator delete[](void *p, size_t) noexcept { std::free(p); }
// This is the explicit legacy-vector bridge fixture. Default-ON request state
// now owns C snapshots; it must not be mutated to recreate vector staging.
using State = std::vector<gufo::sampling::JsonConstraint::Stack>;
static State source(size_t count) {
  State s(count);
  for (size_t i = 0; i < count; ++i) {
    for (size_t j = 0; j < i % 5; ++j)
      s[i].symbols.push_back(0x80000000u | static_cast<uint32_t>((i + j) % 3));
    for (size_t j = 0; j < i % 48; ++j)
      s[i].lexeme += static_cast<char>(i * 137 + j * 71);
  }
  return s;
}
#if defined(LIE_TEST_BIAS)
static lie_gufo::GrammarState owned(const State &s) {
  static const lie_grammar_range rules[] = {{0, 1}}, sequences[] = {{0, 0}};
  static const uint8_t classes[96] = {0};
  lie_grammar_description d;
  lie_grammar_description_init(&d);
  d.rules = rules;
  d.rule_count = 1;
  d.sequences = sequences;
  d.sequence_count = 1;
  d.classes = classes;
  d.class_count = 3;
  lie_grammar_program *raw = nullptr;
  lie_gufo::grammar_check(lie_grammar_program_create(&d, &raw));
  std::unique_ptr<lie_grammar_program, decltype(&lie_grammar_program_release)>
      p(raw, lie_grammar_program_release);
  return lie_gufo::grammar_import(raw, s);
}
static void faults() {
  auto input = source(64);
  auto state = owned(input);
  auto hash = lie_grammar_state_hash(state.get());
  calls = 0;
  auto result = lie_gufo::grammar_export(state.get());
  size_t count = calls;
  assert(result == input && count > 1);
  for (size_t fail = 1; fail <= count; ++fail) {
    calls = 0;
    fail_at = fail;
    bool refused = false;
    try {
      auto output = lie_gufo::grammar_export(state.get());
      (void)output;
    } catch (const std::bad_alloc &) {
      refused = true;
    }
    fail_at = 0;
    assert(refused && lie_grammar_state_hash(state.get()) == hash);
  }
  std::printf("CPP_STAGING_ALLOCATION_REFUSALS=%zu INPUT_HASH_PRESERVED "
              "HOST_NOT_INFERENCE\n",
              count);
}
#endif
int main(int argc, char **argv) {
#if defined(LIE_TEST_BIAS)
  if (argc == 2 && !std::strcmp(argv[1], "faults")) {
    faults();
    return 0;
  }
#else
  (void)argc;
  (void)argv;
#endif
  size_t frames = 0;
  for (size_t count = 0; count <= 64; ++count) {
    auto input = source(count);
    auto original = input;
#if defined(LIE_TEST_BIAS)
    auto state = owned(input);
    input.clear();
    auto result = lie_gufo::grammar_export(state.get());
#else
    auto result = input;
    input.clear();
#endif
    assert(result == original);
    auto copied = result;
    result.clear();
    assert(copied == original);
    std::printf("snapshot=%zu frames=%zu\n", count, copied.size());
    for (const auto &f : copied) {
      std::printf("symbols=");
      for (auto s : f.symbols)
        std::printf("%u,", s);
      std::printf(" bytes=");
      for (unsigned char b : f.lexeme)
        std::printf("%02x", unsigned(b));
      std::printf("\n");
      ++frames;
    }
  }
  std::printf("SNAPSHOTS=65 FRAMES=%zu COMPLETE_SNAPSHOT_HOST_NOT_INFERENCE\n",
              frames);
}
