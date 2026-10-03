# SPDX-License-Identifier: MIT
# Private, lease-bound ROCm 10 compile inside the pinned device-free container.
cmake_minimum_required(VERSION 3.21)
get_filename_component(root "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
if(NOT "$ENV{LIE_ROCM10_BUILD_WINDOW}" STREQUAL "admitted" OR EXISTS "/dev/kfd")
  message(FATAL_ERROR "An admitted build window without GPU devices is required")
endif()
if(NOT DEFINED LABEL OR NOT LABEL MATCHES "^rocm10-point-modern-r[1-9][0-9]*$" OR
   NOT DEFINED SOURCE_COMMIT OR NOT SOURCE_COMMIT MATCHES "^[0-9a-f]+$")
  message(FATAL_ERROR "An exclusive modern Point label and source commit are required")
endif()
file(READ "${root}/SOURCE-COMMIT.txt" recorded_commit)
string(STRIP "${recorded_commit}" recorded_commit)
if(NOT recorded_commit STREQUAL SOURCE_COMMIT)
  message(FATAL_ERROR "Source capsule commit identity mismatch")
endif()
set(provider "${LABEL}-provider")
set(runtime "${LABEL}-runtime")
set(out "${root}/evidence/${LABEL}-compile")
if(EXISTS "${out}" OR EXISTS "${root}/build/${provider}" OR
   EXISTS "${root}/build/${runtime}")
  message(FATAL_ERROR "Build label exists; refusing replacement")
endif()
file(MAKE_DIRECTORY "${out}")
file(WRITE "${out}/result.json"
  "{\"state\":\"RUNNING\",\"source_commit\":\"${SOURCE_COMMIT}\",\"label\":\"${LABEL}\",\"exit_code\":null}\n")
macro(run_stage name)
  string(JOIN " " command_text ${ARGN})
  file(WRITE "${out}/${name}.command" "${command_text}\n")
  execute_process(COMMAND ${ARGN} WORKING_DIRECTORY "${root}"
    RESULT_VARIABLE stage_exit OUTPUT_FILE "${out}/${name}.stdout"
    ERROR_FILE "${out}/${name}.stderr")
  file(WRITE "${out}/${name}.exit" "${stage_exit}\n")
  if(NOT stage_exit EQUAL 0)
    file(WRITE "${out}/result.json"
      "{\"state\":\"FAILED\",\"source_commit\":\"${SOURCE_COMMIT}\",\"label\":\"${LABEL}\",\"failed_stage\":\"${name}\",\"failed_stage_exit\":\"${stage_exit}\",\"exit_code\":1}\n")
    message(FATAL_ERROR "${name} failed with ${stage_exit}; retained command and output")
  endif()
endmacro()
run_stage(provider
  "${CMAKE_COMMAND}" "-DLABEL=${provider}" -DLIE_HIP_ARCHITECTURE=gfx1150
  -DLIE_GUFO_STATE_ACCESS=ON -DLIE_DS4_RUNTIME_CACHE=ON
  -DLIE_C17_SAMPLING=ON -DLIE_VISION_WEIGHT_DECODE=ON
  -P "${root}/cmake/provider/Build.cmake")
run_stage(configure
  "${CMAKE_COMMAND}" -S "${root}" -B "${root}/build/${runtime}" -G Ninja
  -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF
  -DLIE_GUFO_RUNTIME=ON -DLIE_GUFO_STATE_ACCESS=ON
  -DLIE_DS4_RUNTIME_CACHE=ON -DLIE_C17_SAMPLING=ON
  -DLIE_VISION_WEIGHT_DECODE=ON -DLIE_CHECKPOINT_COMPRESSION=ON
  -DLIE_MTP=ON -DLIE_VISION=ON -DLIE_HIP_ARCHITECTURE=gfx1150
  "-DLIE_BUILD_ID=${runtime}"
  "-DGUFO_SOURCE=${root}/.deps/gufo-state-access-${provider}"
  "-DGUFO_BUILD=${root}/build/${provider}")
run_stage(link
  "${CMAKE_COMMAND}" --build "${root}/build/${runtime}" --parallel 1
  --target synapse-lie-server synapse-lie-bench
  synapse-lie-bench-gufo-reference lie-hip-probe)
set(binaries "{}")
foreach(name IN ITEMS synapse-lie-server synapse-lie-bench
    synapse-lie-bench-gufo-reference lie-hip-probe)
  file(SHA256 "${root}/build/${runtime}/${name}" hash)
  string(JSON binaries SET "${binaries}" "${name}" "\"${hash}\"")
endforeach()
file(WRITE "${out}/result.json"
  "{\"state\":\"BUILT_NOT_GPU_TESTED\",\"source_commit\":\"${SOURCE_COMMIT}\",\"label\":\"${LABEL}\",\"hip_architecture\":\"gfx1150\",\"checkpoint_compression\":true,\"exit_code\":0,\"binaries\":${binaries}}\n")
