/* SPDX-License-Identifier: MIT */
#include "lie/executor.h"
#include "lie/sampling_observer.h"
#include <string.h>
#include <stddef.h>
_Static_assert(LIE_EXECUTOR_ABI == 3, "ABI marker");
_Static_assert(sizeof(lie_model_options) == 20, "versioned profile options layout");
_Static_assert(offsetof(lie_model_options, rope_profile) == 16, "profile alignment");
_Static_assert(sizeof(lie_decode_result) == 16, "fixed result layout");
_Static_assert(offsetof(lie_model_info, weights_bytes) == 24, "info alignment");
_Static_assert(sizeof(lie_error) == 256, "caller-owned error");
/* Layout and unavailable-backend linkage only, never model execution. */
int main(void) {
    uint32_t stop = 0x12345678;
    lie_error error = {{0}};
    if (lie_model_token_is_stop(NULL, 0, &stop, &error) != LIE_UNSUPPORTED)
        return 1;
    if (stop != 0x12345678 || !error.message[0])
        return 2;
    if (lie_model_token_is_stop(NULL, -1, NULL, NULL) != LIE_UNSUPPORTED)
        return 3;
    lie_mtp_outcome observed, before;
    memset(&observed, 0x5a, sizeof(observed)); before = observed;
    if (lie_sequence_decode_mtp_observed(NULL, 1, NULL, &observed, &error) != LIE_UNSUPPORTED ||
        memcmp(&observed, &before, sizeof(observed)))
        return 4;
    return 0;
}
