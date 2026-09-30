/* SPDX-License-Identifier: MIT */
#include "lie/metrics.h"
#include <json-c/json.h>
#include <llhttp.h>
#include <uv.h>
#include <errno.h>
#include <locale.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define JSON_TYPE "application/vnd.spring-boot.actuator.v3+json"
#define PROM_TYPE "text/plain; version=0.0.4; charset=utf-8"
#define MAX_RESPONSE (1024 * 1024)
#define MAX_BODY (64 * 1024)
#define MAX_HEADERS (16 * 1024)
#define MAX_CONNECTIONS 64
#define TIMEOUT_NS UINT64_C(5000000000)

typedef struct server server;
typedef struct connection connection;
typedef struct { uv_tcp_t tcp; server *owner; bool management; } listener;
struct connection {
    uv_tcp_t tcp;
    uv_write_t write;
    llhttp_t parser;
    server *owner;
    connection *next;
    char url[2048]; size_t url_size, headers_size, body_size, wire_size;
    uint64_t started;
    char *response;
    bool management, responded;
};
struct server {
    uv_loop_t loop;
    listener api, management;
    uv_timer_t timer;
    uv_signal_t interrupt, terminate;
    llhttp_settings_t settings;
    connection *connections;
    size_t active;
    bool stopping;
    lie_metrics *metrics;
    lie_meter uptime, ready, connections_meter, rejected, tokens, http[3][3];
    uint64_t started;
    char instance[64];
};
static void close_connection(connection *c);
static char *json_text(json_object *j) {
    char *s = strdup(json_object_to_json_string_ext(j, JSON_C_TO_STRING_PLAIN));
    json_object_put(j); return s;
}
static const char *reason(int code) {
    switch (code) {
        case 200: return "OK"; case 400: return "Bad Request";
        case 404: return "Not Found"; case 405: return "Method Not Allowed";
        case 413: return "Content Too Large"; case 431: return "Request Header Fields Too Large";
        case 500: return "Internal Server Error"; case 503: return "Service Unavailable";
        default: return "Error";
    }
}
static void wrote(uv_write_t *w, int status) {
    (void)status;
    connection *c = w->data; free(c->response); c->response = NULL; close_connection(c);
}
static void respond(connection *c, int code, const char *type, const char *body) {
    if (c->responded || uv_is_closing((uv_handle_t *)&c->tcp)) return;
    c->responded = true; uv_read_stop((uv_stream_t *)&c->tcp);
    if (!body || strlen(body) > MAX_RESPONSE) { code = 500; type = "application/json"; body = "{\"error\":\"response_unavailable\"}"; }
    size_t length = strlen(body), cap = length + 512;
    c->response = malloc(cap);
    if (!c->response) { close_connection(c); return; }
    int h = snprintf(c->response, cap,
        "HTTP/1.1 %d %s\r\nContent-Type: %s\r\nContent-Length: %zu\r\nConnection: close\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nContent-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'\r\n\r\n",
        code, reason(code), type, length);
    if (h < 0 || (size_t)h >= cap || length >= cap - (size_t)h) { free(c->response); c->response = NULL; close_connection(c); return; }
    memcpy(c->response + h, body, length);
    size_t method = c->parser.method == HTTP_GET ? 0 : c->parser.method == HTTP_POST ? 1 : 2;
    size_t status = code < 400 ? 0 : code < 500 ? 1 : 2;
    (void)lie_timer_record(c->owner->metrics, c->owner->http[method][status],
                           (double)(lie_monotonic_ns() - c->started) / 1e9);
    uv_buf_t b = uv_buf_init(c->response, (unsigned)((size_t)h + length));
    c->write.data = c;
    int rc = uv_write(&c->write, (uv_stream_t *)&c->tcp, &b, 1, wrote);
    if (rc) { free(c->response); c->response = NULL; close_connection(c); }
}
static void error_response(connection *c, int code, const char *message) {
    json_object *j = json_object_new_object(), *e = json_object_new_object();
    json_object_object_add(e, "code", json_object_new_string(message));
    json_object_object_add(e, "message", json_object_new_string(reason(code)));
    json_object_object_add(j, "error", e);
    char *body = json_text(j); respond(c, code, "application/json", body); free(body);
}
static int hex(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}
static bool decode_component(char *s) {
    char *to = s;
    for (char *p = s; *p; ++p) {
        if (*p == '%') {
            if (!p[1] || !p[2] || hex(p[1]) < 0 || hex(p[2]) < 0) return false;
            char ch = (char)((hex(p[1]) << 4) | hex(p[2]));
            if (!ch || (unsigned char)ch < 32 || ch == 127) return false;
            *to++ = ch; p += 2;
        } else { if ((unsigned char)*p < 32) return false; *to++ = *p == '+' ? ' ' : *p; }
    }
    *to = 0; return true;
}
static bool query_tags(char *query, lie_tag *filters, size_t *count) {
    *count = 0;
    if (!query) return true;
    if (!*query) return false;
    char *p = query;
    while (p) {
        char *end = strchr(p, '&'); if (end) *end++ = 0;
        if (strncmp(p, "tag=", 4) || *count == LIE_MAX_TAGS || !decode_component(p + 4)) return false;
        char *colon = strchr(p + 4, ':'); if (!colon || colon == p + 4) return false;
        *colon = 0; filters[*count] = (lie_tag){p + 4, colon + 1}; ++*count;
        p = end;
    }
    return true;
}
static char *discovery(void) {
    const char *names[] = {"self", "health", "liveness", "readiness", "info", "metrics", "metrics-requiredMetricName", "prometheus", "llm", "monitor"};
    const char *paths[] = {"/actuator", "/actuator/health", "/actuator/health/liveness", "/actuator/health/readiness", "/actuator/info", "/actuator/metrics", "/actuator/metrics/{requiredMetricName}", "/actuator/prometheus", "/actuator/llm", "/monitor"};
    json_object *j = json_object_new_object(), *links = json_object_new_object();
    for (size_t i = 0; i < sizeof(names) / sizeof(*names); ++i) {
        json_object *link = json_object_new_object();
        json_object_object_add(link, "href", json_object_new_string(paths[i]));
        json_object_object_add(link, "templated", json_object_new_boolean(i == 6));
        json_object_object_add(links, names[i], link);
    }
    json_object_object_add(j, "_links", links); return json_text(j);
}
static const char PAGE[] =
    "<!doctype html><html lang=en-US><meta charset=utf-8><title>Synapse LIE</title>"
    "<style>body{font:16px monospace;background:#171b24;color:#d8e6ef;margin:2em}pre{white-space:pre-wrap}</style>"
    "<h1>Synapse LIE: development diagnostics</h1><p>No inference backend connected. Unknown is not zero.</p>"
    "<pre id=view>Connecting...</pre><script>const history=[];async function poll(){try{"
    "const r=await fetch('/actuator/llm');if(!r.ok)throw Error('HTTP '+r.status);const s=await r.json();"
    "history.push({at:new Date().toISOString(),state:s});if(history.length>30)history.shift();"
    "document.getElementById('view').textContent=JSON.stringify(history[history.length-1],null,2);"
    "}catch(e){document.getElementById('view').textContent='Unavailable: '+e.message;}setTimeout(poll,2000);}poll();</script></html>";
