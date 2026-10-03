/* SPDX-License-Identifier: MIT */
/* Feature wiring through HTTP, core and synthetic provider. NOT-INFERENCE. */
#include "bench_native.h"
#if defined(TEST_VISION)
#include "vision_fixture.h"
#endif
#include <arpa/inet.h>
#include <errno.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
static pid_t owned = -1;
static void pause_ms(void) {
  struct timespec t = {0, 10000000};
  while (nanosleep(&t, &t) && errno == EINTR) {}
}
static void cleanup(void) {
  if (owned <= 0) return;
  kill(owned, SIGTERM);
  int status;
  for (unsigned i = 0; i < 100; ++i) {
    pid_t r = waitpid(owned, &status, WNOHANG);
    if (r == owned || (r < 0 && errno == ECHILD)) { owned = -1; return; }
    pause_ms();
  }
  kill(owned, SIGKILL);
  while (waitpid(owned, &status, 0) < 0 && errno == EINTR) {}
  owned = -1;
}
static void require(bool ok, const char *why) {
  if (!ok) { fprintf(stderr, "Feature HTTP: %s\n", why); exit(1); }
}
static unsigned reserve(int *fd) {
  *fd = socket(AF_INET, SOCK_STREAM, 0);
  require(*fd >= 0, "socket");
  struct sockaddr_in a = {.sin_family = AF_INET,
                          .sin_addr.s_addr = htonl(INADDR_LOOPBACK)};
  require(!bind(*fd, (struct sockaddr *)&a, sizeof(a)), "bind");
  socklen_t n = sizeof(a);
  require(!getsockname(*fd, (struct sockaddr *)&a, &n), "port");
  return ntohs(a.sin_port);
}
int main(int argc, char **argv) {
  require(argc == 2, "server argument");
  atexit(cleanup);
  int a, b;
  unsigned ap = reserve(&a), mp = reserve(&b);
  char aps[16], mps[16], api[128], health[128];
  snprintf(aps, sizeof(aps), "%u", ap);
  snprintf(mps, sizeof(mps), "%u", mp);
  snprintf(api, sizeof(api), "http://127.0.0.1:%u/v1", ap);
  snprintf(health, sizeof(health), "http://127.0.0.1:%u/actuator/health/readiness", mp);
  close(a); close(b);
  owned = fork();
  require(owned >= 0, "fork");
  if (!owned) {
    setenv("PATH", "/nonexistent-native-feature-test", 1);
    setenv("LC_ALL", "C", 1);
    execl(argv[1], argv[1], "--model", ":fixture:", "--model-id", "cpu-test-fixture",
#if defined(TEST_VISION)
          "--model-vision", ":vision-a:",
#else
          "--model-mtp", ":wide-fixture:",
#endif
          "--host", "127.0.0.1", "--port", aps, "--management-port", mps,
          "--context", "128", "--prefill-chunk", "4", "--max-active", "2",
          "--kv-cache-ram-mb", "0", (char *)NULL);
    _exit(127);
  }
  bool ready = false;
  for (unsigned i = 0; i < 500; ++i) {
    int status;
    pid_t r = waitpid(owned, &status, WNOHANG);
    if (r == owned) owned = -1;
    require(r == 0, "server exited before readiness");
    nb_error error = {0};
    json_object *o = nb_http_get(health, .25, &error);
    if (o) { json_object_put(o); ready = true; break; }
    pause_ms();
  }
  require(ready, "readiness deadline");
  snprintf(health, sizeof(health), "http://127.0.0.1:%u/actuator/info", mp);
  nb_error metadata_error = {0};
  json_object *metadata = nb_http_get(health, 1, &metadata_error);
  require(metadata != NULL, metadata_error.message);
  json_object *backend = nb_get(metadata, "backend");
  require(!json_object_get_boolean(nb_get(backend, "prefix_state")), "incomplete feature state advertised as cacheable");
#if defined(TEST_VISION)
  require(json_object_get_boolean(nb_get(backend, "vision")) &&
          nb_number(backend, "max_images") == 16, "vision capability");
#else
  require(json_object_get_boolean(nb_get(backend, "mtp")) &&
          nb_number(backend, "max_decode_output_tokens") == 13, "MTP capability");
#endif
  json_object_put(metadata);
  for (unsigned responses = 0; responses < 2; ++responses)
    for (unsigned stream = 0; stream < 2; ++stream)
      for (unsigned budget = 4; budget <= 19; budget += 15) {
      char body[2048], content[1024];
#if defined(TEST_VISION)
      snprintf(content, sizeof(content), responses ?
          "[{\"type\":\"input_text\",\"text\":\"normal\"},{\"type\":\"input_image\",\"image_url\":\"%s\"}]" :
          "[{\"type\":\"text\",\"text\":\"normal\"},{\"type\":\"image_url\",\"image_url\":{\"url\":\"%s\"}}]", image_url);
#else
      strcpy(content, "\"normal\"");
#endif
      snprintf(body, sizeof(body),
          "{\"model\":\"cpu-test-fixture\",\"%s\":[{\"role\":\"user\",\"content\":%s}],\"%s\":%u,\"stream\":%s%s}",
          responses ? "input" : "messages", content,
          responses ? "max_output_tokens" : "max_tokens", budget, stream ? "true" : "false",
          stream && !responses ? ",\"stream_options\":{\"include_usage\":true}" : "");
      nb_error error = {0};
      json_object *request = nb_parse(body, strlen(body), &error);
      require(request != NULL, error.message);
      nb_http_options opts = {.url = api, .model = "cpu-test-fixture",
          .provider = "cpu-test-fixture-NOT-INFERENCE", .timeout = 5,
          .responses = responses, .stream = stream, .strict = true};
      json_object *o = nb_http_request(&opts, request, &error);
      require(o != NULL, error.message);
      require(nb_number(o, "output_tokens") == (budget == 4 ? 4 : 8) && !nb_number(o, "cached_tokens") &&
              *nb_string(o, "content"), "complete uncached output");
#if defined(TEST_VISION)
      require(nb_number(o, "prompt_tokens") == 7, "image tokens lost in HTTP admission");
#else
      require(nb_number(o, "prompt_tokens") == 4, "prompt count");
      if (!responses) {
        json_object *timings = nb_get(o, "server_timings");
        require((budget == 4 ? nb_number(timings, "decode_calls") == 1 :
                 (nb_number(timings, "decode_calls") >= 1 && nb_number(timings, "decode_calls") <= 2)) &&
                nb_number(timings, "mtp_accepted_tokens") == (budget == 4 ? 3 : 7) &&
                nb_number(timings, "max_decode_output_tokens") == 13 &&
                !strcmp(nb_string(timings, "decode_mode"), "mtp"), "MTP metrics lost");
      }
#endif
      json_object_put(o);
      json_object_put(request);
    }
  pid_t pid = owned;
  require(!kill(pid, SIGTERM), "graceful stop");
  int status = 0;
  while (waitpid(pid, &status, 0) < 0) require(errno == EINTR, "wait");
  owned = -1;
  require(WIFEXITED(status) && !WEXITSTATUS(status), "server/sanitizer exit");
  puts("Feature HTTP Chat/Responses JSON/SSE: PASS (NOT-INFERENCE)");
}
