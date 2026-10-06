// SPDX-License-Identifier: MIT
// Typed Gufo tree construction/exception translation; syntax belongs to C17.
#ifndef LIE_GUFO_JSON_PARSE_HPP
#define LIE_GUFO_JSON_PARSE_HPP
#include "lie/json_parse.h"
#include <exception>
#include <new>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>
namespace lie_gufo {
class JsonTreeSink {
  using Value=gufo::json::Value;
  struct Frame { Value value; std::string key; };
  std::vector<Frame> frames_;
  Value root_;
  std::exception_ptr failure_;
  void attach(Value value) {
    if (frames_.empty()) root_=std::move(value);
    else if (frames_.back().value.is_object())
      frames_.back().value.append_member(std::move(frames_.back().key),std::move(value));
    else frames_.back().value.push_back(std::move(value));
  }
  void event(const lie_json_event &e) {
    switch (e.kind) {
    case LIE_JSON_BEGIN_OBJECT: frames_.push_back({Value::object(),{}});break;
    case LIE_JSON_BEGIN_ARRAY: frames_.push_back({Value::array(),{}});break;
    case LIE_JSON_END_OBJECT:case LIE_JSON_END_ARRAY: {
      Value value=std::move(frames_.back().value);frames_.pop_back();attach(std::move(value));break;
    }
    case LIE_JSON_KEY: frames_.back().key.assign(e.text,e.text_bytes);break;
    case LIE_JSON_STRING: attach(Value(std::string(e.text,e.text_bytes)));break;
    case LIE_JSON_NUMBER: attach(Value(e.number));break;
    case LIE_JSON_BOOL: attach(Value(e.boolean));break;
    case LIE_JSON_NULL: attach(Value());break;
    }
  }
  static bool emit(void *context,const lie_json_event *e) noexcept {
    auto &sink=*static_cast<JsonTreeSink *>(context);
    try { sink.event(*e);return true; }
    catch (...) { sink.failure_=std::current_exception();return false; }
  }
public:
  Value parse(std::string_view text) {
    lie_json_sink sink{this,emit};lie_json_parse_error error{};
    const auto rc=lie_json_parse_events(text.data(),text.size(),nullptr,&sink,&error,nullptr);
    if (failure_) std::rethrow_exception(failure_);
    if (rc==LIE_JSON_PARSE_RESOURCE) throw std::bad_alloc();
    if (rc!=LIE_JSON_PARSE_OK)
      throw std::runtime_error(std::string("JSON parse error: ")+error.message);
    return std::move(root_);
  }
};
inline gufo::json::Value parse_json(std::string_view text) {
  JsonTreeSink sink;return sink.parse(text);
}
} // namespace lie_gufo
#endif
