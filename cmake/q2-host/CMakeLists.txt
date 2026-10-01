# SPDX-License-Identifier: MIT
# Transitional provider host-only tests. No HIP or model forward is linked.
cmake_minimum_required(VERSION 3.21)
project(lie_q2_host_contract LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
option(LIE_SANITIZERS "Enable CPU address/undefined sanitizers" OFF)
if(NOT EXISTS "${GUFO_SOURCE}/src/models/qwen38_flash_next/weights.cpp")
  message(FATAL_ERROR "GUFO_SOURCE must name the explicitly selected test source")
endif()
get_filename_component(LIE_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)
add_library(q2-host-core STATIC
  "${GUFO_SOURCE}/src/core/gguf_reader.cpp"
  "${GUFO_SOURCE}/src/core/quant/ggml_dequant.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/config.cpp")
# The test includes weights.cpp to exercise its actual private Binder, not a mock.
add_executable(test-q2-host "${LIE_ROOT}/tests/test_q2_host.cpp")
# Optional manual probe reads only an explicitly preserved bounded header file.
# It is NOT an inference executable or an automatic test of installed models.
add_executable(q2-header-bind "${LIE_ROOT}/tests/q2_header_bind.cpp"
  "${GUFO_SOURCE}/src/models/qwen38_flash_next/weights.cpp")
target_link_libraries(test-q2-host PRIVATE q2-host-core)
target_link_libraries(q2-header-bind PRIVATE q2-host-core)
foreach(target q2-host-core test-q2-host q2-header-bind)
  target_include_directories(${target} PRIVATE "${GUFO_SOURCE}")
  target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  if(LIE_SANITIZERS)
    target_compile_options(${target} PRIVATE -fsanitize=address,undefined -fno-omit-frame-pointer)
    target_link_options(${target} PRIVATE -fsanitize=address,undefined)
  endif()
endforeach()
enable_testing()
foreach(case storage iq2 padded inject legacy rejection combined config)
  add_test(NAME q2-host-${case} COMMAND test-q2-host ${case})
  set_tests_properties(q2-host-${case} PROPERTIES TIMEOUT 20)
endforeach()
