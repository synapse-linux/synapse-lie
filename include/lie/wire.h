/* SPDX-License-Identifier: MIT */
#ifndef LIE_WIRE_H
#define LIE_WIRE_H
#include "lie/worker.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
/* Returned strings are owned. Content is a length-delimited valid UTF-8 span. */
char *lie_wire_completion(const char *id, const char *model, int64_t created,
                          const char *content, size_t bytes, const lie_job_info *);
char *lie_wire_chunk(const char *id, const char *model, int64_t created,
                     const char *content, size_t bytes, bool role);
char *lie_wire_end(const char *id, const char *model, int64_t created,
                   const lie_job_info *, bool usage);
#endif
