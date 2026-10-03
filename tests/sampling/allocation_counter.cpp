// SPDX-License-Identifier: MIT
// Counts requested C++ heap bytes in a separate, untimed probe composition.
#include "allocation_counter.hpp"
#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <new>
namespace {
struct Header { void *base; std::size_t bytes, generation; };
std::size_t generation;
bool active;
lie_sampling_allocations counts{};
void *allocate(std::size_t bytes,std::size_t alignment) {
  alignment=std::max(alignment,alignof(std::max_align_t));
  const std::size_t overhead=sizeof(Header)+alignment-1;
  if(bytes>std::numeric_limits<std::size_t>::max()-overhead)throw std::bad_alloc();
  void *base=std::malloc(bytes+overhead);
  if(!base)throw std::bad_alloc();
  const auto begin=reinterpret_cast<std::uintptr_t>(base)+sizeof(Header);
  const auto address=(begin+alignment-1)&~(alignment-1);
  Header header{base,bytes,active?generation:0};
  std::memcpy(reinterpret_cast<void*>(address-sizeof(Header)),&header,sizeof(header));
  if(active){++counts.calls;counts.requested_bytes+=bytes;counts.live_bytes+=bytes;
    counts.peak_live_bytes=std::max(counts.peak_live_bytes,counts.live_bytes);}
  return reinterpret_cast<void*>(address);
}
void release(void *pointer) noexcept {
  if(!pointer)return;
  Header header{};
  std::memcpy(&header,static_cast<unsigned char*>(pointer)-sizeof(header),sizeof(header));
  if(header.generation&&header.generation==generation){
    if(header.bytes>counts.live_bytes)std::abort();
    counts.live_bytes-=header.bytes;
  }
  std::free(header.base);
}
}
void lie_sampling_alloc_begin(){
  if(active||counts.live_bytes)std::abort();
  ++generation;counts={};active=true;
}
lie_sampling_allocations lie_sampling_alloc_end(){
  if(!active)std::abort();
  active=false;
  return counts;
}
void *operator new(std::size_t n){return allocate(n,alignof(std::max_align_t));}
void *operator new[](std::size_t n){return allocate(n,alignof(std::max_align_t));}
void operator delete(void *p) noexcept{release(p);}
void operator delete[](void *p) noexcept{release(p);}
void operator delete(void *p,std::size_t) noexcept{release(p);}
void operator delete[](void *p,std::size_t) noexcept{release(p);}
void *operator new(std::size_t n,std::align_val_t a){return allocate(n,static_cast<std::size_t>(a));}
void *operator new[](std::size_t n,std::align_val_t a){return allocate(n,static_cast<std::size_t>(a));}
void operator delete(void *p,std::align_val_t) noexcept{release(p);}
void operator delete[](void *p,std::align_val_t) noexcept{release(p);}
void operator delete(void *p,std::size_t,std::align_val_t) noexcept{release(p);}
void operator delete[](void *p,std::size_t,std::align_val_t) noexcept{release(p);}
