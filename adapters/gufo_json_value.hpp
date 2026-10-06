// SPDX-License-Identifier: MIT
// Private C++ facade/projections only; authoritative values/tables belong to C17.
#ifndef LIE_GUFO_JSON_VALUE_HPP
#define LIE_GUFO_JSON_VALUE_HPP
#include "lie/json_value.h"
#include "lie/json_store.h"
#include <cmath>
#include <cstdint>
#include <exception>
#include <initializer_list>
#include <iterator>
#include <limits>
#include <mutex>
#include <new>
#include <stdexcept>
#include <string>
#include <string_view>
#include <type_traits>
#include <utility>
namespace gufo::json {
class Value;
class ArrayView;
class ObjectView;
struct MemberView { const std::string &first;const Value &second; };
class Value {
  lie_json_value *node_=nullptr;
  bool owns_=true;
  lie_json_value_kind shadow_kind_=LIE_JSON_VALUE_NULL;
  bool shadow_bool_=false;double shadow_number_=0;
  mutable std::string string_projection_,key_projection_;
  mutable uint64_t string_revision_=0;
  mutable bool key_ready_=false;
  mutable std::mutex projection_mutex_;
  Value(lie_json_value *n,bool owns):node_(n),owns_(owns) {}
  static bool initialize(void *,lie_json_value *n,void *storage) noexcept {
    new (storage) Value(n,false);return true;
  }
  static void release_view(void *,void *storage) noexcept {
    static_cast<Value *>(storage)->~Value();
  }
  static void check(lie_json_value_status rc) {
    if (rc==LIE_JSON_VALUE_OK) return;
    if (rc==LIE_JSON_VALUE_RESOURCE) throw std::bad_alloc();
    if (rc==LIE_JSON_VALUE_NONFINITE) throw std::invalid_argument("JSON numbers must be finite");
    if (rc==LIE_JSON_VALUE_LIMIT) throw std::runtime_error("JSON value resource limit exceeded");
    throw std::runtime_error("invalid C17 JSON value operation");
  }
  void scalar(lie_json_value_kind kind,bool boolean= false,double number=0,
              const char *text=nullptr,size_t bytes=0) {
    ensure();check(lie_json_value_set(node_,kind,boolean,number,text,bytes));
  }
  void ensure() {
    if (node_) return;
    const auto d=description();check(lie_json_value_create(&d,&node_));
    try { check(lie_json_value_set(node_,shadow_kind_,shadow_bool_,shadow_number_,nullptr,0)); }
    catch (...) { lie_json_value_release(node_);node_=nullptr;throw; }
  }
  void remember_moved() noexcept {
    if (!node_) return;
    shadow_kind_=lie_json_value_type(node_);shadow_bool_=lie_json_value_boolean(node_,false);
    shadow_number_=lie_json_value_number(node_,0);
  }
public:
  enum class Type:std::uint8_t { kNull,kBool,kNumber,kString,kArray,kObject };
  using Array=ArrayView;using Member=MemberView;using Object=ObjectView;
  Value()=default;Value(std::nullptr_t) {}
  Value(bool v):Value() { scalar(LIE_JSON_VALUE_BOOL,v); }
  Value(double v):Value() { scalar(LIE_JSON_VALUE_NUMBER,false,v); }
  Value(int v):Value(static_cast<double>(v)) {}
  Value(long v):Value(static_cast<double>(v)) {}
  Value(long long v):Value(static_cast<double>(v)) {}
  Value(unsigned long long v):Value(static_cast<double>(v)) {}
  Value(std::size_t v):Value(static_cast<double>(v)) {}
  Value(const char *v):Value(std::string_view(v)) {}
  Value(const std::string &v):Value(std::string_view(v)) {}
  Value(std::string &&v):Value(std::string_view(v)) {}
  explicit Value(std::string_view v):Value() { scalar(LIE_JSON_VALUE_STRING,false,0,v.data(),v.size()); }
  Value(const Value &v):Value() {
    if (v.node_) { const auto d=description();check(lie_json_value_clone(v.node_,&d,&node_)); }
    else if (v.shadow_kind_!=LIE_JSON_VALUE_NULL) scalar(v.shadow_kind_,v.shadow_bool_,v.shadow_number_);
  }
  Value(Value &&v) {
    if (v.owns_) {
      v.remember_moved();node_=v.node_;v.node_=nullptr;shadow_kind_=v.shadow_kind_;
      shadow_bool_=v.shadow_bool_;shadow_number_=v.shadow_number_;
    }
    else { const auto d=description();check(lie_json_value_move_clone(v.node_,&d,&node_)); }
  }
  ~Value() { if (owns_) lie_json_value_release(node_); }
  Value &operator=(const Value &v) {
    if (this==&v) return *this;
    if (!owns_) {
      if (v.node_ || v.shadow_kind_==LIE_JSON_VALUE_NULL) check(lie_json_value_assign(node_,v.node_));
      else { Value copy(v);check(lie_json_value_assign(node_,copy.node_)); }
      return *this;
    }
    Value copy(v);std::swap(node_,copy.node_);shadow_kind_=v.shadow_kind_;
    shadow_bool_=v.shadow_bool_;shadow_number_=v.shadow_number_;string_revision_=0;return *this;
  }
  Value &operator=(Value &&v) {
    if (this==&v) return *this;
    if (!owns_ || !v.owns_) {
      ensure();v.ensure();check(lie_json_value_move_assign(node_,v.node_));return *this;
    }
    v.remember_moved();lie_json_value_release(node_);node_=v.node_;v.node_=nullptr;
    shadow_kind_=v.shadow_kind_;shadow_bool_=v.shadow_bool_;shadow_number_=v.shadow_number_;
    string_revision_=0;
    return *this;
  }
  static lie_json_value_description description() {
    lie_json_value_description d;lie_json_value_description_init(&d);
    d.view_bytes=sizeof(Value);d.view_initialize=initialize;d.view_release=release_view;return d;
  }
  static Value adopt(lie_json_value *n) { return Value(n,true); }
  // Refusal retains this owning facade. Success publishes an exact root into
  // the C17 collection before relinquishing it; no inline-view move/clone.
  lie_json_store_status transfer_root(lie_json_store *store,lie_json_value **out) {
    if (!owns_ || !store || !out) return LIE_JSON_STORE_INVALID;
    ensure();
    const auto rc=lie_json_store_adopt(store,node_);
    if (rc==LIE_JSON_STORE_OK) {
      remember_moved();*out=node_;node_=nullptr;
    }
    return rc;
  }
  const lie_json_value *native() const noexcept { return node_; }
  const lie_json_value *native() {
    if (!node_ && shadow_kind_!=LIE_JSON_VALUE_NULL) ensure();
    return node_;
  }
  const lie_json_value *raw() const noexcept { return node_; }
  static const Value &facade(const lie_json_value *n) noexcept {
    return *static_cast<const Value *>(lie_json_value_view(n));
  }
  static Value object() { Value v;v.scalar(LIE_JSON_VALUE_OBJECT);return v; }
  static Value array() { Value v;v.scalar(LIE_JSON_VALUE_ARRAY);return v; }
  Type type() const noexcept { return static_cast<Type>(node_ ? lie_json_value_type(node_) : shadow_kind_); }
  bool is_null() const noexcept { return type()==Type::kNull; }
  bool is_bool() const noexcept { return type()==Type::kBool; }
  bool is_number() const noexcept { return type()==Type::kNumber; }
  bool is_string() const noexcept { return type()==Type::kString; }
  bool is_array() const noexcept { return type()==Type::kArray; }
  bool is_object() const noexcept { return type()==Type::kObject; }
  Value &operator[](const std::string &key) {
    ensure();lie_json_value *child=nullptr;
    check(lie_json_value_member(node_,key.data(),key.size(),&child));
    return const_cast<Value &>(facade(child));
  }
  const Value *find(const std::string &key) const noexcept {
    const auto *child=lie_json_value_find(node_,key.data(),key.size());
    return child ? &facade(child) : nullptr;
  }
  bool contains(const std::string &key) const noexcept { return find(key)!=nullptr; }
  Object members() const noexcept;
  void append_member(std::string key,Value value) {
    ensure();check(lie_json_value_append_member(node_,key.data(),key.size(),value.native(),nullptr));
  }
  std::string member_str(const std::string &key,const std::string &def="") const {
    const auto *v=find(key);return v && v->is_string() ? v->str() : def;
  }
  std::size_t member_size(const std::string &key,std::size_t def=0) const noexcept {
    const auto *v=find(key);return v ? v->as_size(def) : def;
  }
  double member_double(const std::string &key,double def=0) const noexcept {
    const auto *v=find(key);return v ? v->as_double(def) : def;
  }
  void push_back(Value value) { ensure();check(lie_json_value_append(node_,value.native(),nullptr)); }
  void push_back() { ensure();check(lie_json_value_append(node_,nullptr,nullptr)); }
  Array items() const noexcept;
  std::size_t size() const noexcept { return lie_json_value_size(node_); }
  bool empty() const noexcept { return size()==0; }
  bool as_bool(bool def=false) const noexcept { return node_ ? lie_json_value_boolean(node_,def) : is_bool() ? shadow_bool_ : def; }
  double as_double(double def=0) const noexcept { return node_ ? lie_json_value_number(node_,def) : is_number() ? shadow_number_ : def; }
  std::size_t as_size(std::size_t def=0) const noexcept {
    if (node_) return lie_json_value_size_number(node_,def);
    const double n=shadow_number_;
    return is_number() && std::isfinite(n) && n>=0 && std::floor(n)==n &&
      n<std::ldexp(1.0,std::numeric_limits<std::size_t>::digits) ? static_cast<std::size_t>(n) : def;
  }
  const std::string &str() const {
    static const std::string empty;
    if (!is_string() || !node_) return empty;
    const std::lock_guard<std::mutex> lock(projection_mutex_);
    const auto revision=lie_json_value_revision(node_);
    if (string_revision_!=revision) {
      size_t bytes=0;const char *text=lie_json_value_string(node_,&bytes);
      string_projection_.assign(text,bytes);string_revision_=revision;
    }
    return string_projection_;
  }
  const std::string &key_projection() const {
    const std::lock_guard<std::mutex> lock(projection_mutex_);
    if (!key_ready_) {
      size_t bytes=0;const char *text=lie_json_value_key(node_,&bytes);
      key_projection_.assign(text,bytes);key_ready_=true;
    }
    return key_projection_;
  }
  std::string get_str(const std::string &def="") const { return is_string() ? str() : def; }
  std::string dump() const {
    if (!node_ && shadow_kind_!=LIE_JSON_VALUE_NULL) return Value(*this).dump();
    struct Sink {
      std::string text;std::exception_ptr failure;
      static bool write(void *p,const char *s,size_t bytes) noexcept {
        auto &self=*static_cast<Sink *>(p);
        try { self.text.append(s,bytes);return true; }
        catch (...) { self.failure=std::current_exception();return false; }
      }
    } output;
    lie_json_value_sink sink{&output,Sink::write};
    const auto rc=lie_json_value_dump(native(),&sink);
    if (output.failure) std::rethrow_exception(output.failure);
    check(rc);return std::move(output.text);
  }
};
template<bool Object> class ValueIterator {
  const lie_json_value *node_=nullptr;std::size_t index_=0;
public:
  using iterator_category=std::forward_iterator_tag;
  using difference_type=std::ptrdiff_t;
  using value_type=std::conditional_t<Object,MemberView,Value>;
  using reference=std::conditional_t<Object,MemberView,const Value &>;
  using pointer=std::conditional_t<Object,void,const Value *>;
  ValueIterator()=default;
  ValueIterator(const lie_json_value *n,std::size_t i):node_(n),index_(i) {}
  reference operator*() const {
    const auto &v=Value::facade(lie_json_value_at(node_,Object,index_));
    if constexpr(Object) return {v.key_projection(),v};else return v;
  }
  ValueIterator &operator++() { ++index_;return *this; }
  ValueIterator operator++(int) { auto old=*this;++*this;return old; }
  bool operator==(const ValueIterator &other) const { return node_==other.node_ && index_==other.index_; }
  bool operator!=(const ValueIterator &other) const { return !(*this==other); }
};
class ArrayView {
  Value owned_;const lie_json_value *borrowed_=nullptr;bool borrow_=false;
  const lie_json_value *node() const { return borrow_ ? borrowed_ : owned_.native(); }
  explicit ArrayView(const lie_json_value *n):borrowed_(n),borrow_(true) {}
  friend class Value;
public:
  using const_iterator=ValueIterator<false>;
  ArrayView():owned_(Value::array()) {}
  ArrayView(std::initializer_list<Value> values):ArrayView() { for (const auto &v:values) owned_.push_back(v); }
  ArrayView(const ArrayView &v):ArrayView() { for (const auto &item:v) owned_.push_back(item); }
  ArrayView(ArrayView &&)=default;
  ArrayView &operator=(ArrayView v) { std::swap(owned_,v.owned_);std::swap(borrowed_,v.borrowed_);std::swap(borrow_,v.borrow_);return *this; }
  void push_back(const Value &v) { if (borrow_) throw std::logic_error("immutable JSON array view");owned_.push_back(v); }
  std::size_t size() const { return lie_json_value_array_size(node()); }
  bool empty() const { return size()==0; }
  const Value &operator[](std::size_t i) const { return Value::facade(lie_json_value_at(node(),false,i)); }
  const Value &back() const { return operator[](size()-1); }
  const_iterator begin() const { return {node(),0}; }
  const_iterator end() const { return {node(),size()}; }
};
class ObjectView {
  const lie_json_value *node_;
public:
  using const_iterator=ValueIterator<true>;
  explicit ObjectView(const lie_json_value *n):node_(n) {}
  std::size_t size() const noexcept { return lie_json_value_object_size(node_); }
  bool empty() const noexcept { return size()==0; }
  MemberView operator[](std::size_t i) const {
    const auto &v=Value::facade(lie_json_value_at(node_,true,i));return {v.key_projection(),v};
  }
  const_iterator begin() const noexcept { return {node_,0}; }
  const_iterator end() const noexcept { return {node_,size()}; }
};
inline Value::Array Value::items() const noexcept { return ArrayView(node_); }
inline Value::Object Value::members() const noexcept { return ObjectView(node_); }
} // namespace gufo::json
#endif
