# SPDX-License-Identifier: MIT
enable_language(HIP)
if(NOT CMAKE_HIP_ARCHITECTURES STREQUAL "gfx1151")
  message(FATAL_ERROR "This qualification targets gfx1151")
endif()
list(APPEND CMAKE_PREFIX_PATH /opt/rocm)
find_package(hip REQUIRED)
find_package(hipblas REQUIRED)
find_package(hipblaslt REQUIRED)
find_package(Threads REQUIRED)
find_path(HIPCUB_INCLUDE_DIR hipcub/hipcub.hpp REQUIRED)
find_path(ROCPRIM_INCLUDE_DIR rocprim/rocprim.hpp REQUIRED)
set(ENGINE_ENABLE_HIP ON)
# Compile the original model target, including executor/device-model changes.
# Keep the qualification executable on the same upstream numerical target.
add_library(gufo_core ALIAS q2_host)
target_link_libraries(q2_host PUBLIC hip::host)
target_compile_definitions(q2_host PUBLIC ENGINE_ENABLE_HIP=1)
target_sources(q2_host PRIVATE ${GUFO_SOURCE}/src/core/hip/hipblaslt_plan_database.cpp)
set(PROJECT_SOURCE_DIR "${GUFO_SOURCE}")
add_subdirectory("${GUFO_SOURCE}/src/models/qwen38_flash_next" qwen)
set(MMQ "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/mmq")
set(Q2_MMQ_ARCHIVE "" CACHE FILEPATH "Verified task-owned unchanged MMQ archive")
if(Q2_MMQ_ARCHIVE)
  if(NOT EXISTS "${Q2_MMQ_ARCHIVE}")
    message(FATAL_ERROR "Verified MMQ archive is missing")
  endif()
  add_library(q2_qualified_mmq STATIC IMPORTED GLOBAL)
  set_target_properties(q2_qualified_mmq PROPERTIES
    IMPORTED_LOCATION "${Q2_MMQ_ARCHIVE}"
    INTERFACE_INCLUDE_DIRECTORIES "${MMQ}"
    INTERFACE_LINK_LIBRARIES "hip::host;roc::hipblas")
  foreach(property IN ITEMS LINK_LIBRARIES INTERFACE_LINK_LIBRARIES)
    get_target_property(links gufo_qwen38_flash_next ${property})
    list(TRANSFORM links REPLACE "^gufo_qwen38_flash_next_mmq$" "q2_qualified_mmq")
    set_target_properties(gufo_qwen38_flash_next PROPERTIES ${property} "${links}")
  endforeach()
endif()
file(READ "${MMQ}/ggml-common.h" table_source)
string(REGEX MATCH "GGML_TABLE_BEGIN\\(uint64_t, iq2xxs_grid, 256\\)([^)]*)GGML_TABLE_END\\(\\)" table_match "${table_source}")
if(NOT table_match)
  message(FATAL_ERROR "IQ2 format codebook was not found")
endif()
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/iq2-grid.inc" "${CMAKE_MATCH_1}")
add_executable(q2_operators ../../tests/q2_operators.cpp)
target_include_directories(q2_operators PRIVATE "${CMAKE_CURRENT_BINARY_DIR}")
target_link_libraries(q2_operators PRIVATE gufo_qwen38_flash_next)
add_test(NAME q2_operators COMMAND q2_operators)
add_executable(q2_iq2_signs EXCLUDE_FROM_ALL ../../tests/q2_iq2_signs.hip)
target_include_directories(q2_iq2_signs PRIVATE "${MMQ}" "${CMAKE_CURRENT_BINARY_DIR}")
target_compile_options(q2_iq2_signs PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next_mmq,COMPILE_OPTIONS>)
target_compile_definitions(q2_iq2_signs PRIVATE GGML_HIP_NO_VMM)
target_link_libraries(q2_iq2_signs PRIVATE gufo_qwen38_flash_next)
find_package(ICU REQUIRED COMPONENTS uc i18n)
find_package(OpenSSL REQUIRED COMPONENTS Crypto)
find_package(PNG REQUIRED)
find_package(JPEG REQUIRED)
find_package(CURL REQUIRED)
find_package(rocblas REQUIRED)
set(MODEL_SUPPORT
  src/core/image.cpp src/core/crypto/sha256.cpp
  src/core/hip/weight_upload.cpp
  src/models/qwen/tokenizer.cpp src/models/qwen/chat_template.cpp
  src/models/qwen/vision/prompt.cpp src/models/qwen/vision/encoder.hip
  src/models/qwen/vision/device_input.hip
  src/models/qwen/hip/kernels/hipblaslt_gemm.hip
  src/models/qwen/hip/kernels/sample.hip)
list(TRANSFORM MODEL_SUPPORT PREPEND "${GUFO_SOURCE}/")
target_sources(q2_host PRIVATE ${MODEL_SUPPORT})
target_include_directories(q2_host SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_host PUBLIC ICU::uc ICU::i18n OpenSSL::Crypto
  PNG::PNG JPEG::JPEG CURL::libcurl roc::rocblas roc::hipblas roc::hipblaslt)
