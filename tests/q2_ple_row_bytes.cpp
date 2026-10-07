// SPDX-License-Identifier: MIT
#include "src/models/qwen38_flash_next/ngram.hpp"
#include <array>
#include <atomic>
#include <cassert>
#include <cerrno>
#include <cstdint>
#include <cstdlib>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <span>
#include <unistd.h>
#include <vector>

static std::atomic<unsigned> calls{}, retries{};
static std::atomic<std::uint64_t> requested{};
static std::atomic<bool> inject_eintr{}, watch{};
extern "C" ssize_t __real_pread(int, void*, size_t, off_t);
extern "C" ssize_t __wrap_pread(int fd, void* dst, size_t size, off_t offset) {
  if (watch.load()) {
    assert(size == 320);
    assert((fcntl(fd, F_GETFL) & O_DIRECT) == 0);
    if (inject_eintr.exchange(false)) {
      ++retries;
      errno = EINTR;
      return -1;
    }
    ++calls;
    requested += size;
  }
  return __real_pread(fd,dst,size,offset);
}

int main() {
  using gufo::models::qwen38_flash_next::NgramTable;
  using gufo::core::GgmlType;
  char name[]="/tmp/lie-q2-row-bytes-XXXXXX";
  const int fd=mkstemp(name);
  assert(fd>=0 && unlink(name)==0);
  constexpr std::size_t rows=257, width=160, prefix=7;
  std::vector<std::uint8_t> bytes(prefix+rows*width*2);
  for(std::size_t r=0;r<rows;++r)for(std::size_t j=0;j<width;++j){
    const std::uint16_t bits=0x3f00+((r*11+j*7)%256);
    std::memcpy(bytes.data()+prefix+2*(r*width+j),&bits,2);
  }
  assert(write(fd,bytes.data(),bytes.size())==static_cast<ssize_t>(bytes.size()));
  auto table=NgramTable::Open(fd,prefix,rows,width,GgmlType::kBF16);
  assert(table);
  std::vector<std::uint32_t> ids;
  for(std::uint32_t r=0;r<rows;++r){ids.push_back(r);ids.push_back(r);}
  std::vector<float> output(ids.size()*width+2,-12345.0F);
  inject_eintr=true;watch=true;
  assert(table->Read(ids,std::span(output).subspan(1,ids.size()*width)));
  watch=false;
  assert(calls==rows && retries==1 && requested==rows*width*2);
  assert(output.front()==-12345.0F && output.back()==-12345.0F);
  for(std::size_t r=0;r<ids.size();++r)for(std::size_t j=0;j<width;++j){
    const std::uint32_t bits=(0x3f00+((ids[r]*11+j*7)%256))<<16;
    float expected;
    std::memcpy(&expected,&bits,4);
    assert(output[1+r*width+j]==expected);
  }
  const unsigned first_calls=calls;
  watch=true;
  assert(table->Read(ids,std::span(output).subspan(1,ids.size()*width)));
  watch=false;
  assert(calls==first_calls);
  // A declared row beyond the private file must report failure, not publish
  // an incomplete row, touch output guards, or map inaccessible pages.
  auto short_table=NgramTable::Open(fd,prefix,rows+1,width,GgmlType::kBF16);
  std::array<std::uint32_t,1> short_id{rows};
  std::array<float,width+2> short_out{};short_out.fill(-12345.0F);
  watch=true;
  assert(!short_table->Read(short_id,std::span(short_out).subspan(1,width)));
  watch=false;
  for(float x:short_out)assert(x==-12345.0F);
  table.reset();short_table.reset();assert(close(fd)==0);
  std::printf("BF16 row bytes exact: rows=%zu bytes=%zu duplicates=%zu EINTR=1 warm_reads=0 short_read_rejected=1\n",rows,rows*width*2,rows);
}
