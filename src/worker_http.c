/* SPDX-License-Identifier: MIT */
#include "lie/worker.h"
void lie_chat_core_request(const lie_chat_request *r, lie_core_request *input) {
  lie_core_request_init(input);
  input->chat = (lie_chat_template){r->messages, r->details,    r->count,
                                    r->tools,    r->tool_count, 0};
  input->images = r->image_count ? r->images : NULL;
  input->image_count = r->image_count;
  input->max_tokens = r->max_tokens;
  input->tool_choice = r->tool_choice;
  input->parallel_tool_calls = r->parallel_tools;
  input->named_tool = r->named_tool;
  input->format = r->format;
  input->schema_json = r->schema_json;
  input->strict = r->strict;
  input->truncate_oldest = r->truncate_oldest;
  input->stop_count = r->stop_count;
  for (size_t i = 0; i < r->stop_count; ++i)
    input->stop[i] = r->stop[i];
  /* Preserve default generation for legacy programmatic HTTP fixtures. */
  if (r->generation.abi_version)
    input->generation = r->generation;
}
int lie_worker_submit(lie_worker *w, lie_chat_request *r, lie_job **out) {
  if (!r)
    return 3;
  lie_core_request input;
  lie_chat_core_request(r, &input);
  int rc = lie_core_submit(w, &input, out);
  if (!rc)
    lie_chat_free(r);
  return rc;
}
