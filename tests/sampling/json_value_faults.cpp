// SPDX-License-Identifier: MIT
// Private projection/output allocation failures; isolated untimed host probe.
#include "src/core/json.hpp"
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <new>
#include <string>
namespace {
union Header { std::max_align_t alignment;struct {size_t bytes,generation;} record; };
size_t generation,calls,live,fail;
bool active;
void *allocate(size_t bytes) {
  if (active && ++calls==fail) throw std::bad_alloc();
  if (bytes>SIZE_MAX-sizeof(Header)) throw std::bad_alloc();
  auto *h=static_cast<Header *>(std::malloc(sizeof(Header)+bytes));
  if (!h) throw std::bad_alloc();
  h->record={bytes,active ? generation : 0};if (active) live+=bytes;return h+1;
}
void retire(void *p) noexcept {
  if (!p) return;
  auto *h=static_cast<Header *>(p)-1;
  if (h->record.generation && h->record.generation==generation) {
    if (h->record.bytes>live) std::abort();
    live-=h->record.bytes;
  }
  std::free(h);
}
struct CoreHeap {size_t live=0;};
void *take(void *p,size_t bytes) { void *out=std::malloc(bytes);if (out) ++static_cast<CoreHeap *>(p)->live;return out; }
void give(void *p,void *bytes) { auto &h=*static_cast<CoreHeap *>(p);assert(h.live);--h.live;std::free(bytes); }
using V=gufo::json::Value;
void exercise(CoreHeap &heap,const std::string &fixture) {
  auto d=V::description();d.allocator={&heap,take,give};lie_json_value *root=nullptr;
  assert(lie_json_value_parse(fixture.data(),fixture.size(),&d,nullptr,&root,nullptr,nullptr)==LIE_JSON_VALUE_OK);
  V v=V::adopt(root);
  const auto *leaf=v.find("text");assert(leaf && leaf->str().size()==4096);
  for (const auto &[key,value]:v.members()) { assert(!key.empty());(void)value.str(); }
  V copy(v);V moved(std::move(copy));assert(moved.member_str("text").size()==4096);
  v["added"]=std::string(4096,'z');assert(v.find("added")->str().size()==4096);
  const auto dumped=v.dump();assert(dumped.size()>8192);
  assert(v.member_str("text").size()==4096);
}
}
void *operator new(size_t n) { return allocate(n); }
void *operator new[](size_t n) { return allocate(n); }
void operator delete(void *p) noexcept { retire(p); }
void operator delete[](void *p) noexcept { retire(p); }
void operator delete(void *p,size_t) noexcept { retire(p); }
void operator delete[](void *p,size_t) noexcept { retire(p); }
int main() {
  const std::string fixture="{\"text\":\""+std::string(4096,'x')+"\",\""+std::string(256,'k')+"\":\""+std::string(1024,'y')+"\"}";
  CoreHeap heap;active=true;++generation;calls=live=fail=0;exercise(heap,fixture);
  active=false;assert(!live && !heap.live);const size_t count=calls;
  for (size_t i=1;i<=count;++i) {
    ++generation;calls=live=0;fail=i;active=true;bool refused=false;
    try { exercise(heap,fixture); } catch (const std::bad_alloc &) { refused=true; }
    active=false;assert(refused && !live && !heap.live);
  }
  std::cout<<"PRIVATE JSON PROJECTION REFUSALS="<<count<<" LIVE_BYTES=0 CORE_LIVE_ALLOCATIONS=0 HOST_NOT_INFERENCE\n";
}
