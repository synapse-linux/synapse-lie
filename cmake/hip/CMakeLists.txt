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
add_executable(q2_model ../../tests/q2_model.cpp)
target_link_libraries(q2_model PRIVATE gufo_qwen38_flash_next)
