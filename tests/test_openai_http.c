/* SPDX-License-Identifier: MIT */
/* Native protocol/state fixtures. No weights or GPU inference. */
#include "bench_native.h"
#include "lie/tools.h"
#include <arpa/inet.h>
#include <curl/curl.h>
#include <errno.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
static pid_t owned = -1;
static void require(bool ok, const char *why) {
  if (!ok) {
    fprintf(stderr, "OpenAI HTTP: %s\n", why);
    exit(1);
  }
}
static void pause_ms(void) {
  struct timespec t = {0, 10000000};
  nanosleep(&t, NULL);
}
static void cleanup(void) {
  if (owned > 0) {
    kill(owned, SIGTERM);
    int status = 0;
    for (unsigned i = 0; i < 500; ++i) {
      pid_t r = waitpid(owned, &status, WNOHANG);
      if (r == owned) {
        owned = -1;
        require(WIFEXITED(status) && WEXITSTATUS(status) == 0,
                "server clean shutdown");
        return;
      }
      pause_ms();
    }
    kill(owned, SIGKILL);
    waitpid(owned, &status, 0);
    owned = -1;
    require(false, "shutdown deadline");
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
} buffer;
static size_t collect(char *p, size_t s, size_t n, void *arg) {
  buffer *b = arg;
  if (s && n > SIZE_MAX / s)
    return 0;
  size_t bytes = s * n;
  if (bytes > 32u * 1024u * 1024u - b->bytes)
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
static char *transfer(const char *base, const char *path, const char *method,
                      const char *body, long expected) {
  char url[512];
  snprintf(url, sizeof(url), "%s%s", base, path);
  CURL *curl = curl_easy_init();
  require(curl != NULL, "curl");
  buffer b = {0};
  struct curl_slist *headers =
      curl_slist_append(NULL, "Content-Type: application/json");
  curl_easy_setopt(curl, CURLOPT_URL, url);
  curl_easy_setopt(curl, CURLOPT_CUSTOMREQUEST, method);
  curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
  curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS, 10000L);
  curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, collect);
  curl_easy_setopt(curl, CURLOPT_WRITEDATA, &b);
  if (body)
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, body);
  require(curl_easy_perform(curl) == CURLE_OK, "transfer");
  long status = 0;
  curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &status);
  curl_slist_free_all(headers);
  curl_easy_cleanup(curl);
  if (status != expected)
    fprintf(stderr, "%s %s: %ld %s\n", method, path, status,
            b.data ? b.data : "");
  require(status == expected && b.data, "HTTP status/body");
  return b.data;
}
static json_object *field(json_object *o, const char *name) {
  json_object *v = NULL;
  json_object_object_get_ex(o, name, &v);
  return v;
}
static json_object *json_transfer(const char *base, const char *path,
                                  const char *method, const char *body,
                                  long status) {
  char *text = transfer(base, path, method, body, status);
  json_object *j = json_tokener_parse(text);
  if (!j)
    fprintf(stderr, "Invalid JSON: %s\n", text);
  free(text);
  require(j != NULL, "JSON response");
  return j;
}
static json_object *chat(const char *extra) {
  char body[8192];
  snprintf(body, sizeof(body),
           "{\"model\":\"cpu-test-fixture\",\"messages\":[{\"role\":\"user\","
           "\"content\":\"ok\"}]%s}",
           extra);
  json_object *j = json_tokener_parse(body);
  require(j != NULL, "request JSON");
  return j;
}
static void automatic_output_http(const char *api) {
  /* Synthetic non-EOS row proves the omitted budget exceeds the old128 cap. */
  const char *long_requests[] = {
      "{\"model\":\"cpu-test-fixture\",\"messages\":[{\"role\":\"user\",\"content\":\"LONG\"}]}",
      "{\"model\":\"cpu-test-fixture\",\"input\":\"LONG\",\"store\":false}"};
  const char *paths[] = {"/chat/completions", "/responses"};
  const char *counts[] = {"completion_tokens", "output_tokens"};
  for (unsigned api_index=0;api_index<2;++api_index) {
    json_object *j=json_transfer(api,paths[api_index],"POST",long_requests[api_index],200);
    require(json_object_get_int(field(field(j,"usage"),counts[api_index]))==2044,
            "omitted output limit uses available context past128");
    require(json_object_get_int(api_index ? field(j,"max_output_tokens") :
                               field(field(j,"lie_timings"),"output_token_limit"))==2044,
            "resolved output budget is observable");
    json_object_put(j);
  }
  const char *near_requests[] = {
      "{\"model\":\"cpu-test-fixture\",\"messages\":[{\"role\":\"user\",\"content\":\"FIXTURE-TOKENS:2045\\n\"}],\"max_completion_tokens\":null,\"stream\":true,\"stream_options\":{\"include_usage\":true}}",
      "{\"model\":\"cpu-test-fixture\",\"input\":\"FIXTURE-TOKENS:2045\\n\",\"max_output_tokens\":null,\"stream\":true,\"store\":false}"};
  for(unsigned api_index=0;api_index<2;++api_index) {
    char *stream=transfer(api,paths[api_index],"POST",near_requests[api_index],200);
    require(strstr(stream,api_index?"\"max_output_tokens\":3":"\"output_token_limit\":3")!=NULL,
            "null budget uses three remaining tokens");
    require(strstr(stream,api_index?"\"output_tokens\":3":"\"completion_tokens\":3")!=NULL,
            "automatic SSE reports exact output count");
    free(stream);
  }
  json_object *j=json_transfer(api,"/responses","POST",
      "{\"model\":\"cpu-test-fixture\",\"input\":\"ok\",\"max_output_tokens\":null}",200);
  char path[256];snprintf(path,sizeof(path),"/responses/%s",json_object_get_string(field(j,"id")));
  require(json_object_get_int(field(field(j,"usage"),"output_tokens"))==8,
          "auto stored response preserves natural EOS");
  json_object_put(j);
  j=json_transfer(api,path,"GET",NULL,200);
  require(json_object_get_int(field(j,"max_output_tokens"))==2044,
          "stored replay retains resolved output budget");
  json_object_put(j);j=json_transfer(api,path,"DELETE",NULL,200);json_object_put(j);
  j=json_transfer(api,"/chat/completions","POST",
      "{\"model\":\"cpu-test-fixture\",\"messages\":[{\"role\":\"user\",\"content\":\"FIXTURE-TOKENS:2048\\n\"}]}",400);
  json_object_put(j);
  j=json_transfer(api,"/chat/completions","POST",
      "{\"model\":\"cpu-test-fixture\",\"messages\":[{\"role\":\"user\",\"content\":\"FIXTURE-TOKENS:2045\\n\"}],\"max_tokens\":4}",400);
  json_object_put(j);
}
static size_t abandon_collect(char *p, size_t s, size_t n, void *arg) {
  size_t bytes = collect(p, s, n, arg);
  buffer *b = arg;
  return bytes && strstr(b->data, "event: response.output_text.delta") ? 0
                                                                       : bytes;
}
static char *abandon_background_stream(const char *base) {
  char url[512];
  snprintf(url, sizeof(url), "%s/responses", base);
  CURL *curl = curl_easy_init();
  require(curl != NULL, "abort curl");
  struct curl_slist *headers =
      curl_slist_append(NULL, "Content-Type: application/json");
  buffer b = {0};
  curl_easy_setopt(curl, CURLOPT_URL, url);
  curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
  curl_easy_setopt(
      curl, CURLOPT_POSTFIELDS,
      "{\"model\":\"cpu-test-fixture\",\"input\":\"SLOW-DECODE\",\"max_output_"
      "tokens\":12,\"background\":true,\"stream\":true}");
  curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS, 10000L);
  curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, abandon_collect);
  curl_easy_setopt(curl, CURLOPT_WRITEDATA, &b);
  require(curl_easy_perform(curl) == CURLE_WRITE_ERROR,
          "intentional creating stream disconnect");
  curl_slist_free_all(headers);
  curl_easy_cleanup(curl);
  const char *data = b.data ? strstr(b.data, "data: ") : NULL;
  require(data != NULL, "abandoned first event");
  const char *p = data + 6, *end = strstr(p, "\n\n");
  require(end != NULL, "abandoned event boundary");
  char *raw = strndup(p, (size_t)(end - p));
  json_object *j = json_tokener_parse(raw);
  free(raw);
  require(j != NULL, "abandoned event JSON");
  const char *identity =
      json_object_get_string(field(field(j, "response"), "id"));
  require(identity != NULL, "abandoned event identity");
  char *id = strdup(identity);
  json_object_put(j);
  free(b.data);
  require(id != NULL, "abandoned response id");
  return id;
}
static void stream_choices(const char *text) {
  unsigned finishes = 0, usage = 0, done = 0;
  bool indexes[3] = {0};
  const char *p = text;
  while ((p = strstr(p, "data: "))) {
    p += 6;
    const char *end = strstr(p, "\n\n");
    require(end != NULL, "SSE boundary");
    if ((size_t)(end - p) == 6 && !memcmp(p, "[DONE]", 6)) {
      ++done;
      p = end + 2;
      continue;
    }
    char *raw = strndup(p, (size_t)(end - p));
    json_object *j = json_tokener_parse(raw);
    free(raw);
    require(j != NULL, "SSE JSON");
    json_object *choices = field(j, "choices");
    if (!json_object_array_length(choices))
      ++usage;
    else {
      json_object *c = json_object_array_get_idx(choices, 0);
      int index = json_object_get_int(field(c, "index"));
      require(index >= 0 && index < 3, "SSE choice index");
      indexes[index] = true;
      if (field(c, "finish_reason"))
        ++finishes;
    }
    json_object_put(j);
    p = end + 2;
  }
  require(finishes == 3 && usage == 1 && done == 1 && indexes[0] &&
              indexes[1] && indexes[2],
          "complete multi-choice SSE");
}
static void sampling_filters_http(const char *api) {
  const char *paths[] = {"/chat/completions", "/responses"};
  const char *prefixes[] = {
      "{\"model\":\"cpu-test-fixture\",\"messages\":[{\"role\":\"user\",\"content\":\"ok\"}],\"max_tokens\":16",
      "{\"model\":\"cpu-test-fixture\",\"input\":\"ok\",\"max_output_tokens\":16"
  };
  const char *bad[] = {",\"top_k\":-1", ",\"top_k\":2147483648",
                      ",\"top_k\":18446744073709551615", ",\"top_k\":1.0",
                      ",\"top_k\":true", ",\"top_k\":null",
                      ",\"min_p\":-0.01", ",\"min_p\":1.01",
                      ",\"min_p\":true", ",\"min_p\":null"};
  for (size_t endpoint = 0; endpoint < 2; ++endpoint) {
    char body[1024];
    snprintf(body, sizeof(body), "%s,\"top_k\":5,\"min_p\":0.05}", prefixes[endpoint]);
    json_object *j = json_transfer(api, paths[endpoint], "POST", body, 200);
    if (endpoint == 1) {
      require(json_object_get_int(field(j, "top_k")) == 5 &&
                  json_object_get_double(field(j, "min_p")) == .05,
              "response sampling filter echo");
      char retained[256];
      snprintf(retained, sizeof(retained), "/responses/%s", json_object_get_string(field(j, "id")));
      json_object *stored = json_transfer(api, retained, "GET", NULL, 200);
      require(json_object_get_int(field(stored, "top_k")) == 5 &&
                  json_object_get_double(field(stored, "min_p")) == .05,
              "stored response sampling filters");
      json_object_put(stored);
      stored = json_transfer(api, retained, "DELETE", NULL, 200);
      json_object_put(stored);
    }
    json_object_put(j);
    for (size_t i = 0; i < sizeof(bad)/sizeof(*bad); ++i) {
      snprintf(body, sizeof(body), "%s%s}", prefixes[endpoint], bad[i]);
      j = json_transfer(api, paths[endpoint], "POST", body, 400);
      require(field(j, "error") != NULL, "invalid filter error object");
      json_object_put(j);
    }
  }
}
static uint64_t response_sequences(const char *text, int64_t after) {
  const char *p = text;
  uint64_t last = 0;
  bool any = false, terminal = false;
  while ((p = strstr(p, "data: "))) {
    p += 6;
    const char *end = strstr(p, "\n\n");
    require(end != NULL, "response frame");
    char *raw = strndup(p, (size_t)(end - p));
    json_object *j = json_tokener_parse(raw);
    free(raw);
    require(j != NULL, "response event JSON");
    int64_t sequence = json_object_get_int64(field(j, "sequence_number"));
    require(sequence > after && (!any || sequence == (int64_t)last + 1),
            "resume sequence monotonic/contiguous");
    if (!any)
      require(sequence == after + 1, "resume first event");
    any = true;
    last = (uint64_t)sequence;
    if (lie_json_literal(field(j, "type"), "response.completed") ||
        lie_json_literal(field(j, "type"), "response.incomplete"))
      terminal = true;
    json_object_put(j);
    p = end + 2;
  }
  require(any && terminal && !strstr(text, "[DONE]"),
          "response replay terminal");
  return last;
}
int main(int argc, char **argv) {
  require(argc == 2 || (argc == 3 && !strcmp(argv[2], "mtp13")),
          "server path and optional mtp13");
  atexit(cleanup);
  int a, b;
  unsigned ap = reserve(&a), mp = reserve(&b);
  char api[128], health[128], aps[16], mps[16];
  snprintf(api, sizeof(api), "http://127.0.0.1:%u/v1", ap);
  snprintf(health, sizeof(health),
           "http://127.0.0.1:%u/actuator/health/readiness", mp);
  snprintf(aps, sizeof(aps), "%u", ap);
  snprintf(mps, sizeof(mps), "%u", mp);
  close(a);
  close(b);
  owned = fork();
  require(owned >= 0, "fork");
  if (!owned) {
    setenv("PATH", "/nonexistent-native-openai-test", 1);
    if (argc == 3) {
      execl(argv[1], argv[1], "--model", ":fixture:", "--model-mtp",
            ":wide-fixture:", "--model-id", "cpu-test-fixture", "--host",
            "127.0.0.1", "--port", aps, "--management-port", mps, "--context",
            "2048", "--prefill-chunk", "16", "--max-active", "8",
            "--kv-cache-ram-mb", "0", (char *)NULL);
      _exit(127);
    }
    execl(argv[1], argv[1], "--model", ":fixture:", "--model-id",
          "cpu-test-fixture", "--host", "127.0.0.1", "--port", aps,
          "--management-port", mps, "--context", "2048", "--prefill-chunk",
          "16", "--max-active", "8", "--kv-cache-ram-mb", "0", (char *)NULL);
    _exit(127);
  }
  bool ready = false;
  for (unsigned i = 0; i < 500; ++i) {
    nb_error error = {0};
    json_object *j = nb_http_get(health, .1, &error);
    if (j) {
      json_object_put(j);
      ready = true;
      break;
    }
    pause_ms();
  }
  require(ready, "readiness");
  automatic_output_http(api);
  sampling_filters_http(api);
  json_object *j =
      json_transfer(api, "/models/cpu-test-fixture", "GET", NULL, 200);
  require(lie_json_literal(field(j, "object"), "model"), "model detail");
  require(json_object_get_int(field(j,"context_length"))==2048&&
              json_object_get_int(field(j,"max_output_tokens"))==LIE_CORE_MAX_OUTPUT,
          "model detail advertises actual context and output ceiling");
  json_object_put(j);
  j=json_transfer(api,"/models","GET",NULL,200);
  json_object *listed=json_object_array_get_idx(field(j,"data"),0);
  require(json_object_get_int(field(listed,"context_length"))==2048&&
              json_object_get_int(field(listed,"max_output_tokens"))==LIE_CORE_MAX_OUTPUT,
          "model list supports automatic client discovery");
  json_object_put(j);
  char *abandoned_id = abandon_background_stream(api), abandoned_path[256];
  snprintf(abandoned_path, sizeof(abandoned_path), "/responses/%s?stream=true",
           abandoned_id);
  char *abandoned_stream = transfer(api, abandoned_path, "GET", NULL, 200);
  response_sequences(abandoned_stream, -1);
  free(abandoned_stream);
  snprintf(abandoned_path, sizeof(abandoned_path), "/responses/%s",
           abandoned_id);
  j = json_transfer(api, abandoned_path, "GET", NULL, 200);
  require(json_object_get_int(field(field(j, "usage"), "output_tokens")) == 12,
          "background owns credits after creating disconnect");
  json_object_put(j);
  free(abandoned_id);
  json_object *r = chat(",\"stop\":\"🙂\"");
  j = json_transfer(api, "/chat/completions", "POST", nb_encoded(r), 200);
  json_object *message =
      field(json_object_array_get_idx(field(j, "choices"), 0), "message");
  require(
      !strcmp(json_object_get_string(field(message, "content")), "fixture: "),
      "stop spans tokens");
  json_object_put(j);
  json_object_put(r);
  r = chat(",\"stop\":\"🙂\",\"logprobs\":true");
  j = json_transfer(api, "/chat/completions", "POST", nb_encoded(r), 200);
  require(
      json_object_array_length(field(
          field(json_object_array_get_idx(field(j, "choices"), 0), "logprobs"),
          "content")) == 2,
      "stopped token logprobs hidden");
  json_object_put(j);
  json_object_put(r);
  r = chat(",\"n\":3,\"logprobs\":true,\"top_logprobs\":2,\"store\":true,"
           "\"metadata\":{\"task\":\"multi\"},\"service_tier\":\"auto\"");
  j = json_transfer(api, "/chat/completions", "POST", nb_encoded(r), 200);
  require(json_object_array_length(field(j, "choices")) == 3, "three choices");
  require(lie_json_literal(field(j, "service_tier"), "default"),
          "actual local service tier");
  require(json_object_get_int(field(field(j, "usage"), "completion_tokens")) ==
              24,
          "aggregate usage");
  for (unsigned i = 0; i < 3; ++i) {
    json_object *c = json_object_array_get_idx(field(j, "choices"), i),
                *logs = field(field(c, "logprobs"), "content");
    require(json_object_get_int(field(c, "index")) == (int)i &&
                json_object_array_length(logs) == 8,
            "choice logprobs");
    require(json_object_array_length(
                field(json_object_array_get_idx(logs, 0), "top_logprobs")) == 2,
            "top logprobs");
  }
  char *chat_id = strdup(json_object_get_string(field(j, "id"))), path[256];
  require(chat_id != NULL, "chat id");
  json_object_put(j);
  json_object_put(r);
  snprintf(path, sizeof(path), "/chat/completions/%s", chat_id);
  j = json_transfer(api, path, "GET", NULL, 200);
  require(json_object_array_length(field(j, "choices")) == 3, "stored choices");
  json_object_put(j);
  j = json_transfer(api, path, "POST", "{\"metadata\":{\"task\":\"updated\"}}",
                    200);
  require(!strcmp(json_object_get_string(field(field(j, "metadata"), "task")),
                  "updated"),
          "metadata update");
  json_object_put(j);
  j = json_transfer(
      api,
      "/chat/"
      "completions?model=cpu-test-fixture&metadata%5Btask%5D=updated&limit=1",
      "GET", NULL, 200);
  require(
      json_object_array_length(field(j, "data")) == 1 &&
          !strcmp(json_object_get_string(field(
                      json_object_array_get_idx(field(j, "data"), 0), "id")),
                  chat_id),
      "filtered completion list");
  json_object_put(j);
  j = json_transfer(api, "/chat/completions?model=missing", "GET", NULL, 200);
  require(!json_object_array_length(field(j, "data")), "empty model filter");
  json_object_put(j);
  r = chat(
      ",\"n\":3,\"stream\":true,\"stream_options\":{\"include_usage\":true}");
  char *stream = transfer(api, "/chat/completions", "POST", nb_encoded(r), 200);
  stream_choices(stream);
  free(stream);
  json_object_put(r);
  r = chat(",\"logit_bias\":{\"193\":100}");
  j = json_transfer(api, "/chat/completions", "POST", nb_encoded(r), 200);
  message = field(json_object_array_get_idx(field(j, "choices"), 0), "message");
  require(
      !strcmp(json_object_get_string(field(message, "content")), "AAAAAAAA"),
      "fixture bias applied");
  json_object_put(j);
  json_object_put(r);
  r = chat(",\"tools\":[{\"type\":\"function\",\"function\":{\"name\":\"read\","
           "\"strict\":true,\"parameters\":{\"type\":\"object\",\"properties\":"
           "{\"path\":{\"type\":\"string\"}},\"required\":[\"path\"],"
           "\"additionalProperties\":false}}}],\"tool_choice\":\"required\"");
  j = json_transfer(api, "/chat/completions", "POST", nb_encoded(r), 200);
  message = field(json_object_array_get_idx(field(j, "choices"), 0), "message");
  json_object *tool_call =
      json_object_array_get_idx(field(message, "tool_calls"), 0);
  require(
      lie_json_literal(field(field(tool_call, "function"), "name"), "read") &&
          strstr(json_object_get_string(
                     field(field(tool_call, "function"), "arguments")),
                 "fixture.txt"),
      "strict canonical function call");
  json_object_put(j);
  json_object_put(r);
  const char *history_tools =
      "[{\"type\":\"function\",\"name\":\"read\",\"parameters\":{\"type\":"
      "\"object\",\"properties\":{\"path\":{\"type\":\"string\"},\"offset\":{"
      "\"type\":\"integer\"},\"options\":{\"type\":\"object\"}},\"required\":["
      "\"path\"],\"additionalProperties\":false}}]";
  char tool_body[2048];
  snprintf(tool_body, sizeof(tool_body),
           "{\"model\":\"cpu-test-fixture\",\"input\":\"TOOL\",\"tools\":%s,"
           "\"max_output_tokens\":256}",
           history_tools);
  j = json_transfer(api, "/responses", "POST", tool_body, 200);
  json_object *function_item = NULL;
  for (size_t i = 0; i < json_object_array_length(field(j, "output")); ++i) {
    json_object *item = json_object_array_get_idx(field(j, "output"), i);
    if (lie_json_literal(field(item, "type"), "function_call"))
      function_item = item;
  }
  require(function_item != NULL, "stored function output");
  char *function_parent = strdup(json_object_get_string(field(j, "id"))),
       *call_id =
           strdup(json_object_get_string(field(function_item, "call_id")));
  json_object_put(j);
  snprintf(path, sizeof(path), "/responses/%s?stream=true&starting_after=1",
           function_parent);
  stream = transfer(api, path, "GET", NULL, 200);
  response_sequences(stream, 1);
  require(strstr(stream, "response.function_call_arguments.delta") != NULL,
          "function replay arguments");
  free(stream);
  snprintf(tool_body, sizeof(tool_body),
           "{\"model\":\"cpu-test-fixture\",\"previous_response_id\":\"%s\","
           "\"tools\":%s,\"input\":[{\"type\":\"function_call_output\",\"call_"
           "id\":\"%s\",\"output\":\"OK\"}]}",
           function_parent, history_tools, call_id);
  j = json_transfer(api, "/responses", "POST", tool_body, 200);
  require(lie_json_literal(field(j, "status"), "completed"),
          "stored correlated function result");
  json_object_put(j);
  free(function_parent);
  free(call_id);
  const char *structured =
      "{\"model\":\"cpu-test-fixture\",\"input\":\"ok\",\"text\":{\"format\":{"
      "\"type\":\"json_schema\",\"name\":\"answer\",\"strict\":true,\"schema\":"
      "{\"type\":\"object\",\"properties\":{\"ok\":{\"type\":\"boolean\"}},"
      "\"required\":[\"ok\"],\"additionalProperties\":false}}}}";
  j = json_transfer(api, "/responses", "POST", structured, 200);
  require(lie_json_literal(field(j, "status"), "completed") &&
              json_object_get_boolean(field(j, "store")),
          "stored structured response");
  json_object *part = json_object_array_get_idx(
      field(json_object_array_get_idx(field(j, "output"), 0), "content"), 0);
  require(!strcmp(json_object_get_string(field(part, "text")), "{\"ok\":true}"),
          "structured fixture output");
  char *id = strdup(json_object_get_string(field(j, "id")));
  json_object_put(j);
  require(id != NULL, "response id");
  snprintf(path, sizeof(path), "/responses/%s", id);
  j = json_transfer(api, path, "GET", NULL, 200);
  require(lie_json_literal(field(j, "status"), "completed"),
          "response retrieval");
  json_object_put(j);
  snprintf(path, sizeof(path), "/responses/%s?stream=true", id);
  stream = transfer(api, path, "GET", NULL, 200);
  uint64_t final_sequence = response_sequences(stream, -1);
  free(stream);
  snprintf(path, sizeof(path), "/responses/%s?stream=true&starting_after=3",
           id);
  stream = transfer(api, path, "GET", NULL, 200);
  require(response_sequences(stream, 3) == final_sequence,
          "same replay terminal");
  free(stream);
  snprintf(path, sizeof(path), "/responses/%s?starting_after=3", id);
  j = json_transfer(api, path, "GET", NULL, 400);
  json_object_put(j);
  j = json_transfer(
      api, "/responses", "POST",
      "{\"model\":\"cpu-test-fixture\",\"input\":\"SLOW-DECODE\","
      "\"background\":true,\"top_logprobs\":2,\"max_output_tokens\":8}",
      200);
  char *live_id = strdup(json_object_get_string(field(j, "id")));
  json_object_put(j);
  snprintf(path, sizeof(path), "/responses/%s?stream=true", live_id);
  stream = transfer(api, path, "GET", NULL, 200);
  response_sequences(stream, -1);
  free(stream);
  snprintf(path, sizeof(path), "/responses/%s", live_id);
  j = json_transfer(api, path, "GET", NULL, 200);
  part = json_object_array_get_idx(
      field(json_object_array_get_idx(field(j, "output"), 0), "content"), 0);
  require(json_object_array_length(field(part, "logprobs")) == 8,
          "stored logprob witnesses");
  json_object_put(j);
  free(live_id);
  r = json_object_new_object();
  json_object_object_add(r, "model",
                         json_object_new_string("cpu-test-fixture"));
  json_object_object_add(r, "instructions",
                         json_object_new_string("TRUNCATION-FIXTURE"));
  json_object *inputs = json_object_new_array(),
              *old_msg = json_object_new_object(),
              *new_msg = json_object_new_object();
  char old_text[2101];
  memset(old_text, 'x', 2100);
  old_text[2100] = 0;
  json_object_object_add(old_msg, "role", json_object_new_string("user"));
  json_object_object_add(old_msg, "content", json_object_new_string(old_text));
  json_object_array_add(inputs, old_msg);
  json_object_object_add(new_msg, "role", json_object_new_string("user"));
  json_object_object_add(new_msg, "content", json_object_new_string("ok"));
  json_object_array_add(inputs, new_msg);
  json_object_object_add(r, "input", inputs);
  json_object_object_add(r, "store", json_object_new_boolean(false));
  j = json_transfer(api, "/responses", "POST", nb_encoded(r), 400);
  json_object_put(j);
  json_object_object_add(r, "truncation", json_object_new_string("auto"));
  j = json_transfer(api, "/responses", "POST", nb_encoded(r), 200);
  require(json_object_get_int(field(field(j, "usage"), "input_tokens")) == 6,
          "automatic context truncation");
  json_object_put(j);
  json_object_put(r);
  char body[1024];
  snprintf(body, sizeof(body),
           "{\"model\":\"cpu-test-fixture\",\"previous_response_id\":\"%s\","
           "\"input\":\"continue\",\"instructions\":\"new instructions\"}",
           id);
  j = json_transfer(api, "/responses", "POST", body, 200);
  require(!strcmp(json_object_get_string(field(j, "previous_response_id")), id),
          "history correlation");
  char *next_id = strdup(json_object_get_string(field(j, "id")));
  json_object_put(j);
  snprintf(path, sizeof(path), "/responses/%s/input_items", next_id);
  j = json_transfer(api, path, "GET", NULL, 200);
  require(json_object_array_length(field(j, "data")) >= 3, "effective history");
  json_object_put(j);
  free(next_id);
  j = json_transfer(api, "/responses", "POST",
                    "{\"model\":\"cpu-test-fixture\",\"input\":\"SLOW-DECODE\","
                    "\"max_output_tokens\":100,\"background\":true}",
                    200);
  require(json_object_get_boolean(field(j, "background")),
          "background enabled");
  char *bg_id = strdup(json_object_get_string(field(j, "id")));
  json_object_put(j);
  snprintf(path, sizeof(path), "/responses/%s/cancel", bg_id);
  j = json_transfer(api, path, "POST", "{}", 200);
  require(lie_json_literal(field(j, "status"), "cancelled"),
          "cancelled response");
  json_object_put(j);
  j = json_transfer(api, path, "POST", "{}", 200);
  require(lie_json_literal(field(j, "status"), "cancelled"),
          "idempotent cancellation");
  json_object_put(j);
  free(bg_id);
  snprintf(path, sizeof(path), "/responses/%s", id);
  j = json_transfer(api, path, "DELETE", NULL, 200);
  require(json_object_get_boolean(field(j, "deleted")), "delete response");
  json_object_put(j);
  j = json_transfer(api, path, "GET", NULL, 404);
  json_object_put(j);
  free(id);
  free(chat_id);
  cleanup();
  puts("OpenAI generation/state HTTP fixtures: PASS (NOT-INFERENCE)");
  return 0;
}
