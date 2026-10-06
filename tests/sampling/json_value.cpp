// SPDX-License-Identifier: MIT
// Complete observable ownership witnesses from pristine, selected C17 and OFF.
#include "src/core/json.hpp"
#include <bit>
#include <cstdint>
#include <iostream>
#include <limits>
#include <string>
#include <utility>
using V=gufo::json::Value;
static std::uint64_t random_state=UINT64_C(0x23971823de7821a0);
static size_t cases=0;
static std::uint64_t random_word() {
  random_state^=random_state<<13;random_state^=random_state>>7;random_state^=random_state<<17;return random_state;
}
static void bytes(const std::string &s) {
  static const char hex[]="0123456789abcdef";
  std::cout<<s.size()<<':';for (const unsigned char c:s) std::cout<<hex[c>>4]<<hex[c&15];std::cout<<' ';
}
static void witness(const V &v) {
  std::cout<<static_cast<unsigned>(v.type())<<'/'<<v.size()<<'/'<<v.items().size()<<'/'<<v.members().size()<<'/'
    <<v.as_bool(true)<<'/'<<std::bit_cast<std::uint64_t>(v.as_double(-73.5))<<'/'<<v.as_size(912)<<' ';
  bytes(v.str());bytes(v.get_str("default"));
  try { bytes(v.dump()); } catch (const std::exception &e) { bytes(std::string(e.what())); }
  for (const auto &item:v.items()) witness(item);
  for (const auto &[key,member]:v.members()) { bytes(key);witness(member); }
  std::cout<<"END ";
}
static V generated(unsigned depth) {
  const unsigned kind=static_cast<unsigned>(random_word()%(depth<4 ? 6 : 4));
  switch (kind) {
  case 0:return V();case 1:return V((random_word()&1)!=0);
  case 2:return V((static_cast<double>(random_word()%20001)-10000)/8);
  case 3: {
    std::string text;const auto n=random_word()%19;
    for (size_t i=0;i<n;++i) text+=static_cast<char>(random_word()%128);
    return V(std::move(text));
  }
  case 4: {
    V v=V::array();const auto n=random_word()%5;
    for (size_t i=0;i<n;++i) v.push_back(generated(depth+1));return v;
  }
  default: {
    V v=V::object();const auto n=random_word()%5;
    for (size_t i=0;i<n;++i) v.append_member(std::string("key\0",4)+std::to_string(i),generated(depth+1));return v;
  }
  }
}
int main() {
  for (unsigned i=0;i<2000;++i) {
    V value=generated(0);std::cout<<"CASE "<<cases++<<' ';witness(value);
    V copied(value);witness(copied);V assigned;assigned=copied;witness(assigned);
    V moved(std::move(copied));witness(moved);witness(copied);
    V target=V::object();target["leaf"]=moved;witness(target);
    target["leaf"]=std::move(assigned);witness(target);witness(assigned);
    V child(std::move(target["leaf"]));witness(child);witness(target);
    V array=V::array();array.push_back(value);array.push_back();witness(array);
    V object=array;object["coerce"]=value;witness(object);
    object.push_back(value);witness(object);object["second"]=true;witness(object);
    object.append_member("second",false);witness(object);
    std::cout<<'\n';
  }
  for (const double number:{-0.0,1.0,-1.0,0.5,std::numeric_limits<double>::infinity(),std::numeric_limits<double>::quiet_NaN()}) {
    V a(number);V b(std::move(a));witness(a);witness(b);std::cout<<'\n';++cases;
  }
  V a(std::string(256,'a'));bytes(a.str());a=std::string(256,'b');bytes(a.str());
  V b(std::string(256,'c'));a=std::move(b);bytes(a.str());bytes(b.str());std::cout<<'\n';++cases;
  std::cout<<"JSON VALUE CASES="<<cases<<" HOST_NOT_INFERENCE\n";
}
