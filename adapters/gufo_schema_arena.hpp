// SPDX-License-Identifier: MIT
// Private facade/error projections only; native construction/storage is C17.
#ifndef LIE_GUFO_SCHEMA_ARENA_HPP
#define LIE_GUFO_SCHEMA_ARENA_HPP
#include "lie/schema_arena.h"
#include "src/core/json.hpp"
#include "src/core/json_schema_lexeme.hpp"
#include <cstring>
#include <exception>
#include <stdexcept>
namespace lie_gufo {
inline lie_schema_transform_description schema_reader();
inline void schema_check(lie_schema_status, const lie_schema_error &);
class NativeSchemaArena {
  using Value = gufo::json::Value;
  lie_schema_arena *arena_ = nullptr;
  std::exception_ptr failure_;
  void native_check(lie_schema_status rc) {
    if (rc == LIE_SCHEMA_OK) return;
    lie_schema_arena_error e{}; lie_schema_arena_error_describe(arena_, &e);
    if (rc == LIE_SCHEMA_RESOURCE || e.value_status == LIE_JSON_VALUE_RESOURCE ||
        e.store_status == LIE_JSON_STORE_RESOURCE) throw std::bad_alloc();
    if (e.value_status != LIE_JSON_VALUE_OK) {
      if (e.value_status == LIE_JSON_VALUE_NONFINITE)
        throw std::invalid_argument("JSON numbers must be finite");
      if (e.value_status == LIE_JSON_VALUE_LIMIT)
        throw std::runtime_error("JSON value resource limit exceeded");
      throw std::runtime_error("invalid C17 JSON value operation");
    }
    if (e.store_status != LIE_JSON_STORE_OK) {
      if (e.store_status == LIE_JSON_STORE_LIMIT)
        throw std::invalid_argument("JSON Schema: schema expansion exceeds its resource budget");
      throw std::logic_error("invalid schema root ownership operation");
    }
    if (rc == LIE_SCHEMA_INVALID && e.schema_error.message &&
        std::strcmp(e.schema_error.message, "JSON numbers must be finite") == 0)
      throw std::invalid_argument(e.schema_error.message);
    if (rc == LIE_SCHEMA_CALLBACK && e.schema_error.message &&
        (std::strcmp(e.schema_error.message, "JSON number serialization failed") == 0 ||
         std::strcmp(e.schema_error.message, "JSON parse error: bad number") == 0))
      throw std::runtime_error(e.schema_error.message);
    schema_check(rc, e.schema_error);
  }
  static const Value &value(lie_schema_node n) { return *static_cast<const Value *>(n); }
  static lie_json_value *mutable_value(lie_schema_node n) {
    return const_cast<lie_json_value *>(value(n).raw());
  }
  static lie_schema_status clone(void *p, lie_schema_node n, lie_schema_node *out) noexcept {
    auto &a = *static_cast<NativeSchemaArena *>(p);
    return a.invoke([&](auto &) {
      lie_json_value *root = nullptr;
      a.native_check(lie_schema_arena_clone(a.arena_, value(n).raw(), &root));
      *out = &Value::facade(root);
    });
  }
  static lie_schema_status create(void *p, const lie_schema_value *v, lie_schema_node *out) noexcept {
    auto &a = *static_cast<NativeSchemaArena *>(p);
    return a.invoke([&](auto &) {
      lie_json_value *root = nullptr;
      a.native_check(lie_schema_arena_make(a.arena_, v, &root));
      *out = &Value::facade(root);
    });
  }
  static lie_schema_status put(void *p, lie_schema_node n, lie_schema_bytes key,
      lie_schema_node v) noexcept {
    auto &a = *static_cast<NativeSchemaArena *>(p);
    return a.invoke([&](auto &) {
      a.native_check(lie_schema_arena_put(a.arena_, mutable_value(n), key, value(v).raw()));
    });
  }
  static lie_schema_status append(void *p, lie_schema_node n, lie_schema_node v) noexcept {
    auto &a = *static_cast<NativeSchemaArena *>(p);
    return a.invoke([&](auto &) {
      a.native_check(lie_schema_arena_append(a.arena_, mutable_value(n), value(v).raw()));
    });
  }
  static lie_schema_status format(void *p, lie_schema_bytes text, lie_schema_node *out) noexcept {
    auto &a = *static_cast<NativeSchemaArena *>(p);
    return a.invoke([&](auto &) {
      lie_json_value *root = nullptr;
      a.native_check(lie_schema_arena_format(a.arena_, text, &root));
      *out = &Value::facade(root);
    });
  }
  static lie_schema_status multiple(void *p, lie_schema_node left, lie_schema_node right,
      lie_schema_node *out) noexcept {
    auto &a = *static_cast<NativeSchemaArena *>(p);
    return a.invoke([&](auto &) {
      lie_json_value *root = nullptr;
      a.native_check(lie_schema_arena_multiple(a.arena_, value(left).raw(), value(right).raw(), &root));
      *out = &Value::facade(root);
    });
  }
public:
  NativeSchemaArena() {
    lie_schema_arena_description d; lie_schema_arena_description_init(&d);
    d.values = Value::description();
    const auto rc = lie_schema_arena_create(&d, &arena_);
    if (rc == LIE_SCHEMA_RESOURCE) throw std::bad_alloc();
    if (rc != LIE_SCHEMA_OK) throw std::invalid_argument("JSON Schema: invalid native schema arena");
  }
  ~NativeSchemaArena() { lie_schema_arena_release(arena_); }
  NativeSchemaArena(const NativeSchemaArena &) = delete;
  NativeSchemaArena &operator=(const NativeSchemaArena &) = delete;
  template<class F> lie_schema_status invoke(F &&f) noexcept {
    try { f(*this); return LIE_SCHEMA_OK; }
    catch (const gufo::sampling::JsonSchemaEmpty &) {
      failure_ = std::current_exception(); return LIE_SCHEMA_EMPTY;
    } catch (...) { failure_ = std::current_exception(); return LIE_SCHEMA_CALLBACK; }
  }
  static lie_schema_status append_member(void *p, lie_schema_node n,
      lie_schema_bytes key, lie_schema_node v) noexcept {
    auto &a = *static_cast<NativeSchemaArena *>(p);
    return a.invoke([&](auto &) {
      a.native_check(lie_schema_arena_append_member(a.arena_, mutable_value(n), key, value(v).raw()));
    });
  }
  lie_schema_transform_description description() {
    auto d = schema_reader(); d.access.context = this;
    d.access.clone = clone; d.access.create = create; d.access.put = put;
    d.access.append = append; d.access.format = format; d.access.multiple = multiple;
    return d;
  }
  void rethrow_if_failed(lie_schema_status rc, const lie_schema_error &e) {
    if (failure_ && (rc == LIE_SCHEMA_CALLBACK || (rc == LIE_SCHEMA_EMPTY && !e.message)))
      std::rethrow_exception(failure_);
  }
  void check(lie_schema_status rc, const lie_schema_error &e) {
    rethrow_if_failed(rc, e); schema_check(rc, e);
  }
  Value take(lie_schema_node n) {
    lie_json_value *root = nullptr;
    native_check(lie_schema_arena_take(arena_, value(n).raw(), &root));
    return Value::adopt(root);
  }
  Value conjoin(const Value &root, const Value &left, const Value &right, unsigned depth) {
    const auto d = description();
    lie_schema_node out = nullptr; lie_schema_error error{};
    check(lie_schema_conjoin(&d, &root, &left, &right, depth, &out, &error), error);
    return take(out);
  }
};
} // namespace lie_gufo
#endif
