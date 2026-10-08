// SPDX-License-Identifier: MIT
// Actual pristine/ON/OFF JSON number conversion and complete bit witnesses.
#include "src/core/json.hpp"
#include <bit>
#include <charconv>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <limits>
#include <string>
#include <vector>
static size_t cases;
static void witness(double value) {
 if(!std::isfinite(value))return;
 const auto text=gufo::json::Value(value).dump();
 const auto round=gufo::json::parse(text).as_double();
 char reference[64];auto result=std::to_chars(reference,reference+sizeof(reference),value);
 if(text!=std::string(reference,result.ptr)||std::bit_cast<uint64_t>(round)!=std::bit_cast<uint64_t>(value))throw std::runtime_error("binary64 spelling/roundtrip differs");
 std::cout<<std::hex<<std::bit_cast<uint64_t>(value)<<' '<<text<<' '<<std::bit_cast<uint64_t>(round)<<std::dec<<'\n';++cases;
}
int main(){
 for(double v:{0.,-0.,0.1,0.3,1000000000000000128.,std::numeric_limits<double>::denorm_min(),std::numeric_limits<double>::min(),std::numeric_limits<double>::max()})witness(v);
 for(int exp=-1074;exp<1024;++exp){double v=std::ldexp(1.,exp);witness(v);witness(std::nextafter(v,0.));witness(std::nextafter(v,std::numeric_limits<double>::infinity()));}
 uint64_t seed=0x7e64d1eaa4fb53b9ULL;
 for(size_t i=0;i<100000;++i){seed^=seed<<13;seed^=seed>>7;seed^=seed<<17;witness(std::bit_cast<double>(seed));}
 const std::string midpoint="1.00000000000000011102230246251565404236316680908203125";
 std::vector<std::string> texts={"0", "-0", "1e-400", "1e400", "1e-999999999999999999999999", "0e999999999999999999999999",midpoint,midpoint+std::string(10000,'0'),midpoint+std::string(10000,'0')+"1","01","1.","1e+","1 2"," \n0.3\t "};
 for(const auto &s:texts){std::cout<<"PARSE "<<s.size()<<' ';try{double v=gufo::json::parse(s).as_double();std::cout<<std::hex<<std::bit_cast<uint64_t>(v)<<std::dec;}catch(const std::runtime_error&e){std::cout<<"RUNTIME "<<e.what();}std::cout<<'\n';++cases;}
 std::cout<<"BINARY64 CASES="<<cases<<" HOST_NOT_INFERENCE\n";
}
