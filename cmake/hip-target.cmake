# SPDX-License-Identifier: MIT
# One real target per qualified build; never impersonate another GPU.
set(LIE_HIP_ARCHITECTURE "gfx1151" CACHE STRING "HIP target: gfx1151 (Strix Halo) or gfx1150 (Strix Point)")
set_property(CACHE LIE_HIP_ARCHITECTURE PROPERTY STRINGS gfx1151 gfx1150)
if(NOT LIE_HIP_ARCHITECTURE MATCHES "^gfx115[01]$")
  message(FATAL_ERROR "LIE_HIP_ARCHITECTURE must be gfx1150 or gfx1151")
endif()
