// SPDX-License-Identifier: MIT
// Provider leaf/cache/storage/exception translation; tree algorithms are C17.
#ifndef LIE_GUFO_SCHEMA_VALUES_HPP
#define LIE_GUFO_SCHEMA_VALUES_HPP
#include "gufo_grammar_builder.hpp"
#include "gufo_schema_transform.hpp"
#include "gufo_schema_number.hpp"
#include "lie/schema_values.h"
#include <map>
#include <optional>
namespace lie_gufo {
#if LIE_C17_SAMPLING
class ValueChecks {
  lie_lexeme_memo *memo_ = nullptr;
  bool owns_ = true;
public:
  ValueChecks() { lexeme_check(lie_lexeme_memo_create(nullptr, &memo_)); }
  explicit ValueChecks(lie_lexeme_memo *borrowed) : memo_(borrowed), owns_(false) {
    if (!memo_) throw std::invalid_argument("JSON Schema: invalid borrowed predicate memo");
  }
  ~ValueChecks() { if (owns_) lie_lexeme_memo_release(memo_); }
  ValueChecks(const ValueChecks &) = delete;
  ValueChecks &operator=(const ValueChecks &) = delete;
  const lie_grammar_lexeme *find(const SchemaValue *key) const noexcept {
    return lie_lexeme_memo_get(memo_, key);
  }
  void put(const SchemaValue *key, const gufo::sampling::JsonSchemaLexeme &value) {
    lexeme_check(lie_lexeme_memo_put(memo_, key, value.C17Lexeme()));
  }
};
#else
using ValueChecks =
    std::map<const SchemaValue *,
             std::shared_ptr<const gufo::sampling::JsonSchemaLexeme>>;
#endif
inline lie_schema_values_description values_reader() {
  lie_schema_values_description d;
  lie_schema_values_description_init(&d);
  d.transform = schema_reader();
  return d;
}
inline bool values_matches(const SchemaValue &v, std::string_view type) {
  const auto d = values_reader();
  bool out = false;
  lie_schema_error e{};
  schema_check(
      lie_schema_matches_type(&d, &v, {type.data(), type.size()}, &out, &e), e);
  return out;
}
inline size_t values_characters(const SchemaValue &v, size_t remaining) {
  auto d = values_reader();
  d.max_characters = remaining;
  size_t out = 0;
  lie_schema_error e{};
  schema_check(lie_schema_value_characters(&d, &v, &out, &e), e);
  return out;
}
inline size_t values_characters(std::string_view v, size_t remaining) {
  auto d = values_reader();
  d.max_characters = remaining;
  size_t out = 0;
  lie_schema_error e{};
  schema_check(lie_schema_text_characters(&d, {v.data(), v.size()}, &out, &e),
               e);
  return out;
}
class SchemaValues {
  SchemaArena arena_;
  ValueChecks *checks_;
  static lie_schema_status put(void *p, lie_schema_node n, lie_schema_bytes key,
                               lie_schema_node value) noexcept {
#if LIE_C17_SAMPLING
    return SchemaArena::append_member(p, n, key, value);
#else
    auto &arena = *static_cast<SchemaArena *>(p);
    return arena.invoke([&](auto &) {
      auto &target =
          *const_cast<SchemaValue *>(static_cast<const SchemaValue *>(n));
      target.append_member(std::string(key.data, key.size),
                           schema_value(value));
    });
#endif
  }
  static lie_schema_status accept(void *p, lie_schema_node schema,
                                  lie_schema_node value, bool *out) noexcept {
    auto &v = *static_cast<SchemaValues *>(p);
    return v.arena_.invoke([&](auto &) {
#if LIE_C17_SAMPLING
      const auto *key = static_cast<const SchemaValue *>(schema);
      auto *predicate = v.checks_->find(key);
      if (!predicate) {
        const auto value_check = schema_value(value).is_string()
            ? gufo::sampling::JsonSchemaLexeme::String(schema_value(schema))
            : gufo::sampling::JsonSchemaLexeme::Number(schema_value(schema), false);
        v.checks_->put(key, *value_check); predicate = v.checks_->find(key);
      }
      *out = LexemeView(predicate).AcceptValue(schema_value(value));
#else
      auto &check = (*v.checks_)[static_cast<const SchemaValue *>(schema)];
      if (!check)
        check =
            schema_value(value).is_string()
                ? gufo::sampling::JsonSchemaLexeme::String(schema_value(schema))
                : gufo::sampling::JsonSchemaLexeme::Number(schema_value(schema),
                                                           false);
      *out = check->AcceptValue(schema_value(value));
#endif
    });
  }
  static lie_schema_status number(void *p, lie_schema_node value,
                                  lie_grammar_builder *b,
                                  uint32_t *out) noexcept {
    auto &v = *static_cast<SchemaValues *>(p);
    return v.arena_.invoke([&](auto &) {
      SchemaNumber number;
      *out = number.literal(schema_value(value), b);
    });
  }

public:
  explicit SchemaValues(ValueChecks *checks = nullptr) : checks_(checks) {}
  lie_schema_values_description description() {
    auto d = values_reader();
    d.transform = arena_.description();
    d.transform.access.put = put;
    d.leaf_context = this;
    d.accept = accept;
    d.number_literal = number;
    return d;
  }
  template <class F> lie_schema_status invoke(F &&f) noexcept {
    return arena_.invoke(std::forward<F>(f));
  }
  void check(lie_schema_status rc, const lie_schema_error &e) {
    arena_.check(rc, e);
  }
  void rethrow_if_failed(lie_schema_status rc,const lie_schema_error &e) {
    arena_.rethrow_if_failed(rc,e);
  }
  std::optional<SchemaValue> normalize(const SchemaValue &root,
                                       const SchemaValue &schema,
                                       const SchemaValue &value, size_t depth) {
    const auto d = description();
    lie_schema_normalized out{};
    lie_schema_error e{};
    check(lie_schema_normalize(&d, &root, &schema, &value, depth, &out, &e), e);
    return out.matched ? std::optional<SchemaValue>(arena_.take(out.value))
                       : std::nullopt;
  }
  uint32_t literal(const SchemaValue &value, lie_grammar_builder *b,
                   uint32_t ws) {
    const auto d = description();
    uint32_t out = 0;
    lie_schema_error e{};
    check(lie_schema_value_literal(&d, &value, b, ws, &out, &e), e);
    return out;
  }
};
inline std::optional<SchemaValue>
values_normalize(const SchemaValue &root, const SchemaValue &schema,
                 const SchemaValue &value, size_t depth, ValueChecks &checks) {
  SchemaValues v(&checks);
  return v.normalize(root, schema, value, depth);
}
inline uint32_t values_literal(const SchemaValue &value, lie_grammar_builder *b,
                               uint32_t ws) {
  SchemaValues v;
  return v.literal(value, b, ws);
}
template <class F> struct SchemaVisit {
  SchemaValues *values;
  F *visit;
  static lie_schema_status call(void *p, lie_schema_node n, size_t depth,
                                uint32_t *out) noexcept {
    auto &v = *static_cast<SchemaVisit *>(p);
    return v.values->invoke(
        [&](auto &) { *out = (*v.visit)(schema_value(n), depth); });
  }
};
template <class F>
inline uint32_t values_object(const SchemaValue &schema, size_t depth,
                              bool strict, lie_grammar_builder *b, uint32_t ws,
                              lie_schema_container_counts &counts, F visit) {
  SchemaValues v;
  const auto d = v.description();
  SchemaVisit<F> hook{&v, &visit};
  uint32_t out = 0;
  lie_schema_error e{};
  v.check(lie_schema_object(&d, &schema, depth, strict, b, ws,
                            {&hook, SchemaVisit<F>::call}, &counts, &out, &e),
          e);
  return out;
}
template <class F>
inline uint32_t values_array(const SchemaValue &schema, size_t depth,
                             lie_grammar_builder *b, uint32_t ws, F visit) {
  SchemaValues v;
  const auto d = v.description();
  SchemaVisit<F> hook{&v, &visit};
  uint32_t out = 0;
  lie_schema_error e{};
  v.check(lie_schema_array(&d, &schema, depth, b, ws,
                           {&hook, SchemaVisit<F>::call}, &out, &e),
          e);
  return out;
}
} // namespace lie_gufo
#endif
