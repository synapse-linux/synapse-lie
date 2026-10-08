# SPDX-License-Identifier: MIT
"""Exact 130925-token diagnostic using the pinned native prefill workload."""
import q2_long_profile as base


def inputs(root):
    return base.inputs(root, 131072)


def client_argv(root, binary, output, depth=None):
    return base.client_argv(root, binary, output, depth, profile_depth=131072)


def validate_result(root, path, depth=None):
    return base.validate_result(root, path, depth, profile_depth=131072)


def profiler_argv(profiler, directory, server_argv):
    return base.profiler_argv(profiler, directory, server_argv, profile_depth=131072)
