// SPDX-License-Identifier: MIT
// Borrowed JSON views, binary64 codec and typed exceptions only.
#ifndef LIE_GUFO_SCHEMA_NUMBER_HPP
#define LIE_GUFO_SCHEMA_NUMBER_HPP
#include "lie/schema_number.h"
#include "gufo_schema_transform.hpp"
#include <charconv>
#include <cstring>
namespace lie_gufo {
class SchemaNumber {
  std::exception_ptr failure_;
  static lie_schema_status serialize(void *p, double value, char *text,
      size_t capacity, size_t *bytes) noexcept {
    auto &self = *static_cast<SchemaNumber *>(p);
    return self.invoke([&](auto &) {
      const auto result = std::to_chars(text, text + capacity, value);
      if (result.ec != std::errc{})
        throw std::runtime_error("JSON number serialization failed");
      *bytes = static_cast<size_t>(result.ptr - text);
    });
  }
  static lie_schema_status parse(void *p, lie_schema_bytes text, double *out) noexcept {
    auto &self = *static_cast<SchemaNumber *>(p);
    return self.invoke([&](auto &) {
      *out = gufo::json::parse(std::string_view(text.data, text.size)).as_double();
    });
  }
public:
  template<class F> lie_schema_status invoke(F &&f) noexcept {
    try { f(*this); return LIE_SCHEMA_OK; }
    catch (const gufo::sampling::JsonSchemaEmpty &) {
      failure_ = std::current_exception(); return LIE_SCHEMA_EMPTY;
    }
    catch (...) { failure_ = std::current_exception(); return LIE_SCHEMA_CALLBACK; }
  }
  lie_schema_number_description description() {
    lie_schema_number_description d;
    lie_schema_number_description_init(&d);
    d.transform = schema_reader();
    d.conversion_context = this;
    d.serialize = serialize;
    d.parse = parse;
    return d;
  }
  void check(lie_schema_status rc, const lie_schema_error &e) {
    // Value::dump's codec diagnostic has no schema prefix. Policy validation
    // and selection remain in C; this preserves its typed presentation.
    if (rc == LIE_SCHEMA_INVALID && e.message &&
        std::strcmp(e.message, "JSON numbers must be finite") == 0)
      throw std::invalid_argument(e.message);
    if (failure_ && (rc == LIE_SCHEMA_CALLBACK || (rc == LIE_SCHEMA_EMPTY && !e.message)))
      std::rethrow_exception(failure_);
    schema_check(rc, e);
  }
  std::shared_ptr<const lie_number_policy> create(const SchemaValue &schema, bool integer) {
    const auto d = description();
    lie_number_policy *out = nullptr;
    lie_schema_error e{};
    check(lie_schema_number_create(&d, &schema, integer, &out, &e), e);
    // The shared_ptr constructor calls its deleter if control allocation fails.
    return {out, lie_number_release};
  }
  bool accept(const lie_number_policy *policy, const SchemaValue &value) {
    const auto d = description();
    bool out = false;
    lie_schema_error e{};
    check(lie_schema_number_accept(&d, policy, &value, &out, &e), e);
    return out;
  }
  SchemaValue intersect(const SchemaValue &left, const SchemaValue &right) {
    const auto d = description();
    double out = 0;
    lie_schema_error e{};
    check(lie_schema_number_intersect(&d, &left, &right, &out, &e), e);
    return SchemaValue(out);
  }
  uint32_t literal(const SchemaValue &value, lie_grammar_builder *builder) {
    const auto d = description();
    uint32_t out = 0;
    lie_schema_error e{};
    check(lie_schema_number_literal(&d, &value, builder, &out, &e), e);
    return out;
  }
};
} // namespace lie_gufo
#endif
