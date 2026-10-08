// SPDX-License-Identifier: MIT
// Failure-only drain. Never adds a synchronization to a successful step.
#include <hip/hip_runtime_api.h>
#include <cstdio>
#include <cstdlib>
extern "C" void lie_gufo_quiesce_or_exit(void) noexcept {
    const auto status=hipDeviceSynchronize();
    if (status!=hipSuccess) {
        // Cannot promise retirement: no retry, fallback, unsafe free or core dump.
        std::fprintf(stderr,"GPU quiescence failed (%d); process exiting without retry\n",static_cast<int>(status));
        std::fflush(stderr);
        std::_Exit(70);
    }
}
