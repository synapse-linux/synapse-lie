# SPDX-License-Identifier: MIT
cmake_minimum_required(VERSION 3.21)
project(lie_ds4_walk_bench LANGUAGES C CXX)
get_filename_component(ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)
foreach(contract IN ITEMS source archives)
  if(contract STREQUAL "source")
    file(READ "${ROOT}/config/ds4-walk-bench-source.json" manifest)
    set(key files)
    string(JSON prefix GET "${manifest}" source)
  else()
    file(READ "${ROOT}/config/q2-counting-bench-build.json" manifest)
    set(key retained_archives)
    set(prefix "")
  endif()
  string(JSON count LENGTH "${manifest}" ${key})
  math(EXPR last "${count}-1")
  foreach(i RANGE 0 ${last})
    string(JSON name MEMBER "${manifest}" ${key} ${i})
    string(JSON expected GET "${manifest}" ${key} "${name}")
    file(SHA256 "${ROOT}/${prefix}/${name}" actual)
    if(NOT actual STREQUAL expected)
      message(FATAL_ERROR "Retained ${contract} changed: ${name}")
    endif()
  endforeach()
endforeach()
set(LIE_GUFO_RUNTIME OFF CACHE BOOL "" FORCE)
set(LIE_C17_SAMPLING OFF CACHE BOOL "" FORCE)
set(LIE_MTP OFF CACHE BOOL "" FORCE)
set(LIE_VISION OFF CACHE BOOL "" FORCE)
set(LIE_DS4_RUNTIME_CACHE OFF CACHE BOOL "" FORCE)
set(LIE_KVC_INTERCHANGE OFF CACHE BOOL "" FORCE)
set(LIE_SYSTEM_LIBUV ON CACHE BOOL "" FORCE)
set(LIE_BUILD_ID ds4-walk-bench CACHE STRING "" FORCE)
set(BUILD_TESTING OFF CACHE BOOL "" FORCE)
add_subdirectory("${ROOT}/.deps/lie-ds4-walk-bench" core)
get_target_property(bench_sources synapse-lie-bench SOURCES)
list(FILTER bench_sources EXCLUDE REGEX "executor_unavailable\\.c$")
set_property(TARGET synapse-lie-bench PROPERTY SOURCES "${bench_sources}")
set_property(TARGET synapse-lie-bench PROPERTY LINKER_LANGUAGE CXX)
# The numerical HIP archives are qualified and byte-verified above.
set(RETAINED "${ROOT}/.deps/build-prefill-chunks")
target_link_libraries(synapse-lie-bench PRIVATE
  "${RETAINED}/cmake/curve/libq2_curve_adapter.a"
  lie_qwen_state lie_store
  "${RETAINED}/cmake/hip/qwen/libgufo_qwen38_flash_next.a"
  "${RETAINED}/libq2_host.a"
  icuuc icui18n jpeg curl crypto png z
  "${ROOT}/.deps/build-hc-scalar-matched/cmake/hip/qwen/libgufo_qwen38_flash_next_mmq.a"
  /opt/rocm/lib/libhipblas.so /opt/rocm/lib/librocblas.so
  /opt/rocm/lib/libamdhip64.so /opt/rocm/lib/libhipblaslt.so)
target_link_options(synapse-lie-bench PRIVATE --offload-arch=gfx1151)
