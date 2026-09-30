/* SPDX-License-Identifier: MIT */
/* Explicit composition, not a claim of owned numerical execution. */
#include "lie/executor.h"
const char *lie_backend_ownership(void) { return "delegated"; }
const char *lie_backend_source_pin(void) { return "f783fedb9bea2ec7de941f6da4e02f4a4596b29e"; }
lie_status lie_backend_open(const char *path, const lie_model_options *options,
                             lie_model **model, lie_error *error) {
    return lie_gufo_open(path,options,model,error);
}
