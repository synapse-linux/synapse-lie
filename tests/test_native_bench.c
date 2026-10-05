/* SPDX-License-Identifier: MIT */
/* Native-only CLI/HTTP/report contract. Owns synthetic children and private
 * ephemeral loopback listeners. No GPU or numerical performance evidence. */
#include "bench_native.h"
#include <arpa/inet.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static pid_t server_pid = -1;
static const char *steering_server_bank;
static bool gate_mode;
static bool closed_stderr;
static char root[2300], logpath[2400];
static void pause_ms(unsigned ms) {
  struct timespec t = {ms / 1000, (long)(ms % 1000) * 1000000};
  while (nanosleep(&t, &t) && errno == EINTR) {
  }
}
static void stop_server(void) {
  if (server_pid <= 0)
    return;
  pid_t pid = server_pid;
  server_pid = -1;
  int status;
  if (waitpid(pid, &status, WNOHANG) == 0) {
    kill(pid, SIGTERM);
    for (unsigned i = 0; i < 100; i++) {
      if (waitpid(pid, &status, WNOHANG) == pid)
        return;
      pause_ms(10);
    }
    kill(pid, SIGKILL);
    while (waitpid(pid, &status, 0) < 0 && errno == EINTR) {
    }
  }
}
static void require(bool good, const char *why) {
  if (good)
    return;
  fprintf(stderr, "Native benchmark fixture failed: %s (files: %s)\n", why,
          root);
  exit(1);
}
static void path(char out[2400], const char *name) {
  require(snprintf(out, 2400, "%s/%s", root, name) < 2400, "path overflow");
}
static void clean(const char *dir) {
  DIR *d = opendir(dir);
  require(d != NULL, "cleanup open");
  struct dirent *ent;
  while ((ent = readdir(d))) {
    if (!strcmp(ent->d_name, ".") || !strcmp(ent->d_name, ".."))
      continue;
    char child[4096];
    require(snprintf(child, sizeof(child), "%s/%s", dir, ent->d_name) <
                (int)sizeof(child),
            "cleanup path");
    struct stat st;
    require(!lstat(child, &st), "cleanup stat");
    if (S_ISDIR(st.st_mode))
      clean(child);
    else
      require(!unlink(child), "cleanup unlink");
  }
  closedir(d);
  require(!rmdir(dir), "cleanup directory");
}
static void save(const char *name, const char *text) {
  char p[2400];
  path(p, name);
  FILE *f = fopen(p, "w");
  require(f != NULL, "fixture output");
  require(fputs(text, f) >= 0 && !fclose(f), "fixture write");
}
static void child_env(void) {
  setenv("PATH", "/nonexistent-native-bench-contract", 1);
  setenv("LC_ALL", "C", 1);
}
static void read_gate(void *unused, bool hold) {
  (void)unused;
  char file[2400];
  path(file, "gate/hold");
  if (hold)
    save("gate/hold", "Owned synthetic disk barrier\n");
  else
    require(!unlink(file) || errno == ENOENT, "release synthetic gate");
}
static void run(char *const args[], int expected) {
  pid_t pid = fork();
  require(pid >= 0, "fork");
  if (!pid) {
    child_env();
    int fd = open(logpath, O_WRONLY | O_CREAT | O_TRUNC, 0600);
    if (fd < 0)
      _exit(126);
    dup2(fd, STDOUT_FILENO);
    dup2(fd, STDERR_FILENO);
    close(fd);
    if(closed_stderr){
      int output_pipe[2];if(pipe(output_pipe))_exit(126);
      close(output_pipe[0]);if(dup2(output_pipe[1],STDERR_FILENO)<0)_exit(126);
      close(output_pipe[1]);
    }
    if (gate_mode) {
      server_pid = -1;
      int argc = 0;
      while (args[argc])
        argc++;
      exit(nb_ssd_main_with_gate(argc, (char **)args, read_gate, NULL));
    }
    execv(args[0], args);
    _exit(127);
  }
  int status;
  while (waitpid(pid, &status, 0) < 0)
    require(errno == EINTR, "wait child");
  if (!WIFEXITED(status) || WEXITSTATUS(status) != expected) {
    FILE *f = fopen(logpath, "r");
    if (f) {
      char line[1024];
      while (fgets(line, sizeof(line), f))
        fputs(line, stderr);
      fclose(f);
    }
    fprintf(stderr, "Child %s: status %d, expected exit %d\n", args[0], status,
            expected);
    require(false, "child exit");
  }
}
static unsigned reserve(int *fd) {
  *fd = socket(AF_INET, SOCK_STREAM, 0);
  require(*fd >= 0, "ephemeral socket");
  struct sockaddr_in a = {.sin_family = AF_INET,
                          .sin_addr.s_addr = htonl(INADDR_LOOPBACK)};
  require(!bind(*fd, (struct sockaddr *)&a, sizeof(a)), "ephemeral bind");
  socklen_t size = sizeof(a);
  require(!getsockname(*fd, (struct sockaddr *)&a, &size), "ephemeral port");
  return ntohs(a.sin_port);
}
static void start_server(const char *binary, char api[128],
                         char management[128]) {
  int a, b;
  unsigned ap = reserve(&a), mp = reserve(&b);
  char aps[16], mps[16], store[2400], log[2400];
  snprintf(aps, sizeof(aps), "%u", ap);
  snprintf(mps, sizeof(mps), "%u", mp);
  snprintf(api, 128, "http://127.0.0.1:%u/v1", ap);
  snprintf(management, 128, "http://127.0.0.1:%u", mp);
  path(store, "store");
  path(log, "server.log");
  close(a);
  close(b);
  server_pid = fork();
  require(server_pid >= 0, "server fork");
  if (!server_pid) {
    child_env();
    char gate[2400];
    path(gate, "gate");
    setenv("LIE_TEST_SSD_READ_GATE", gate, 1);
    int fd = open(log, O_WRONLY | O_CREAT | O_APPEND, 0600);
    if (fd < 0)
      _exit(126);
    dup2(fd, STDOUT_FILENO);
    dup2(fd, STDERR_FILENO);
    close(fd);
    if(steering_server_bank){
      execl(binary,binary,"--model",":fixture:","--port",aps,"--management-port",mps,
            "--context","128","--prefill-chunk","4","--max-active","2",
            "--dir-steering-file",steering_server_bank,"--dir-steering-ffn","-2","--dir-steering-attn","0.25",(char *)NULL);
      _exit(127);
    }
    execl(binary, binary, "--model", ":fixture:", "--port", aps,
          "--management-port", mps, "--context", "4096", "--prefill-chunk", "4",
          "--max-active", "2", "--kv-cache-policy", "legacy",
          "--kv-cache-ram-mb", "0", "--kv-disk-dir", store,
          "--kv-disk-space-mb", "1", "--kv-disk-staging-mb", "1", (char *)NULL);
    _exit(127);
  }
  char url[180];
  snprintf(url, sizeof(url), "%s/actuator/health/readiness", management);
  for (unsigned i = 0; i < 500; i++) {
    int status;
    require(waitpid(server_pid, &status, WNOHANG) == 0,
            "server exited before readiness");
    nb_error e = {0};
    json_object *o = nb_http_get(url, .5, &e);
    if (o) {
      json_object_put(o);
      return;
    }
    pause_ms(10);
  }
  require(false, "server readiness deadline");
}
static json_object *read_json(const char *name, bool lines) {
  char p[2400];
  path(p, name);
  nb_error e = {0};
  json_object *o = nb_read(p, lines, &e);
  require(o != NULL, e.message);
  return o;
}
static void save_rows(const char *name, json_object *rows) {
  char p[2400];
  path(p, name);
  FILE *f = fopen(p, "w");
  require(f != NULL, "sampling evidence fixture");
  for (size_t i = 0; i < json_object_array_length(rows); ++i)
    require(nb_emit(f, json_object_array_get_idx(rows, i)), "sampling fixture write");
  require(!fclose(f), "sampling fixture close");
}
static void graph_files(const char *name) {
  char p[2400];
  char n[256];
  const char *files[] = {"summary.json", "summary.csv", "benchmark.svg",
                         "benchmark.png"};
  for (unsigned i = 0; i < 4; i++) {
    snprintf(n, sizeof(n), "%s/%s", name, files[i]);
    path(p, n);
    struct stat st;
    require(!stat(p, &st) && st.st_size > 40, "missing native report artifact");
  }
  snprintf(n, sizeof(n), "%s/benchmark.png", name);
  path(p, n);
  FILE *f = fopen(p, "rb");
  require(f != NULL, "PNG file");
  unsigned char signature[8];
  require(fread(signature, 1, 8, f) == 8 &&
              !memcmp(signature, "\x89PNG\r\n\x1a\n", 8),
          "PNG signature");
  fclose(f);
}
static void parsers(void) {
  nb_error e = {0};
  require(!nb_parse("{}{}", 4, &e), "trailing JSON accepted");
  const char overflow[] = "{\"value\":1e999}";
  require(!nb_parse(overflow, sizeof(overflow) - 1, &e),
          "nonfinite JSON accepted");
  const char nul[] = "{\"text\":\"a\\u0000b\"}";
  require(!nb_parse(nul, sizeof(nul) - 1, &e),
          "NUL would truncate text evidence");
  require(!nb_parse("{\"a\":\"\xff\"}", 9, &e), "invalid UTF8 accepted");
  require(!nb_http_url("file:///etc/passwd", &e) &&
              !nb_http_url("http://user:pass@127.0.0.1/v1", &e) &&
              !nb_http_url("http://localhost/v1?q=1", &e),
          "invalid URL accepted");
  double values[] = {10, 1, 2, 3, 4, 5, 6, 7, 8, 9};
  json_object *d = nb_distribution(values, 10);
  require(d && json_object_get_double(nb_get(d, "median")) == 5.5 &&
              nb_number(d, "p50") == 5 && nb_number(d, "p95") == 10 &&
              nb_number(d, "p99") == 10,
          "nearest rank distribution");
  json_object_put(d);
  json_object *ids = nb_parse("[0,1,2147483647]", 16, &e);
  char hash[65];
  require(ids && nb_ids_hash(ids, hash), "physical ID digest");
  json_object_put(ids);
}
static void direct_clock_contract(json_object *rows) {
  const char *keys[] = {"sample_begin_monotonic_ns", "sample_begin_wall_time_ns",
                        "prefill_begin_monotonic_ns", "prefill_end_monotonic_ns",
                        "decode_begin_monotonic_ns", "decode_end_monotonic_ns"};
  require(!strcmp(nb_string(json_object_array_get_idx(rows, 0), "timing_clock"),
                   "CLOCK_MONOTONIC"), "direct clock domain");
  for (unsigned mode = 0; mode < 5; ++mode) {
    json_object *copy = NULL;
    require(!json_object_deep_copy(rows, &copy, NULL), "clock evidence copy");
    json_object *identity = json_object_array_get_idx(copy, 0), *first = NULL;
    for (size_t i = 0; i < json_object_array_length(copy); ++i) {
      json_object *r = json_object_array_get_idx(copy, i);
      if (strcmp(nb_string(r, "event"), "sample"))
        continue;
      if (!first)
        first = r;
      for (size_t k = 0; k < sizeof(keys) / sizeof(*keys); ++k)
        require(nb_count(r, keys[k], 1, INT64_MAX, NULL), "missing native phase timestamp");
      if (mode == 4)
        for (size_t k = 0; k < sizeof(keys) / sizeof(*keys); ++k)
          json_object_object_del(r, keys[k]);
    }
    require(first != NULL, "clock evidence sample");
    if (mode == 0)
      nb_num(first, keys[3], nb_number(first, keys[3]) + 1);
    else if (mode == 1)
      json_object_object_del(first, keys[4]);
    else if (mode == 2)
      nb_num(first, keys[0], nb_number(first, keys[2]) + 1);
    else if (mode == 3)
      json_object_object_add(identity, "timing_clock", json_object_new_string("CLOCK_REALTIME"));
    else
      json_object_object_del(identity, "timing_clock");
    char name[80], input[2400], directory[2400];
    snprintf(name, sizeof(name), "clock-%u.jsonl", mode);
    path(input, name);
    FILE *f = fopen(input, "w");
    require(f != NULL, "clock evidence file");
    for (size_t i = 0; i < json_object_array_length(copy); ++i)
      require(nb_emit(f, json_object_array_get_idx(copy, i)), "clock evidence write");
    require(!fclose(f), "clock evidence close");
    json_object_put(copy);
    snprintf(name, sizeof(name), "clock-%u-graphs", mode);
    path(directory, name);
    nb_error error = {0};
    int rc = nb_report(input, directory, "fixture", NULL, "reference", false, &error);
    if (mode == 4) {
      require(!rc, "retained evidence without clock fields must remain readable");
      graph_files(name);
    } else {
      require(rc && strstr(error.message, "monotonic phase"), "forged phase clock accepted");
      struct stat st;
      require(lstat(directory, &st) && errno == ENOENT, "invalid phase evidence published graphs");
    }
  }
  json_object *summary = read_json("direct-graphs/summary.json", false);
  json_object *point = json_object_array_get_idx(nb_get(nb_get(summary, "primary"), "configurations"), 0);
  require(nb_number(nb_get(point, "prefill_seconds"), "n") == 2 &&
          json_object_get_double(nb_get(nb_get(point, "prefill_seconds"), "median")) > 0 &&
          nb_number(nb_get(point, "decode_seconds"), "n") == 2,
          "missing measured duration distributions");
  json_object_put(summary);
  char csvpath[2400], header[1024];
  path(csvpath, "direct-graphs/summary.csv");
  FILE *f = fopen(csvpath, "r");
  require(f && fgets(header, sizeof(header), f) &&
          strstr(header, "pp_median_s,pp_min_s,pp_max_s,tg_median_s,tg_min_s,tg_max_s"),
          "CSV does not expose phase duration distributions");
  require(!fclose(f), "duration CSV close");
}
static void reordered_comparison(json_object *rows, const char *original) {
  json_object *inputs = json_object_new_array();
  for (size_t i = 0; i < json_object_array_length(rows); i++) {
    json_object *row = json_object_array_get_idx(rows, i);
    if (!strcmp(nb_string(row, "event"), "input"))
      json_object_array_add(inputs, json_object_get(row));
  }
  size_t remaining = json_object_array_length(inputs);
  require(remaining == 4, "comparison must exercise four workloads");
  char reversed[2400], graphs[2400];
  path(reversed, "reordered.jsonl");
  FILE *f = fopen(reversed, "w");
  require(f != NULL, "reordered fixture file");
  for (size_t i = 0; i < json_object_array_length(rows); i++) {
    json_object *row = json_object_array_get_idx(rows, i);
    if (!strcmp(nb_string(row, "event"), "input"))
      row = json_object_array_get_idx(inputs, --remaining);
    require(nb_emit(f, row), "reordered fixture write");
  }
  require(!fclose(f) && !remaining, "reordered fixture close");
  json_object_put(inputs);
  nb_error e = {0};
  path(graphs, "self-comparison");
  require(
      !nb_report(original, graphs, "primary", original, "reference", false, &e),
      e.message);
  graph_files("self-comparison");
  char marker_path[2400], marker_line[256];
  path(marker_path, "self-comparison/benchmark.svg");
  FILE *markers = fopen(marker_path, "r");
  require(markers != NULL, "comparison marker file");
  int positions[2][8][2];
  size_t marker_counts[2] = {0};
  while (fgets(marker_line, sizeof(marker_line), markers)) {
    int x, y;
    unsigned color;
    if (sscanf(marker_line, "<circle cx=\"%d\" cy=\"%d\" r=\"4\" fill=\"#%x", &x, &y, &color) != 3)
      continue;
    require(color == 0x1769aa || color == 0xb34b17, "comparison marker color");
    unsigned series = color == 0x1769aa ? 0 : 1;
    require(marker_counts[series] < 8, "unexpected comparison marker count");
    positions[series][marker_counts[series]][0] = x;
    positions[series][marker_counts[series]++][1] = y;
  }
  require(!fclose(markers) && marker_counts[0] == 8 && marker_counts[1] == 8,
          "missing four-category comparison markers");
  for (size_t i = 0; i < 8; ++i)
    require(positions[0][i][1] == positions[1][i][1] &&
                abs(positions[1][i][0] - positions[0][i][0]) >= 8,
            "coincident comparison markers hide a series");
  path(graphs, "reordered-comparison");
  require(
      !nb_report(original, graphs, "primary", reversed, "reference", false, &e),
      e.message);
  graph_files("reordered-comparison");
  const char *formats[] = {"svg", "png"};
  for (unsigned i = 0; i < 2; i++) {
    char a[2400], b[2400], name[100], ah[65], bh[65];
    snprintf(name, sizeof(name), "self-comparison/benchmark.%s", formats[i]);
    path(a, name);
    snprintf(name, sizeof(name), "reordered-comparison/benchmark.%s",
             formats[i]);
    path(b, name);
    require(nb_file_hash(a, ah) && nb_file_hash(b, bh) && !strcmp(ah, bh),
            "comparison graph changed when reference workload order changed");
  }
}
static void core_clock_contract(json_object *rows) {
  /* Mutate both warmups and measurements. A zero-time job must not disappear
   * from the rate distribution while its output still counts toward a pass. */
  for (unsigned mode = 0; mode < 8; ++mode) {
    json_object *copy = NULL, *job = NULL;
    require(!json_object_deep_copy(rows, &copy, NULL), "core timing evidence copy");
    for (size_t i = 0; i < json_object_array_length(copy); ++i) {
      json_object *r = json_object_array_get_idx(copy, i);
      if (!strcmp(nb_string(r, "event"), "job") &&
          nb_number(r, "rep") == (mode == 1 ? 1 : 0)) {
        job = r;
        break;
      }
    }
    require(job != NULL, "core timing job");
    switch (mode) {
    case 0:
    case 1: nb_num(job, "decode_ns", 0); break;
    case 2: nb_num(job, "prefill_ns", 0); break;
    case 3: nb_num(job, "prefill_calls", 0); break;
    case 4: nb_num(job, "decode_calls", 0); break;
    case 5: nb_num(job, "decode_ns", nb_number(job, "total_ns") + 1); break;
    case 6: nb_num(job, "prefill_ns", nb_number(job, "total_ns") + 1); break;
    case 7: nb_num(job, "decode_ns", nb_number(job, "total_ns")); break;
    }
    char name[80], input[2400], directory[2400];
    snprintf(name, sizeof(name), "core-clock-%u.jsonl", mode);
    save_rows(name, copy);
    path(input, name);
    json_object_put(copy);
    snprintf(name, sizeof(name), "core-clock-%u-graphs", mode);
    path(directory, name);
    nb_error error = {0};
    require(nb_report(input, directory, "fixture", NULL, NULL, false, &error) &&
                strstr(error.message, "core phase timing"),
            "invalid core phase accepted");
    struct stat st;
    require(lstat(directory, &st) && errno == ENOENT,
            "invalid core timing published graphs");
  }
}
static void core_eos_contract(char *bench, char *tokens) {
  char output[2400], graphs[2400], changed[2400], refused[2400];
  path(output, "fixed-eos-core.jsonl");path(graphs, "fixed-eos-core-graphs");
  char *args[] = {bench,"--suite","core","--model",":eos:","--tokens-file",tokens,
                 "--tg","16","--users","2","--warmups","0","--repetitions","2",
                 "--kv-cache-ram-mb","0","--ignore-eos","--output",output,"--graphs",graphs,NULL};
  run(args,0);graph_files("fixed-eos-core-graphs");
  json_object *rows=read_json("fixed-eos-core.jsonl",true),*id=json_object_array_get_idx(rows,0);
  require(!strcmp(nb_string(id,"eos_policy"),"ignore"),"fixed EOS policy not declared");
  unsigned jobs=0;
  for(size_t i=0;i<json_object_array_length(rows);++i){json_object *r=json_object_array_get_idx(rows,i);
    if(strcmp(nb_string(r,"event"),"job"))continue;
    require(nb_number(r,"output_tokens")==16 && nb_number(r,"output_bytes")==15 &&
            !strcmp(nb_string(r,"finish"),"length") &&
            json_object_get_int(json_object_array_get_idx(nb_get(r,"output_ids"),7))==255,
            "EOS must be a confirmed token, including its zero-byte text, not masked or retried");++jobs;
  }
  require(jobs==4,"missing EOS cohorts/repetitions");
  json_object *summary=read_json("fixed-eos-core-graphs/summary.json",false);
  json_object *point=json_object_array_get_idx(nb_get(nb_get(summary,"primary"),"configurations"),0);
  require(!strcmp(nb_string(point,"eos_policy"),"ignore"),"EOS policy lost from summary");json_object_put(summary);
  nb_str(id,"eos_policy","stop");save_rows("other-eos-policy.jsonl",rows);
  path(changed,"other-eos-policy.jsonl");path(refused,"other-eos-policy-graphs");nb_error error={0};
  require(nb_report(output,refused,"fixed",changed,"natural",false,&error)!=0,
          "different EOS methods accepted as a matched comparison");
  struct stat st;require(lstat(refused,&st)&&errno==ENOENT,"mismatched EOS published graphs");
  json_object_object_del(id,"eos_policy");save_rows("historical-eos-policy.jsonl",rows);
  path(changed,"historical-eos-policy.jsonl");path(graphs,"historical-eos-policy-graphs");
  char declared[2400];path(declared,"other-eos-policy.jsonl");
  require(!nb_report(declared,graphs,"stop",changed,"historical",false,&error),
          "historical core EOS policy must normalize to stop");
  for(unsigned i=0;i<4;++i){
    json_object_object_add(id,"eos_policy",i==0?NULL:i==1?json_object_new_boolean(true):
                           i==2?json_object_new_int(1):json_object_new_string("unknown"));
    char name[96];snprintf(name,sizeof(name),"invalid-eos-policy-%u.jsonl",i);
    save_rows(name,rows);path(changed,name);
    require(nb_report(changed,refused,"invalid",NULL,NULL,false,&error)!=0,"malformed EOS policy accepted");
  }
  json_object_put(rows);
  path(output,"natural-eos-core.jsonl");
  char *natural[]={bench,"--suite","core","--model",":eos:","--tokens-file",tokens,
                   "--tg","16","--warmups","0","--repetitions","1","--kv-cache-ram-mb","0",
                   "--output",output,NULL};run(natural,0);
  rows=read_json("natural-eos-core.jsonl",true);id=json_object_array_get_idx(rows,0);
  require(!strcmp(nb_string(id,"eos_policy"),"stop"),"default EOS policy changed");
  nb_str(id,"eos_policy","ignore");save_rows("incomplete-fixed-eos-core.jsonl",rows);
  path(changed,"incomplete-fixed-eos-core.jsonl");
  require(nb_report(changed,refused,"incomplete",NULL,NULL,false,&error)!=0,
          "short output qualified as fixed-budget decode");json_object_put(rows);
  path(output,"fixed-eos-provider-fault.jsonl");
  char *fault[]={bench,"--suite","core","--model",":eos-policy-fault:","--tokens-file",tokens,
                 "--tg","16","--warmups","0","--repetitions","1","--kv-cache-ram-mb","0",
                 "--ignore-eos","--output",output,NULL};run(fault,1);
  rows=read_json("fixed-eos-provider-fault.jsonl",true);
  json_object *last=json_object_array_get_idx(rows,json_object_array_length(rows)-1);
  require(nb_number(last,"exit_code")==1&&!strcmp(nb_string(last,"event"),"failed"),
          "provider EOS violation published a successful footer");json_object_put(rows);
#if LIE_MTP
  path(output,"fixed-eos-mtp.jsonl");
  char *mtp[]={bench,"--suite","core","--model",":eos:","--model-mtp",":fixture:",
               "--tokens-file",tokens,"--tg","16","--users","2","--repetitions","1",
               "--kv-cache-ram-mb","0","--ignore-eos","--output",output,NULL};run(mtp,0);
  rows=read_json("fixed-eos-mtp.jsonl",true);jobs=0;
  for(size_t i=0;i<json_object_array_length(rows);++i){json_object *r=json_object_array_get_idx(rows,i);
    if(strcmp(nb_string(r,"event"),"job"))continue;
    require(nb_number(r,"output_tokens")==16&&nb_number(r,"output_bytes")==15&&
            nb_number(r,"mtp_accepted_tokens")>0&&!strcmp(nb_string(r,"finish"),"length"),
            "MTP did not preserve its fixed-token burst past EOS");++jobs;
  }
  require(jobs==2,"missing MTP fixed EOS rows");json_object_put(rows);
#endif
  char *duplicate[]={bench,"--suite","core","--build-info","--ignore-eos","--ignore-eos",NULL};run(duplicate,2);
  char *vision[]={bench,"--suite","core","--build-info","--ignore-eos","--model-vision",":vision-a:",NULL};run(vision,2);
  char *probe[]={bench,"--suite","core","--build-info","--ignore-eos","--reactive-probe",NULL};run(probe,2);
}
static void core_sampling_contract(char *bench, char *tokens, char *greedy) {
  char output[2400], graphs[2400];
  path(output, "sampled-core.jsonl");
  path(graphs, "sampled-core-graphs");
  char *args[] = {bench, "--suite", "core", "--model", ":sampling:",
                 "--tokens-file", tokens, "--tg", "8", "--users", "2",
                 "--warmups", "1", "--repetitions", "2", "--temperature", ".75",
                 "--top-p", ".9", "--top-k", "5", "--min-p", ".05", "--frequency-penalty", ".25",
                 "--presence-penalty", "-.5", "--seed", "9223372036854775807",
                 "--kv-cache-ram-mb", "0", "--output", output, "--graphs", graphs, NULL};
  run(args, 0); /* The fixture refuses configuration unless all seven controls arrive. */
  graph_files("sampled-core-graphs");
  json_object *summary = read_json("sampled-core-graphs/summary.json", false);
  json_object *point = json_object_array_get_idx(nb_get(nb_get(summary, "primary"), "configurations"), 0);
  require(nb_number(nb_get(point, "generation"), "seed") == INT64_MAX &&
          nb_number(nb_get(point, "generation"), "top_k") == 5 &&
          json_object_get_double(nb_get(nb_get(point, "generation"), "min_p")) == .05 &&
          json_object_get_double(nb_get(nb_get(point, "generation"), "temperature")) == .75,
          "sampling controls missing from summary");
  json_object_put(summary);
  const char *bad[][2] = {{"--temperature", "NaN"}, {"--temperature", "0x1p-1"},
                         {"--temperature", "2.01"}, {"--temperature", ".8"},
                         {"--top-p", "0"}, {"--top-p", "1.01"},
                         {"--top-k", "-1"}, {"--top-k", "2147483648"},
                         {"--top-k", "1.0"}, {"--top-k", "true"},
                         {"--min-p", "-0.01"}, {"--min-p", "1.01"},
                         {"--min-p", "NaN"}, {"--min-p", "0x1p-1"}, {"--min-p", "null"},
                         {"--frequency-penalty", "-2.1"}, {"--presence-penalty", "3"},
                         {"--seed", "9223372036854775808"}, {"--seed", "-1"},
                         {"--seed", ""}};
  for (size_t i = 0; i < sizeof(bad) / sizeof(*bad); ++i) {
    char *invalid[] = {bench, "--suite", "core", "--build-info", (char *)bad[i][0], (char *)bad[i][1], NULL};
    run(invalid, 2);
  }
  char *duplicate[] = {bench, "--suite", "core", "--build-info", "--seed", "1", "--seed", "2", NULL};
  run(duplicate, 2);
  char *duplicate_filter[] = {bench, "--suite", "core", "--build-info", "--top-k", "5", "--top-k", "6", NULL};
  run(duplicate_filter, 2);
  json_object *rows = read_json("sampled-core.jsonl", true);
  core_clock_contract(rows);
  json_object *generation = nb_get(json_object_array_get_idx(rows, 0), "generation");
  json_object *identity = json_object_array_get_idx(rows, 0);
  nb_str(identity, "rope_scaling", "yarn4");
  save_rows("sampled-other-rope.jsonl", rows);
  char rope_changed[2400], rope_refused[2400];
  path(rope_changed, "sampled-other-rope.jsonl");
  path(rope_refused, "sampled-other-rope-graphs");
  nb_error rope_error = {0};
  require(nb_report(output, rope_refused, "native", rope_changed, "yarn4", false, &rope_error) != 0,
          "different RoPE profiles accepted as matched comparison");
  nb_str(identity, "rope_scaling", "native");
  const char *filter_keys[] = {"top_k", "min_p"};
  for (size_t i = 0; i < 2; ++i) {
    char name[128], changed_filter[2400], refused_filter[2400];
    if (i == 0) nb_num(generation, "top_k", 6);
    else nb_real(generation, "min_p", .06);
    snprintf(name, sizeof(name), "sampled-other-%s.jsonl", filter_keys[i]);
    save_rows(name, rows); path(changed_filter, name);
    snprintf(name, sizeof(name), "sampled-other-%s-graphs", filter_keys[i]);
    path(refused_filter, name);
    nb_error filter_error = {0};
    require(nb_report(output, refused_filter, "primary", changed_filter, "other filter", false, &filter_error) != 0,
            "different sampling filters accepted as matched comparison");
    struct stat filter_stat;
    require(lstat(refused_filter, &filter_stat) && errno == ENOENT,
            "mismatched filters published graphs");
    nb_num(generation, "top_k", 5); nb_real(generation, "min_p", .05);
  }
  nb_num(generation, "seed", 7);
  save_rows("sampled-other-seed.jsonl", rows);
  char changed[2400], refused[2400];
  path(changed, "sampled-other-seed.jsonl");
  path(refused, "sampled-other-seed-graphs");
  nb_error error = {0};
  require(nb_report(output, refused, "primary", changed, "other seed", false, &error) != 0,
          "different sampling controls accepted as matched comparison");
  struct stat st;
  require(lstat(refused, &st) && errno == ENOENT, "mismatched sampling published graphs");
  json_object_object_add(generation, "seed", json_object_new_uint64((uint64_t)INT64_MAX + 1));
  save_rows("sampled-seed-overflow.jsonl", rows);
  path(changed, "sampled-seed-overflow.jsonl");
  require(nb_report(changed, refused, "primary", NULL, NULL, false, &error) != 0,
          "unsigned sampling seed silently saturated");
  nb_num(generation, "seed", INT64_MAX);
  for (unsigned i = 0; i < 4; ++i) {
    if (i == 0) json_object_object_add(generation, "top_k", json_object_new_uint64(UINT64_MAX));
    if (i == 1) json_object_object_add(generation, "top_k", json_object_new_boolean(true));
    if (i == 2) json_object_object_add(generation, "min_p", json_object_new_boolean(true));
    if (i == 3) nb_num(generation, "unknown_filter", 5);
    char name[128]; snprintf(name, sizeof(name), "sampled-invalid-filter-%u.jsonl", i);
    save_rows(name, rows); path(changed, name);
    require(nb_report(changed, refused, "primary", NULL, NULL, false, &error) != 0,
            "invalid sampling filter identity accepted");
    nb_num(generation, "top_k", 5); nb_real(generation, "min_p", .05);
    json_object_object_del(generation, "unknown_filter");
  }
  json_object_put(rows);
  rows = read_json("core.jsonl", true);
  generation = nb_get(json_object_array_get_idx(rows, 0), "generation");
  json_object_object_del(generation, "top_k");
  json_object_object_del(generation, "min_p");
  save_rows("historical-five-control-core.jsonl", rows);
  path(changed, "historical-five-control-core.jsonl");
  path(graphs, "historical-five-control-core-graphs");
  require(!nb_report(greedy, graphs, "current", changed, "historical", false, &error),
          "historical five-control identity lost compatibility");
  json_object_object_del(json_object_array_get_idx(rows, 0), "generation");
  save_rows("historical-greedy-core.jsonl", rows);
  json_object_put(rows);
  path(changed, "historical-greedy-core.jsonl");
  path(graphs, "historical-greedy-core-graphs");
  require(!nb_report(greedy, graphs, "current", changed, "historical", false, &error),
          "historical greedy identity lost compatibility");
}
static void core_progress_contract(char *bench) {
  save("progress-input.json","[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]\n");
  char input[2400],output[2400],graphs[2400];
  path(input,"progress-input.json");path(output,"progress-core.jsonl");
  path(graphs,"progress-core-graphs");
  char *args[]={bench,"--suite","core","--model",":progress-fixture:",
                "--tokens-file",input,"--output",output,"--context","128",
                "--chunk","4","--users","2","--tg","8","--warmups","0",
                "--repetitions","1","--kv-cache-ram-mb","0",
                "--progress-ms","100","--graphs",graphs,NULL};
  run(args,0);
  nb_error error={0};json_object *progress=nb_read(logpath,true,&error);
  require(progress&&json_object_array_length(progress)>=3,"missing native progress observations");
  uint64_t previous=0;bool pending=false;int64_t completed[2]={0},delivered[2]={0};
  size_t count=json_object_array_length(progress);
  for(size_t i=0;i<count;++i){
    json_object *line=json_object_array_get_idx(progress,i),*jobs=nb_get(line,"jobs");
    require(!strcmp(nb_string(line,"event"),"core_progress")&&
            !strcmp(nb_string(line,"schema"),"synapse-lie.core-progress.v1")&&
            json_object_get_boolean(nb_get(line,"synthetic"))&&
            nb_number(line,"elapsed_ns")>=(int64_t)previous&&
            nb_number(line,"snapshot_monotonic_ns")>0&&
            json_object_array_length(jobs)==2,"invalid progress identity/clock/cohort");
    previous=(uint64_t)nb_number(line,"elapsed_ns");
    require(json_object_get_boolean(nb_get(line,"final_snapshot"))==(i+1==count),
            "progress final observation count/order");
    for(unsigned u=0;u<2;++u){
      json_object *job=json_object_array_get_idx(jobs,u);
      int64_t pp=nb_number(job,"prefill_tokens"),out=nb_number(job,"consumer_tokens");
      require(nb_number(job,"user")==u&&pp>=completed[u]&&pp<=16&&
              pp==4*nb_number(job,"prefill_calls")&&out>=delivered[u]&&out<=8&&
              nb_number(job,"output_tokens")>=out,"progress reported speculative/future work");
      completed[u]=pp;delivered[u]=out;
      if(!strcmp(nb_string(line,"executor_phase"),"prefill")&&
          nb_number(line,"prefill_started")>nb_number(line,"prefill_returned")&&
          json_object_get_boolean(nb_get(job,"prepared"))&&pp<16)pending=true;
    }
  }
  require(pending&&completed[0]==16&&completed[1]==16&&delivered[0]==8&&delivered[1]==8,
          "progress lacks pending/confirmed/final witness");
  json_object_put(progress);graph_files("progress-core-graphs");
  json_object *result=read_json("progress-core.jsonl",true),*identity=json_object_array_get_idx(result,0);
  require(nb_number(identity,"progress_interval_ms")==100,"missing progress timing declaration");
  /* The default native client remains silent; progress policy must be matched
   * when comparing wall latency. A missing historical field means disabled. */
  json_object_object_add(identity,"progress_interval_ms",json_object_new_int(0));
  save_rows("progress-disabled.jsonl",result);
  char disabled[2400],comparison[2400];path(disabled,"progress-disabled.jsonl");path(comparison,"progress-mismatch");
  require(nb_report(output,comparison,"enabled",disabled,"disabled",false,&error)==1&&
          strstr(error.message,"settings mismatch"),"different progress policies compared silently");
  json_object_object_del(identity,"progress_interval_ms");save_rows("progress-historical.jsonl",result);
  char historical[2400];path(historical,"progress-historical.jsonl");path(comparison,"progress-compatible");
  require(!nb_report(disabled,comparison,"disabled",historical,"historical",false,&error),
          "historical disabled-progress compatibility");
  json_object_put(result);
  path(output,"progress-cached.jsonl");
  char *cached[]={bench,"--suite","core","--model",":progress-fixture:",
                  "--tokens-file",input,"--output",output,"--context","128","--chunk","4",
                  "--tg","8","--warmups","1","--repetitions","1","--kv-cache-ram-mb","1",
                  "--kv-cache-policy","legacy","--progress-ms","100",NULL};
  run(cached,0);progress=nb_read(logpath,true,&error);require(progress,"cached progress lost");
  unsigned finals=0;
  for(size_t i=0;i<json_object_array_length(progress);++i){
    json_object *line=json_object_array_get_idx(progress,i);
    if(!json_object_get_boolean(nb_get(line,"final_snapshot")))continue;
    json_object *job=json_object_array_get_idx(nb_get(line,"jobs"),0);
    require(nb_number(line,"rep")==finals&&nb_number(job,"output_tokens")==8,
            "cache repetition progress order");
    require(nb_number(line,"warmup")==!finals&&
            nb_number(job,"prefill_tokens")==(!finals?16:0)&&
            nb_number(job,"cached_tokens")==(!finals?0:16),
            "cache reuse presented as completed prefill");
    ++finals;
  }
  require(finals==2,"missing cache warmup/measured final observations");json_object_put(progress);
  path(output,"progress-quiet.jsonl");
  char *quiet[]={bench,"--suite","core","--model",":fixture:","--tokens-file",input,
                 "--output",output,"--context","128","--chunk","4","--tg","8",
                 "--repetitions","1","--kv-cache-ram-mb","0",NULL};
  run(quiet,0);struct stat quiet_log;
  require(!stat(logpath,&quiet_log)&&quiet_log.st_size==0,"default benchmark emits progress");
  path(output,"progress-failure.jsonl");
  char *failed[]={bench,"--suite","core","--model",":progress-failure:",
                  "--tokens-file",input,"--output",output,"--context","128","--chunk","4",
                  "--tg","8","--repetitions","1","--kv-cache-ram-mb","0","--progress-ms","100",NULL};
  run(failed,1);progress=nb_read(logpath,true,&error);require(progress,"failure progress lost");
  json_object *last=json_object_array_get_idx(progress,json_object_array_length(progress)-1),
              *job=json_object_array_get_idx(nb_get(last,"jobs"),0);
  require(json_object_get_boolean(nb_get(last,"final_snapshot"))&&
          nb_number(job,"prefill_tokens")==4&&nb_number(job,"output_tokens")==0&&
          nb_number(job,"prefill_calls")==2&&strstr(nb_string(job,"error"),"four completed tokens"),
          "failed executor work reported as completed prefill");
  json_object_put(progress);
  path(output,"progress-timeout.jsonl");
  char *timeout[]={bench,"--suite","core","--model",":progress-timeout:",
                   "--tokens-file",input,"--output",output,"--context","128","--chunk","4",
                   "--tg","8","--repetitions","1","--kv-cache-ram-mb","0",
                   "--timeout-ms","150","--progress-ms","100",NULL};
  run(timeout,1);progress=nb_read(logpath,true,&error);require(progress,"timeout progress lost");
  last=json_object_array_get_idx(progress,json_object_array_length(progress)-1);
  job=json_object_array_get_idx(nb_get(last,"jobs"),0);
  require(json_object_get_boolean(nb_get(last,"final_snapshot"))&&
          !json_object_get_boolean(nb_get(job,"retired"))&&
          nb_number(job,"prefill_tokens")==0&&nb_number(job,"output_tokens")==0,
          "unfinished executor call counted at timeout");
  json_object_put(progress);
  path(output,"progress-write-failure.jsonl");
  char *write_failure[]={bench,"--suite","core","--model",":progress-fixture:",
                         "--tokens-file",input,"--output",output,"--context","128","--chunk","4",
                         "--tg","8","--repetitions","1","--kv-cache-ram-mb","0","--progress-ms","100",NULL};
  closed_stderr=true;run(write_failure,1);closed_stderr=false;
  result=read_json("progress-write-failure.jsonl",true);
  last=json_object_array_get_idx(result,json_object_array_length(result)-1);
  require(!strcmp(nb_string(last,"event"),"failed")&&
          !strcmp(nb_string(last,"error"),"core progress output failed"),
          "broken progress pipe bypassed owned cleanup/failed evidence");
  json_object_put(result);
  for(unsigned i=0;i<3;++i){
    char *bad[]={bench,"--suite","core","--build-info","--progress-ms",
                 i==0?"1":i==1?"60001":"-1",NULL};run(bad,2);
  }
  char *duplicate[]={bench,"--suite","core","--build-info","--progress-ms","100","--progress-ms","100",NULL};run(duplicate,2);
}
static void steering_contract(char *server,char *bench){
  const char *invalid[]={"nan","inf","101","-101","1x"," 1","1,5"};
  for(size_t k=0;k<sizeof(invalid)/sizeof(*invalid);++k){
    char *a[]={bench,"--suite","core","--build-info","--dir-steering-ffn",(char *)invalid[k],NULL};run(a,2);
    char *b[]={server,"--dir-steering-ffn",(char *)invalid[k],NULL};run(b,2);
  }
  char *missing[]={bench,"--suite","core","--build-info","--dir-steering-ffn","1",NULL};run(missing,2);
  char *missing_model[]={server,"--dir-steering-file","unused.f32",NULL};run(missing_model,2);
  if(!LIE_DIRECTIONAL_STEERING)return;
  char bank[2400],input[2400],outputs[3][2400],graphs[2400];path(bank,"steering.f32");path(input,"steering.txt");
  const unsigned char data[]={0,0,128,63,0,0,0,64,0,0,64,64,0,0,128,64};
  FILE *f=fopen(bank,"wb");require(f&&fwrite(data,1,sizeof(data),f)==sizeof(data)&&!fclose(f),"private direction bank");
  save("steering.txt","abcdefgh");
  for(unsigned k=0;k<3;++k){
    char name[96];snprintf(name,sizeof(name),"steering-%u.jsonl",k);path(outputs[k],name);
    char *a[]={bench,"--suite","core","--model",":fixture:","--prompt-file",input,"--output",outputs[k],
      "--context","128","--chunk","4","--users","2","--tg","4","--repetitions","2",
      "--kv-cache-min-tokens","1","--kv-cache-boundary-trim-tokens","0","--kv-cache-boundary-align-tokens","0",
      "--kv-cache-capture-finish","off","--dir-steering-file",bank,"--dir-steering-ffn",k==1?"0":"1",NULL};run(a,0);
    if(k==0){unsigned char other[16];memcpy(other,data,16);other[2]=0;other[3]=64;
      char b[2400];path(b,"steering-other.f32");f=fopen(b,"wb");
      require(f&&fwrite(other,1,16,f)==16&&!fclose(f),"second bank");}
    if(k==1)path(bank,"steering-other.f32");
  }
  nb_error error={0};path(graphs,"steering-matched-graphs");
  require(!nb_report(outputs[0],graphs,"same",outputs[0],"same",false,&error),error.message);
  for(unsigned k=1;k<3;++k){char name[96];snprintf(name,sizeof(name),"steering-refused-%u",k);path(graphs,name);
    require(nb_report(outputs[0],graphs,"first",outputs[k],"different",false,&error)!=0,"steering scale/bank mismatch accepted as matched");
    struct stat st;require(lstat(graphs,&st)&&errno==ENOENT,"mismatched steering published graphs");}
  json_object *rows=read_json("steering-0.jsonl",true),*ready=NULL;
  for(size_t k=0;k<json_object_array_length(rows);++k){json_object *r=json_object_array_get_idx(rows,k);
    if(!strcmp(nb_string(r,"event"),"core_ready"))ready=r;}
  require(ready&&nb_number(nb_get(ready,"steering"),"host_vector_bytes")==16&&
          nb_number(nb_get(ready,"steering"),"device_vector_bytes")==0,"native admission/resource projection");
  json_object_object_add(nb_get(ready,"steering"),"admitted",json_object_new_boolean(false));
  save_rows("steering-invalid-admission.jsonl",rows);json_object_put(rows);
  char corrupted[2400];path(corrupted,"steering-invalid-admission.jsonl");path(graphs,"steering-corrupt-graphs");
  require(nb_report(corrupted,graphs,"invalid",NULL,NULL,false,&error)!=0,"inconsistent steering admission accepted");
  rows=read_json("core.jsonl",true);
  json_object_object_del(json_object_array_get_idx(rows,0),"steering");
  for(size_t k=0;k<json_object_array_length(rows);++k){json_object *r=json_object_array_get_idx(rows,k);
    if(!strcmp(nb_string(r,"event"),"core_ready"))json_object_object_del(r,"steering");}
  save_rows("historical-no-steering.jsonl",rows);json_object_put(rows);
  char historical[2400],current[2400];path(historical,"historical-no-steering.jsonl");path(current,"core.jsonl");path(graphs,"historical-no-steering-graphs");
  require(!nb_report(current,graphs,"current",historical,"historical",false,&error),"legacy unsteered reports lost compatibility");
  path(bank,"steering.f32");char *duplicate[]={bench,"--suite","core","--build-info","--dir-steering-file",bank,
    "--dir-steering-ffn","1","--dir-steering-ffn","1",NULL};run(duplicate,2);
  char *server_duplicate[]={server,"--model",":fixture:","--dir-steering-file",bank,
    "--dir-steering-ffn","1","--dir-steering-ffn","1",NULL};run(server_duplicate,2);
  char api[128],management[128],url[256];steering_server_bank=bank;start_server(server,api,management);
  snprintf(url,sizeof(url),"%s/actuator/info",management);json_object *info=nb_http_get(url,2,&error);
  require(info!=NULL,error.message);json_object *s=nb_get(nb_get(info,"backend"),"steering");
  require(json_object_get_boolean(nb_get(s,"admitted"))&&nb_number(s,"host_vector_bytes")==16&&
          nb_number(s,"device_vector_bytes")==0&&json_object_get_double(nb_get(s,"ffn"))==-2&&json_object_get_double(nb_get(s,"attention"))==.25,
          "HTTP admission projection differs from the core");json_object_put(info);
  require(!unlink(bank),"bank release after model admission");
  for(unsigned responses=0;responses<2;++responses)for(unsigned stream=0;stream<2;++stream){
    char body[512];snprintf(body,sizeof(body),
      "{\"model\":\"cpu-test-fixture\",\"%s\":[{\"role\":\"user\",\"content\":\"LONG\"}],\"%s\":4,\"stream\":%s%s}",
      responses?"input":"messages",responses?"max_output_tokens":"max_tokens",stream?"true":"false",
      stream&&!responses?",\"stream_options\":{\"include_usage\":true}":"");
    json_object *request=nb_parse(body,strlen(body),&error);require(request!=NULL,error.message);
    nb_http_options o={.url=api,.model="cpu-test-fixture",.provider="cpu-test-fixture-NOT-INFERENCE",
      .timeout=5,.responses=responses,.stream=stream,.strict=true};
    json_object *result=nb_http_request(&o,request,&error);require(result&&nb_number(result,"output_tokens")==4,error.message);
    json_object_put(result);json_object_put(request);
  }
  stop_server();steering_server_bank=NULL;
}
int main(int argc, char **argv) {
  require(argc == 4, "server, accounting bench and steering bench paths required");
  require(atexit(stop_server) == 0, "cleanup registration");
  char cwd[2048];
  require(getcwd(cwd, sizeof(cwd)) != NULL, "working directory");
  require(snprintf(root, sizeof(root), "%s/native-bench-XXXXXX", cwd) <
                  (int)sizeof(root) &&
              mkdtemp(root),
          "private fixture directory");
  path(logpath, "child.log");
  char gate[2400];
  path(gate, "gate");
  require(!mkdir(gate, 0700), "gate directory");
  parsers();
  char output[2400], graphs[2400], tokens[2400];
  save("tokens.json", "[0,1,2,3]\n");
  path(tokens, "tokens.json");
  path(output, "core.jsonl");
  path(graphs, "core-graphs");
  char *core[] = {argv[2],     "--suite",
                  "core",      "--model",
                  ":fixture:", "--tokens-file",
                  tokens,      "--tg",
                  "8",         "--users",
                  "2",         "--warmups",
                  "1",         "--repetitions",
                  "2",         "--kv-cache-policy",
                  "legacy",    "--output",
                  output,      "--graphs",
                  graphs,      NULL};
  run(core, 0);
  graph_files("core-graphs");
  json_object *sum = read_json("core-graphs/summary.json", false),
              *point = json_object_array_get_idx(
                  nb_get(nb_get(sum, "primary"), "configurations"), 0);
  require(!nb_get(point, "job_prefill_tps") &&
              nb_number(nb_get(point, "cached_tokens"), "median") == 4 &&
              nb_number(nb_get(point, "job_decode_tps"), "median") > 0,
          "cached prefill presented as executed work");
  json_object_put(sum);
  core_sampling_contract(argv[2], tokens, output);
  core_eos_contract(argv[2], tokens);
  core_progress_contract(argv[2]);
  steering_contract(argv[1],argv[3]);
  path(output, "direct.jsonl");
  path(graphs, "direct-graphs");
  char *direct[] = {
      argv[2],   "--suite",  "multi", "--model",   ":fixture:", "--users",
      "1,2,4,8", "--tg",     "8",     "--warmups", "0",         "--repetitions",
      "2",       "--output", output,  "--graphs",  graphs,      NULL};
  run(direct, 0);
  graph_files("direct-graphs");
  json_object *rows = read_json("direct.jsonl", true);
  direct_clock_contract(rows);
  reordered_comparison(rows, output);
  json_object *sample = NULL;
  for (size_t i = 0; i < json_object_array_length(rows); i++) {
    json_object *r = json_object_array_get_idx(rows, i);
    if (!strcmp(nb_string(r, "event"), "sample")) {
      sample = r;
      break;
    }
  }
  require(sample != NULL, "direct sample");
  nb_num(sample, "output_tokens", 999);
  char bad[2400];
  path(bad, "bad.jsonl");
  FILE *f = fopen(bad, "w");
  require(f != NULL, "mutation file");
  for (size_t i = 0; i < json_object_array_length(rows); i++)
    require(nb_emit(f, json_object_array_get_idx(rows, i)), "mutation write");
  fclose(f);
  json_object_put(rows);
  nb_error e = {0};
  char badgraphs[2400];
  path(badgraphs, "bad-graphs");
  require(nb_report(bad, badgraphs, "fixture", NULL, "reference", false, &e) !=
              0,
          "invalid evidence accepted");
  struct stat st;
  require(lstat(badgraphs, &st) && errno == ENOENT,
          "invalid evidence published a graph");
  char api[128], management[128];
  start_server(argv[1], api, management);
  char cases[2400], reference[2400];
  save("cases.json",
       "[{\"id\":\"disk\",\"prompt\":\"LONG-A\",\"max_tokens\":16},{\"id\":"
       "\"peer\",\"prompt\":\"LONG-B\",\"max_tokens\":512}]\n");
  path(cases, "cases.json");
  path(output, "write.jsonl");
  char *write[] = {argv[2],
                   "--suite",
                   "http-kv-disk",
                   "--url",
                   api,
                   "--management-url",
                   management,
                   "--model",
                   "cpu-test-fixture",
                   "--provider",
                   "cpu-test-fixture-NOT-INFERENCE",
                   "--cases",
                   cases,
                   "--output",
                   output,
                   "--phase",
                   "write",
                   "--chunk",
                   "4",
                   "--timeout",
                   "15",
                   NULL};
  run(write, 0);
  stop_server();
  start_server(argv[1], api, management);
  path(reference, "write.jsonl.summary.json");
  path(output, "read.jsonl");
  path(graphs, "disk-graphs");
  char *read[] = {argv[2],
                  "--suite",
                  "http-kv-disk",
                  "--url",
                  api,
                  "--management-url",
                  management,
                  "--model",
                  "cpu-test-fixture",
                  "--provider",
                  "cpu-test-fixture-NOT-INFERENCE",
                  "--cases",
                  cases,
                  "--output",
                  output,
                  "--phase",
                  "read",
                  "--reference",
                  reference,
                  "--chunk",
                  "4",
                  "--repetitions",
                  "2",
                  "--timeout",
                  "15",
                  "--overlap",
                  "--slow-client",
                  "--graphs",
                  graphs,
                  NULL};
  gate_mode = true;
  run(read, 0);
  gate_mode = false;
  graph_files("disk-graphs");
  sum = read_json("read.jsonl.summary.json", false);
  require(!strcmp(nb_string(sum, "state"), "PASS") &&
              json_object_array_length(nb_get(sum, "samples")) == 20 &&
              json_object_array_length(nb_get(sum, "cohorts")) == 2 &&
              json_object_get_boolean(nb_get(
                  nb_get(sum, "overlap"), "peer_progress_while_ssd_pending")) &&
              json_object_get_boolean(nb_get(nb_get(sum, "overlap"),
                                             "cancelled_while_io_pending")) &&
              !strcmp(nb_string(nb_get(sum, "slow_client"), "state"), "PASS"),
          "restart, C2 or slow-client witness");
  json_object_put(sum);
  save("requests.jsonl", "{\"id\":\"dialogue\",\"body\":{\"messages\":[{"
                         "\"role\":\"user\",\"content\":\"hello\"}],\"max_"
                         "tokens\":8},\"followups\":[\"continue\"]}\n");
  char requests[2400];
  path(requests, "requests.jsonl");
  path(output, "http.jsonl");
  path(graphs, "http-graphs");
  char *http[] = {argv[2],
                  "--suite",
                  "http",
                  "--url",
                  api,
                  "--model",
                  "cpu-test-fixture",
                  "--requests",
                  requests,
                  "--server-label",
                  "NOT-INFERENCE",
                  "--server-kv-cache",
                  "on",
                  "--output",
                  output,
                  "--graphs",
                  graphs,
                  "--repetitions",
                  "2",
                  NULL};
  run(http, 0);
  graph_files("http-graphs");
  run(http, 1);
  stop_server();
  clean(root);
  puts("Native HTTP/KV restart/C2/backpressure, report/parser and PNG/SVG "
       "fixtures: PASS (NOT-INFERENCE; child PATH contains no Python)");
  return 0;
}
