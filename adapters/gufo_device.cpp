// SPDX-License-Identifier: MIT
// Failure-only drain. Never adds a synchronization to a successful step.
#include <hip/hip_runtime_api.h>
#include <cstdio>
#include <cstdlib>
extern "C" int lie_gufo_device_identity(char *out,size_t cap) noexcept {
    int device=0,driver=0,runtime=0;hipDeviceProp_t properties{};
    if(hipGetDevice(&device)!=hipSuccess||hipGetDeviceProperties(&properties,device)!=hipSuccess||
       hipDriverGetVersion(&driver)!=hipSuccess||hipRuntimeGetVersion(&runtime)!=hipSuccess)return 0;
    int n=std::snprintf(out,cap,"HIP/%d/%d/device=%d/arch=%s/name=%s/pci=%d:%d:%d",
        driver,runtime,device,properties.gcnArchName,properties.name,properties.pciDomainID,properties.pciBusID,properties.pciDeviceID);
    return n>=0&&static_cast<size_t>(n)<cap;
}
extern "C" void lie_gufo_quiesce_or_exit(void) noexcept {
    const auto status=hipDeviceSynchronize();
    if (status!=hipSuccess) {
        // Cannot promise retirement: no retry, fallback, unsafe free or core dump.
        std::fprintf(stderr,"GPU quiescence failed (%d); process exiting without retry\n",static_cast<int>(status));
        std::fflush(stderr);
        std::_Exit(70);
    }
}
