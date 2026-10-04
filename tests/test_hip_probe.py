#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Probe error/retirement controls against synthetic HIP/BLAS only."""
import json
import os
import subprocess
import sys

binary = sys.argv[1]
env = dict(os.environ)
env.pop('HSA_OVERRIDE_GFX_VERSION', None)
env.pop('LIE_PROBE_FAULT', None)

def run(arguments, expected, extra=None):
    result = subprocess.run([binary, *arguments], env=dict(env, **(extra or {})),
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == expected, (arguments, extra, result.returncode, result.stderr)
    assert 'AddressSanitizer' not in result.stderr and 'runtime error:' not in result.stderr, result.stderr
    return result

run([], 2)
run(['--help'], 0, {'LIE_PROBE_FAULT': 'quiesce'})
run(['--run'], 1, {'HSA_OVERRIDE_GFX_VERSION': '11.5.0'})
success = json.loads(run(['--run'], 0).stdout)
assert success['scope'] == 'SYNTHETIC_CPU_NOT_INFERENCE'
assert 'SYNTHETIC HIP fixture' in success['device']
assert success['explicit_allocation_bytes'] == 48
assert success['sgemm_elements_verified'] == 4
for fault in ('device', 'arch', 'identity', 'memory_info', 'allocate', 'copy_inputs',
              'zero_output', 'create_blas', 'sgemm', 'complete', 'copy_output',
              'wrong_output', 'nan_output', 'destroy_blas', 'free'):
    result = run(['--run'], 1, {'LIE_PROBE_FAULT': fault})
    assert not result.stdout, (fault, result.stdout)
run(['--run'], 70, {'LIE_PROBE_FAULT': 'quiesce'})
print('Synthetic probe controls passed; no GPU/model attempted')
