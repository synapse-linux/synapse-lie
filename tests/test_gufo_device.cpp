// SPDX-License-Identifier: MIT
// Link the actual admission wrapper to a synthetic HIP API, never a GPU driver.
#include <hip/hip_runtime_api.h>
#include "lie/executor.h"
#include <cstdlib>
#include <cstring>
#define CHECK(x) do { if (!(x)) std::abort(); } while (0)
extern "C" lie_status lie_gufo_device_validate(lie_error *) noexcept;
static int calls = 0, failure = 0;
static hipDeviceProp_t reported{};
hipError_t hipGetDevice(int *device) { ++calls; *device = 0; return failure; }
hipError_t hipGetDeviceProperties(hipDeviceProp_t *properties, int) { ++calls; *properties = reported; return failure; }
hipError_t hipDriverGetVersion(int *version) { *version = 70200; return 0; }
hipError_t hipRuntimeGetVersion(int *version) { *version = 70200; return 0; }
hipError_t hipDeviceSynchronize(void) { std::abort(); }
int main() {
    lie_error error{};
    CHECK(!unsetenv("HSA_OVERRIDE_GFX_VERSION"));
    std::strcpy(reported.gcnArchName, "gfx1150:xnack-");
    reported.warpSize = 32;
    CHECK(lie_gufo_device_validate(&error) == LIE_OK);
    CHECK(calls == 2);
    std::strcpy(reported.gcnArchName, "gfx1151");
    CHECK(lie_gufo_device_validate(&error) == LIE_UNSUPPORTED);
    CHECK(std::strstr(error.message, "built for gfx1150"));
    CHECK(std::strstr(error.message, "found gfx1151"));
    std::strcpy(reported.gcnArchName, "gfx1150");
    reported.warpSize = 64;
    CHECK(lie_gufo_device_validate(nullptr) == LIE_UNSUPPORTED);
    reported.warpSize = 32;
    failure = 1;
    CHECK(lie_gufo_device_validate(&error) == LIE_BACKEND_FAILED);
    failure = 0;
    calls = 0;
    CHECK(!setenv("HSA_OVERRIDE_GFX_VERSION", "11.5.0", 1));
    CHECK(lie_gufo_device_validate(&error) == LIE_UNSUPPORTED);
    CHECK(calls == 0);
    CHECK(!unsetenv("HSA_OVERRIDE_GFX_VERSION"));
    return 0;
}
