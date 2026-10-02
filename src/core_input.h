/* SPDX-License-Identifier: MIT */
#ifndef LIE_CORE_INPUT_H
#define LIE_CORE_INPUT_H
#include "lie/core.h"
/* Private immutable arena, freed by the last job reference. */
bool lie_core_input_copy(const lie_core_request *, lie_core_request *, void **);
#endif
