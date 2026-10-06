// SPDX-License-Identifier: MIT
// Actual pristine/ON/OFF parse entry points: complete ordered trees and errors.
#include "src/core/json.hpp"
#include <bit>
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>
static size_t cases;
static void hex(std::string_view text) {
  const char *digits="0123456789abcdef";
  for(unsigned char c:text)std::cout<<digits[c>>4]<<digits[c&15];
}
static void tree(const gufo::json::Value &v) {
  std::cout<<static_cast<unsigned>(v.type())<<':'<<v.size()<<':';
  if(v.is_number())std::cout<<std::hex<<std::bit_cast<uint64_t>(v.as_double())<<std::dec;
  if(v.is_bool())std::cout<<v.as_bool();
  if(v.is_string())hex(v.str());
  if(v.is_array())for(const auto &item:v.items()){std::cout<<'[';tree(item);std::cout<<']';}
  if(v.is_object())for(const auto &member:v.members()){std::cout<<'{';hex(member.first);std::cout<<'=';tree(member.second);std::cout<<'}';}
}
static void witness(std::string_view input) {
  std::cout<<cases++<<' ';hex(input);std::cout<<' ';
  try { auto value=gufo::json::parse(input);std::cout<<"OK ";hex(value.dump());std::cout<<' ';tree(value); }
  catch(const std::runtime_error &e){std::cout<<"RUNTIME ";hex(e.what());}
  std::cout<<'\n';
}
static uint64_t state=UINT64_C(0x61facbd90871ee53);
static uint64_t random_value(){state^=state<<13;state^=state>>7;state^=state<<17;return state;}
static gufo::json::Value generated(unsigned depth) {
  using V=gufo::json::Value;unsigned kind=static_cast<unsigned>(random_value()%(depth<5 ? 6 : 4));
  if(kind==0)return V();
  if(kind==1)return V((random_value()&1)!=0);
  if(kind==2)return V(static_cast<double>(static_cast<int64_t>(random_value()%100000)-50000)/8);
  if(kind==3)return V(std::string("x\0\\\"\n\xe2\x82\xac",8)+std::to_string(random_value()%100));
  V value=kind==4 ? V::array() : V::object();unsigned count=static_cast<unsigned>(random_value()%4);
  for(unsigned i=0;i<count;++i) {
    auto child=generated(depth+1);
    if(kind==4)value.push_back(std::move(child));
    else value.append_member("key"+std::to_string(i)+std::string("\0",1),std::move(child));
  }
  return value;
}
int main() {
  std::vector<std::string> samples={"null","true","false","-0","0.3","1e400","1e-400",
    "{\"a\":1,\"\\u0061\":BAD}","{\"a\":{\"a\":1},\"b\":{\"a\":2}}",
    "{\"\\u0000\":1,\"\\u0000\":2}","{\"\\ud83d\\ude00\":1,\"\xf0\x9f\x98\x80\":2}",
    "\"\\b\\f\\n\\r\\t\\/\\\\\\\"\"","\"\\u0000\\u0080\\udbff\\udfff\"",
    "\"\\ud800\"","\"\\ud800\\u0000\"","\"\\udfff\"","\"\\u0\"","\"\\u00xz\"",
    "\"\xe0\x80\x80\"","\"\xed\xa0\x80\"","\"\xf4\x90\x80\x80\""};
  for(const auto &input:samples)witness(input);
  for(unsigned byte=0;byte<256;++byte) {
    witness(std::string("\"")+static_cast<char>(byte)+'"');
    witness(std::string("{\"")+static_cast<char>(byte)+"\":0}");
  }
  const std::string alphabet="{}[]:,\"0tfn\\ ";
  size_t count=1;
  for(unsigned length=0;length<=4;++length) {
    for(size_t code=0;code<count;++code) {
      size_t value=code;std::string input;
      for(unsigned i=0;i<length;++i){input+=alphabet[value%alphabet.size()];value/=alphabet.size();}
      witness(input);
    }
    count*=alphabet.size();
  }
  for(unsigned depth:{127,128,129}) {
    witness(std::string(depth,'[')+std::string(depth,']'));
    std::string input;for(unsigned i=0;i<depth;++i)input+="{\"a\":";
    witness(input+"0"+std::string(depth,'}'));
  }
  for(unsigned i=0;i<1000;++i)witness(generated(0).dump());
  for(const auto &input:samples) {
    for(size_t n=0;n<input.size();++n)witness(std::string_view(input).substr(0,n));
    for(size_t n=0;n<input.size();++n)for(char byte:std::string("}\"\\:0 ")) {
      auto corrupted=input;corrupted[n]=byte;witness(corrupted);
    }
  }
  std::string wide="{";
  for(unsigned i=0;i<1000;++i)wide+=(i ? "," : "")+std::string("\"key\\u0061")+std::to_string(i)+"\":0";
  witness(wide+"}");witness(wide+",\"keya0\":bad}");
  std::cout<<"JSON PARSER CASES="<<cases<<" HOST_NOT_INFERENCE\n";
}