# PROJECT_SOURCE_DIR above belongs to the upstream provider. Qualification
# fixtures remain relative to this CMake file, independently of that override.
get_filename_component(Q2_FIXTURE_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)
set(Q2_MODEL_FIXTURE "${Q2_FIXTURE_ROOT}/tests/q2_model.cpp")
if(Q2_COUNTING_BASELINE)
  if(Q2_CURVE_SERVER OR Q2_ORIGINAL_BASELINE OR Q2_TERMINAL_SERVER)
    message(FATAL_ERROR "Historical counting requires its separate direct-executor target")
  endif()
  file(READ "${Q2_FIXTURE_ROOT}/config/q2-counting-harness.json" Q2_COUNTING_MANIFEST)
  string(JSON Q2_COUNTING_SHA GET "${Q2_COUNTING_MANIFEST}" sha256)
  string(JSON Q2_MARKERS_SHA GET "${Q2_COUNTING_MANIFEST}" markers_sha256)
  set(Q2_MODEL_FIXTURE "${Q2_FIXTURE_ROOT}/experiments/counting-baseline/q2_model.cpp")
  file(SHA256 "${Q2_MODEL_FIXTURE}" Q2_COUNTING_ACTUAL)
  file(SHA256 "${Q2_FIXTURE_ROOT}/tests/q2_profile_markers.hip" Q2_MARKERS_ACTUAL)
  if(NOT Q2_COUNTING_ACTUAL STREQUAL Q2_COUNTING_SHA OR
     NOT Q2_MARKERS_ACTUAL STREQUAL Q2_MARKERS_SHA)
    message(FATAL_ERROR "Historical counting harness identity changed")
  endif()
