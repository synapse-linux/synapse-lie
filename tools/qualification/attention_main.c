/* SPDX-License-Identifier: MIT */
/* Native generated GPU component qualification; no model or performance run. */
#include "attention.h"
#include <errno.h>
#include <fcntl.h>
#include <float.h>
#include <json-c/json.h>
#include <math.h>
#include <openssl/evp.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static volatile sig_atomic_t interrupted;
static void stop(int n) { (void)n; interrupted = 1; }
static void number(json_object *j, const char *key, uint64_t value) {
  json_object_object_add(j, key, json_object_new_uint64(value));
}
static void text(json_object *j, const char *key, const char *value) {
  json_object_object_add(j, key, json_object_new_string(value));
}
static void boolean(json_object *j, const char *key, bool value) {
  json_object_object_add(j, key, json_object_new_boolean(value));
}
static bool emit(FILE *file, json_object *j) {
  bool ok = fputs(json_object_to_json_string_ext(j, JSON_C_TO_STRING_PLAIN), file) >= 0 &&
      fputc('\n', file) != EOF && !fflush(file);
  json_object_put(j); return ok;
}
static bool raw(int dir, const char *name, const void *data, size_t bytes,
                json_object *record, const char *key) {
  int fd = openat(dir, name, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600);
  if (fd < 0) return false;
  const unsigned char *p = data; size_t at = 0; bool ok = true;
  while (at < bytes) {
    ssize_t n = write(fd, p + at, bytes - at);
    if (n < 0 && errno == EINTR) continue;
    if (n <= 0) { ok = false; break; }
    at += (size_t)n;
  }
  if (fsync(fd)) ok = false;
  if (close(fd)) ok = false;
  unsigned char digest[32]; unsigned n = 0; char hash[65];
  if (!ok || !EVP_Digest(data, bytes, digest, &n, EVP_sha256(), NULL) || n != 32) return false;
  for (unsigned i = 0; i < n; ++i) snprintf(hash + i * 2, 3, "%02x", digest[i]);
  json_object *j = json_object_new_object();
  text(j, "file", name); text(j, "sha256", hash); number(j, "bytes", bytes);
  json_object_object_add(record, key, j); return true;
}
static bool finite(const float *data, size_t values) {
  for (size_t i = 0; i < values; ++i) if (!isfinite(data[i])) return false;
  return true;
}
/* Independent scalar sanity oracle for zero-query generated data only. Uniform
 * softmax has unit exponentials; all V sums here are exact binary fractions.
 * This is not a CPU model forward or a general attention implementation. */
