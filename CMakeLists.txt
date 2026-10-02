# SPDX-License-Identifier: MIT
cmake_minimum_required(VERSION 3.21)
project(lie_q2_qualification LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(GUFO_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/source" CACHE PATH "Pinned patched Gufo source")
option(Q2_SANITIZERS "Enable host ASan and UBSan" OFF)
option(Q2_HIP "Build GPU qualification targets" OFF)
if(Q2_HIP)
  enable_language(HIP)
  set(CMAKE_HIP_STANDARD 20)
  set(CMAKE_HIP_STANDARD_REQUIRED ON)
endif()
add_compile_options(-include chrono)
if(Q2_SANITIZERS)
  add_compile_options(-fsanitize=address,undefined -fno-omit-frame-pointer)
  add_link_options(-fsanitize=address,undefined)
endif()
enable_testing()
find_package(Python3 REQUIRED COMPONENTS Interpreter)
add_test(NAME q2_process COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/q2_process_test.py)
set_tests_properties(q2_process PROPERTIES TIMEOUT 30)
add_test(NAME q2_thermal COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/q2_thermal_test.py)
add_test(NAME q2_reuse COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/q2_reuse_test.py)
add_test(NAME q2_profile COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/q2_profile_test.py)
add_library(q2_host STATIC
  ${GUFO_SOURCE}/src/core/gguf_reader.cpp
  ${GUFO_SOURCE}/src/core/quant/ggml_dequant.cpp
  ${GUFO_SOURCE}/src/models/qwen38_flash_next/config.cpp
  ${GUFO_SOURCE}/src/models/qwen38_flash_next/weights.cpp)
target_include_directories(q2_host PUBLIC ${GUFO_SOURCE})
foreach(pair IN ITEMS "reader|core/gguf_reader" "dequant|core/ggml_dequant"
    "config|models/qwen38_flash_next/config")
  string(REPLACE "|" ";" parts "${pair}")
  list(GET parts 0 name)
  list(GET parts 1 file)
  add_executable(test_${name} ${GUFO_SOURCE}/tests/${file}_test.cpp)
  target_link_libraries(test_${name} PRIVATE q2_host)
  add_test(NAME ${name} COMMAND test_${name})
endforeach()
add_executable(test_q2_storage tests/q2_storage.cpp)
target_link_libraries(test_q2_storage PRIVATE q2_host)
add_test(NAME q2_storage COMMAND test_q2_storage)
if(Q2_HIP)
  add_subdirectory(cmake/hip)
endif()
