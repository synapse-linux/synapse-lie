# SPDX-License-Identifier: MIT
# A reference sampler and numerical/controller archives must share OFF layouts.
include("${CMAKE_CURRENT_LIST_DIR}/Verify.cmake")
include("${CMAKE_CURRENT_LIST_DIR}/Target.cmake")
function(lie_verify_gufo_reference source build state_access kvc target)
  if(NOT build)
    message(FATAL_ERROR "Gufo reference requires a separately verified OFF provider build")
  endif()
  set(LIE_C17_SAMPLING OFF)
  lie_verify_gufo("${source}" "${build}" "${state_access}" "${kvc}")
  lie_verify_hip_target("${build}" "${target}")
endfunction()
if(CMAKE_SCRIPT_MODE_FILE STREQUAL CMAKE_CURRENT_LIST_FILE)
  lie_verify_gufo_reference("${GUFO_SOURCE}" "${GUFO_BUILD}"
    "${LIE_GUFO_STATE_ACCESS}" "${LIE_DS4_RUNTIME_CACHE}" "${LIE_HIP_ARCHITECTURE}")
endif()