static bool uniform_oracle(const lie_attention_fixture_plan *p, const float *out, float *maximum) {
  if (!p->spec.zero_query) return true;
  for (uint32_t row = 0; row < p->spec.rows; ++row) {
    const uint32_t query = p->deep_start + row;
    for (uint32_t head = 0; head < 24; ++head) {
      for (uint32_t dim = 0; dim < 256; ++dim) {
        float sum = 0; uint32_t count = 0;
        for (uint32_t rank = 0; rank < p->block_count; ++rank) {
          const uint32_t block = p->blocks[rank];
          const uint32_t bit = p->deep_mask[(size_t)row * p->deep_pitch + block / 32] &
              (UINT32_C(1) << (block % 32));
          if (!bit && block < (query + 1) / 4) continue;
          for (uint32_t tail = 0; tail < 4; ++tail) {
            if (block * 4 + tail > query) continue;
            const uint32_t key = rank * 4 + tail;
            sum += (float)((int)(key % 31) - 15) / 16.0f +
                (float)((head / 12) * 3 + dim % 11) / 32.0f;
            ++count;
          }
        }
        const float expected = count ? (sum / (float)count) * .5f : 0.0f;
        const float error = fabsf(out[(size_t)row * LIE_ATTENTION_FIXTURE_WIDTH + head * 256 + dim] - expected);
        if (error > *maximum) *maximum = error;
      }
    }
  }
  /* The pinned device kernel uses fast math, including reciprocal division.
   * Fix this sanity bound before any GPU run. The complete long/short output
   * comparison remains bitwise exact. */
  return *maximum <= 1e-6;
}
static json_object *identity(void) {
  json_object *j = json_object_new_object();
  text(j, "event", "identity"); text(j, "schema", "synapse-lie.attention-fixture.v1");
  text(j, "program", "lie-attention-qualify"); text(j, "build_id", LIE_BUILD_ID);
  text(j, "source_pin", "f783fedb9bea2ec7de941f6da4e02f4a4596b29e");
  boolean(j, "synthetic", true); boolean(j, "model_inference", false);
  boolean(j, "component_only", true); boolean(j, "long_context_wmma", LIE_LONG_CONTEXT_WMMA);
#ifdef LIE_ATTENTION_HOST_FIXTURE
  boolean(j, "host_fixture", true);
#else
  boolean(j, "host_fixture", false);
#endif
  text(j, "classification", "GENERATED-COMPONENT-NOT-MODEL-INFERENCE");
  text(j, "encoding", "IEEE754-F32/U32-little-endian");
  text(j, "generator", "rank-v1; K[d=0]=(key%17-8)/8; V=(key%31-15)/16+(kv_head*3+dim%11)/32; Q[d=0]=16*(1+row/8+head/16); gate=0");
  number(j, "cases", LIE_ATTENTION_FIXTURE_COUNT); number(j, "width", LIE_ATTENTION_FIXTURE_WIDTH);
  json_object_object_add(j, "uniform_max_abs_error_limit", json_object_new_double(1e-6));
  return j;
}
static bool case_run(int dir, FILE *file, unsigned index) {
  lie_attention_fixture_plan p = {0};
  if (lie_attention_fixture_prepare(&lie_attention_fixture_specs[index], &p)) return false;
  const size_t values = (size_t)p.spec.rows * LIE_ATTENTION_FIXTURE_WIDTH;
  float *deep = malloc(values * sizeof(*deep)), *short_out = malloc(values * sizeof(*short_out));
  if (!deep || !short_out) { free(deep); free(short_out); lie_attention_fixture_dispose(&p); return false; }
  memset(deep, 0xff, values * sizeof(*deep)); memset(short_out, 0xff, values * sizeof(*short_out));
  lie_attention_fixture_result result = {0};
  int exit_code = interrupted ? 1 : lie_attention_fixture_gpu(&p, deep, short_out, &result);
  const bool expected_refusal = !LIE_LONG_CONTEXT_WMMA && p.deep_pitch > 2048;
  bool unchanged = true;
  for (size_t i = 0; i < values; ++i) {
    uint32_t bits = 0; memcpy(&bits, deep + i, sizeof(bits));
    if (bits != UINT32_MAX) unchanged = false;
  }
  const bool exact = !memcmp(deep, short_out, values * sizeof(*deep));
  float uniform_error = 0;
  const bool numerical = finite(short_out, values) && uniform_oracle(&p, short_out, &uniform_error) &&
      (expected_refusal ? unchanged : finite(deep, values) && exact && uniform_oracle(&p, deep, &uniform_error));
  bool ok = !exit_code && !interrupted && !result.primary_error && !result.cleanup_error &&
      result.short_accepted && numerical &&
      (expected_refusal ? !result.accepted && result.expected_refusal &&
         result.refusal == 2 && result.output_unchanged : result.accepted &&
         !result.expected_refusal && result.refusal == 0);
#ifdef LIE_ATTENTION_HOST_FIXTURE
  ok = ok && !result.gpu_execution;
#else
  ok = ok && result.gpu_execution;
#endif
  json_object *j = json_object_new_object(); text(j, "event", "case"); number(j, "index", index);
  number(j, "end", p.spec.end); number(j, "rows", p.spec.rows); number(j, "selections", p.spec.selections);
  number(j, "deep_start", p.deep_start); number(j, "short_start", p.short_start);
  number(j, "deep_capacity", p.deep_capacity); number(j, "short_capacity", p.short_capacity);
  number(j, "deep_pitch", p.deep_pitch); number(j, "short_pitch", p.short_pitch);
  number(j, "short_base", p.short_base); number(j, "prefix_blocks", p.prefix_blocks);
  number(j, "block_count", p.block_count); number(j, "values", values);
  boolean(j, "zero_query", p.spec.zero_query); boolean(j, "zero_mask", p.spec.zero_mask);
  boolean(j, "gpu_execution", result.gpu_execution); boolean(j, "accepted", result.accepted);
  boolean(j, "short_accepted", result.short_accepted); boolean(j, "expected_refusal", result.expected_refusal);
  boolean(j, "output_unchanged", unchanged); boolean(j, "exact", exact); boolean(j, "numerical", numerical);
  boolean(j, "uniform_oracle_applicable", p.spec.zero_query);
  json_object_object_add(j, "uniform_max_abs_error", json_object_new_double(uniform_error));
  number(j, "refusal", result.refusal); number(j, "primary_error", result.primary_error);
  number(j, "cleanup_error", result.cleanup_error); number(j, "adapter_exit_code", (unsigned)exit_code);
  number(j, "requested_device_bytes", result.requested_device_bytes); text(j, "device_arch", result.device_arch);
  char name[64]; bool saved = true;
#define SAVE(suffix, data, bytes, key) do { \
  snprintf(name, sizeof(name), "case-%02u." suffix, index); \
  if (!raw(dir, name, data, bytes, j, key)) saved = false; } while (0)
  SAVE("deep.f32", deep, values * sizeof(*deep), "deep_output");
  SAVE("short.f32", short_out, values * sizeof(*short_out), "short_output");
  SAVE("blocks.u32", p.blocks, (size_t)p.block_count * sizeof(*p.blocks), "blocks");
  SAVE("deep-mask.u32", p.deep_mask, (size_t)p.spec.rows * p.deep_pitch * sizeof(*p.deep_mask), "deep_mask");
  SAVE("short-mask.u32", p.short_mask, (size_t)p.spec.rows * p.short_pitch * sizeof(*p.short_mask), "short_mask");
