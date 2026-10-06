// SPDX-License-Identifier: MIT
// Borrowed JSON views, private staging storage and leaf/error translation only.
#ifndef LIE_GUFO_SCHEMA_TRANSFORM_HPP
#define LIE_GUFO_SCHEMA_TRANSFORM_HPP
#include "lie/schema_transform.h"
#include "lie/schema_format.h"
#include "src/core/json_schema_lexeme.hpp"
#include <deque>
#include <exception>
#include <stdexcept>
namespace lie_gufo {
using SchemaValue = gufo::json::Value;
inline const SchemaValue &schema_value(lie_schema_node n) { return *static_cast<const SchemaValue *>(n); }
inline lie_schema_status schema_describe(void *, lie_schema_node n, lie_schema_value *out) noexcept {
  const auto &v=schema_value(n);
  *out={}; out->count=v.size(); out->number=v.as_double(); out->boolean=v.as_bool();
  switch (v.type()) {
  case SchemaValue::Type::kNull: out->kind=LIE_SCHEMA_NULL; break;
  case SchemaValue::Type::kBool: out->kind=LIE_SCHEMA_BOOL; break;
  case SchemaValue::Type::kNumber: out->kind=LIE_SCHEMA_NUMBER; break;
  case SchemaValue::Type::kString: {
    out->kind=LIE_SCHEMA_STRING;size_t bytes=0;
    const char *text=lie_json_value_string(v.raw(),&bytes);out->text={text,bytes};break;
  }
  case SchemaValue::Type::kArray: out->kind=LIE_SCHEMA_ARRAY; break;
  case SchemaValue::Type::kObject: out->kind=LIE_SCHEMA_OBJECT; break;
  }
  return LIE_SCHEMA_OK;
}
inline lie_schema_status schema_child(void *, lie_schema_node n, size_t i,
    lie_schema_bytes *key, lie_schema_node *out) noexcept {
  const auto &v=schema_value(n); if (i>=v.size()) return LIE_SCHEMA_INVALID;
  *key={};
  if (v.is_array()) *out=&v.items()[i];
  else if (v.is_object()) {
    const auto *child=lie_json_value_at(v.raw(),true,i);size_t bytes=0;
    const char *text=lie_json_value_key(child,&bytes);*key={text,bytes};*out=&SchemaValue::facade(child);
  }
  else return LIE_SCHEMA_INVALID;
  return LIE_SCHEMA_OK;
}
inline void schema_check(lie_schema_status rc, const lie_schema_error &e) {
  if (rc==LIE_SCHEMA_OK) return;
  if (rc==LIE_SCHEMA_RESOURCE) throw std::bad_alloc();
  std::string text="JSON Schema: "; text+=e.message ? e.message : "invalid schema transformation";
  if (e.detail.size) text.append(e.detail.data,e.detail.size);
  if (e.suffix) text+=e.suffix;
  if (rc==LIE_SCHEMA_EMPTY) throw gufo::sampling::JsonSchemaEmpty(text);
  if (rc==LIE_SCHEMA_WORK_LIMIT) throw std::runtime_error(text);
  throw std::invalid_argument(text);
}
inline lie_schema_transform_description schema_reader() {
  lie_schema_transform_description d; lie_schema_transform_description_init(&d);
  d.access.describe=schema_describe; d.access.child=schema_child; return d;
}
inline bool schema_equal(const SchemaValue &a, const SchemaValue &b) {
  const auto d=schema_reader(); bool same=false; lie_schema_error e{};
  schema_check(lie_schema_equal(&d,&a,&b,&same,&e),e); return same;
}
inline const SchemaValue *schema_reference(const SchemaValue &root, const SchemaValue &ref) {
  const auto d=schema_reader(); lie_schema_node out=nullptr; lie_schema_error e{};
  schema_check(lie_schema_reference(&d,&root,&ref,&out,&e),e);
  return static_cast<const SchemaValue *>(out);
}
inline void schema_keys(const SchemaValue &n) {
  const auto d=schema_reader(); lie_schema_error e{};
  schema_check(lie_schema_keys(&d,&n,&e),e);
}
class SchemaArena {
  std::deque<SchemaValue> values_;
  std::exception_ptr failure_;
  template<class F> static lie_schema_status protect(void *p, F &&f) noexcept {
    auto &a=*static_cast<SchemaArena *>(p);
    return a.invoke(std::forward<F>(f));
  }
  SchemaValue *store(SchemaValue value) {
    if (values_.size()>=262144) throw std::invalid_argument("JSON Schema: schema expansion exceeds its resource budget");
    values_.push_back(std::move(value)); return &values_.back();
  }
  static lie_schema_status clone(void *p, lie_schema_node n, lie_schema_node *out) noexcept {
    return protect(p,[&](auto &a){ *out=a.store(schema_value(n)); });
  }
  static lie_schema_status create(void *p, const lie_schema_value *v, lie_schema_node *out) noexcept {
    return protect(p,[&](auto &a){
      SchemaValue n;
      switch (v->kind) {
      case LIE_SCHEMA_NULL: break;
      case LIE_SCHEMA_BOOL: n=SchemaValue(v->boolean); break;
      case LIE_SCHEMA_NUMBER: n=SchemaValue(v->number); break;
      case LIE_SCHEMA_STRING: n=SchemaValue(std::string(v->text.data,v->text.size)); break;
      case LIE_SCHEMA_ARRAY: n=SchemaValue::array(); break;
      case LIE_SCHEMA_OBJECT: n=SchemaValue::object(); break;
      }
      *out=a.store(std::move(n));
    });
  }
  static lie_schema_status put(void *p, lie_schema_node n, lie_schema_bytes key, lie_schema_node value) noexcept {
    return protect(p,[&](auto &){
      auto &target=*const_cast<SchemaValue *>(static_cast<const SchemaValue *>(n));
      target[std::string(key.data,key.size)]=schema_value(value);
    });
  }
  static lie_schema_status append(void *p, lie_schema_node n, lie_schema_node value) noexcept {
    return protect(p,[&](auto &){
      auto &target=*const_cast<SchemaValue *>(static_cast<const SchemaValue *>(n));
      target.push_back(schema_value(value));
    });
  }
  static lie_schema_status format(void *p, lie_schema_bytes text, lie_schema_node *out) noexcept {
    return protect(p,[&](auto &a){
      const auto d=a.description(); lie_schema_node result=nullptr; lie_schema_error e{};
      a.check(lie_schema_format_expand(&d,text,&result,&e),e); *out=result;
    });
  }
  static lie_schema_status multiple(void *p, lie_schema_node l, lie_schema_node r, lie_schema_node *out) noexcept {
    return protect(p,[&](auto &a){ *out=a.store(gufo::sampling::JsonSchemaLexeme::IntersectMultipleOf(schema_value(l),schema_value(r))); });
  }
public:
  static lie_schema_status append_member(void *p,lie_schema_node n,
      lie_schema_bytes key,lie_schema_node value) noexcept {
    return protect(p,[&](auto &){
      auto &target=*const_cast<SchemaValue *>(static_cast<const SchemaValue *>(n));
      target.append_member(std::string(key.data,key.size),schema_value(value));
    });
  }
  template<class F> lie_schema_status invoke(F &&f) noexcept {
    try { f(*this); return LIE_SCHEMA_OK; }
    catch (const gufo::sampling::JsonSchemaEmpty &) { failure_=std::current_exception(); return LIE_SCHEMA_EMPTY; }
    catch (...) { failure_=std::current_exception(); return LIE_SCHEMA_CALLBACK; }
  }
  lie_schema_transform_description description() {
    auto d=schema_reader(); d.access.context=this;
    d.access.clone=clone; d.access.create=create; d.access.put=put; d.access.append=append;
    d.access.format=format; d.access.multiple=multiple; return d;
  }
  void rethrow_if_failed(lie_schema_status rc,const lie_schema_error &e) {
    if (failure_ && (rc==LIE_SCHEMA_CALLBACK || (rc==LIE_SCHEMA_EMPTY && !e.message))) std::rethrow_exception(failure_);
  }
  void check(lie_schema_status rc,const lie_schema_error &e) {
    rethrow_if_failed(rc,e);
    schema_check(rc,e);
  }
  SchemaValue take(lie_schema_node n) {
    return std::move(*const_cast<SchemaValue *>(static_cast<const SchemaValue *>(n)));
  }
  SchemaValue conjoin(const SchemaValue &root,const SchemaValue &l,const SchemaValue &r,unsigned depth) {
    const auto d=description();
    lie_schema_node out=nullptr; lie_schema_error e{};
    const auto rc=lie_schema_conjoin(&d,&root,&l,&r,depth,&out,&e);
    check(rc,e); return take(out);
  }
};
inline SchemaValue schema_conjoin(const SchemaValue &root,const SchemaValue &l,const SchemaValue &r,unsigned depth) {
  SchemaArena a; return a.conjoin(root,l,r,depth);
}
} // namespace lie_gufo
#endif
