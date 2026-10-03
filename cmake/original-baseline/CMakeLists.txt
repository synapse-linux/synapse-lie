# SPDX-License-Identifier: MIT
# Historical C17 ABI is private to this benchmark, never linked into the server.
set(original "${CMAKE_SOURCE_DIR}/experiments/original-baseline")
file(READ "${CMAKE_SOURCE_DIR}/config/q2-original-baseline-source.json" manifest)
string(JSON count LENGTH "${manifest}" files)
math(EXPR last "${count}-1")
foreach(i RANGE 0 ${last})
  string(JSON name MEMBER "${manifest}" files ${i})
  string(JSON expected GET "${manifest}" files "${name}")
  file(SHA256 "${original}/${name}" actual)
  if(NOT actual STREQUAL expected)
    message(FATAL_ERROR "Original baseline source differs: ${name}")
  endif()
endforeach()
find_package(PkgConfig REQUIRED)
pkg_check_modules(Q2_JSON REQUIRED IMPORTED_TARGET json-c)
find_package(OpenSSL REQUIRED COMPONENTS Crypto)
target_sources(q2_host PRIVATE
  "${GUFO_SOURCE}/src/core/gguf_identity.cpp"
  "${GUFO_SOURCE}/src/core/json_constraint.cpp"
  "${GUFO_SOURCE}/src/core/json_schema_lexeme.cpp"
  "${GUFO_SOURCE}/src/core/json_schema_regex.cpp"
  "${GUFO_SOURCE}/src/core/sampling.cpp"
  "${GUFO_SOURCE}/src/core/speculative/speculative_verifier.cpp")
add_library(q2_original_adapter STATIC
  "${original}/adapters/gufo.cpp"
  "${original}/adapters/gufo_binding.c"
  "${original}/adapters/gufo_device.cpp")
target_compile_definitions(q2_original_adapter PRIVATE LIE_GUFO_ADAPTER_OPT_IN=1)
target_include_directories(q2_original_adapter PRIVATE "${original}/include" "${GUFO_SOURCE}")
target_link_libraries(q2_original_adapter PUBLIC gufo_qwen38_flash_next)
add_executable(q2_original_baseline "${original}/tools/executor-bench.c")
target_include_directories(q2_original_baseline PRIVATE "${original}/include")
target_compile_definitions(q2_original_baseline PRIVATE _POSIX_C_SOURCE=200809L
  LIE_BUILD_ID="q2-original-baseline-experiment")
target_compile_options(q2_original_baseline PRIVATE -Wall -Wextra -Wpedantic -Werror -fno-common)
target_link_libraries(q2_original_baseline PRIVATE q2_original_adapter
  PkgConfig::Q2_JSON OpenSSL::Crypto m)
