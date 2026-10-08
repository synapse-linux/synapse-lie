// SPDX-License-Identifier: MIT
// Complete pinned pattern/conjunction/prefix witnesses plus language oracles.
#include "src/core/json.hpp"
#include "src/core/json_schema_lexeme.hpp"
#include <cassert>
#include <iostream>
#include <string>
namespace gufo::sampling {
json::Value LieSchemaConjoinProbe(const json::Value &,const json::Value &,const json::Value &,unsigned);
}
using gufo::json::Value;
using gufo::sampling::JsonSchemaLexeme;
static size_t formats,values,prefixes,conjunctions,refusals;
struct Example { const char *format,*text;bool accepted; };
static const Example examples[]={
  {"date","2000-02-29",true},{"date","2024-12-31",true},
  {"date","1900-02-29",false},{"date","2023-02-29",false},{"date","2024-04-31",false},
  {"time","23:59:60Z",true},{"time","00:00:00.123+01:30",true},
  {"time","24:00:00Z",false},{"time","12:00:00",false},
  {"date-time","2024-02-29T23:59:59Z",true},{"date-time","2000-02-29t00:00:00z",true},
  {"date-time","2023-02-29T12:00:00Z",false},
  {"uuid","12345678-1234-1234-1234-123456789abc",true},
  {"uuid","12345678-1234-1234-1234-123456789abx",false},
  {"ipv4","0.0.0.0",true},{"ipv4","255.255.255.255",true},
  {"ipv4","256.0.0.1",false},{"ipv4","01.2.3.4",false},
  {"ipv6","::",true},{"ipv6","::1",true},{"ipv6","2001:db8::1",true},
  {"ipv6","1:2:3:4:5:6:7:8",true},{"ipv6","::ffff:192.0.2.1",true},
  {"ipv6","1:2:3:4:5:6:7",false},{"ipv6","1::2::3",false},
  {"ipv6","::ffff:256.0.0.1",false},{"ipv6","12345::",false},
  {"hostname","example.com",true},{"hostname","example.com.",true},
  {"hostname","-host.example",false},{"hostname","host_.example",false},
  {"email","a@example.com",true},{"email","a+b@example.com",true},
  {"email","a@@example.com",false},{"email","a b@example.com",false},
  {"duration","P1W",true},{"duration","P1Y2M3DT4H5M6.5S",true},
  {"duration","PT1S",true},{"duration","P",false},{"duration","PT",false},
  {"duration","P1WT1S",false}
};
int main() {
  const char *names[]={"date","time","date-time","uuid","ipv4","ipv6","hostname","email","duration"};
  for (const auto *name : names) {
    const auto expanded=JsonSchemaLexeme::Format(name);
    std::cout << "FORMAT " << name << ' ' << expanded.dump() << '\n';++formats;
    auto schema=Value::object();schema["format"]=name;
    const auto before=schema.dump();const auto lexeme=JsonSchemaLexeme::String(schema);
    for (const auto &example : examples) {
      if (std::string(example.format)!=name) continue;
      const auto encoded=Value(example.text).dump();
      assert(lexeme->Check(encoded).complete==example.accepted);
      std::cout << "VALUE " << encoded << " EXPECTED " << example.accepted << '\n';++values;
      for (size_t n=0;n<=encoded.size();++n) {
        const auto match=lexeme->Check(std::string_view(encoded.data(),n));
        std::cout << "PREFIX " << n << ' ' << match.prefix << ',' << match.complete << '\n';++prefixes;
      }
    }
    if (std::string(name)=="hostname") {
      for (const auto &text : {std::string(63,'a'),std::string(64,'a'),
          std::string(63,'a')+"."+std::string(63,'b')+"."+std::string(63,'c')+"."+std::string(60,'d'),
          std::string(63,'a')+"."+std::string(63,'b')+"."+std::string(63,'c')+"."+std::string(61,'d')}) {
        const bool expected=text.size()<=253 && (text.find('.')!=std::string::npos || text.size()<=63);
        const auto match=lexeme->Check(Value(text).dump());assert(match.complete==expected);
        std::cout << "HOSTNAME_LENGTH " << text.size() << ' ' << match.prefix << ',' << match.complete << '\n';++values;
      }
    }
    assert(schema.dump()==before);
    for (const auto *other : names) {
      auto left=Value::object();left["type"]="string";left["format"]=name;
      auto right=Value::object();right["type"]="string";right["format"]=other;
      const auto l=left.dump(),r=right.dump();
      std::cout << "JOIN " << name << ',' << other << ' '
        << gufo::sampling::LieSchemaConjoinProbe(Value::object(),left,right,0).dump() << '\n';
      assert(left.dump()==l && right.dump()==r);++conjunctions;
    }
  }
  for (const auto &name : {std::string(),std::string("DATE"),std::string("uri"),std::string("email\0x",7)}) {
    std::cout << "REFUSAL " << Value(name).dump() << ' ';
    try { (void)JsonSchemaLexeme::Format(name);assert(false); }
    catch (const std::invalid_argument &e) {
      assert(std::string(e.what())=="JSON Schema: unsupported string format");std::cout << e.what();++refusals;
    }
    std::cout << '\n';
  }
  std::cout << "FORMAT_CONTROLS=" << formats << " VALUES=" << values
    << " PREFIXES=" << prefixes << " CONJUNCTIONS=" << conjunctions
    << " REFUSALS=" << refusals << " HOST_NOT_INFERENCE\n";
}
