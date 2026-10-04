/* SPDX-License-Identifier: MIT */
#include "lie/executor.h"
#include <stddef.h>
_Static_assert(LIE_EXECUTOR_ABI == 2, "ABI marker");
_Static_assert(sizeof(lie_model_options) == 16, "fixed options layout");
_Static_assert(sizeof(lie_decode_result) == 16, "fixed result layout");
_Static_assert(offsetof(lie_model_info, weights_bytes) == 24, "info alignment");
_Static_assert(sizeof(lie_error) == 256, "caller-owned error");
int main(void) { return 0; } /* Layout compilation only, never model execution. */
