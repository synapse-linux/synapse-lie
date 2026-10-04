/* SPDX-License-Identifier: MIT */
#include "lie/steering.h"
#include <errno.h>
#include <fcntl.h>
#include <float.h>
#include <math.h>
#include <openssl/evp.h>
#include <stdbool.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
_Static_assert(sizeof(float) == 4 && FLT_RADIX == 2 && FLT_MANT_DIG == 24 &&
                   FLT_MAX_EXP == 128,
               "Steering banks require IEEE754 binary32");
struct lie_steering_bank {
  atomic_size_t references;
  lie_steering_info info;
  float *values;
};
static lie_status refusal(lie_error *e, lie_status status, const char *text) {
  if (e) snprintf(e->message, sizeof(e->message), "%s", text);
  return status;
}
static void le32(unsigned char *p, uint32_t x) {
  for (unsigned i = 0; i < 4; ++i) p[i] = (unsigned char)(x >> (8 * i));
}
static bool unchanged(const struct stat *a, const struct stat *b) {
  return b->st_nlink && a->st_dev == b->st_dev && a->st_ino == b->st_ino &&
         a->st_size == b->st_size && a->st_mtim.tv_sec == b->st_mtim.tv_sec &&
         a->st_mtim.tv_nsec == b->st_mtim.tv_nsec &&
         a->st_ctim.tv_sec == b->st_ctim.tv_sec &&
         a->st_ctim.tv_nsec == b->st_ctim.tv_nsec;
}
lie_status lie_steering_bank_load(const char *path, const lie_steering_geometry *g,
                                  lie_steering_bank **out, lie_error *e) {
  if (!path || !*path || !g || !out || *out ||
      g->abi_version != LIE_STEERING_ABI || g->struct_bytes != sizeof(*g) ||
      !g->layers || !g->width || !g->max_bytes)
    return refusal(e, LIE_INVALID, "invalid steering geometry or output handle");
  if ((uint64_t)g->layers > UINT64_MAX / 4 / g->width)
    return refusal(e, LIE_RESOURCE_LIMIT, "steering geometry size overflow");
  uint64_t bytes = (uint64_t)g->layers * g->width * 4;
  if (bytes > g->max_bytes || bytes > SIZE_MAX)
    return refusal(e, LIE_RESOURCE_LIMIT, "steering bank exceeds host vector budget");
  int fd = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK);
  if (fd < 0) return refusal(e, LIE_INVALID, "cannot open steering bank");
  struct stat before, after;
  if (fstat(fd, &before) || !S_ISREG(before.st_mode) || !before.st_nlink ||
      before.st_size < 0 || (uint64_t)before.st_size != bytes) {
    close(fd);
    return refusal(e, LIE_INVALID, "steering file does not match model geometry");
  }
  lie_steering_bank *bank = calloc(1, sizeof(*bank));
  EVP_MD_CTX *file_hash = EVP_MD_CTX_new(), *scope_hash = EVP_MD_CTX_new();
  lie_status status = LIE_RESOURCE_LIMIT;
  const char *reason = "cannot allocate steering bank";
  if (!bank || !file_hash || !scope_hash ||
      !(bank->values = malloc((size_t)bytes))) goto fail;
  bank->info = (lie_steering_info){.abi_version=LIE_STEERING_ABI,
                                  .struct_bytes=sizeof(lie_steering_info),
                                  .layers=g->layers,.width=g->width,.bytes=bytes};
  unsigned char shape[8]; le32(shape, g->layers); le32(shape+4, g->width);
  static const char domain[] = "synapse-lie.steering.v1";
  if (!EVP_DigestInit_ex(file_hash, EVP_sha256(), NULL) ||
      !EVP_DigestInit_ex(scope_hash, EVP_sha256(), NULL) ||
      !EVP_DigestUpdate(scope_hash, domain, sizeof(domain)) ||
      !EVP_DigestUpdate(scope_hash, shape, sizeof(shape))) goto hash_fail;
  uint64_t consumed = 0;
  unsigned char chunk[16384];
  while (consumed < bytes) {
    size_t wanted = bytes - consumed < sizeof(chunk) ? (size_t)(bytes-consumed) : sizeof(chunk);
    size_t got = 0;
    while (got < wanted) {
      ssize_t n = read(fd, chunk+got, wanted-got);
      if (n < 0 && errno == EINTR) continue;
      if (n <= 0) { status=LIE_INVALID; reason="cannot read complete steering bank"; goto fail; }
      got += (size_t)n;
    }
    if (!EVP_DigestUpdate(file_hash, chunk, got) ||
        !EVP_DigestUpdate(scope_hash, chunk, got)) goto hash_fail;
    for (size_t i = 0; i < got; i += 4) {
      uint32_t bits = (uint32_t)chunk[i] | (uint32_t)chunk[i+1] << 8 |
                      (uint32_t)chunk[i+2] << 16 | (uint32_t)chunk[i+3] << 24;
      float value; memcpy(&value, &bits, 4);
      if (!isfinite(value)) { status=LIE_INVALID; reason="nonfinite steering direction"; goto fail; }
      memcpy(bank->values + (size_t)(consumed/4) + i/4, &bits, 4);
    }
    consumed += got;
  }
  if (fstat(fd, &after) || !unchanged(&before, &after)) {
    status=LIE_INVALID; reason="steering file changed during load"; goto fail;
  }
  unsigned file_size = 0, scope_size = 0;
  if (!EVP_DigestFinal_ex(file_hash, bank->info.file_sha256, &file_size) || file_size != 32 ||
      !EVP_DigestFinal_ex(scope_hash, bank->info.scope_sha256, &scope_size) || scope_size != 32)
    goto hash_fail;
  close(fd); EVP_MD_CTX_free(file_hash); EVP_MD_CTX_free(scope_hash);
  atomic_init(&bank->references, 1);
  *out = bank;
  if (e) e->message[0] = 0;
  return LIE_OK;
hash_fail:
  reason = "cannot hash steering bank";
fail:
  close(fd); EVP_MD_CTX_free(file_hash); EVP_MD_CTX_free(scope_hash);
  if (bank) { free(bank->values); free(bank); }
  return refusal(e, status, reason);
}
lie_status lie_steering_bank_info(const lie_steering_bank *bank,
                                  lie_steering_info *out, lie_error *e) {
  if (!bank || !out || out->abi_version != LIE_STEERING_ABI ||
      out->struct_bytes != sizeof(*out))
    return refusal(e, LIE_INVALID, "invalid steering info ABI or handle");
  *out = bank->info;
  if (e) e->message[0] = 0;
  return LIE_OK;
}
const float *lie_steering_bank_values(const lie_steering_bank *bank) {
  return bank ? bank->values : NULL;
}
lie_status lie_steering_bank_retain(lie_steering_bank *bank) {
  if (!bank) return LIE_INVALID;
  size_t count = atomic_load_explicit(&bank->references, memory_order_relaxed);
  while (count && count < SIZE_MAX) {
    if (atomic_compare_exchange_weak_explicit(&bank->references, &count, count+1,
                                             memory_order_relaxed, memory_order_relaxed))
      return LIE_OK;
  }
  return count ? LIE_RESOURCE_LIMIT : LIE_INVALID;
}
void lie_steering_bank_release(lie_steering_bank **handle) {
  if (!handle || !*handle) return;
  lie_steering_bank *bank = *handle; *handle = NULL;
  if (atomic_fetch_sub_explicit(&bank->references, 1, memory_order_acq_rel) == 1) {
    free(bank->values); free(bank);
  }
}
