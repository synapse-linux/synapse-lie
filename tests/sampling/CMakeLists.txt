# SPDX-License-Identifier: MIT
# Host-only, independently pinned controls. No HIP discovery or model forward.
cmake_minimum_required(VERSION 3.21)
project(lie_sampling_host_checks LANGUAGES C CXX)
get_filename_component(REPO "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
include("${REPO}/cmake/provider/Source.cmake")
set(CMAKE_C_STANDARD 17)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
option(LIE_SANITIZERS "ASan/UBSan host fixtures" ON)
option(LIE_SAMPLING_PERFORMANCE "Host-only cost and separate allocation probes" OFF)
add_compile_options(-Wall -Wextra -Wpedantic -UNDEBUG)
if(LIE_SANITIZERS)
  add_compile_options(-fsanitize=address,undefined -fno-omit-frame-pointer)
  add_link_options(-fsanitize=address,undefined)
endif()
set(pristine "${REPO}/.deps/gufo-f783fedb")
file(READ "${REPO}/third_party/gufo-source.json" manifest)
string(JSON original_files GET "${manifest}" files)
lie_verify_files("${pristine}" "${original_files}")
lie_variant_files(ON ON files changed)
set(variant "${CMAKE_CURRENT_BINARY_DIR}/variant")
string(JSON count LENGTH "${changed}")
math(EXPR last "${count}-1")
foreach(i RANGE 0 ${last})
  string(JSON name MEMBER "${changed}" ${i})
  string(JSON content GET "${changed}" "${name}")
  get_filename_component(parent "${variant}/${name}" DIRECTORY)
  file(MAKE_DIRECTORY "${parent}")
  file(WRITE "${variant}/${name}" "${content}")
endforeach()
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/variant-files.json" "${files}\n")
find_package(ICU REQUIRED COMPONENTS uc i18n)
find_package(Threads REQUIRED)
include(CTest)
foreach(arm IN ITEMS reference candidate fallback)
  set(sources "${pristine}/src/core/json_constraint.cpp"
    "${pristine}/src/core/json_schema_lexeme.cpp" "${pristine}/src/core/json_schema_regex.cpp")
  if(arm STREQUAL "reference")
    list(APPEND sources "${pristine}/src/core/sampling.cpp")
  else()
    list(APPEND sources "${variant}/src/core/sampling.cpp" "${REPO}/src/sampling.c" "${REPO}/src/sampling_history.c" "${REPO}/src/sampling_distribution.c")
  endif()
  add_library(${arm} STATIC ${sources})
  if(NOT arm STREQUAL "reference")
    target_include_directories(${arm} PUBLIC "${variant}" "${REPO}/include")
    target_include_directories(${arm} PUBLIC "${REPO}/adapters")
  endif()
  target_include_directories(${arm} PUBLIC "${pristine}")
  if(arm STREQUAL "candidate")
    target_compile_definitions(${arm} PUBLIC LIE_C17_SAMPLING=1)
  else()
    target_compile_definitions(${arm} PUBLIC LIE_C17_SAMPLING=0)
  endif()
  if(NOT arm STREQUAL "reference")
    target_compile_definitions(${arm} PUBLIC LIE_TEST_BIAS=1)
  endif()
  target_link_libraries(${arm} PUBLIC ICU::uc ICU::i18n Threads::Threads m)
  foreach(test IN ITEMS logit grammar mtp)
    if(test STREQUAL "logit")
      set(test_source tests/cli/logit_sampler_test.cpp)
    elseif(test STREQUAL "grammar")
      set(test_source tests/core/json_constraint_test.cpp)
    else()
      set(test_source tests/models/qwen38_flash_next/mtp_sampling_test.cpp)
    endif()
    add_executable(${arm}-${test} "${pristine}/${test_source}")
    target_link_libraries(${arm}-${test} PRIVATE ${arm})
    add_test(NAME ${arm}-${test} COMMAND ${arm}-${test})
    set_tests_properties(${arm}-${test} PROPERTIES TIMEOUT 90)
  endforeach()
  add_executable(${arm}-probe "${REPO}/tests/sampling/probe.cpp")
  target_link_libraries(${arm}-probe PRIVATE ${arm})
  add_executable(${arm}-history "${REPO}/tests/sampling/history.cpp")
  target_link_libraries(${arm}-history PRIVATE ${arm})
  add_executable(${arm}-distribution "${REPO}/tests/sampling/distribution.cpp")
  target_link_libraries(${arm}-distribution PRIVATE ${arm})
  add_executable(${arm}-vocabulary "${REPO}/tests/sampling/vocabulary.cpp")
  target_link_libraries(${arm}-vocabulary PRIVATE ${arm})
  if(LIE_SAMPLING_PERFORMANCE)
    add_executable(${arm}-cost "${CMAKE_CURRENT_LIST_DIR}/performance.cpp")
    target_compile_definitions(${arm}-cost PRIVATE LIE_SAMPLING_ARM="${arm}")
    target_link_libraries(${arm}-cost PRIVATE ${arm})
    add_executable(${arm}-allocation "${CMAKE_CURRENT_LIST_DIR}/performance.cpp"
      "${CMAKE_CURRENT_LIST_DIR}/allocation_counter.cpp")
    target_compile_definitions(${arm}-allocation PRIVATE
      LIE_SAMPLING_ARM="${arm}" LIE_TRACK_ALLOCATIONS=1)
    target_link_libraries(${arm}-allocation PRIVATE ${arm})
    add_test(NAME ${arm}-allocation-retirement
      COMMAND ${arm}-allocation --quick)
    set_tests_properties(${arm}-allocation-retirement PROPERTIES TIMEOUT 90)
  endif()
endforeach()
add_executable(candidate-controls "${REPO}/tests/test_gufo_sampling.cpp")
target_link_libraries(candidate-controls PRIVATE candidate)
add_test(NAME candidate-controls COMMAND candidate-controls)
add_executable(fallback-controls "${REPO}/tests/test_gufo_sampling.cpp")
target_link_libraries(fallback-controls PRIVATE fallback)
add_test(NAME fallback-controls COMMAND fallback-controls)
add_test(NAME complete-sampling-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-probe>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-probe>"
  "-DFALLBACK=$<TARGET_FILE:fallback-probe>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/parity" -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(complete-sampling-reference-parity PROPERTIES TIMEOUT 120)
add_test(NAME complete-biased-sampling-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:fallback-probe>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-probe>"
  "-DARGUMENT=--bias" "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/biased-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(complete-biased-sampling-parity PROPERTIES TIMEOUT 120)
add_test(NAME full-vocabulary-sampling-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-vocabulary>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-vocabulary>"
  "-DFALLBACK=$<TARGET_FILE:fallback-vocabulary>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/vocabulary-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(full-vocabulary-sampling-parity PROPERTIES TIMEOUT 120)
add_test(NAME sampling-history-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-history>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-history>"
  "-DFALLBACK=$<TARGET_FILE:fallback-history>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/history-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(sampling-history-reference-parity PROPERTIES TIMEOUT 120)
add_test(NAME compact-distribution-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-distribution>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-distribution>"
  "-DFALLBACK=$<TARGET_FILE:fallback-distribution>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/distribution-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(compact-distribution-reference-parity PROPERTIES TIMEOUT 120)
