/* SPDX-License-Identifier: MIT */
/* Independent byte-layout oracle; no project codec or model provider linked.
 * Tiny synthetic geometry through 128K tokens. NOT-INFERENCE. */
#include <assert.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

typedef struct {
  unsigned char *p;
  size_t n, capacity;
} bytes;
static void append(bytes *b, const void *p, size_t n) {
  if (!n)
    return;
  assert(n <= 32 * 1024 * 1024 - b->n);
  if (b->n + n > b->capacity) {
    b->capacity = (b->n + n) * 2;
    assert(b->capacity <= 64 * 1024 * 1024);
    b->p = realloc(b->p, b->capacity);
    assert(b->p);
  }
  memcpy(b->p + b->n, p, n);
  b->n += n;
}
static void u32(bytes *b, uint32_t n) {
  unsigned char p[4];
  for (unsigned i = 0; i < 4; i++)
    p[i] = (unsigned char)(n >> (i * 8));
  append(b, p, 4);
}
static void u64(bytes *b, uint64_t n) {
  u32(b, (uint32_t)n);
  u32(b, (uint32_t)(n >> 32));
}
static void tensor(bytes *b, size_t size, unsigned salt) {
  for (size_t i = 0; i < size; i++) {
    unsigned char v = (unsigned char)(i * 29 + salt);
    append(b, &v, 1);
  }
}
static void native(bytes *b, const bytes *part, size_t offset) {
  unsigned char zero = 0;
  while (b->n % 8)
    append(b, &zero, 1);
  assert(offset <= part->n);
  append(b, part->p + offset, part->n - offset);
}
static bytes fixture(unsigned n, unsigned threshold, bool tiny, unsigned mtp,
                     bool vision, bytes *expected) {
  bytes payload = {0}, roles[11][5] = {0}, record = {0};
  unsigned cap = n > 64 ? n : 64;
  unsigned header[] = {0x34565344, 2, cap, 8, cap, cap,       6,
                       n,          5, 4,   3, 32,  0x51573802};
  for (unsigned i = 0; i < 13; i++)
    u32(&payload, header[i]);
  uint32_t *tokens = malloc(n * sizeof(*tokens));
  assert(tokens);
  for (unsigned i = 0; i < n; i++) {
    tokens[i] = tiny ? i + 1 : 1 + i % 30;
    if (!tiny && n > 2 && i == n - 2)
      tokens[i] = 31;
    u32(&roles[1][0], tokens[i]);
  }
  append(&payload, roles[1][0].p, roles[1][0].n);
  for (unsigned i = 0; i < 32; i++) {
    float value = i / 8.0f;
    uint32_t bits;
    _Static_assert(sizeof(float) == 4, "binary32 fixture");
    memcpy(&bits, &value, 4);
    u32(&roles[2][0], bits);
  }
  append(&payload, roles[2][0].p, roles[2][0].n);
  u32(&payload, tiny ? mtp : 0);
  for (unsigned layer = 0; layer < (tiny ? 5u : 4u); layer++) {
    if (layer < 4 && !(layer % 2)) {
      unsigned rs[] = {6, 5};
      size_t sizes[] = {4 * 2 * 3 * 3, 4 * 2 * 5};
      for (unsigned k = 0; k < 2; k++) {
        unsigned role = rs[k];
        tensor(&roles[role][layer], sizes[k],
               tiny ? layer + (k ? 20 : 10) : layer * 7 + role);
        append(&payload, roles[role][layer].p, roles[role][layer].n);
      }
    } else {
      unsigned rows = layer < 4 ? n : mtp, rs[] = {3, 4, 9, 10};
      size_t sizes[] = {2 * rows * 4, 2 * rows * 4, 4 * rows * 3,
                        2 * (rows / 4) * 3};
      for (unsigned k = 0; k < 4; k++) {
        unsigned role = rs[k];
        tensor(&roles[role][layer], sizes[k],
               tiny ? layer + 30 + 10 * k : layer * 7 + role);
        append(&payload, roles[role][layer].p, roles[role][layer].n);
      }
    }
  }
  tensor(&roles[7][0], 4 * 2 * 6, tiny ? 90 : 7);
  append(&payload, roles[7][0].p, roles[7][0].n);
  for (unsigned i = 0; i < 8; i++)
    u32(&payload, i < n ? tokens[n - 1 - i] : 31);
  u32(&payload, vision ? (uint32_t)-2 : 0);
  for (unsigned i = 0; i < n; i++) {
    u32(&payload, i);
    u32(&payload, vision ? 0 : i);
    u32(&payload, i);
    u32(&payload, 0);
  }
  const unsigned char start[] = {'K', 'V',          'C',           1,
                                 4,   tiny ? 6 : 1, tiny ? 15 : 0, 5};
  append(&record, start, 8);
  u32(&record, n);
  u32(&record, tiny ? 7 : 0);
  u32(&record, cap);
  u32(&record, 2);
  u64(&record, tiny ? 123456789 : 1);
  u64(&record, tiny ? 123456999 : 2);
  u64(&record, payload.n);
  assert(record.n == 48);
  const unsigned char text[] = {'a', 0, 'b', 'c', 0xe2, 0x82, 0xac};
  u32(&record, tiny ? 7 : 3);
  append(&record, tiny ? text : (const unsigned char *)"key", tiny ? 7 : 3);
  append(&record, payload.p, payload.n);
  if (tiny) {
    const unsigned char trailer[] = {0xff, 'o', 'p', 'a', 'q', 'u',
                                     'e',  0,   'e', 'x', 't', 'e',
                                     'n',  's', 'i', 'o', 'n'};
    append(&record, trailer, sizeof(trailer));
  } else if (expected) {
    native(expected, &roles[1][0], 0);
    native(expected, &roles[2][0], 0);
    bytes history = {0};
    for (unsigned i = 0; i < 2; i++)
      u32(&history, i < n ? tokens[n - 1 - i] : UINT32_MAX);
    native(expected, &history, 0);
    free(history.p);
    native(expected, &roles[7][0], 0);
    unsigned blocks = n > threshold ? n / 4 : 0;
    for (unsigned layer = 0; layer < 4; layer++) {
      if (!(layer % 2)) {
        native(expected, &roles[5][layer], 0);
        native(expected, &roles[6][layer], 0);
      } else {
        native(expected, &roles[3][layer], 0);
        native(expected, &roles[4][layer], 0);
        if (n - blocks * 4)
          native(expected, &roles[9][layer], blocks * 4 * 3 * 4);
        if (blocks)
          native(expected, &roles[10][layer], 0);
      }
    }
  }
  free(tokens);
  free(payload.p);
  for (unsigned i = 0; i < 11; i++)
    for (unsigned j = 0; j < 5; j++)
      free(roles[i][j].p);
  return record;
}
static void write_bytes(const char *path, const void *p, size_t n) {
  FILE *f = fopen(path, "wb");
  assert(f && fwrite(p, 1, n, f) == n && !fclose(f));
}
static bytes read_bytes(const char *path) {
  FILE *f = fopen(path, "rb");
  assert(f);
  bytes b = {0};
  unsigned char part[8192];
  size_t n;
  while ((n = fread(part, 1, sizeof(part), f)))
    append(&b, part, n);
  assert(!ferror(f) && !fclose(f));
  return b;
}
static void equal_file(const char *path, const bytes *expected) {
  bytes b = read_bytes(path);
  assert(b.n == expected->n && !memcmp(b.p, expected->p, b.n));
  free(b.p);
}
static char logpath[4096];
static void run(char *const argv[], int expected) {
  pid_t pid = fork();
  assert(pid >= 0);
  if (!pid) {
    int fd = open(logpath, O_WRONLY | O_CREAT | O_TRUNC, 0600);
    if (fd < 0)
      _exit(126);
    if (dup2(fd, STDOUT_FILENO) < 0 || dup2(fd, STDERR_FILENO) < 0)
      _exit(126);
    close(fd);
    execv(argv[0], argv);
    _exit(127);
  }
  int status;
  while (waitpid(pid, &status, 0) < 0)
    assert(errno == EINTR);
  if (!WIFEXITED(status) || WEXITSTATUS(status) != expected) {
    bytes b = read_bytes(logpath);
    fwrite(b.p, 1, b.n, stderr);
    free(b.p);
    fprintf(stderr, "child %s: status %d, expected exit %d\n", argv[0], status,
            expected);
    abort();
  }
}
static void contains(const char *needle) {
  bytes b = read_bytes(logpath);
  unsigned char zero = 0;
  append(&b, &zero, 1);
  assert(strstr((char *)b.p, needle));
  free(b.p);
}
static void clean(const char *path) {
  DIR *d = opendir(path);
  assert(d);
  struct dirent *ent;
  while ((ent = readdir(d))) {
    if (!strcmp(ent->d_name, ".") || !strcmp(ent->d_name, ".."))
      continue;
    char child[4096];
    assert(snprintf(child, sizeof(child), "%s/%s", path, ent->d_name) <
           (int)sizeof(child));
    struct stat st;
    assert(!lstat(child, &st));
    if (S_ISDIR(st.st_mode))
      clean(child);
    else
      assert(!unlink(child));
  }
  assert(!closedir(d) && !rmdir(path));
}
int main(int argc, char **argv) {
  assert(argc >= 3);
  char cwd[2048], directory[2200];
  assert(getcwd(cwd, sizeof(cwd)));
  assert(snprintf(directory, sizeof(directory), "%s/kvc-native-oracle-XXXXXX",
                  cwd) < (int)sizeof(directory));
  assert(mkdtemp(directory));
  char src[4096], dst[4096], oracle[4096], shape[4096], copy[4096], bad[4096],
      fifo[4096];
  snprintf(src, sizeof(src), "%s/input.kv", directory);
  snprintf(dst, sizeof(dst), "%s/output.kv", directory);
  snprintf(oracle, sizeof(oracle), "%s/expected.bin", directory);
  snprintf(shape, sizeof(shape), "%s/geometry", directory);
  snprintf(copy, sizeof(copy), "%s/copy.kv", directory);
  snprintf(bad, sizeof(bad), "%s/bad.kv", directory);
  snprintf(fifo, sizeof(fifo), "%s/fifo", directory);
  snprintf(logpath, sizeof(logpath), "%s/child.log", directory);
  if (!strcmp(argv[1], "wire")) {
    assert(argc == 4);
    bytes b = fixture(5, 8, true, 3, false, NULL);
    write_bytes(src, b.p, b.n);
    const char geometry[] = "4 1 2 1 4 3 2 3 2 5 2 6 32\n";
    write_bytes(shape, geometry, strlen(geometry));
    char *test[] = {argv[2], src, dst, NULL};
    run(test, 0);
    equal_file(dst, &b);
    char *inspect[] = {argv[3], "inspect", src, "--qwen-geometry", shape, NULL};
    run(inspect, 0);
    contains("\"qwen_layout_validated\":true");
    contains("\"inference_qualified\":false");
    contains("\"text_positions\":true");
    contains("\"mtp_tokens\":3");
    char *inspect_plain[] = {argv[3], "inspect", src, NULL};
    run(inspect_plain, 0);
    contains("\"qwen_layout_validated\":false");
    char *cp[] = {argv[3], "copy", src, copy, "--qwen-geometry", shape, NULL};
    run(cp, 0);
    equal_file(copy, &b);
    struct stat st;
    assert(!stat(copy, &st) && (st.st_mode & 0777) == 0600);
    run(cp, 1);
    equal_file(copy, &b);
    for (unsigned i = 0; i < 2; i++) {
      bytes changed = fixture(5, 8, true, i ? 5 : 0, i != 0, NULL);
      write_bytes(src, changed.p, changed.n);
      free(changed.p);
      run(inspect, 0);
      contains(i ? "\"mtp_tokens\":5" : "\"mtp_tokens\":0");
      contains(i ? "\"text_positions\":false" : "\"text_positions\":true");
    }
    b.p[5] = 255;
    b.p[6] = 128;
    b.p[21] = 99;
    write_bytes(src, b.p, b.n);
    char *opaque[] = {argv[3], "copy", src, bad, NULL};
    run(opaque, 0);
    equal_file(bad, &b);
    assert(!unlink(bad));
    b.p[8] = 4;
    write_bytes(src, b.p, b.n);
    run(inspect, 1);
    free(b.p);
    b = fixture(5, 8, true, 3, false, NULL);
    for (unsigned i = 0; i < 3; i++) {
      size_t n = i == 0 ? 51 : i == 1 ? 70 : b.n;
      if (i == 2)
        memcpy(b.p, "LIEPFX1", 7);
      write_bytes(src, b.p, n);
      run(opaque, 1);
      assert(lstat(bad, &st) && errno == ENOENT);
    }
    free(b.p);
    b = fixture(5, 8, true, 3, false, NULL);
    write_bytes(src, b.p, b.n);
    const char *invalid[] = {"0", "-1", "+1", "1x", "18446744073709551616"};
    for (unsigned i = 0; i < 5; i++) {
      char *args[] = {argv[3],     "inspect",          src,
                      "--max-mib", (char *)invalid[i], NULL};
      run(args, 2);
    }
    char wrong[] = "4 1 2 1 4 3 2 3 2 5 2 6 32 garbage\n";
    write_bytes(shape, wrong, strlen(wrong));
    run(inspect, 1);
    assert(!mkfifo(fifo, 0600));
    char *args[] = {argv[3], "inspect", fifo, NULL};
    run(args, 1);
    free(b.p);
  } else {
    bool map = !strcmp(argv[1], "map");
    assert(map || !strcmp(argv[1], "state"));
    const unsigned ns[] = {1,  2,  3,    4,    7,    8,     9,
                           11, 12, 2047, 2048, 2049, 131072};
    for (size_t i = 0; i < sizeof(ns) / sizeof(ns[0]); i++) {
      unsigned n = ns[i];
      if (!map && n != 1 && n != 3 && n != 4 && n != 2048 && n != 2049 &&
          n != 131072)
        continue;
      unsigned threshold = map && i < 9 ? 8 : 2048,
               ring = threshold == 8 ? 16 : 4096;
      bytes expected = {0},
            b = fixture(n, threshold, false, 0, false, map ? &expected : NULL);
      write_bytes(src, b.p, b.n);
      if (map) {
        write_bytes(oracle, expected.p, expected.n);
        char count[32], th[32], ri[32];
        snprintf(count, sizeof(count), "%u", n);
        snprintf(th, sizeof(th), "%u", threshold);
        snprintf(ri, sizeof(ri), "%u", ring);
        char *args[] = {argv[2], src, oracle, dst, count, th, ri, NULL};
        run(args, 0);
        equal_file(dst, &b);
      } else {
        char *args[] = {argv[2], src, dst, NULL};
        run(args, 0);
        bytes saved = read_bytes(dst);
        assert(saved.n >= b.n + 17 + 192 && !memcmp(saved.p, b.p, 12) &&
               !memcmp(saved.p + 16, b.p + 16, 16) &&
               !memcmp(saved.p + 40, b.p + 40, b.n - 40) &&
               !memcmp(saved.p + b.n, "fixture-extension", 17) &&
               !memcmp(saved.p + saved.n - 192, "LIEKVC1\0", 8) &&
               saved.p[12] == 7 && !saved.p[13] && !saved.p[14] &&
               !saved.p[15]);
        free(saved.p);
        char other[4096];
        assert(snprintf(other, sizeof(other), "%s-other", dst) <
               (int)sizeof(other));
        assert(!unlink(other));
      }
      assert(!unlink(dst));
      free(expected.p);
      free(b.p);
    }
  }
  clean(directory);
  puts("Independent native KVC byte oracle: PASS (NOT-INFERENCE)");
  return 0;
}
