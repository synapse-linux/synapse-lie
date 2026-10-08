# SPDX-License-Identifier: MIT
# Experimental composition only. Never changes the core provider verifier.
set(terminal_core "${CMAKE_SOURCE_DIR}/terminal-core")
file(READ "${CMAKE_SOURCE_DIR}/config/q2-terminal-core-source.json" terminal_manifest)
string(JSON terminal_count LENGTH "${terminal_manifest}" files)
math(EXPR terminal_last "${terminal_count}-1")
foreach(i RANGE 0 ${terminal_last})
  string(JSON name MEMBER "${terminal_manifest}" files ${i})
  string(JSON expected GET "${terminal_manifest}" files "${name}")
  file(SHA256 "${terminal_core}/${name}" actual)
  if(NOT actual STREQUAL expected)
    message(FATAL_ERROR "Frozen Terminal-Bench core differs: ${name}")
  endif()
endforeach()
# This source snapshot supplies the unchanged C17 HTTP/worker contracts.
# It is composed here with this capsule's experimental Q2 model target.
# Qualified core's strict provider receipt mechanism stays unchanged.
set(BUILD_TESTING OFF CACHE BOOL "" FORCE)
set(LIE_GUFO_RUNTIME OFF CACHE BOOL "" FORCE)
set(LIE_GUFO_STATE_ACCESS OFF CACHE BOOL "" FORCE)
set(LIE_DS4_RUNTIME_CACHE OFF CACHE BOOL "" FORCE)
set(LIE_BUILD_ID q2-terminal-experiment CACHE STRING "" FORCE)
add_subdirectory("${terminal_core}" core)
get_target_property(terminal_server_sources synapse-lie-server SOURCES)
list(FILTER terminal_server_sources EXCLUDE REGEX "executor_unavailable\\.c$")
set_property(TARGET synapse-lie-server PROPERTY SOURCES "${terminal_server_sources}")
target_sources(q2_host PRIVATE
  "${GUFO_SOURCE}/src/core/gguf_identity.cpp"
  "${GUFO_SOURCE}/src/core/json_constraint.cpp"
  "${GUFO_SOURCE}/src/core/json_schema_lexeme.cpp"
  "${GUFO_SOURCE}/src/core/json_schema_regex.cpp"
  "${GUFO_SOURCE}/src/core/sampling.cpp"
  "${GUFO_SOURCE}/src/core/speculative/speculative_verifier.cpp")
add_library(q2_terminal_adapter STATIC
  "${terminal_core}/adapters/gufo.cpp"
  "${terminal_core}/adapters/gufo_binding.c"
  "${terminal_core}/adapters/gufo_device.cpp")
target_compile_definitions(q2_terminal_adapter PRIVATE LIE_GUFO_ADAPTER_OPT_IN=1)
target_compile_features(q2_terminal_adapter PRIVATE cxx_std_20)
target_include_directories(q2_terminal_adapter PRIVATE "${terminal_core}/include" "${GUFO_SOURCE}")
target_link_libraries(q2_terminal_adapter PUBLIC lie_qwen_state lie_store gufo_qwen38_flash_next)
target_link_libraries(synapse-lie-server PRIVATE q2_terminal_adapter)
