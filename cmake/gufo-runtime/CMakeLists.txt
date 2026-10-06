# SPDX-License-Identifier: MIT
# LIE-owned build scope, verified pinned source/variant. Not upstream release build.
cmake_minimum_required(VERSION 3.21)
include("${CMAKE_CURRENT_LIST_DIR}/../hip-target.cmake")
if(DEFINED CMAKE_HIP_ARCHITECTURES AND NOT CMAKE_HIP_ARCHITECTURES STREQUAL LIE_HIP_ARCHITECTURE)
  message(FATAL_ERROR "CMAKE_HIP_ARCHITECTURES must match LIE_HIP_ARCHITECTURE")
endif()
set(CMAKE_HIP_ARCHITECTURES "${LIE_HIP_ARCHITECTURE}" CACHE STRING "Explicit single HIP target")
project(lie_gufo_subset LANGUAGES C CXX HIP)
set(CMAKE_C_STANDARD 17)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)
option(LIE_C17_SAMPLING "Use owned C17 sampling and byte/numeric/Unicode/vocabulary grammar runtimes" ON)
option(LIE_VISION_WEIGHT_DECODE "Decode F16/Q8 vision weights once into BF16" ON)
option(LIE_DIRECTIONAL_STEERING "Build owned directional activation operators" ON)
get_filename_component(LIE_ROOT "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_HIP_STANDARD 20)
set(CMAKE_HIP_STANDARD_REQUIRED ON)
if(NOT IS_DIRECTORY "${GUFO_SOURCE}/src/models/qwen38_flash_next")
  message(FATAL_ERROR "GUFO_SOURCE must be the verified pinned source directory")
endif()
if(LIE_DIRECTIONAL_STEERING)
  file(READ "${GUFO_SOURCE}/src/models/qwen38_flash_next/engine.hpp" lie_engine_header)
  if(NOT lie_engine_header MATCHES "#define LIE_GUFO_DIRECTIONAL_STEERING 1")
    message(FATAL_ERROR "Directional steering requires the verified state-access variant")
  endif()
  unset(lie_engine_header)
endif()
list(APPEND CMAKE_PREFIX_PATH /opt/rocm)
find_package(hip REQUIRED)
find_package(hipblas REQUIRED)
find_package(hipblaslt REQUIRED)
find_package(rocblas REQUIRED)
find_package(ICU REQUIRED COMPONENTS uc i18n)
find_package(OpenSSL REQUIRED COMPONENTS Crypto)
find_package(PNG REQUIRED)
find_package(JPEG REQUIRED)
find_package(CURL REQUIRED)
find_package(Threads REQUIRED)
find_path(HIPCUB_INCLUDE_DIR hipcub/hipcub.hpp REQUIRED)
find_path(ROCPRIM_INCLUDE_DIR rocprim/rocprim.hpp REQUIRED)
# These required Qwen files do not use rocWMMA. No fabricated include path.
set(CORE
  src/core/image.cpp src/core/crypto/sha256.cpp src/core/gguf_reader.cpp
  src/core/gguf_identity.cpp src/core/json_constraint.cpp
  src/core/json_schema_lexeme.cpp src/core/json_schema_regex.cpp src/core/sampling.cpp
  src/core/quant/ggml_dequant.cpp src/core/hip/weight_upload.cpp
  src/core/hip/hipblaslt_plan_database.cpp src/core/speculative/speculative_verifier.cpp
  src/models/qwen/tokenizer.cpp src/models/qwen/chat_template.cpp
  src/models/qwen/vision/prompt.cpp src/models/qwen/vision/encoder.hip
  src/models/qwen/vision/device_input.hip
  src/models/qwen/hip/kernels/hipblaslt_gemm.hip
  src/models/qwen/hip/kernels/sample.hip)
list(TRANSFORM CORE PREPEND "${GUFO_SOURCE}/")
list(APPEND CORE "${LIE_ROOT}/src/sampling.c" "${LIE_ROOT}/src/sampling_history.c" "${LIE_ROOT}/src/sampling_distribution.c" "${LIE_ROOT}/src/grammar.c" "${LIE_ROOT}/src/grammar_builder.c" "${LIE_ROOT}/src/schema_transform.c" "${LIE_ROOT}/src/schema_values.c" "${LIE_ROOT}/src/grammar_cache.c" "${LIE_ROOT}/src/ordered_cache.c" "${LIE_ROOT}/src/grammar_composition.c" "${LIE_ROOT}/src/binary64.c" "${LIE_ROOT}/src/json_parse.c" "${LIE_ROOT}/src/json_value.c" "${LIE_ROOT}/src/json_store.c" "${LIE_ROOT}/src/schema_memo.c" "${LIE_ROOT}/src/schema_dispatch.c" "${LIE_ROOT}/src/schema_visit.c" "${LIE_ROOT}/src/schema_root.c" "${LIE_ROOT}/src/schema_compile.c" "${LIE_ROOT}/src/schema_compiler.c" "${LIE_ROOT}/src/schema_arena.c" "${LIE_ROOT}/src/schema_string.c" "${LIE_ROOT}/src/schema_frontend.c" "${LIE_ROOT}/src/schema_body.c" "${LIE_ROOT}/src/schema_number.c" "${LIE_ROOT}/src/schema_integer.c" "${LIE_ROOT}/src/schema_format.c" "${LIE_ROOT}/src/grammar_number.c" "${LIE_ROOT}/src/grammar_regex.c" "${LIE_ROOT}/src/grammar_string.c" "${LIE_ROOT}/src/grammar_lexeme.c" "${LIE_ROOT}/src/grammar_vocabulary.c" "${LIE_ROOT}/src/grammar_regex_compile.c" "${LIE_ROOT}/src/grammar_regex_parse.c" "${LIE_ROOT}/src/grammar_unicode.c")
list(APPEND CORE "${LIE_ROOT}/src/weight_decode.c")
list(APPEND CORE "${LIE_ROOT}/src/steering_activation.c")
add_library(gufo_core STATIC ${CORE})
target_include_directories(gufo_core PUBLIC "${GUFO_SOURCE}")
target_include_directories(gufo_core PUBLIC "${LIE_ROOT}/include")
include("${LIE_ROOT}/cmake/provider/Source.cmake")
lie_verify_binary64_vendor("${LIE_ROOT}")
target_include_directories(gufo_core PRIVATE "${LIE_ROOT}/adapters" "${LIE_ROOT}/third_party/ryu")
target_include_directories(gufo_core SYSTEM PRIVATE ${HIPCUB_INCLUDE_DIR} ${ROCPRIM_INCLUDE_DIR})
target_compile_definitions(gufo_core PUBLIC ENGINE_ENABLE_HIP=1)
target_compile_definitions(gufo_core PUBLIC LIE_C17_SAMPLING=$<BOOL:${LIE_C17_SAMPLING}>)
target_compile_definitions(gufo_core PUBLIC LIE_VISION_WEIGHT_DECODE=$<BOOL:${LIE_VISION_WEIGHT_DECODE}>)
target_compile_definitions(gufo_core PUBLIC LIE_DIRECTIONAL_STEERING=$<BOOL:${LIE_DIRECTIONAL_STEERING}>)
target_link_libraries(gufo_core PUBLIC ICU::uc ICU::i18n OpenSSL::Crypto PNG::PNG JPEG::JPEG CURL::libcurl
  Threads::Threads hip::host roc::hipblas roc::hipblaslt roc::rocblas m)
# Retain the upstream model target, file dialects, wave sizes and numerical flags.
set(PROJECT_SOURCE_DIR "${GUFO_SOURCE}")
add_subdirectory("${GUFO_SOURCE}/src/models/qwen38_flash_next" src/models/qwen38_flash_next)
target_include_directories(gufo_qwen38_flash_next PRIVATE "${LIE_ROOT}/adapters")
if(LIE_DIRECTIONAL_STEERING)
  target_sources(gufo_qwen38_flash_next PRIVATE "${LIE_ROOT}/adapters/hip/steering.hip")
  # Preserve float reduction/update arithmetic even though the inherited
  # provider uses fast-math for other numerical kernels.
  set_source_files_properties("${LIE_ROOT}/adapters/hip/steering.hip" PROPERTIES
    LANGUAGE HIP COMPILE_OPTIONS "-fno-fast-math;-ffp-contract=off")
endif()
