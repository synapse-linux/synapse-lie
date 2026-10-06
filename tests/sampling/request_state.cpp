// SPDX-License-Identifier: MIT
// Complete request-state/copy/sampler witnesses; HOST fixtures, no model forward.
#include "src/core/json_constraint.hpp"
#include "src/core/sampling.hpp"
#include <algorithm>
#include <array>
#include <atomic>
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <new>
#include <thread>
#if LIE_C17_SAMPLING
#include "gufo_grammar.hpp"
#endif
static std::atomic_size_t cpp_allocations;
void *operator new(size_t n) {
  ++cpp_allocations;
  if (void *p = std::malloc(n ? n : 1)) return p;
  throw std::bad_alloc();
}
void *operator new[](size_t n) { return ::operator new(n); }
void operator delete(void *p) noexcept { std::free(p); }
void operator delete[](void *p) noexcept { std::free(p); }
void operator delete(void *p, size_t) noexcept { std::free(p); }
void operator delete[](void *p, size_t) noexcept { std::free(p); }
using gufo::sampling::JsonConstraint;
static void witness(const JsonConstraint &g, const JsonConstraint::State &s) {
  std::printf("state=%zu complete=%u ", s.size(), g.Complete(s));
  for (const auto &f : s) {
    std::printf("symbols=");
    for (auto id : f.symbols) std::printf("%u,", id);
    std::printf(" lexeme=");
    for (unsigned char byte : f.lexeme) std::printf("%02x", unsigned(byte));
    std::printf(";");
  }
  std::puts("");
}
#if LIE_C17_SAMPLING
struct Memory { size_t calls = 0, fail = 0, live = 0; };
static void *allocate(void *ctx, size_t bytes) {
  auto &m = *static_cast<Memory *>(ctx);
  if (++m.calls == m.fail) return nullptr;
  if (auto *p = std::malloc(bytes)) { ++m.live; return p; }
  return nullptr;
}
static void release(void *ctx, void *p) {
  auto &m = *static_cast<Memory *>(ctx);
  assert(p && m.live); --m.live; std::free(p);
}
static void ownership() {
  Memory m;
  const lie_grammar_range rules[] = {{0, 1}}, sequences[] = {{0, 1}};
  const uint32_t symbols[] = {LIE_GRAMMAR_TERMINAL};
  uint8_t classes[32] = {}; classes['a' / 8] = 1u << ('a' % 8);
  lie_grammar_description d; lie_grammar_description_init(&d);
  d.rules = rules; d.rule_count = 1; d.sequences = sequences; d.sequence_count = 1;
  d.symbols = symbols; d.symbol_count = 1; d.classes = classes; d.class_count = 1;
  d.allocator = {&m, allocate, release};
  lie_grammar_program *p = nullptr;
  lie_gufo::grammar_check(lie_grammar_program_create(&d, &p));
  auto initial = lie_gufo::grammar_run(p, {}, 0);
  const auto hash = lie_grammar_state_hash(initial.native());
  const size_t calls = m.calls, cpp = cpp_allocations;
  { auto input = lie_gufo::grammar_import(p, initial);
    assert(input.get() == initial.native()); }
  assert(m.calls == calls && cpp_allocations == cpp);
  auto copied = initial;
  auto assigned = initial;
  assert(copied.native() != initial.native() && assigned.native() != initial.native());
  assert(copied == initial && assigned == initial && cpp_allocations == cpp);
  const auto before = assigned.native();
  const auto live = m.live;
  size_t copy_calls = m.calls;
  { auto sample = initial; }
  copy_calls = m.calls - copy_calls;
  for (size_t fail = 1; fail <= copy_calls; ++fail) {
    m.fail = m.calls + fail;
    bool refused = false;
    try { assigned = initial; } catch (const std::bad_alloc &) { refused = true; }
    assert(refused && assigned.native() == before && assigned == initial &&
           lie_grammar_state_hash(initial.native()) == hash && m.live == live);
  }
  m.fail = 0;
  assigned = assigned;
  assigned = std::move(assigned);
  assert(assigned.native() == before && cpp_allocations == cpp);
  auto accepted = lie_gufo::grammar_run(p, copied, 1, 'a');
  assert(lie_grammar_complete(accepted.native()) && copied == initial);
  auto dead = lie_gufo::grammar_run(p, initial, 1, 'z');
  JsonConstraint::State empty;
  assert(dead.empty() && dead == empty && (dead <=> empty) == 0);
  auto moved = std::move(copied);
  assert(copied.empty() && moved == initial);
  copied = moved;
  assert(copied == initial && copied.native() != moved.native());
  lie_grammar_program_release(p);
  initial.clear(); assigned.clear(); copied.clear();
  assert(lie_grammar_state_hash(moved.native()) == hash);
  auto after_program = moved;
  moved.clear();
  assert(lie_grammar_state_hash(after_program.native()) == hash);
  after_program.clear(); accepted.clear(); dead.clear();
  assert(!m.live && cpp_allocations == cpp);
  bool invalid = false;
  try { (void)empty.at(0); } catch (const std::out_of_range &) { invalid = true; }
  assert(invalid);

  const auto grammar = JsonConstraint::Object();
  const auto state = grammar->Start();
  const auto expected = lie_grammar_state_hash(state.native());
  std::array<std::thread, 4> readers;
  for (auto &thread : readers) thread = std::thread([&] {
    for (size_t i = 0; i < 256; ++i) {
      auto copy = state;
      assert(copy.native() != state.native() && copy == state &&
             lie_grammar_state_hash(copy.native()) == expected);
    }
  });
  for (auto &thread : readers) thread.join();
  std::printf("C17_REQUEST_STATE copy_allocator_refusals=%zu CPP_ALLOCATIONS_IN_STATE_PATH=0 "
              "BORROW_NO_COPY joined_readers=4 read_iterations=256 HOST_NOT_INFERENCE\n", copy_calls);
}
#endif
int main(int argc, char **argv) {
#if LIE_C17_SAMPLING
  if (argc == 2 && !std::strcmp(argv[1], "ownership")) { ownership(); return 0; }
#else
  (void)argc; (void)argv;
#endif
  const char *schemas[] = {
    R"({"type":"object","properties":{"s":{"type":"string","minLength":1,"maxLength":8}},"required":["s"],"additionalProperties":false})",
    R"({"type":"object","properties":{"n":{"type":"number","minimum":-10,"maximum":10,"multipleOf":0.1}},"required":["n"],"additionalProperties":false})",
    R"({"type":"object","properties":{"s":{"type":"string","pattern":"^(a|é|😀){1,4}$"}},"required":["s"],"additionalProperties":false})"
  };
  const std::string texts[] = {R"({"s":"aé😀"})", R"({"n":1.2})", R"({"s":"a\u00e9"})", "invalid", ""};
  size_t checks = 0;
  for (const auto *schema : schemas) {
    const auto grammar = JsonConstraint::Compile(gufo::json::parse(schema), true);
    for (const auto &text : texts) {
      auto state = grammar->Start();
      std::vector<JsonConstraint::State> prefixes;
      for (size_t offset = 0; offset <= text.size(); ++offset) {
        auto copy = state; JsonConstraint::State assigned; assigned = copy;
        auto moved = std::move(copy);
        assert(copy.empty() && moved == state && assigned == state);
        prefixes.push_back(state);
        witness(*grammar, assigned); ++checks;
        if (offset < text.size()) state = grammar->Advance(state, static_cast<unsigned char>(text[offset]));
        assert(prefixes.back() == moved);
      }
      std::sort(prefixes.begin(), prefixes.end());
      for (const auto &prefix : prefixes) { witness(*grammar, prefix); ++checks; }
    }
  }
  std::puts("SAMPLER_COPIES");
  using namespace gufo::sampling;
  const auto grammar = JsonConstraint::Object();
  const auto vocabulary = std::make_shared<ConstraintVocabulary>(257, [](uint32_t id) {
    return ConstraintVocabulary::Piece{id < 256 ? std::string(1, static_cast<char>(id)) : "", id == 256};
  });
  const auto constraint = std::make_shared<TokenConstraint>();
  constraint->grammar = grammar; constraint->vocabulary = vocabulary;
  SamplingConfig config;
  config.temperature = 1; config.top_k = 0; config.top_p = 1; config.min_p = 0;
  config.constraint = constraint;
  SamplerState sampler(config);
  const std::array<TokenId, 1> first{'{'}; sampler.Accept(first);
  SamplerState clone = sampler, assigned; assigned = sampler;
  const std::array<TokenId, 1> close{'}'};
  clone.Accept(close); assigned.Accept(close);
  const std::array<TokenId, 1> other{'"'}; sampler.Accept(other);
  auto logits = std::vector<float>(257, 0);
  for (const auto *s : {&sampler, &clone, &assigned}) {
    const auto distribution = s->Distribution(logits);
    for (uint32_t id = 0; id < 257; ++id)
      std::printf("%u", distribution.probability(id) > 0);
    std::puts("");
  }
  std::printf("REQUEST_STATE_COPY_ORACLES=%zu HOST_NOT_INFERENCE\n", checks);
}