static void route(connection *c) {
    server *s = c->owner; char *query = strchr(c->url, '?'); if (query) *query++ = 0;
    if (!c->management) {
        if (!strcmp(c->url, "/v1/models") && c->parser.method == HTTP_GET && !query) {
            respond(c, 200, "application/json", "{\"object\":\"list\",\"data\":[]}"); return;
        }
        if (!strcmp(c->url, "/v1/chat/completions") && c->parser.method == HTTP_POST && !query) {
            (void)lie_counter_add(s->metrics, s->rejected, 1);
            error_response(c, 503, "backend_unavailable"); return;
        }
        error_response(c, 404, "not_found"); return;
    }
    if (c->parser.method != HTTP_GET) { error_response(c, 405, "method_not_allowed"); return; }
    char *body = NULL;
    if (!strncmp(c->url, "/actuator/metrics/", 18)) {
        lie_tag filters[LIE_MAX_TAGS]; size_t count;
        if (!decode_component(c->url + 18) || !query_tags(query, filters, &count)) { error_response(c, 400, "invalid_filter"); return; }
        lie_metric_status st = lie_metrics_detail(s->metrics, c->url + 18, filters, count, &body);
        if (st != LIE_METRIC_OK) { error_response(c, st == LIE_METRIC_NOT_FOUND ? 404 : st == LIE_METRIC_INVALID ? 400 : 500, "metric_unavailable"); return; }
    } else {
        if (query) { error_response(c, 400, "unexpected_query"); return; }
        if (!strcmp(c->url, "/actuator")) body = discovery();
        else if (!strcmp(c->url, "/actuator/metrics")) body = lie_metrics_names(s->metrics);
        else if (!strcmp(c->url, "/actuator/prometheus")) {
            body = lie_metrics_prometheus(s->metrics); respond(c, 200, PROM_TYPE, body); free(body); return;
        } else if (!strcmp(c->url, "/monitor")) { respond(c, 200, "text/html; charset=utf-8", PAGE); return; }
        else if (!strcmp(c->url, "/actuator/health/liveness")) {
            respond(c, 200, JSON_TYPE, "{\"status\":\"UP\"}"); return;
        } else if (!strcmp(c->url, "/actuator/health") || !strcmp(c->url, "/actuator/health/readiness")) {
            respond(c, 503, JSON_TYPE, "{\"status\":\"OUT_OF_SERVICE\",\"components\":{\"model\":{\"status\":\"UNKNOWN\",\"details\":{\"state\":\"NOT_LOADED\"}}}}"); return;
        } else if (!strcmp(c->url, "/actuator/info")) {
            json_object *j = json_object_new_object();
            json_object_object_add(j, "application", json_object_new_string("synapse-lie"));
            json_object_object_add(j, "version", json_object_new_string("0.1.0-dev"));
            json_object_object_add(j, "instance", json_object_new_string(s->instance));
            json_object_object_add(j, "backend", NULL);
            json_object_object_add(j, "inference_verified", json_object_new_boolean(false));
            body = json_text(j);
        } else if (!strcmp(c->url, "/actuator/llm")) {
            respond(c, 200, JSON_TYPE, "{\"schema\":\"synapse-lie.llm.v1\",\"ready\":false,\"backend\":null,\"scheduler\":null,\"memory\":null,\"cache\":null,\"speculation\":null,\"throughput\":null,\"latency\":null}"); return;
        } else { error_response(c, 404, "not_found"); return; }
    }
    respond(c, 200, JSON_TYPE, body); free(body);
}
static int on_url(llhttp_t *p, const char *data, size_t n) {
    connection *c = p->data;
    if (n >= sizeof(c->url) - c->url_size) { error_response(c, 400, "target_too_long"); return HPE_USER; }
    memcpy(c->url + c->url_size, data, n); c->url_size += n; c->url[c->url_size] = 0; return 0;
}
static int on_header(llhttp_t *p, const char *data, size_t n) {
    (void)data; connection *c = p->data; c->headers_size += n;
    if (c->headers_size > MAX_HEADERS) { error_response(c, 431, "headers_too_large"); return HPE_USER; } return 0;
}
static int on_headers(llhttp_t *p) {
    connection *c = p->data;
    if (p->upgrade) { error_response(c, 400, "upgrade_unsupported"); return HPE_USER; }
    if (p->content_length > MAX_BODY) { error_response(c, 413, "body_too_large"); return HPE_USER; }
    return 0;
}
static int on_body(llhttp_t *p, const char *data, size_t n) {
    (void)data; connection *c = p->data; c->body_size += n;
    if (c->body_size > MAX_BODY) { error_response(c, 413, "body_too_large"); return HPE_USER; } return 0;
}
static int complete(llhttp_t *p) { route(p->data); return HPE_PAUSED; }
static void alloc_buffer(uv_handle_t *h, size_t suggested, uv_buf_t *b) {
    (void)h; (void)suggested; b->base = malloc(8192); b->len = b->base ? 8192 : 0;
}
static void read_data(uv_stream_t *stream, ssize_t n, const uv_buf_t *b) {
    connection *c = stream->data;
    if (n > 0) {
        c->wire_size += (size_t)n;
        if (c->wire_size > MAX_BODY + MAX_HEADERS + 2048) error_response(c, 413, "request_too_large");
        else {
            llhttp_errno_t e = llhttp_execute(&c->parser, b->base, (size_t)n);
            if (e != HPE_OK && e != HPE_PAUSED && !c->responded) error_response(c, 400, "invalid_http");
        }
    } else if (n < 0) close_connection(c);
    free(b->base);
}
static void closed(uv_handle_t *h) {
    connection *c = h->data; server *s = c->owner;
    connection **p = &s->connections;
    while (*p && *p != c) p = &(*p)->next;
    if (*p) *p = c->next;
    --s->active; (void)lie_gauge_set(s->metrics, s->connections_meter, (double)s->active); free(c);
}
static void close_connection(connection *c) { if (!uv_is_closing((uv_handle_t *)&c->tcp)) uv_close((uv_handle_t *)&c->tcp, closed); }
static void accepted(uv_stream_t *stream, int status) {
    if (status < 0) return;
    listener *l = stream->data; server *s = l->owner;
    connection *c = calloc(1, sizeof(*c)); if (!c) return;
    if (uv_tcp_init(&s->loop, &c->tcp)) { free(c); return; }
    c->owner = s; c->management = l->management; c->started = lie_monotonic_ns(); c->tcp.data = c;
    c->next = s->connections; s->connections = c; ++s->active;
    if (uv_accept(stream, (uv_stream_t *)&c->tcp) || s->active > MAX_CONNECTIONS) { close_connection(c); return; }
    (void)lie_gauge_set(s->metrics, s->connections_meter, (double)s->active);
    llhttp_init(&c->parser, HTTP_REQUEST, &s->settings); c->parser.data = c;
    if (uv_read_start((uv_stream_t *)&c->tcp, alloc_buffer, read_data)) close_connection(c);
}
static void tick(uv_timer_t *timer) {
    server *s = timer->data; uint64_t time = lie_monotonic_ns();
    (void)lie_gauge_set(s->metrics, s->uptime, (double)(time - s->started) / 1e9);
    for (connection *c = s->connections; c; c = c->next) if (time - c->started >= TIMEOUT_NS) close_connection(c);
}
static void close_handle(uv_handle_t *handle, void *data) {
    (void)data;
    if (!uv_is_closing(handle)) uv_close(handle, NULL);
}
static void shutdown_server(uv_signal_t *signal, int number) {
    (void)number; server *s = signal->data; if (s->stopping) return;
    s->stopping = true;
    for (connection *c = s->connections; c; c = c->next) close_connection(c);
    uv_walk(&s->loop, close_handle, NULL);
}
static bool init_metrics(server *s) {
    lie_metric_spec spec = {"runtime.uptime", "Runtime uptime", "seconds", LIE_GAUGE, NULL, 0};
    if (lie_metrics_register(s->metrics, &spec, NULL, 0, &s->uptime)) return false;
    spec = (lie_metric_spec){"runtime.ready", "Model and executor ready", NULL, LIE_GAUGE, NULL, 0};
    if (lie_metrics_register(s->metrics, &spec, NULL, 0, &s->ready)) return false;
    spec = (lie_metric_spec){"http.connections.active", "Open HTTP connections", NULL, LIE_GAUGE, NULL, 0};
    if (lie_metrics_register(s->metrics, &spec, NULL, 0, &s->connections_meter)) return false;
    spec = (lie_metric_spec){"llm.requests.rejected", "Requests refused before inference", NULL, LIE_COUNTER, NULL, 0};
    lie_tag tag = {"reason", "backend_unavailable"};
    if (lie_metrics_register(s->metrics, &spec, &tag, 1, &s->rejected)) return false;
    spec = (lie_metric_spec){"llm.tokens.generated", "Confirmed generated tokens", "tokens", LIE_COUNTER, NULL, 0};
    if (lie_metrics_register(s->metrics, &spec, NULL, 0, &s->tokens)) return false;
    double buckets[] = {.001, .01, .1, 1, 5};
    spec = (lie_metric_spec){"http.server.requests", "Connection acceptance to response enqueue; not write completion", "seconds", LIE_TIMER, buckets, 5};
    const char *methods[] = {"GET", "POST", "OTHER"}, *statuses[] = {"2xx", "4xx", "5xx"};
    for (size_t m = 0; m < 3; ++m) for (size_t st = 0; st < 3; ++st) {
        lie_tag tags[] = {{"method", methods[m]}, {"status", statuses[st]}};
        if (lie_metrics_register(s->metrics, &spec, tags, 2, &s->http[m][st])) return false;
    }
    return true;
}
static int start_listener(server *s, listener *l, const char *host, int port, bool management) {
    l->owner = s; l->management = management;
    int rc = uv_tcp_init(&s->loop, &l->tcp); if (rc) return rc;
    l->tcp.data = l; struct sockaddr_in address;
    rc = uv_ip4_addr(host, port, &address); if (rc) return rc;
    rc = uv_tcp_bind(&l->tcp, (const struct sockaddr *)&address, 0); if (rc) return rc;
    return uv_listen((uv_stream_t *)&l->tcp, MAX_CONNECTIONS, accepted);
}
static int port_number(const char *s) {
    char *end; errno = 0; long value = strtol(s, &end, 10);
    return errno || !*s || *end || value < 1 || value > 65535 ? -1 : (int)value;
}
int main(int argc, char **argv) {
    setlocale(LC_ALL, "C"); int port = 19879, management_port = 19880;
    const char *host = "127.0.0.1", *management_host = "127.0.0.1";
    for (int i = 1; i < argc; ++i) {
        if (!strcmp(argv[i], "--help")) { puts("Usage: synapse-lie-server [--host IPv4] [--port N] [--management-host IPv4] [--management-port N]\nDevelopment management runtime only. No inference backend connected."); return 0; }
        if (i + 1 == argc) { fputs("Missing option value\n", stderr); return 2; }
        if (!strcmp(argv[i], "--port")) port = port_number(argv[++i]);
        else if (!strcmp(argv[i], "--management-port")) management_port = port_number(argv[++i]);
        else if (!strcmp(argv[i], "--host")) host = argv[++i];
        else if (!strcmp(argv[i], "--management-host")) management_host = argv[++i];
        else { fputs("Unknown option\n", stderr); return 2; }
    }
    if (port < 0 || management_port < 0 || (port == management_port && !strcmp(host, management_host))) { fputs("Invalid listener configuration\n", stderr); return 2; }
    server s = {0}; s.started = lie_monotonic_ns();
    snprintf(s.instance, sizeof(s.instance), "%ld-%llu", (long)getpid(), (unsigned long long)s.started);
    s.metrics = lie_metrics_create(NULL, NULL);
    if (!s.metrics || !init_metrics(&s) || uv_loop_init(&s.loop)) { lie_metrics_destroy(s.metrics); return 1; }
    llhttp_settings_init(&s.settings); s.settings.on_url = on_url;
    s.settings.on_header_field = on_header; s.settings.on_header_value = on_header;
    s.settings.on_headers_complete = on_headers; s.settings.on_body = on_body; s.settings.on_message_complete = complete;
    int rc = start_listener(&s, &s.api, host, port, false);
    if (!rc) rc = start_listener(&s, &s.management, management_host, management_port, true);
    if (rc) { fprintf(stderr, "Listener startup failed: %s\n", uv_strerror(rc)); uv_walk(&s.loop, close_handle, NULL); uv_run(&s.loop, UV_RUN_DEFAULT); uv_loop_close(&s.loop); lie_metrics_destroy(s.metrics); return 1; }
    uv_timer_init(&s.loop, &s.timer); s.timer.data = &s; uv_timer_start(&s.timer, tick, 0, 250);
    uv_signal_init(&s.loop, &s.interrupt); s.interrupt.data = &s; uv_signal_start(&s.interrupt, shutdown_server, SIGINT);
    uv_signal_init(&s.loop, &s.terminate); s.terminate.data = &s; uv_signal_start(&s.terminate, shutdown_server, SIGTERM);
    printf("API http://%s:%d management http://%s:%d backend=unavailable\n", host, port, management_host, management_port); fflush(stdout);
    uv_run(&s.loop, UV_RUN_DEFAULT); rc = uv_loop_close(&s.loop); lie_metrics_destroy(s.metrics);
    return rc ? 1 : 0;
}
