# SPDX-License-Identifier: MIT
CMAKE ?= cmake
JOBS ?= 2

.DEFAULT_GOAL := help
.PHONY: help strix-halo strix-point

help:
	@printf '%s\n' 'make strix-halo   Build LIE for AMD Strix Halo (gfx1151).' 'make strix-point  Build LIE for AMD Strix Point (gfx1150).' 'JOBS=2 controls application build parallelism; the HIP provider uses one job.'

strix-halo strix-point:
	"$(CMAKE)" "-DLIE_BUILD_TARGET=$@" "-DLIE_BUILD_JOBS=$(JOBS)" -P cmake/BuildTarget.cmake
