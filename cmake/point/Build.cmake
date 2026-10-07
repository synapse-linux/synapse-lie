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
# The pinned runtime image has libzstd 1.5.7 but no development headers.
# Stage matching distribution headers in the sealed source capsule; do not
# install packages or silently disable checkpoint compression.
set(zstd_dev "${root}/third_party/point-zstd-dev")
foreach(name IN ITEMS zstd.h zstd_errors.h LICENSE)
  if(NOT EXISTS "${zstd_dev}/${name}")
    message(FATAL_ERROR "Missing staged Zstandard development file: ${name}")
  endif()
endforeach()
file(READ "${zstd_dev}/zstd.h" zstd_header)
if(NOT zstd_header MATCHES "#define ZSTD_VERSION_MAJOR +1([^0-9]|$)" OR
   NOT zstd_header MATCHES "#define ZSTD_VERSION_MINOR +5([^0-9]|$)" OR
   NOT zstd_header MATCHES "#define ZSTD_VERSION_RELEASE +7([^0-9]|$)")
  message(FATAL_ERROR "The staged Zstandard header must be version 1.5.7")
endif()
set(zstd_library "/usr/lib64/libzstd.so.1")
if(NOT EXISTS "${zstd_library}")
  message(FATAL_ERROR "Pinned image lacks the Zstandard runtime library")
endif()
file(REAL_PATH "${zstd_library}" zstd_library_real)
if(NOT zstd_library_real MATCHES "libzstd\\.so\\.1\\.5\\.7$")
  message(FATAL_ERROR "Pinned image Zstandard runtime is not version 1.5.7")
endif()
file(SHA256 "${zstd_dev}/zstd.h" zstd_header_sha256)
file(SHA256 "${zstd_dev}/zstd_errors.h" zstd_errors_sha256)
file(SHA256 "${zstd_dev}/LICENSE" zstd_license_sha256)
file(SHA256 "${zstd_library}" zstd_library_sha256)
set(provider "${LABEL}-provider")
if(NOT DEFINED LIE_LONG_CONTEXT_WMMA)
  set(LIE_LONG_CONTEXT_WMMA ON)
endif()
if(LIE_LONG_CONTEXT_WMMA)
  set(long_context_wmma_json true)
else()
  set(long_context_wmma_json false)
endif()
set(reference_provider "${LABEL}-reference-provider")
set(runtime "${LABEL}-runtime")
set(out "${root}/evidence/${LABEL}-compile")
if(EXISTS "${out}" OR EXISTS "${root}/build/${provider}" OR
   EXISTS "${root}/build/${reference_provider}" OR
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
  -DLIE_C17_SAMPLING=ON -DLIE_VISION_WEIGHT_DECODE=ON -DLIE_DIRECTIONAL_STEERING=ON
  "-DLIE_LONG_CONTEXT_WMMA=${LIE_LONG_CONTEXT_WMMA}"
  -P "${root}/cmake/provider/Build.cmake")
run_stage(reference-provider
  "${CMAKE_COMMAND}" "-DLABEL=${reference_provider}" -DLIE_HIP_ARCHITECTURE=gfx1150
  -DLIE_GUFO_STATE_ACCESS=ON -DLIE_DS4_RUNTIME_CACHE=ON
  -DLIE_C17_SAMPLING=OFF -DLIE_VISION_WEIGHT_DECODE=ON -DLIE_DIRECTIONAL_STEERING=ON
  "-DLIE_LONG_CONTEXT_WMMA=${LIE_LONG_CONTEXT_WMMA}"
  -P "${root}/cmake/provider/Build.cmake")
run_stage(configure
  "${CMAKE_COMMAND}" -S "${root}" -B "${root}/build/${runtime}" -G Ninja
  -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF
  -DLIE_GUFO_RUNTIME=ON -DLIE_GUFO_STATE_ACCESS=ON
  -DLIE_DS4_RUNTIME_CACHE=ON -DLIE_C17_SAMPLING=ON -DLIE_DIRECTIONAL_STEERING=ON
  "-DLIE_LONG_CONTEXT_WMMA=${LIE_LONG_CONTEXT_WMMA}"
  -DLIE_VISION_WEIGHT_DECODE=ON -DLIE_CHECKPOINT_COMPRESSION=ON
  -DLIE_MTP=ON -DLIE_VISION=ON -DLIE_HIP_ARCHITECTURE=gfx1150
  "-DZSTD_INCLUDE_DIR=${zstd_dev}" "-DZSTD_LIBRARY=${zstd_library}"
  "-DLIE_BUILD_ID=${runtime}"
  "-DGUFO_SOURCE=${root}/.deps/gufo-state-access-${provider}"
  "-DGUFO_BUILD=${root}/build/${provider}"
  "-DGUFO_REFERENCE_BUILD=${root}/build/${reference_provider}")
set(point_binaries synapse-lie-server synapse-lie-bench
  synapse-lie-bench-gufo-reference lie-hip-probe lie-sampling-capture)
run_stage(link
  "${CMAKE_COMMAND}" --build "${root}/build/${runtime}" --parallel 1
  --target ${point_binaries})
set(binaries "{}")
foreach(name IN LISTS point_binaries)
  file(SHA256 "${root}/build/${runtime}/${name}" hash)
  string(JSON binaries SET "${binaries}" "${name}" "\"${hash}\"")
endforeach()
file(SHA256 "${root}/build/${provider}/BUILD-RECEIPT.json" provider_receipt_sha256)
file(SHA256 "${root}/build/${reference_provider}/BUILD-RECEIPT.json" reference_receipt_sha256)
file(WRITE "${out}/result.json"
  "{\"state\":\"BUILT_NOT_GPU_TESTED\",\"source_commit\":\"${SOURCE_COMMIT}\",\"label\":\"${LABEL}\",\"hip_architecture\":\"gfx1150\",\"long_context_wmma\":${long_context_wmma_json},\"reference_control_coherent_off\":true,\"provider_receipt_sha256\":\"${provider_receipt_sha256}\",\"reference_provider_receipt_sha256\":\"${reference_receipt_sha256}\",\"checkpoint_compression\":true,\"zstd_header_sha256\":\"${zstd_header_sha256}\",\"zstd_errors_sha256\":\"${zstd_errors_sha256}\",\"zstd_license_sha256\":\"${zstd_license_sha256}\",\"zstd_library_sha256\":\"${zstd_library_sha256}\",\"exit_code\":0,\"binaries\":${binaries}}\n")
