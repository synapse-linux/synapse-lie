/* SPDX-License-Identifier: MIT */
/* Owned image inputs, protocol normalization and provider-neutral bounds.
 * No image encoder/model inference or GPU execution. */
#include "fake_executor.h"
#include "lie/chat.h"
#include "lie/core.h"
#include "lie/responses.h"
#include "vision_fixture.h"
#include <assert.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
static void pause_short(void) {
  struct timespec t = {0, 1000000};
  nanosleep(&t, NULL);
}
static lie_core_info ready(lie_core *c, lie_core_state target) {
  lie_core_info i = {0};
  for (unsigned k = 0; k < 5000; ++k) {
    lie_core_snapshot(c, &i);
    if (i.state == target)
      return i;
    pause_short();
  }
  assert(!"core deadline");
  return i;
}
static unsigned consume(lie_job *j) {
  unsigned total = 0;
  for (unsigned k = 0; k < 5000; ++k) {
    lie_flow_event e = {0};
    lie_flow *f = lie_job_flow(j);
    lie_flow_status s = lie_flow_next(f, &e);
    if (s == LIE_FLOW_WOULD_BLOCK) {
      struct pollfd fd = {lie_flow_fd(f, LIE_FLOW_OUTPUT_READY), POLLIN, 0};
      assert(poll(&fd, 1, 1) >= 0);
      lie_flow_drain(f, LIE_FLOW_OUTPUT_READY);
      continue;
    }
    assert(s == LIE_FLOW_OK);
    if (e.end != LIE_FLOW_ACTIVE) {
      assert(e.end == LIE_FLOW_COMPLETE);
      return total;
    }
    assert(e.token_offset == total);
    total += (unsigned)e.tokens;
    assert(lie_flow_release(f, e.ticket) == LIE_FLOW_OK);
    lie_flow_request(f, e.tokens);
  }
  assert(!"job deadline");
  return 0;
}
static unsigned char *pixels(size_t *n) {
  unsigned char *p = NULL;
  lie_image_format format = 0;
  lie_error e = {0};
  assert(lie_image_data_url(image_url, strlen(image_url), &p, n, &format, &e) ==
             LIE_OK &&
         format == LIE_IMAGE_PNG);
  return p;
}
static void parsers(void) {
  size_t n = 0;
  unsigned char *p = pixels(&n);
  lie_image_input in = {.data = p, .bytes = n, .format = LIE_IMAGE_PNG};
  lie_image_dimensions d;
  assert(lie_image_inspect(&in, &d, NULL) == LIE_OK && d.width == 1 &&
         d.height == 1);
  for (size_t k = 0; k < 33; ++k) {
    in.bytes = k;
    assert(lie_image_inspect(&in, &d, NULL) == LIE_INVALID);
  }
  in.bytes = n;
  p[16] = 255;
  assert(lie_image_inspect(&in, &d, NULL) == LIE_INVALID);
  free(p);
  const char *bad[] = {
      "https://example.com/p.png",      "file:///tmp/image.png",
      "data:image/png;base64,AAAA",     "data:image/png;base64,AB==",
      "data:image/png;base64,A===",     "data:image/png;base64,AA=A",
      "data:image/png;base64,AA==AAAA", "data:image/png;base64,AA==\n"};
  for (size_t k = 0; k < sizeof(bad) / sizeof(*bad); ++k) {
    p = NULL;
    lie_image_format f;
    assert(lie_image_data_url(bad[k], strlen(bad[k]), &p, &n, &f, NULL) ==
               LIE_INVALID &&
           !p);
  }
  char body[2048], error[256];
  lie_chat_request request;
  snprintf(body, sizeof(body),
           "{\"model\":\"m\",\"messages\":[{\"role\":\"user\",\"content\":[{"
           "\"type\":\"text\",\"text\":\"hi "
           "\"},{\"type\":\"image_url\",\"image_url\":{\"url\":\"%s\"}},{"
           "\"type\":\"text\",\"text\":\"there\"}]}]}",
           image_url);
  assert(lie_chat_parse(body, strlen(body), "m", &request, error));
  assert(request.image_count == 1 && request.images[0].text_offset == 3 &&
         !strcmp(request.messages[0].content, "hi there"));
  lie_chat_free(&request);
  snprintf(body, sizeof(body),
           "{\"model\":\"m\",\"input\":[{\"role\":\"user\",\"content\":[{"
           "\"type\":\"input_image\",\"image_url\":\"%s\"},{\"type\":\"input_"
           "text\",\"text\":\"describe\"}]}]}",
           image_url);
  assert(lie_responses_parse(body, strlen(body), "m", &request, error));
  assert(request.image_count == 1 && !request.images[0].text_offset);
  lie_chat_free(&request);
  snprintf(body, sizeof(body),
           "{\"model\":\"m\",\"messages\":[{\"role\":\"user\",\"content\":[{"
           "\"type\":\"image_url\",\"image_url\":{\"url\":\"%s\"}},{\"type\":"
           "\"unsupported\"}]}]}",
           image_url);
  assert(!lie_chat_parse(body, strlen(body), "m", &request,
                         error)); /* Partial image cleanup. */
}
static void family(const char *encoder, unsigned max_images,
                   unsigned expected_tokens) {
  lie_core_options o;
  lie_core_options_init(&o);
  o.model_path = ":fixture:";
  o.vision_model_path = encoder;
  o.context = 128;
  o.chunk = 4;
  o.max_active = 2;
  o.prefix_cache_bytes = 0;
  lie_core *c = lie_core_create(&o);
  assert(c);
  lie_core_info ci = ready(c, LIE_READY);
  assert(ci.vision.max_images == max_images &&
         ci.vision.prefix_state_supported);
  lie_core_request block;
  lie_core_request_init(&block);
  int32_t ids[] = {0, 10, 10, 10};
  block.kind = LIE_INPUT_TOKENS;
  block.tokens = ids;
  block.token_count = 4;
  block.max_tokens = 4;
  lie_job *hold = NULL;
  fake_barrier_arm_phase(FAKE_PREFILL);
  assert(!lie_core_submit(c, &block, &hold));
  fake_barrier_wait();
  size_t n = 0;
  unsigned char *p = pixels(&n);
  unsigned original = p[n - 1];
  lie_image_input image = {p, n, LIE_IMAGE_PNG, 0, 3};
  char text[] = "normal";
  lie_chat_message message = {LIE_CHAT_USER, text, 6};
  lie_core_request r;
  lie_core_request_init(&r);
  r.chat.messages = &message;
  r.chat.count = 1;
  r.images = &image;
  r.image_count = 1;
  r.max_tokens = 4;
  lie_job *job = NULL;
  assert(!lie_core_submit(c, &r, &job));
  p[n - 1] ^= 255;
  memset(text, 'X', 6);
  free(p);
  image = (lie_image_input){0};
  fake_barrier_release();
  assert(consume(job) == 4 && consume(hold) == 4);
  lie_job_info info;
  lie_job_snapshot(job, &info);
  assert(info.prompt_tokens == expected_tokens && !info.cached_tokens);
  size_t count = 0;
  int32_t physical[128];
  assert(lie_job_prompt_tokens(job, physical, 128, &count) == LIE_OK &&
         count == expected_tokens && physical[count - 1] == (int32_t)original);
  lie_job_release(job);
  lie_job_release(hold);
  p = pixels(&n);
  image = (lie_image_input){p, n, LIE_IMAGE_PNG, 0, 1};
  message = (lie_chat_message){LIE_CHAT_USER, "\xc3\xa8", 2};
  r.chat.messages = &message;
  r.images = &image;
  job = NULL;
  assert(lie_core_submit(c, &r, &job) == 3 &&
         !job); /* Inside a UTF-8 codepoint. */
  image.text_offset = 0;
  image.message_index = 1;
  assert(lie_core_submit(c, &r, &job) == 3 && !job);
  free(p);
  lie_core_stop(c);
  ready(c, LIE_STOPPED);
  lie_core_destroy(c);
}
int main(void) {
  parsers();
  family(":vision-a:", 16, 7);
  family(":vision-b:", 2, 17);
  puts("Model-neutral vision ownership, physical context, PNG/base64 and "
       "Chat/Responses: PASS (NOT-INFERENCE)");
}
