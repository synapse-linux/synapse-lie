/* SPDX-License-Identifier: MIT */
#ifndef LIE_CHOICES_H
#define LIE_CHOICES_H
#include "lie/events.h"
typedef struct lie_choices lie_choices;
/* Independent per-choice model state, scheduled by the same reactive owner.
 * Admission failure cancels and releases every child admitted by this call.
 * A supplied seed is offset by choice index; overflow refuses before submit. */
int lie_core_submit_choices(lie_core *, const lie_core_request *, unsigned,
                            lie_choices **);
/* Each independent child copies the same immutable plan before publication.
 * NULL preserves ordinary admission. Failure cancels/releases all children. */
int lie_core_submit_choices_steering(lie_core *, const lie_core_request *, unsigned,
                                     const lie_steering_schedule *, lie_choices **);
unsigned lie_choices_count(lie_choices *);
lie_job *lie_choices_job(lie_choices *, unsigned);
void lie_choices_cancel(lie_choices *);
void lie_choices_release(lie_choices *);
#endif
