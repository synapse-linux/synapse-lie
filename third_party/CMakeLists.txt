# SPDX-License-Identifier: MIT
# Keep upstream's dialect, feature macros and warnings isolated from LIE.
# Sanitizer instrumentation remains enabled for the bundled event loop.
get_directory_property(lie_vendor_options COMPILE_OPTIONS)
list(REMOVE_ITEM lie_vendor_options -Wall -Wextra -Wpedantic -Werror -fno-common)
set_property(DIRECTORY PROPERTY COMPILE_OPTIONS "${lie_vendor_options}")
set_property(DIRECTORY PROPERTY COMPILE_DEFINITIONS "")
set(LIBUV_BUILD_SHARED OFF CACHE BOOL "" FORCE)
set(LIBUV_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(LIBUV_BUILD_BENCH OFF CACHE BOOL "" FORCE)
add_subdirectory(libuv)
