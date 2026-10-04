# SPDX-License-Identifier: MIT
# Private paired HTTP experiment; does not weaken the core provider verifier.
set(curve_core "${CMAKE_SOURCE_DIR}/curve-core")
file(READ "${CMAKE_SOURCE_DIR}/config/q2-curve-source.json" curve_manifest)
string(JSON curve_count LENGTH "${curve_manifest}" core_files)
math(EXPR curve_last "${curve_count}-1")
foreach(i RANGE 0 ${curve_last})
  string(JSON name MEMBER "${curve_manifest}" core_files ${i})
  string(JSON expected GET "${curve_manifest}" core_files "${name}")
  file(SHA256 "${curve_core}/${name}" actual)
  if(NOT actual STREQUAL expected)
    message(FATAL_ERROR "Frozen curve core differs: ${name}")
  endif()
endforeach()
set(BUILD_TESTING OFF CACHE BOOL "" FORCE)
set(LIE_GUFO_RUNTIME OFF CACHE BOOL "" FORCE)
set(LIE_GUFO_STATE_ACCESS OFF CACHE BOOL "" FORCE)
set(LIE_DS4_RUNTIME_CACHE OFF CACHE BOOL "" FORCE)
set(LIE_C17_SAMPLING OFF CACHE BOOL "" FORCE)
set(LIE_MTP OFF CACHE BOOL "" FORCE)
set(LIE_VISION OFF CACHE BOOL "" FORCE)
set(LIE_BUILD_ID q2-canonical-curve-experiment CACHE STRING "" FORCE)
option(Q2_CURVE_IQ2_SIGNS "Isolated ordered IQ2 sign experiment" OFF)
if(Q2_CURVE_IQ2_SIGNS)
  if(EXISTS "${GUFO_SOURCE}/q2_curve_profile.hpp")
    message(FATAL_ERROR "IQ2 curve and diagnostic instrumentation are separate")
  endif()
  file(READ "${CMAKE_SOURCE_DIR}/config/q2-iq2-signs-ordered-asm-source.json" iq2_manifest)
  set(iq2_header "src/models/qwen38_flash_next/kernels/rocm/mmq/vecdotq.hpp")
  string(JSON iq2_expected GET "${iq2_manifest}" files "${iq2_header}")
  file(SHA256 "${GUFO_SOURCE}/${iq2_header}" iq2_actual)
  if(NOT iq2_actual STREQUAL iq2_expected)
    message(FATAL_ERROR "IQ2 curve requires the measured ordered-sign provider")
  endif()
  set(LIE_BUILD_ID q2-canonical-curve-iq2-signs CACHE STRING "" FORCE)
endif()
if(EXISTS "${GUFO_SOURCE}/q2_curve_profile.hpp")
  set(LIE_BUILD_ID q2-canonical-curve-ple-profile CACHE STRING "" FORCE)
endif()
add_subdirectory("${curve_core}" core)
get_target_property(curve_sources synapse-lie-server SOURCES)
list(FILTER curve_sources EXCLUDE REGEX "executor_unavailable\\.c$")
set_property(TARGET synapse-lie-server PROPERTY SOURCES "${curve_sources}")
target_sources(q2_host PRIVATE
  "${GUFO_SOURCE}/src/core/gguf_identity.cpp"
  "${GUFO_SOURCE}/src/core/json_constraint.cpp"
  "${GUFO_SOURCE}/src/core/json_schema_lexeme.cpp"
  "${GUFO_SOURCE}/src/core/json_schema_regex.cpp"
  "${GUFO_SOURCE}/src/core/sampling.cpp"
  "${GUFO_SOURCE}/src/core/speculative/speculative_verifier.cpp")
add_library(q2_curve_adapter STATIC
  "${curve_core}/adapters/gufo.cpp"
  "${curve_core}/adapters/gufo_binding.c"
  "${curve_core}/adapters/gufo_device.cpp")
target_compile_features(q2_curve_adapter PRIVATE cxx_std_20)
target_compile_definitions(q2_curve_adapter PRIVATE
  LIE_GUFO_ADAPTER_OPT_IN=1 LIE_GUFO_STATE_ACCESS=1 LIE_C17_SAMPLING=0
  LIE_MTP=0 LIE_VISION=0)
target_include_directories(q2_curve_adapter PRIVATE "${curve_core}/include" "${GUFO_SOURCE}")
target_link_libraries(q2_curve_adapter PUBLIC lie_qwen_state lie_store gufo_qwen38_flash_next)
target_link_libraries(synapse-lie-server PRIVATE q2_curve_adapter)
