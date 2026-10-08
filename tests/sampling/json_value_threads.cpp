// SPDX-License-Identifier: MIT
// Parallel immutable reads are a host contract, not inference concurrency.
#include "src/core/json.hpp"
#include <atomic>
#include <cassert>
#include <iostream>
#include <string>
#include <thread>
#include <vector>
int main() {
  using V=gufo::json::Value;
  const std::string text(4096,'x'),key(256,'k');
  const V value=gufo::json::parse("{\"text\":\""+text+"\",\""+key+"\":\""+text+"\"}");
  const std::string expected=value.dump();const V empty;
  V moved_from=V::array();const V moved(std::move(moved_from));
  std::atomic<unsigned> ready{0};std::atomic<bool> go{false},good{true};
  std::vector<std::thread> readers;
  for (unsigned i=0;i<8;++i) readers.emplace_back([&]{
    ++ready;while (!go.load()) std::this_thread::yield();
    for (unsigned repeat=0;repeat<64;++repeat) {
      if (value.find("text")->str()!=text || value.find(key)->str()!=text ||
          value.dump()!=expected || empty.dump()!="null" || moved_from.dump()!="[]" || moved.dump()!="[]") good=false;
      unsigned count=0;
      for (const auto &[name,child]:value.members()) {
        if ((name!="text" && name!=key) || child.str()!=text) good=false;
        ++count;
      }
      if (count!=2) good=false;
    }
  });
  while (ready.load()!=8) std::this_thread::yield();
  go=true;
  for (auto &reader:readers) reader.join();
  assert(good.load());
  std::cout<<"IMMUTABLE JSON READERS=8 ITERATIONS=512 OWNED_THREADS_JOINED HOST_NOT_INFERENCE\n";
}
