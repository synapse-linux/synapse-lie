// SPDX-License-Identifier: MIT
// HOST storage/lifetime controls, never model inference or timing evidence.
#include "src/core/json.hpp"
#include "src/core/json_constraint.hpp"
#include "gufo_grammar_builder.hpp"
#include "gufo_grammar_composition.hpp"
#include "allocation_counter.hpp"
#include <cassert>
#include <cstdlib>
#include <iostream>
#include <optional>

using Program = std::shared_ptr<const lie_grammar_program>;
struct Allocations { size_t live = 0; };
static void *allocate(void *context, size_t bytes) {
  void *p = std::malloc(bytes);
  if (p) ++static_cast<Allocations *>(context)->live;
  return p;
}
static void release(void *context, void *p) {
  if (!p) return;
  auto &live = static_cast<Allocations *>(context)->live;
  assert(live); --live; std::free(p);
}
struct Predicate final : gufo::sampling::JsonSchemaLexeme {
  explicit Predicate(lie_grammar_lexeme *p) : JsonSchemaLexeme(p) {}
};
static lie_gufo::Builder build(size_t extra, lie_gufo::Lexemes &lexemes,
                               Allocations &allocations, uint32_t &root) {
  const lie_grammar_allocator hooks{&allocations, allocate, release};
  lie_lexeme_description description;
  lie_lexeme_description_init(&description);
  description.allocator = hooks;
  lie_grammar_lexeme *whitespace = nullptr;
  lie_gufo::lexeme_check(lie_lexeme_whitespace_create(&description, &whitespace));
  lexemes.push_back(std::make_shared<Predicate>(whitespace));
  auto b = lie_gufo::builder_create();
  // JSON permits empty whitespace. A raw predicate consumes at least one byte.
  const uint32_t whitespace_symbol = LIE_GRAMMAR_LEXEME;
  uint32_t whitespace_rule = 0, optional_whitespace = 0;
  lie_gufo::builder_check(lie_builder_sequence_make(b.get(), &whitespace_symbol,
                                                   1, &whitespace_rule));
  lie_gufo::builder_check(lie_builder_optional(b.get(), whitespace_rule,
                                              &optional_whitespace));
  const uint32_t symbols[] = {optional_whitespace,
      LIE_GRAMMAR_TERMINAL | '{', LIE_GRAMMAR_TERMINAL | '}',
      optional_whitespace};
  const lie_builder_sequence seq{symbols, std::size(symbols)};
  lie_gufo::builder_check(lie_builder_new(b.get(), &seq, 1, &root));
  for (size_t i = 0; i < extra; ++i) {
    const uint8_t bytes[] = {uint8_t('a' + i % 20), uint8_t('A' + i % 20)};
    uint32_t symbol = 0, rule = 0;
    lie_gufo::builder_check(lie_builder_class(b.get(), bytes, 2, &symbol));
    const lie_builder_sequence alternative{&symbol, 1};
    lie_gufo::builder_check(lie_builder_new(b.get(), &alternative, 1, &rule));
  }
  return b;
}
static bool accepts(const Program &p, std::string_view text) {
  lie_grammar_state *state = nullptr;
  lie_gufo::grammar_check(lie_grammar_start(p.get(), &state));
  for (unsigned char byte : text) {
    lie_grammar_state *next = nullptr;
    lie_gufo::grammar_check(lie_grammar_advance(p.get(), state, byte, &next));
    lie_grammar_state_release(state); state = next;
  }
  const bool complete = lie_grammar_complete(state);
  lie_grammar_state_release(state); return complete;
}
int main() {
  size_t handoffs = 0, refusals = 0;
  for (const size_t extra : {size_t(0), size_t(64), size_t(4096)}) {
    Allocations allocations;
    {
      lie_gufo::Lexemes lexemes;
      uint32_t root = 0;
      auto builder = build(extra, lexemes, allocations, root);
      lie_sampling_alloc_begin();
      auto program = lie_gufo::builder_finish(builder.get(), lexemes, root);
      builder.reset(); // The program must own copied C tables now.
      lie_grammar_description d;
      lie_gufo::grammar_check(lie_grammar_program_describe(program.get(), &d));
      assert(d.rule_count == extra + 3 && d.class_count == extra + 256);
      assert(accepts(program, "{}"));
      assert(accepts(program, " \t{}\n"));
      assert(!accepts(program, "[]"));
      program.reset();
      const auto counts = lie_sampling_alloc_end();
      assert(counts.calls <= 1 && counts.live_bytes == 0);
      std::cout << "BUILDER " << extra << " CPP_CALLS=" << counts.calls
                << " CPP_PEAK=" << counts.peak_live_bytes << '\n';
      ++handoffs;
    }
    assert(allocations.live == 0);
    for (const bool tools : {false, true}) {
      {
        lie_gufo::Lexemes destination;
        std::optional<lie_gufo::Lexemes> original;
        original.emplace(); uint32_t source_root = 0;
        auto builder = build(extra, *original, allocations, source_root);
        auto source = lie_gufo::builder_finish(builder.get(), *original, source_root);
        builder.reset();
        lie_composition_description description;
        lie_composition_description_init(&description);
        lie_grammar_composition *raw = nullptr;
        if (tools) {
          const lie_composition_tool tool{reinterpret_cast<const uint8_t *>("call"),
                                           4, source.get()};
          lie_gufo::composition_check(lie_composition_tools(&description,
              source.get(), false, &tool, 1, true, false, &raw));
        } else {
          lie_gufo::composition_check(lie_composition_reasoning(&description,
              source.get(), true, &raw));
        }
        lie_gufo::Composition composition(raw, lie_composition_release);
        const lie_gufo::CompositionSource imports[] = {{source.get(), &*original}};
        uint32_t root = UINT32_MAX; bool stop = false;
        const auto *prior_table = destination.native();
        const size_t prior_live = allocations.live;
        try {
          (void)lie_gufo::composition_finish(composition, {}, destination, root, stop);
          assert(false);
        } catch (const std::logic_error &error) {
          assert(std::string_view(error.what()) ==
                 "C17 grammar composition lost a predicate owner");
          assert(destination.native() == prior_table && destination.size() == 0);
          assert(root == UINT32_MAX && !stop && allocations.live == prior_live);
          ++refusals;
        }
        lie_sampling_alloc_begin();
        auto program = lie_gufo::composition_finish(composition, imports,
                                                    destination, root, stop);
        composition.reset(); source.reset(); original.reset();
        assert(allocations.live > 0); // Only destination retains the predicate.
        assert(accepts(program, tools
            ? "<tool_call>{\"name\":\"call\",\"arguments\":{}}</tool_call>"
            : "thought</think> \t{}\n"));
        assert(!accepts(program, tools ? "{}" : "thought</think>[]"));
        program.reset();
        const auto counts = lie_sampling_alloc_end();
        assert(counts.calls <= 1 && counts.live_bytes == 0);
        std::cout << (tools ? "TOOLS " : "REASONING ") << extra
                  << " CPP_CALLS=" << counts.calls << " CPP_PEAK="
                  << counts.peak_live_bytes << '\n';
        ++handoffs;
      }
      assert(allocations.live == 0);
    }
  }
  std::cout << "HANDOFFS=" << handoffs << " OWNER_REFUSALS=" << refusals
            << " JSON_CONSTRAINT_BYTES=" << sizeof(gufo::sampling::JsonConstraint)
            << " HOST_NOT_INFERENCE\n";
}
