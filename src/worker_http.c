/* SPDX-License-Identifier: MIT */
#include "lie/worker.h"
int lie_worker_submit(lie_worker *w, lie_chat_request *r, lie_job **out) {
    if (!r) return 3;
    lie_core_request input;
    lie_core_request_init(&input);
    input.chat=(lie_chat_template){r->messages,r->details,r->count,r->tools,r->tool_count,0};
    input.max_tokens=r->max_tokens;
    input.tool_choice=r->tool_choice;
    input.named_tool=r->named_tool;
    /* Preserve default generation for legacy programmatic HTTP fixtures. */
    if (r->generation.abi_version) input.generation=r->generation;
    int rc=lie_core_submit(w,&input,out);
    if (!rc) lie_chat_free(r);
    return rc;
}
