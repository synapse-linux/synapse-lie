/* SPDX-License-Identifier: MIT */
/* Semantic Chat/Responses projection. CPU fixtures only, NOT-INFERENCE. */
#include "bench_native.h"
#include <curl/curl.h>
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
  while (nanosleep(&t, &t) && errno == EINTR) {
  }
}
static void cleanup(void) {
  if (owned <= 0)
    return;
  kill(owned, SIGTERM);
  int status;
  for (unsigned i = 0; i < 100; ++i) {
    pid_t r = waitpid(owned, &status, WNOHANG);
    if (r == owned || (r < 0 && errno == ECHILD)) {
      owned = -1;
      return;
    }
    pause_ms();
  }
  kill(owned, SIGKILL);
  while (waitpid(owned, &status, 0) < 0 && errno == EINTR) {
  }
  owned = -1;
}
static void require(bool ok, const char *why) {
  if (!ok) {
    fprintf(stderr, "Feature HTTP: %s\n", why);
    exit(1);
  }
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
typedef struct {
  char *data;
  size_t bytes;
} body_buffer;
static size_t collect(char *p, size_t size, size_t n, void *arg) {
  body_buffer *b = arg;
  if (size && n > SIZE_MAX / size)
    return 0;
  size_t bytes = size * n;
  if (bytes > 16u * 1024u * 1024u - b->bytes)
    return 0;
  char *q = realloc(b->data, b->bytes + bytes + 1);
  if (!q)
    return 0;
  b->data = q;
  memcpy(q + b->bytes, p, bytes);
  b->bytes += bytes;
  q[b->bytes] = 0;
  return bytes;
}
static char *post(const char *base, bool responses, json_object *request,
                  long *status) {
  char url[256];
  snprintf(url, sizeof(url), "%s/%s", base,
           responses ? "responses" : "chat/completions");
  CURL *curl = curl_easy_init();
  require(curl != NULL, "curl init");
  body_buffer b = {0};
  struct curl_slist *h =
      curl_slist_append(NULL, "Content-Type: application/json");
  require(h != NULL, "headers");
  curl_easy_setopt(curl, CURLOPT_URL, url);
  curl_easy_setopt(curl, CURLOPT_HTTPHEADER, h);
  curl_easy_setopt(curl, CURLOPT_POSTFIELDS, nb_encoded(request));
  curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS, 5000L);
  curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, collect);
  curl_easy_setopt(curl, CURLOPT_WRITEDATA, &b);
  require(curl_easy_perform(curl) == CURLE_OK, "HTTP transfer");
  curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, status);
  curl_slist_free_all(h);
  curl_easy_cleanup(curl);
  require(b.data != NULL, "response body");
  return b.data;
}
static json_object *request(bool responses, bool stream, const char *input,
                            unsigned budget, const char *choice, bool tools) {
  char raw[4096];
  const char *params =
      "{\"type\":\"object\",\"properties\":{\"path\":{\"type\":\"string\"},"
      "\"offset\":{\"type\":\"integer\"},\"options\":{\"type\":\"object\"}},"
      "\"required\":[\"path\"],\"additionalProperties\":false}";
  char defs[1024];
  snprintf(defs, sizeof(defs),
           responses
               ? "[{\"type\":\"function\",\"name\":\"read\",\"parameters\":%s}]"
               : "[{\"type\":\"function\",\"function\":{\"name\":\"read\","
                 "\"parameters\":%s}}]",
           params);
  snprintf(
      raw, sizeof(raw),
      "{\"model\":\"cpu-test-fixture\",\"%s\":[{\"role\":\"user\",\"content\":"
      "\"%s\"}],\"%s\":%u,\"stream\":%s,\"tools\":%s,\"tool_choice\":\"%s\"}",
      responses ? "input" : "messages", input,
      responses ? "max_output_tokens" : "max_tokens", budget,
      stream ? "true" : "false", tools ? defs : "[]", choice);
  nb_error e = {0};
  json_object *o = nb_parse(raw, strlen(raw), &e);
  require(o != NULL, e.message);
  return o;
}
static void call_valid(json_object *call, bool responses) {
  require(call != NULL, "call absent");
  json_object *fn = responses ? call : nb_get(call, "function");
  require(!strcmp(nb_string(fn, "name"), "read"), "call name");
  require(*nb_string(call, responses ? "call_id" : "id"), "call ID");
  const char *s = nb_string(fn, "arguments");
  nb_error e = {0};
  json_object *args = nb_parse(s, strlen(s), &e);
  require(args != NULL, e.message);
  require(!strcmp(nb_string(args, "path"), "  caffè 🙂.txt  "),
          "string whitespace/UTF-8");
  require(nb_number(args, "offset") == 3 &&
              json_object_get_boolean(nb_get(nb_get(args, "options"), "raw")),
          "typed arguments");
  json_object_put(args);
}
static void valid(char *body, bool responses, bool stream) {
  nb_error e = {0};
  if (!stream) {
    json_object *o = nb_parse(body, strlen(body), &e);
    require(o != NULL, e.message);
    if (responses) {
      json_object *items = nb_get(o, "output");
      require(json_object_array_length(items) == 2 &&
                  !strcmp(nb_string(o, "status"), "completed"),
              "Responses output");
      call_valid(json_object_array_get_idx(items, 1), true);
    } else {
      json_object *choice = json_object_array_get_idx(nb_get(o, "choices"), 0),
                  *m = nb_get(choice, "message"),
                  *calls = nb_get(m, "tool_calls");
      require(!strcmp(nb_string(choice, "finish_reason"), "tool_calls") &&
                  !strcmp(nb_string(m, "content"), "Reading.\n") &&
                  json_object_array_length(calls) == 1,
              "Chat output");
      call_valid(json_object_array_get_idx(calls, 0), false);
    }
    json_object_put(o);
    return;
  }
  unsigned calls = 0, terminals = 0;
  int64_t sequence = 0;
  bool done = false;
  for (char *p = body; *p;) {
    char *end = strchr(p, '\n');
    if (!end)
      end = p + strlen(p);
    size_t n = (size_t)(end - p);
    if (n > 6 && !memcmp(p, "data: ", 6)) {
      if (n == 12 && !memcmp(p + 6, "[DONE]", 6)) {
        require(!responses && !done && terminals == 1, "DONE order");
        done = true;
      } else {
        require(!done, "data after terminal");
        json_object *o = nb_parse(p + 6, n - 6, &e);
        require(o != NULL, e.message);
        if (responses) {
          require(nb_number(o, "sequence_number") == sequence++,
                  "Responses sequence");
          const char *type = nb_string(o, "type");
          if (!strcmp(type, "response.output_item.done")) {
            json_object *item = nb_get(o, "item");
            if (!strcmp(nb_string(item, "type"), "function_call")) {
              call_valid(item, true);
              ++calls;
            }
          }
          if (!strcmp(type, "response.completed"))
            ++terminals;
          require(strcmp(type, "response.failed"), "success became failure");
        } else {
          json_object *a = nb_get(o, "choices");
          if (json_object_array_length(a)) {
            json_object *choice = json_object_array_get_idx(a, 0),
                        *c = nb_get(nb_get(choice, "delta"), "tool_calls");
            if (c) {
              require(json_object_array_length(c) == 1, "tool delta count");
              call_valid(json_object_array_get_idx(c, 0), false);
              ++calls;
            }
            if (!strcmp(nb_string(choice, "finish_reason"), "tool_calls"))
              ++terminals;
          }
        }
        json_object_put(o);
      }
    }
    p = *end ? end + 1 : end;
  }
  require(calls == 1 && terminals == 1 && (responses || done),
          "SSE calls/terminal");
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
  snprintf(health, sizeof(health),
           "http://127.0.0.1:%u/actuator/health/readiness", mp);
  close(a);
  close(b);
  owned = fork();
  require(owned >= 0, "fork");
  if (!owned) {
    setenv("PATH", "/nonexistent-native-feature-test", 1);
    setenv("LC_ALL", "C", 1);
    execl(argv[1], argv[1], "--model", ":fixture:", "--model-id",
          "cpu-test-fixture",
#if defined(TEST_VISION)
          "--model-vision", ":vision-a:",
#endif
#if defined(TEST_MTP)
          "--model-mtp", ":wide-fixture:",
#endif
          "--host", "127.0.0.1", "--port", aps, "--management-port", mps,
          "--context", "1024", "--prefill-chunk", "4", "--max-active", "2",
          "--kv-cache-ram-mb", "0", "--kv-cache-min-tokens", "1",
          "--kv-cache-boundary-trim-tokens", "0",
          "--kv-cache-boundary-align-tokens", "0", "--kv-cache-capture-finish",
          "off", (char *)NULL);
    _exit(127);
  }
  bool ready = false;
  for (unsigned i = 0; i < 500; ++i) {
    int status;
    pid_t r = waitpid(owned, &status, WNOHANG);
    if (r == owned)
      owned = -1;
    require(r == 0, "server exited before readiness");
    nb_error error = {0};
    json_object *o = nb_http_get(health, .25, &error);
    if (o) {
      json_object_put(o);
      ready = true;
      break;
    }
    pause_ms();
  }
  require(ready, "readiness deadline");
  require(curl_global_init(CURL_GLOBAL_DEFAULT) == CURLE_OK,
          "curl global init");
  for (unsigned responses = 0; responses < 2; ++responses)
    for (unsigned stream = 0; stream < 2; ++stream) {
      long status = 0;
      json_object *q = request(responses, stream, "TOOL", 512, "auto", true);
      char *body = post(api, responses, q, &status);
      require(status == 200, "successful status");
      valid(body, responses, stream);
      free(body);
      json_object_put(q);
      const char *inputs[] = {
          "TOOL-TRUNCATED", "TOOL-UNKNOWN", "TOOL-DUPLICATE", "TOOL-JSON-BAD",
          "TOOL",           "TOOL",         "normal",         "TOOL-TWICE"};
      for (unsigned bad = 0; bad < 8; ++bad) {
        q = request(responses, stream, inputs[bad], bad == 4 ? 40 : 512,
                    bad == 5   ? "none"
                    : bad == 6 ? "required"
                               : "auto",
                    true);
        if (bad == 7)
          json_object_object_add(q, "parallel_tool_calls",
                                 json_object_new_boolean(false));
        body = post(api, responses, q, &status);
        require(status == (stream ? 200 : 502), "failed status");
        require(!strstr(body, "function_call_arguments.delta") &&
                    !strstr(body, "\"tool_calls\""),
                "malformed call escaped");
        require(strstr(body, stream ? (responses ? "response.failed"
                                                 : "invalid_tool_output")
                                    : "invalid_tool_output") != NULL,
                "failure projection");
        free(body);
        json_object_put(q);
      }
      /* Full-size confirmed MTP pieces, beyond the old single-token HTTP
       * buffer. */
      q = request(responses, stream, "LONG-A", 32, "auto", false);
      body = post(api, responses, q, &status);
      require(status == 200, "large burst status");
      if (!stream) {
        nb_error e = {0};
        json_object *o = nb_parse(body, strlen(body), &e);
        require(o != NULL, e.message);
        const char *text =
            responses
                ? nb_string(json_object_array_get_idx(
                                nb_get(json_object_array_get_idx(
                                           nb_get(o, "output"), 0),
                                       "content"),
                                0),
                            "text")
                : nb_string(
                      nb_get(json_object_array_get_idx(nb_get(o, "choices"), 0),
                             "message"),
                      "content");
        require(strlen(text) == 8192, "large burst bytes");
        json_object_put(o);
      } else
        require(strlen(body) > 8192, "large burst stream");
      free(body);
      json_object_put(q);
    }
  snprintf(health, sizeof(health), "http://127.0.0.1:%u/actuator/llm", mp);
  nb_error err = {0};
  json_object *snapshot = nb_http_get(health, 1, &err);
  require(snapshot != NULL, err.message);
  require(nb_number(nb_get(snapshot, "scheduler"),
                    "output_validation_errors") == 32,
          "core output error accounting");
  json_object_put(snapshot);
  pid_t pid = owned;
  require(!kill(pid, SIGTERM), "stop");
  int status = 0;
  while (waitpid(pid, &status, 0) < 0)
    require(errno == EINTR, "wait");
  owned = -1;
  require(WIFEXITED(status) && !WEXITSTATUS(status), "server/sanitizer exit");
  curl_global_cleanup();
  puts("Semantic HTTP Chat/Responses JSON/SSE tools and burst bounds: PASS "
       "(NOT-INFERENCE)");
}
