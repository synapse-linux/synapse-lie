// SPDX-License-Identifier: MIT
// Private typed projections only; C17 owns retained roots and admission limits.
#ifndef LIE_GUFO_SCHEMA_STORE_HPP
#define LIE_GUFO_SCHEMA_STORE_HPP
#include "lie/json_store.h"
#include "src/core/json.hpp"
#include <stdexcept>
namespace lie_gufo {
class SchemaStore {
  lie_json_store *store_=nullptr;
  static void check(lie_json_store_status rc) {
    if (rc==LIE_JSON_STORE_OK) return;
    if (rc==LIE_JSON_STORE_RESOURCE) throw std::bad_alloc();
    if (rc==LIE_JSON_STORE_LIMIT)
      throw std::invalid_argument("JSON Schema: schema expansion exceeds its resource budget");
    throw std::logic_error("invalid schema root ownership operation");
  }
public:
  SchemaStore() { check(lie_json_store_create(nullptr,&store_)); }
  ~SchemaStore() { lie_json_store_release(store_); }
  SchemaStore(const SchemaStore &)=delete;
  SchemaStore &operator=(const SchemaStore &)=delete;
  const gufo::json::Value &store(gufo::json::Value value) {
    lie_json_value *root=nullptr;check(value.transfer_root(store_,&root));
    return gufo::json::Value::facade(root);
  }
  gufo::json::Value take(const gufo::json::Value &value) {
    lie_json_value *root=nullptr;check(lie_json_store_take(store_,value.raw(),&root));
    return gufo::json::Value::adopt(root);
  }
};
} // namespace lie_gufo
#endif
