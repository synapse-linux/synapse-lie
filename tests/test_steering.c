/* SPDX-License-Identifier: MIT */
/* Host vector format/ownership fixtures; no activations, model or GPU forward. */
#include "lie/steering.h"
#include <assert.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
static char directory[] = "/tmp/lie-steering-fixture-XXXXXX", file[256];
static const uint32_t vectors[] = {0x3f800000,0,0,0,0x3f19999a,0x3f4ccccd};
static void write_vectors(const uint32_t *bits, size_t count) {
  int fd = open(file, O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC, 0600); assert(fd >= 0);
  for (size_t i = 0; i < count; ++i) {
    unsigned char data[4];
    for (unsigned b = 0; b < 4; ++b) data[b] = (unsigned char)(bits[i] >> (8*b));
    assert(write(fd,data,sizeof(data)) == (ssize_t)sizeof(data));
  }
  assert(!close(fd));
}
static lie_steering_geometry geometry(uint32_t layers, uint32_t width, uint64_t budget) {
  return (lie_steering_geometry){LIE_STEERING_ABI,sizeof(lie_steering_geometry),layers,width,budget};
}
static lie_steering_info info(lie_steering_bank *bank) {
  lie_steering_info out = {.abi_version=LIE_STEERING_ABI,.struct_bytes=sizeof(out)};
  assert(lie_steering_bank_info(bank,&out,NULL) == LIE_OK); return out;
}
static void refused(const char *path, lie_steering_geometry g, lie_status expected) {
  lie_steering_bank *bank = NULL; lie_error e = {0};
  assert(lie_steering_bank_load(path,&g,&bank,&e) == expected && !bank && e.message[0]);
}
static void *references(void *arg) {
  lie_steering_bank *bank = arg;
  for (unsigned i = 0; i < 10000; ++i) {
    assert(lie_steering_bank_retain(bank) == LIE_OK);
    lie_steering_bank *pin = bank;
    const float *values = lie_steering_bank_values(pin);
    assert(values[0] == 1 && values[4] == .6f && info(pin).bytes == 24);
    lie_steering_bank_release(&pin); assert(!pin);
  }
  return NULL;
}
static void hex(const unsigned char digest[32], char out[65]) {
  for (unsigned i = 0; i < 32; ++i) snprintf(out+2*i,3,"%02x",digest[i]);
}
int main(void) {
  assert(mkdtemp(directory)); snprintf(file,sizeof(file),"%s/bank.f32",directory);
  write_vectors(vectors,6);
  lie_steering_geometry g = geometry(2,3,24);
  lie_steering_bank *bank = NULL; lie_error e = {.message="uncleared"};
  assert(lie_steering_bank_load(file,&g,&bank,&e) == LIE_OK && bank && !e.message[0]);
  lie_steering_info first = info(bank);
  assert(first.layers == 2 && first.width == 3 && first.bytes == 24);
  const float *data = lie_steering_bank_values(bank);
  for (unsigned i = 0; i < 6; ++i) { uint32_t bits; memcpy(&bits,data+i,4); assert(bits == vectors[i]); }
  char digest[65]; hex(first.file_sha256,digest);
  /* Independent Python struct.pack('<6f',1,0,0,0,.6,.8) / hashlib oracle. */
  assert(!strcmp(digest,"c9aaf239e1d42d42890025f13384e36ea8cb991b78e381b9900ece9e2d0b77eb"));
  hex(first.scope_sha256,digest); assert(!strcmp(digest,"806fa88a30706b8578ffad1d034a28fa4feff36160d0d34ff9dbf6055100347b"));
  lie_steering_bank *reshaped = NULL;
  lie_steering_geometry other = geometry(3,2,24);
  assert(lie_steering_bank_load(file,&other,&reshaped,NULL) == LIE_OK);
  lie_steering_info second = info(reshaped);
  assert(!memcmp(first.file_sha256,second.file_sha256,32));
  assert(memcmp(first.scope_sha256,second.scope_sha256,32));
  lie_steering_bank_release(&reshaped);
  lie_steering_info bad = {.abi_version=0,.struct_bytes=sizeof(bad),.width=99};
  assert(lie_steering_bank_info(bank,&bad,&e) == LIE_INVALID && bad.width == 99);
  bad.abi_version=LIE_STEERING_ABI; --bad.struct_bytes;
  assert(lie_steering_bank_info(bank,&bad,&e) == LIE_INVALID && bad.width == 99);
  assert(lie_steering_bank_load(file,&g,&bank,&e) == LIE_INVALID && bank);
  refused(file,geometry(0,3,24),LIE_INVALID);
  refused(file,geometry(2,0,24),LIE_INVALID);
  refused(file,geometry(2,3,0),LIE_INVALID);
  refused(file,geometry(2,3,23),LIE_RESOURCE_LIMIT);
  refused(file,geometry(UINT32_MAX,UINT32_MAX,UINT64_MAX),LIE_RESOURCE_LIMIT);
  other=g; --other.abi_version; refused(file,other,LIE_INVALID);
  other=g; --other.struct_bytes; refused(file,other,LIE_INVALID);
  refused(NULL,g,LIE_INVALID); refused("",g,LIE_INVALID);
  assert(lie_steering_bank_load(file,NULL,&reshaped,&e) == LIE_INVALID && !reshaped);
  assert(lie_steering_bank_load(file,&g,NULL,&e) == LIE_INVALID);
  assert(!lie_steering_bank_values(NULL) && lie_steering_bank_retain(NULL) == LIE_INVALID);
  pthread_t threads[8];
  for (unsigned i = 0; i < 8; ++i) assert(!pthread_create(&threads[i],NULL,references,bank));
  for (unsigned i = 0; i < 8; ++i) assert(!pthread_join(threads[i],NULL));
  assert(lie_steering_bank_retain(bank) == LIE_OK); reshaped=bank;
  lie_steering_bank_release(&bank); assert(!bank && info(reshaped).bytes == 24);
  write_vectors(vectors,5); refused(file,g,LIE_INVALID);
  uint32_t changed[7]; memcpy(changed,vectors,sizeof(vectors)); changed[6]=0;
  write_vectors(changed,7); refused(file,g,LIE_INVALID);
  for (unsigned i = 0; i < 3; ++i) {
    changed[2] = i == 0 ? 0x7fc00000 : i == 1 ? 0x7f800000 : 0xff800000;
    write_vectors(changed,6); refused(file,g,LIE_INVALID);
  }
  changed[2]=0x80000000; changed[3]=1; write_vectors(changed,6);
  assert(lie_steering_bank_load(file,&g,&bank,NULL) == LIE_OK);
  for (unsigned i = 0; i < 6; ++i) { uint32_t bits; memcpy(&bits,lie_steering_bank_values(bank)+i,4); assert(bits == changed[i]); }
  lie_steering_bank_release(&bank);
  /* Cross multiple bounded read chunks and a short final chunk. */
  const size_t many_count = 3 * 4097;
  uint32_t *many = malloc(many_count * sizeof(*many)); assert(many);
  for (size_t i = 0; i < many_count; ++i) many[i] = 0x3f800000 + (uint32_t)i;
  write_vectors(many,many_count);
  other=geometry(3,4097,many_count*4);
  assert(lie_steering_bank_load(file,&other,&bank,NULL) == LIE_OK);
  for (size_t i = 0; i < many_count; ++i) { uint32_t bits; memcpy(&bits,lie_steering_bank_values(bank)+i,4); assert(bits == many[i]); }
  free(many); lie_steering_bank_release(&bank);
  char link[256], pipe[256], missing[256];
  snprintf(link,sizeof(link),"%s/link",directory); assert(!symlink(file,link));
  refused(link,g,LIE_INVALID); assert(!unlink(link));
  snprintf(pipe,sizeof(pipe),"%s/fifo",directory); assert(!mkfifo(pipe,0600));
  refused(pipe,g,LIE_INVALID); assert(!unlink(pipe));
  refused(directory,g,LIE_INVALID);
  snprintf(missing,sizeof(missing),"%s/missing",directory); refused(missing,g,LIE_INVALID);
  assert(!unlink(file));
  /* Snapshot values outlive source mutation/unlink and the first owner's pin. */
  for (unsigned i = 0; i < 6; ++i) { uint32_t bits; memcpy(&bits,lie_steering_bank_values(reshaped)+i,4); assert(bits == vectors[i]); }
  lie_steering_bank_release(&reshaped); assert(!reshaped);
  lie_steering_bank_release(&reshaped); lie_steering_bank_release(NULL);
  assert(!rmdir(directory));
  puts("steering bank format/identity/lifetimes: PASS (not inference)");
  return 0;
}