#undef SAVE
  ok = ok && saved; boolean(j, "passed", ok); boolean(j, "artifacts_complete", saved);
  free(deep); free(short_out); lie_attention_fixture_dispose(&p);
  return emit(file, j) && ok;
}
int main(int argc, char **argv) {
  if (argc == 2 && !strcmp(argv[1], "--help")) {
    puts("Usage: lie-attention-qualify --run --output-dir NEW_DIRECTORY\nRequires an admitted GPU lease. Saves complete generated sparse-WMMA comparisons through 1M.\nNo model, performance or reactive-serving qualification."); return 0;
  }
  bool run = false; const char *directory = NULL;
  for (int i = 1; i < argc; ++i) {
    if (!strcmp(argv[i], "--run") && !run) run = true;
    else if (!strcmp(argv[i], "--output-dir") && !directory && i + 1 < argc && argv[i + 1][0] && argv[i + 1][0] != '-')
      directory = argv[++i];
    else { fputs("Expected --run --output-dir NEW_DIRECTORY\n", stderr); return 2; }
  }
  const uint32_t one = 1;
  if (!run || !directory) { fputs("Expected --run --output-dir NEW_DIRECTORY\n", stderr); return 2; }
  if (sizeof(float) != 4 || FLT_RADIX != 2 || FLT_MANT_DIG != 24 || FLT_MAX_EXP != 128 || *(const unsigned char *)&one != 1) {
    fputs("Requires IEEE754 binary32 and little-endian encoding\n", stderr); return 1;
  }
  struct sigaction action = {0}; action.sa_handler = stop; sigemptyset(&action.sa_mask);
  if (sigaction(SIGINT, &action, NULL) || sigaction(SIGTERM, &action, NULL)) return 1;
  if (mkdir(directory, 0700)) { fputs("Output directory must be new\n", stderr); return 1; }
  int dir = open(directory, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
  if (dir < 0) return 1;
  int fd = openat(dir, "attention.jsonl", O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
  if (fd < 0) { close(dir); return 1; }
  FILE *file = fdopen(fd, "w");
  if (!file) { close(fd); close(dir); return 1; }
  bool ok = emit(file, identity()); unsigned completed = 0;
  for (unsigned i = 0; ok && i < LIE_ATTENTION_FIXTURE_COUNT; ++i) {
    ok = case_run(dir, file, i); if (ok) ++completed;
  }
  json_object *j = json_object_new_object(); text(j, "event", ok ? "complete" : "failed");
  number(j, "exit_code", ok ? 0 : 1); number(j, "completed_cases", completed);
  if (!emit(file, j)) ok = false;
  if (fsync(fd)) ok = false;
  if (fclose(file)) ok = false;
  if (close(dir)) ok = false;
  return ok ? 0 : 1;
}
