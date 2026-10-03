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
add_executable(q2_model ../../tests/q2_model.cpp ../../tests/q2_profile_markers.hip)
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