endif()
add_executable(q2_model "${Q2_MODEL_FIXTURE}" ../../tests/q2_profile_markers.hip)
target_link_libraries(q2_model PRIVATE gufo_qwen38_flash_next)
add_executable(q2_ple EXCLUDE_FROM_ALL ../../tests/q2_ple.cpp)
target_link_libraries(q2_ple PRIVATE gufo_qwen38_flash_next)
add_executable(q2_ple_lookahead EXCLUDE_FROM_ALL ../../tests/q2_ple_lookahead.cpp)
target_link_libraries(q2_ple_lookahead PRIVATE gufo_qwen38_flash_next lie_ple_flow)
# The HC diagnostic uses the exact upstream kernel translation unit and its
# numerical flags, without compiling unrelated MMQ and model executor code.
add_executable(q2_hc ../../tests/q2_hc.cpp
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip")
set_source_files_properties(
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
  PROPERTIES LANGUAGE HIP)
set_source_files_properties(
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  PROPERTIES COMPILE_OPTIONS "-mwavefrontsize64")
target_compile_options(q2_hc PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_hc PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_hc PRIVATE "${GUFO_SOURCE}")
target_include_directories(q2_hc SYSTEM PRIVATE
  ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_hc PRIVATE hip::host)
add_executable(q2_hc_decode_reduce EXCLUDE_FROM_ALL ../../tests/q2_hc_decode_reduce.cpp
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip")
target_compile_options(q2_hc_decode_reduce PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_hc_decode_reduce PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_hc_decode_reduce PRIVATE "${GUFO_SOURCE}")
target_include_directories(q2_hc_decode_reduce SYSTEM PRIVATE
  ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_hc_decode_reduce PRIVATE hip::host)
add_executable(q2_hc_pp ../../tests/q2_hc_pp.cpp
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/blaslt.cpp"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_hc_pp PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_hc_pp PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_hc_pp PRIVATE "${GUFO_SOURCE}")
target_include_directories(q2_hc_pp SYSTEM PRIVATE
  ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_hc_pp PRIVATE hip::host roc::hipblaslt OpenSSL::Crypto)

# Consumer-side narrowing: retained HC oracles plus exact F32-input replay.
add_executable(q2_hc_input EXCLUDE_FROM_ALL ../../tests/q2_hc_input.cpp
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/blaslt.cpp"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_hc_input PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_hc_input PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_hc_input PRIVATE "${GUFO_SOURCE}")
target_include_directories(q2_hc_input SYSTEM PRIVATE
  ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_hc_input PRIVATE hip::host roc::hipblaslt OpenSSL::Crypto)

# Raw-HC Q8 producer and complete shared-expert consumer, direct kernel build.
# New exact Q8 pair lookup versus retained test-only numerical control.
# New SSM row tile with full convolution and required raw-buffer coverage.
add_executable(q2_ssm_row128 EXCLUDE_FROM_ALL ../../tests/q2_ssm_row128.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_ssm_row128 PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_ssm_row128 PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_ssm_row128 PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_ssm_row128 SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_ssm_row128 PRIVATE hip::host OpenSSL::Crypto)
add_executable(q2_q8_halfpair EXCLUDE_FROM_ALL ../../tests/q2_q8_halfpair.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_q8_halfpair PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_q8_halfpair PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_q8_halfpair PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_q8_halfpair SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_q8_halfpair PRIVATE hip::host OpenSSL::Crypto)

add_executable(q2_q8_grouped EXCLUDE_FROM_ALL ../../tests/q2_q8_grouped.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_q8_grouped PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_q8_grouped PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_q8_grouped PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_q8_grouped SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_q8_grouped PRIVATE hip::host OpenSSL::Crypto)

# New IQ2 producer-half stage and literal retained parent numerical control.
add_executable(q2_iq2_halfstage EXCLUDE_FROM_ALL ../../tests/q2_iq2_halfstage.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_iq2_halfstage PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_iq2_halfstage PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_iq2_halfstage PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_iq2_halfstage SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_iq2_halfstage PRIVATE hip::host OpenSSL::Crypto)

# Deferred scaled-Q2 down unpacking; literal retained IQ2 raw-prefetch parent.
add_executable(q2_down_raw_prefetch EXCLUDE_FROM_ALL ../../tests/q2_down_raw_prefetch.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_down_raw_prefetch PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_down_raw_prefetch PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_down_raw_prefetch PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_down_raw_prefetch SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_down_raw_prefetch PRIVATE hip::host OpenSSL::Crypto)

# Fused IQ2 sign/code table plus exhaustive format/whole-output replay.
# Exact 1KiB IQ2 high-byte sign masks, literal measured-parent control.
# Persistent Q8-derived F16 mirrors with original single K16 accumulation.
add_executable(q2_expert_cache EXCLUDE_FROM_ALL ../../tests/q2_expert_cache.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_expert_cache PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_expert_cache PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_expert_cache PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_expert_cache SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_expert_cache PRIVATE hip::host OpenSSL::Crypto)

add_executable(q2_compressed_cache EXCLUDE_FROM_ALL ../../tests/q2_compressed_cache.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_compressed_cache PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_compressed_cache PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_compressed_cache PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_compressed_cache SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_compressed_cache PRIVATE hip::host OpenSSL::Crypto)

add_executable(q2_q8_mirror EXCLUDE_FROM_ALL ../../tests/q2_q8_mirror.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_q8_mirror PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_q8_mirror PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_q8_mirror PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_q8_mirror SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_q8_mirror PRIVATE hip::host OpenSSL::Crypto)

add_executable(q2_iq2_sign_mask EXCLUDE_FROM_ALL ../../tests/q2_iq2_sign_mask.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_iq2_sign_mask PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_iq2_sign_mask PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_iq2_sign_mask PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_iq2_sign_mask SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_iq2_sign_mask PRIVATE hip::host OpenSSL::Crypto)

add_executable(q2_iq2_fused_grid EXCLUDE_FROM_ALL ../../tests/q2_iq2_fused_grid.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_iq2_fused_grid PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_iq2_fused_grid PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_iq2_fused_grid PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_iq2_fused_grid SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_iq2_fused_grid PRIVATE hip::host OpenSSL::Crypto)

# Q2 fixed-width integer consumer geometry; literal measured eight-value control.
add_executable(q2_half_fixed_width EXCLUDE_FROM_ALL ../../tests/q2_half_fixed_width.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_half_fixed_width PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_half_fixed_width PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_half_fixed_width PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_half_fixed_width SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_half_fixed_width PRIVATE hip::host OpenSSL::Crypto)

# Q2 eight-value half consumer; literal measured four-value parent control.
add_executable(q2_half_consumer_eight EXCLUDE_FROM_ALL ../../tests/q2_half_consumer_eight.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_half_consumer_eight PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_half_consumer_eight PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_half_consumer_eight PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_half_consumer_eight SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_half_consumer_eight PRIVATE hip::host OpenSSL::Crypto)

# Q2 register transpose; literal retained1574 LDS vector epilogue.
add_executable(q2_down_register_scatter EXCLUDE_FROM_ALL ../../tests/q2_down_register_scatter.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_down_register_scatter PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_down_register_scatter PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_down_register_scatter PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_down_register_scatter SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_down_register_scatter PRIVATE hip::host OpenSSL::Crypto)

# SSM row-group4 composition; literal retained1580 projection control.
add_executable(q2_ssm_row_group EXCLUDE_FROM_ALL ../../tests/q2_ssm_row_group.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_ssm_row_group PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_ssm_row_group PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_ssm_row_group PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_ssm_row_group SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_ssm_row_group PRIVATE hip::host OpenSSL::Crypto)

# Four shared-down arms separate persistent F16 weights from fixed-shape addressing.
add_executable(q2_shared_down_mirror EXCLUDE_FROM_ALL ../../tests/q2_shared_down_mirror.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_shared_down_mirror PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_shared_down_mirror PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_shared_down_mirror PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_shared_down_mirror SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_shared_down_mirror PRIVATE hip::host OpenSSL::Crypto)

# Compact-LDS and alternating-slot SSM; retained1580 control and resource limits.
add_executable(q2_ssm_compact_lds EXCLUDE_FROM_ALL ../../tests/q2_ssm_compact_lds.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_ssm_compact_lds PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_ssm_compact_lds PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_ssm_compact_lds PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_ssm_compact_lds SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_ssm_compact_lds PRIVATE hip::host OpenSSL::Crypto)

# Q2 aligned eight-half stores; literal measured half-pair parent control.
add_executable(q2_down_half_vector EXCLUDE_FROM_ALL ../../tests/q2_down_half_vector.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_down_half_vector PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_down_half_vector PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_down_half_vector PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_down_half_vector SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_down_half_vector PRIVATE hip::host OpenSSL::Crypto)

# Q2 paired half stores; literal measured half-storage parent control.
add_executable(q2_down_half_pair EXCLUDE_FROM_ALL ../../tests/q2_down_half_pair.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_down_half_pair PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_down_half_pair PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_down_half_pair PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_down_half_pair SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_down_half_pair PRIVATE hip::host OpenSSL::Crypto)

# Q2 half-output storage and direct ordered combine; retained F32 controls.
add_executable(q2_down_half_storage EXCLUDE_FROM_ALL ../../tests/q2_down_half_storage.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_down_half_storage PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_down_half_storage PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_down_half_storage PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_down_half_storage SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_down_half_storage PRIVATE hip::host OpenSSL::Crypto)

# Q2 down unread-store suppression; literal live-compose parent control.
add_executable(q2_down_live_stage EXCLUDE_FROM_ALL ../../tests/q2_down_live_stage.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_down_live_stage PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_down_live_stage PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_down_live_stage PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_down_live_stage SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_down_live_stage PRIVATE hip::host OpenSSL::Crypto)

# Q2 down output-row reuse; literal lane parent control.
add_executable(q2_down_output_reuse EXCLUDE_FROM_ALL ../../tests/q2_down_output_reuse.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_down_output_reuse PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_down_output_reuse PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_down_output_reuse PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_down_output_reuse SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_down_output_reuse PRIVATE hip::host OpenSSL::Crypto)

# IQ2 paired-row reuse and wave-local epilogue; literal lane parent control.
add_executable(q2_iq2_wide_pair EXCLUDE_FROM_ALL ../../tests/q2_iq2_wide_pair.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_iq2_wide_pair PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_iq2_wide_pair PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_iq2_wide_pair PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_iq2_wide_pair SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_iq2_wide_pair PRIVATE hip::host OpenSSL::Crypto)

add_executable(q2_iq2_four_wave EXCLUDE_FROM_ALL ../../tests/q2_iq2_four_wave.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_iq2_four_wave PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_iq2_four_wave PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_iq2_four_wave PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_iq2_four_wave SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_iq2_four_wave PRIVATE hip::host OpenSSL::Crypto)

# Four-lane compact IQ2 producer ownership; unchanged literal parent control.
add_executable(q2_iq2_lane_commit EXCLUDE_FROM_ALL ../../tests/q2_iq2_lane_commit.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_iq2_lane_commit PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_iq2_lane_commit PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_iq2_lane_commit PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_iq2_lane_commit SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_iq2_lane_commit PRIVATE hip::host OpenSSL::Crypto)

# Short-expert maps share the measured parent's unchanged numerical kernels.
add_executable(q2_iq2_short_tiles_check EXCLUDE_FROM_ALL ../../tests/q2_iq2_short_tiles.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_iq2_short_tiles_check PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_iq2_short_tiles_check PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_iq2_short_tiles_check PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_iq2_short_tiles_check SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_iq2_short_tiles_check PRIVATE
  q2_iq2_short_tiles iq2_mixed_tiles hip::host OpenSSL::Crypto)

add_executable(q2_iq2_tail16_check EXCLUDE_FROM_ALL ../../tests/q2_iq2_tail16.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_iq2_tail16_check PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_iq2_tail16_check PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_iq2_tail16_check PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_iq2_tail16_check SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_iq2_tail16_check PRIVATE
  q2_iq2_tail16 iq2_mixed_tiles hip::host OpenSSL::Crypto)

# IQ2 register-stage candidate against the frozen literal parent.
add_executable(q2_iq2_register_stage_check EXCLUDE_FROM_ALL ../../tests/q2_iq2_register_stage.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_iq2_register_stage_check PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_iq2_register_stage_check PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_iq2_register_stage_check PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_iq2_register_stage_check SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_iq2_register_stage_check PRIVATE
  iq2_mixed_tiles hip::host OpenSSL::Crypto)

add_executable(q2_iq2_half_sign_arithmetic_check EXCLUDE_FROM_ALL ../../tests/q2_iq2_half_sign_arithmetic.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_iq2_half_sign_arithmetic_check PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_iq2_half_sign_arithmetic_check PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_iq2_half_sign_arithmetic_check PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_iq2_half_sign_arithmetic_check SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_iq2_half_sign_arithmetic_check PRIVATE
  iq2_mixed_tiles hip::host OpenSSL::Crypto)

add_executable(q2_iq2_table_lds_check EXCLUDE_FROM_ALL ../../tests/q2_iq2_table_lds.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_iq2_table_lds_check PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_iq2_table_lds_check PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_iq2_table_lds_check PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_iq2_table_lds_check SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_iq2_table_lds_check PRIVATE
  iq2_mixed_tiles hip::host OpenSSL::Crypto)

add_executable(q2_iq2_dpp_commit_check EXCLUDE_FROM_ALL ../../tests/q2_iq2_dpp_commit.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_iq2_dpp_commit_check PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_iq2_dpp_commit_check PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_iq2_dpp_commit_check PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_iq2_dpp_commit_check SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_iq2_dpp_commit_check PRIVATE
  iq2_mixed_tiles hip::host OpenSSL::Crypto)

add_executable(q2_iq2_fixed_bounds_check EXCLUDE_FROM_ALL ../../tests/q2_iq2_fixed_bounds.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_iq2_fixed_bounds_check PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_iq2_fixed_bounds_check PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_iq2_fixed_bounds_check PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_iq2_fixed_bounds_check SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_iq2_fixed_bounds_check PRIVATE
  iq2_mixed_tiles hip::host OpenSSL::Crypto)

# Whole640 producer/packing drafts; the retained provider is unchanged.
add_executable(q2_iq2_whole640_check EXCLUDE_FROM_ALL ../../tests/q2_iq2_whole640.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip")
target_compile_options(q2_iq2_whole640_check PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_iq2_whole640_check PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_iq2_whole640_check PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}"
  "${CMAKE_CURRENT_BINARY_DIR}")
target_include_directories(q2_iq2_whole640_check SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_iq2_whole640_check PRIVATE hip::host)

# New sixteen-wave whole640 drafts; the retained provider is unchanged.
add_executable(q2_iq2_whole640_wave16_check EXCLUDE_FROM_ALL ../../tests/q2_iq2_whole640_wave16.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip")
target_compile_options(q2_iq2_whole640_wave16_check PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_iq2_whole640_wave16_check PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_iq2_whole640_wave16_check PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}"
  "${CMAKE_CURRENT_BINARY_DIR}")
target_include_directories(q2_iq2_whole640_wave16_check SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_iq2_whole640_wave16_check PRIVATE hip::host)

# Integrated producer, selective packing and unchanged down consumer.
add_executable(q2_iq2_whole640_chain_check EXCLUDE_FROM_ALL ../../tests/q2_iq2_whole640_chain.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_iq2_whole640_chain_check PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_iq2_whole640_chain_check PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_iq2_whole640_chain_check PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_iq2_whole640_chain_check SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_iq2_whole640_chain_check PRIVATE q2_iq2_whole640_tiles iq2_mixed_tiles hip::host OpenSSL::Crypto)

# New HC-up arithmetic candidate, with the unchanged retained provider as control.
add_executable(q2_hc_up_short_chain_check EXCLUDE_FROM_ALL ../../tests/q2_hc_up_short_chain.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_hc_up_short_chain_check PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_hc_up_short_chain_check PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_hc_up_short_chain_check PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_hc_up_short_chain_check SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_hc_up_short_chain_check PRIVATE hip::host OpenSSL::Crypto)

add_executable(q2_ssm_resident_check EXCLUDE_FROM_ALL ../../tests/q2_ssm_resident.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_ssm_resident_check PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_ssm_resident_check PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_ssm_resident_check PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_ssm_resident_check SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_ssm_resident_check PRIVATE hip::host OpenSSL::Crypto)

add_executable(q2_hc_down_direct_weight_check EXCLUDE_FROM_ALL ../../tests/q2_hc_down_direct_weight.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_hc_down_direct_weight_check PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_hc_down_direct_weight_check PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_hc_down_direct_weight_check PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_hc_down_direct_weight_check SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_hc_down_direct_weight_check PRIVATE hip::host OpenSSL::Crypto)

# Only the scalar Q8 consumer bodies; no model executor or unrelated MMQ build.
add_executable(q2_decode_q8_rows4_check EXCLUDE_FROM_ALL ../../tests/q2_decode_q8_rows4.hip
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
set_target_properties(q2_decode_q8_rows4_check PROPERTIES HIP_STANDARD 20 CXX_STANDARD 20)
target_compile_options(q2_decode_q8_rows4_check PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next_mmq,COMPILE_OPTIONS>)
target_compile_definitions(q2_decode_q8_rows4_check PRIVATE GGML_HIP_NO_VMM)
target_include_directories(q2_decode_q8_rows4_check PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}" "${MMQ}")
target_link_libraries(q2_decode_q8_rows4_check PRIVATE hip::host OpenSSL::Crypto)

# Sparse attention capacity, against the unchanged GPU fallback and FP64 formula.
add_executable(q2_attention_capacity_check EXCLUDE_FROM_ALL ../../tests/q2_attention_capacity_gpu.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip")
target_compile_options(q2_attention_capacity_check PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_attention_capacity_check PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_attention_capacity_check PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_attention_capacity_check SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_attention_capacity_check PRIVATE hip::host)

# Active Q2 down fixed contract; frozen literal half-output control.
add_executable(q2_down_fixed_contract_check EXCLUDE_FROM_ALL ../../tests/q2_down_fixed_contract.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_down_fixed_contract_check PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_down_fixed_contract_check PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_down_fixed_contract_check PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_down_fixed_contract_check SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_down_fixed_contract_check PRIVATE
  hip::host OpenSSL::Crypto)

# Active Q2 down fixed bounds; frozen literal half-output control.
add_executable(q2_down_fixed_bounds_check EXCLUDE_FROM_ALL ../../tests/q2_down_fixed_bounds.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_down_fixed_bounds_check PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_down_fixed_bounds_check PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_down_fixed_bounds_check PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_down_fixed_bounds_check SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_down_fixed_bounds_check PRIVATE
  hip::host OpenSSL::Crypto)

# Active Q2 down register palette; frozen literal half-output control.
add_executable(q2_down_register_palette_check EXCLUDE_FROM_ALL ../../tests/q2_down_register_palette.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_down_register_palette_check PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_down_register_palette_check PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_down_register_palette_check PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_down_register_palette_check SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_down_register_palette_check PRIVATE
  hip::host OpenSSL::Crypto)

# Bounded IQ2 commits; literal measured raw-prefetch parent control.
add_executable(q2_iq2_slice_commit EXCLUDE_FROM_ALL ../../tests/q2_iq2_slice_commit.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_iq2_slice_commit PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_iq2_slice_commit PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_iq2_slice_commit PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_iq2_slice_commit SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_iq2_slice_commit PRIVATE hip::host OpenSSL::Crypto)

# Deferred IQ2 expansion with raw prefetch; literal compact-parent control.
add_executable(q2_iq2_raw_prefetch EXCLUDE_FROM_ALL ../../tests/q2_iq2_raw_prefetch.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_iq2_raw_prefetch PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_iq2_raw_prefetch PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_iq2_raw_prefetch PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_iq2_raw_prefetch SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_iq2_raw_prefetch PRIVATE hip::host OpenSSL::Crypto)

# Compact half-byte IQ2 and exhaustive scale-bit replay; literal parent control.
add_executable(q2_iq2_halfbyte EXCLUDE_FROM_ALL ../../tests/q2_iq2_halfbyte.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_iq2_halfbyte PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_iq2_halfbyte PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_iq2_halfbyte PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_iq2_halfbyte SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_iq2_halfbyte PRIVATE hip::host OpenSSL::Crypto)

add_executable(q2_shared_q8_producer EXCLUDE_FROM_ALL ../../tests/q2_shared_q8_producer.cpp
  ../../tests/q2_shared_q8_scalar_oracle.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/blaslt.cpp"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_shared_q8_producer PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_shared_q8_producer PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_shared_q8_producer PRIVATE "${GUFO_SOURCE}")
target_include_directories(q2_shared_q8_producer SYSTEM PRIVATE
  ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_shared_q8_producer PRIVATE hip::host roc::hipblaslt OpenSSL::Crypto)

# Unchanged independent format oracle; replay only saved arrays, no provider kernels.
add_executable(q2_shared_q8_oracle_replay EXCLUDE_FROM_ALL
  ../../tests/q2_shared_q8_oracle_replay.cpp ../../tests/q2_shared_q8_scalar_oracle.hip)
target_compile_options(q2_shared_q8_oracle_replay PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_link_libraries(q2_shared_q8_oracle_replay PRIVATE hip::host)

# Preserved norm controls and paired producer, both using the actual HC library.
add_executable(q2_hc_library_norm EXCLUDE_FROM_ALL ../../tests/q2_hc_library_norm.cpp
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/blaslt.cpp")
target_compile_options(q2_hc_library_norm PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_hc_library_norm PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_hc_library_norm PRIVATE "${GUFO_SOURCE}")
target_include_directories(q2_hc_library_norm SYSTEM PRIVATE
  ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_hc_library_norm PRIVATE hip::host roc::hipblaslt OpenSSL::Crypto)

# Exact retained library recipe plus the new native HC-down candidate.
add_executable(q2_hc_bk256 EXCLUDE_FROM_ALL ../../tests/q2_hc_bk256.cpp
  ../../experiments/q2_hc_blaslt_control.cpp
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/blaslt.cpp")
target_compile_options(q2_hc_bk256 PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_hc_bk256 PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_hc_bk256 PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_hc_bk256 SYSTEM PRIVATE
  ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_hc_bk256 PRIVATE hip::host roc::hipblaslt OpenSSL::Crypto)

# Same original norm/narrowing with native or library HC down on ragged rows.
add_executable(q2_hc_library_ragged EXCLUDE_FROM_ALL ../../tests/q2_hc_library_ragged.cpp
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/blaslt.cpp")
target_compile_options(q2_hc_library_ragged PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_hc_library_ragged PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_hc_library_ragged PRIVATE "${GUFO_SOURCE}")
target_include_directories(q2_hc_library_ragged SYSTEM PRIVATE
  ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_hc_library_ragged PRIVATE hip::host roc::hipblaslt OpenSSL::Crypto)

# Only built for experimental sources exposing the compensated routed entry.
add_executable(q2_routed EXCLUDE_FROM_ALL ../../tests/q2_routed.cpp
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip")
target_compile_options(q2_routed PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_routed PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_routed PRIVATE "${GUFO_SOURCE}" "${CMAKE_CURRENT_BINARY_DIR}")
target_include_directories(q2_routed SYSTEM PRIVATE
  ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_routed PRIVATE hip::host)

# Only built for experimental sources exposing the compensated routed entry.
add_executable(q2_iq2_pair EXCLUDE_FROM_ALL ../../tests/q2_iq2_pair.cpp
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip")
target_compile_options(q2_iq2_pair PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_iq2_pair PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_iq2_pair PRIVATE "${GUFO_SOURCE}" "${CMAKE_CURRENT_BINARY_DIR}")
target_include_directories(q2_iq2_pair SYSTEM PRIVATE
  ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_iq2_pair PRIVATE hip::host)

add_executable(q2_iq2_wmma_signs EXCLUDE_FROM_ALL ../../tests/q2_iq2_wmma_signs.cpp
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_iq2_wmma_signs PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_iq2_wmma_signs PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_iq2_wmma_signs PRIVATE "${GUFO_SOURCE}" "${CMAKE_CURRENT_BINARY_DIR}")
target_include_directories(q2_iq2_wmma_signs SYSTEM PRIVATE
  ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_iq2_wmma_signs PRIVATE hip::host OpenSSL::Crypto)

add_executable(q2_iq2_live_epilogue EXCLUDE_FROM_ALL ../../tests/q2_iq2_live_epilogue.cpp
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_iq2_live_epilogue PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_iq2_live_epilogue PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_iq2_live_epilogue PRIVATE "${GUFO_SOURCE}" "${CMAKE_CURRENT_BINARY_DIR}")
target_include_directories(q2_iq2_live_epilogue SYSTEM PRIVATE
  ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_iq2_live_epilogue PRIVATE hip::host OpenSSL::Crypto)

add_executable(q2_iq2_mixed_tiles EXCLUDE_FROM_ALL ../../tests/q2_iq2_mixed_tiles.cpp
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_iq2_mixed_tiles PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_iq2_mixed_tiles PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_iq2_mixed_tiles PRIVATE "${GUFO_SOURCE}" "${CMAKE_CURRENT_BINARY_DIR}")
target_include_directories(q2_iq2_mixed_tiles SYSTEM PRIVATE
  ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_iq2_mixed_tiles PRIVATE iq2_mixed_tiles hip::host OpenSSL::Crypto)

# Packed activation experiment: original independent cases plus exact replay.
add_executable(q2_packed EXCLUDE_FROM_ALL ../../tests/q2_packed.cpp
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip")
target_compile_options(q2_packed PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_packed PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_packed PRIVATE "${GUFO_SOURCE}" "${CMAKE_CURRENT_BINARY_DIR}")
target_include_directories(q2_packed SYSTEM PRIVATE
  ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_packed PRIVATE hip::host)

# Full original-shape synthetic down projection, with both input paths.
add_executable(q2_packed_bench EXCLUDE_FROM_ALL ../../tests/q2_packed_bench.cpp
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_packed_bench PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_packed_bench PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_packed_bench PRIVATE "${GUFO_SOURCE}" "${CMAKE_CURRENT_BINARY_DIR}")
target_include_directories(q2_packed_bench SYSTEM PRIVATE
  ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_packed_bench PRIVATE hip::host OpenSSL::Crypto)

add_executable(q2_shared_fork EXCLUDE_FROM_ALL ../../tests/q2_shared_fork.cpp
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_shared_fork PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_shared_fork PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_shared_fork PRIVATE "${GUFO_SOURCE}" "${CMAKE_CURRENT_BINARY_DIR}")
target_include_directories(q2_shared_fork SYSTEM PRIVATE
  ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_shared_fork PRIVATE lie_gpu_fork hip::host OpenSSL::Crypto)

add_executable(q2_scaled EXCLUDE_FROM_ALL ../../tests/q2_scaled.cpp
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_scaled PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_scaled PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_scaled PRIVATE "${GUFO_SOURCE}" "${CMAKE_CURRENT_BINARY_DIR}")
target_include_directories(q2_scaled SYSTEM PRIVATE
  ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_scaled PRIVATE hip::host OpenSSL::Crypto)

add_executable(q2_scaled_row_reuse EXCLUDE_FROM_ALL ../../tests/q2_scaled_row_reuse.cpp
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_scaled_row_reuse PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_scaled_row_reuse PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_scaled_row_reuse PRIVATE "${GUFO_SOURCE}" "${CMAKE_CURRENT_BINARY_DIR}")
target_include_directories(q2_scaled_row_reuse SYSTEM PRIVATE
  ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_scaled_row_reuse PRIVATE hip::host OpenSSL::Crypto)

add_executable(q2_scaled_tiles EXCLUDE_FROM_ALL ../../tests/q2_scaled_tiles.cpp
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_scaled_tiles PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_scaled_tiles PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_scaled_tiles PRIVATE "${GUFO_SOURCE}" "${CMAKE_CURRENT_BINARY_DIR}")
target_include_directories(q2_scaled_tiles SYSTEM PRIVATE
  ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_scaled_tiles PRIVATE hip::host OpenSSL::Crypto)

# Component-only F32/F16 conversion, including its unchanged GEMM consumers.
add_executable(q2_narrow_vector EXCLUDE_FROM_ALL ../../tests/q2_narrow_vector.cpp
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip")
target_compile_options(q2_narrow_vector PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_narrow_vector PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_narrow_vector PRIVATE "${GUFO_SOURCE}")
target_include_directories(q2_narrow_vector SYSTEM PRIVATE
  ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_narrow_vector PRIVATE hip::host)

# Original F16 HC up projection fused with the F32 mixer and half output.
add_executable(q2_hc_up_fused EXCLUDE_FROM_ALL ../../tests/q2_hc_up_fused.cpp
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip")
target_compile_options(q2_hc_up_fused PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_hc_up_fused PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_hc_up_fused PRIVATE "${GUFO_SOURCE}")
target_include_directories(q2_hc_up_fused SYSTEM PRIVATE
  ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_hc_up_fused PRIVATE hip::host)

# Original HC up checks plus larger-tile chain-pair comparison and timings.
add_executable(q2_hc_up_chains EXCLUDE_FROM_ALL ../../tests/q2_hc_up_chains.cpp
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip")
target_compile_options(q2_hc_up_chains PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_hc_up_chains PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_hc_up_chains PRIVATE "${GUFO_SOURCE}")
target_include_directories(q2_hc_up_chains SYSTEM PRIVATE
  ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_hc_up_chains PRIVATE hip::host)

# Original F32 MoE outputs combined with HC residual/norm in one launch.
add_executable(q2_hc_moe_fused EXCLUDE_FROM_ALL ../../tests/q2_hc_moe_fused.cpp
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip")
target_compile_options(q2_hc_moe_fused PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_hc_moe_fused PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_hc_moe_fused PRIVATE "${GUFO_SOURCE}")
target_include_directories(q2_hc_moe_fused SYSTEM PRIVATE
  ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_hc_moe_fused PRIVATE hip::host)

# Preserve the F32 HC norm and emit the consumer's original F16 copy.
add_executable(q2_hc_norm_half EXCLUDE_FROM_ALL ../../tests/q2_hc_norm_half.cpp
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip")
target_compile_options(q2_hc_norm_half PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_hc_norm_half PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_hc_norm_half PRIVATE "${GUFO_SOURCE}")
target_include_directories(q2_hc_norm_half SYSTEM PRIVATE
  ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_hc_norm_half PRIVATE hip::host)

# Time complete HC producer/narrowing/down sequences with exact paired replay.
add_executable(q2_hc_sequence EXCLUDE_FROM_ALL ../../tests/q2_hc_sequence.cpp
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip")
target_compile_options(q2_hc_sequence PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_hc_sequence PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_hc_sequence PRIVATE "${GUFO_SOURCE}")
target_include_directories(q2_hc_sequence SYSTEM PRIVATE
  ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_hc_sequence PRIVATE hip::host OpenSSL::Crypto)

# Time complete HC cycles without materializing the F32 normalized tensor.
add_executable(q2_hc_deferred_norm EXCLUDE_FROM_ALL ../../tests/q2_hc_deferred_norm.cpp
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip")
target_compile_options(q2_hc_deferred_norm PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_hc_deferred_norm PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_hc_deferred_norm PRIVATE "${GUFO_SOURCE}")
target_include_directories(q2_hc_deferred_norm SYSTEM PRIVATE
  ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_hc_deferred_norm PRIVATE hip::host OpenSSL::Crypto)


# Ordered Q8 K16 phases; literal retained IQ2 raw-prefetch parent.
add_executable(q2_q8_k16_phases EXCLUDE_FROM_ALL ../../tests/q2_q8_k16_phases.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_q8_k16_phases PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_q8_k16_phases PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_q8_k16_phases PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_q8_k16_phases SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_q8_k16_phases PRIVATE hip::host OpenSSL::Crypto)

# Ordered Q8 aligned pair; literal retained IQ2 raw-prefetch parent.
add_executable(q2_q8_aligned_pair EXCLUDE_FROM_ALL ../../tests/q2_q8_aligned_pair.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_q8_aligned_pair PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_q8_aligned_pair PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_q8_aligned_pair PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_q8_aligned_pair SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_q8_aligned_pair PRIVATE hip::host OpenSSL::Crypto)

# Shared Q8 pair, production W8A8 reference and complete down cycle.
add_executable(q2_shared_q8_pair EXCLUDE_FROM_ALL ../../tests/q2_shared_q8_pair.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_shared_q8_pair PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_shared_q8_pair PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_shared_q8_pair PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_shared_q8_pair SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_shared_q8_pair PRIVATE hip::host OpenSSL::Crypto)

# Wave-owned scaled packing, retained row control and unchanged Q2 down cycle.
add_executable(q2_scaled_wave_pack EXCLUDE_FROM_ALL ../../tests/q2_scaled_wave_pack.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_scaled_wave_pack PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_scaled_wave_pack PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_scaled_wave_pack PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_scaled_wave_pack SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_scaled_wave_pack PRIVATE hip::host OpenSSL::Crypto)

# Expert-ordered packing and full Q2 down cycle.
add_executable(q2_scaled_expert_order EXCLUDE_FROM_ALL ../../tests/q2_scaled_expert_order.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_scaled_expert_order PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_scaled_expert_order PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_scaled_expert_order PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_scaled_expert_order SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_scaled_expert_order PRIVATE hip::host OpenSSL::Crypto)

# Compact expert producer, original packing and ordered down output.
add_executable(q2_compact_expert_chain EXCLUDE_FROM_ALL ../../tests/q2_compact_expert_chain.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_compact_expert_chain PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_compact_expert_chain PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_compact_expert_chain PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_compact_expert_chain SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_compact_expert_chain PRIVATE hip::host OpenSSL::Crypto)

# Original F16 chain versus producer-Q8/integer-down, plus unchanged MMQ
# format/reference calls and an independent sampled FP64 affine operator.
add_executable(q2_producer_q8 EXCLUDE_FROM_ALL ../../tests/q2_producer_q8.hip
  ../../tests/q2_producer_q8_reference.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_producer_q8 PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_producer_q8 PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1 GGML_HIP_NO_VMM)
target_include_directories(q2_producer_q8 PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}" "${MMQ}")
target_include_directories(q2_producer_q8 SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_producer_q8 PRIVATE gufo_qwen38_flash_next_mmq hip::host OpenSSL::Crypto)

# Complete mix/injection reuse, built directly from the retained parent.
add_executable(q2_hc_inject_reuse EXCLUDE_FROM_ALL ../../tests/q2_hc_inject_reuse.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_hc_inject_reuse PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_hc_inject_reuse PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_hc_inject_reuse PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_hc_inject_reuse SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_hc_inject_reuse PRIVATE hip::host OpenSSL::Crypto)

# Complete ordinary/MoE RMS owner comparison against the retained parent.
add_executable(q2_hc_norm_owner EXCLUDE_FROM_ALL ../../tests/q2_hc_norm_owner.hip
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/kernels/rocm/w8a8_wave64.hip"
  "${GUFO_SOURCE}/src/core/crypto/sha256.cpp")
target_compile_options(q2_hc_norm_owner PRIVATE
  $<TARGET_PROPERTY:gufo_qwen38_flash_next,COMPILE_OPTIONS>)
target_compile_definitions(q2_hc_norm_owner PRIVATE QFN_ROCM_BUILD=1 ENGINE_ENABLE_HIP=1)
target_include_directories(q2_hc_norm_owner PRIVATE "${GUFO_SOURCE}" "${Q2_FIXTURE_ROOT}")
target_include_directories(q2_hc_norm_owner SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_link_libraries(q2_hc_norm_owner PRIVATE hip::host OpenSSL::Crypto)
