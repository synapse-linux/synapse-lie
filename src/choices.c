/* SPDX-License-Identifier: MIT */
#include "lie/choices.h"
#include <limits.h>
#include <stdlib.h>
struct lie_choices {
  unsigned count;
  lie_job *jobs[LIE_CORE_JOBS];
};
int lie_core_submit_choices_steering(lie_core *core, const lie_core_request *request,
                            unsigned count, const lie_steering_schedule *schedule,
                            lie_choices **out) {
  if (!core || !request || !out || *out || !count || count > LIE_CORE_JOBS ||
      (request->generation.seed >= 0 &&
       request->generation.seed > INT64_MAX - (int64_t)(count - 1)))
    return 3;
  lie_choices *choices = calloc(1, sizeof(*choices));
  if (!choices)
    return 3;
  int result = 0;
  for (unsigned i = 0; i < count; ++i) {
    lie_core_request input = *request;
    if (input.generation.seed >= 0)
      input.generation.seed += (int64_t)i;
    result = lie_core_submit_steering(core, &input, schedule, &choices->jobs[i]);
    if (result)
      break;
    ++choices->count;
  }
  if (result) {
    lie_choices_cancel(choices);
    lie_choices_release(choices);
    return result;
  }
  *out = choices;
  return 0;
}
int lie_core_submit_choices(lie_core *core,const lie_core_request *request,
                            unsigned count,lie_choices **out){
  return lie_core_submit_choices_steering(core,request,count,NULL,out);
}
unsigned lie_choices_count(lie_choices *c) { return c ? c->count : 0; }
lie_job *lie_choices_job(lie_choices *c, unsigned i) {
  return c && i < c->count ? c->jobs[i] : NULL;
}
void lie_choices_cancel(lie_choices *c) {
  if (c)
    for (unsigned i = 0; i < c->count; ++i)
      lie_job_cancel(c->jobs[i]);
}
void lie_choices_release(lie_choices *c) {
  if (c) {
    for (unsigned i = 0; i < c->count; ++i)
      lie_job_release(c->jobs[i]);
    free(c);
  }
}
