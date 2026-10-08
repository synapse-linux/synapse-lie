// SPDX-License-Identifier: MIT
// Exception/publication translation only; parsing and typed staging are C17.
#ifndef LIE_GUFO_JSON_PARSE_HPP
#define LIE_GUFO_JSON_PARSE_HPP
#include "lie/json_value.h"
#include <new>
#include <stdexcept>
#include <string>
#include <string_view>
namespace lie_gufo {
inline gufo::json::Value parse_json(std::string_view text) {
  const auto d=gufo::json::Value::description();
  lie_json_value *root=nullptr;lie_json_parse_error error{};
  const auto rc=lie_json_value_parse(text.data(),text.size(),&d,nullptr,&root,&error,nullptr);
  if (rc==LIE_JSON_VALUE_RESOURCE) throw std::bad_alloc();
  if (rc==LIE_JSON_VALUE_SYNTAX)
    throw std::runtime_error(std::string("JSON parse error: ")+error.message);
  if (rc!=LIE_JSON_VALUE_OK) throw std::runtime_error("JSON value resource limit exceeded");
  return gufo::json::Value::adopt(root);
}
} // namespace lie_gufo
#endif
