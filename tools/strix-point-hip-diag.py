#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bounded ROCm 10 memory-copy diagnostic. Requires the leased GPU runner."""
import ctypes as c
import json
import os
from pathlib import Path


def main():
    if os.environ.get('LIE_GPU_DIAGNOSTIC_WINDOW') != 'admitted' or not Path('/dev/kfd').exists():
        raise SystemExit('An admitted device window is required')
    hip = c.CDLL('libamdhip64.so')
    hip.hipGetErrorName.argtypes = [c.c_int]
    hip.hipGetErrorName.restype = c.c_char_p
    hip.hipGetErrorString.argtypes = [c.c_int]
    hip.hipGetErrorString.restype = c.c_char_p
    hip.hipGetDeviceCount.argtypes = [c.POINTER(c.c_int)]
    hip.hipSetDevice.argtypes = [c.c_int]
    hip.hipMalloc.argtypes = [c.POINTER(c.c_void_p), c.c_size_t]
    hip.hipFree.argtypes = [c.c_void_p]
    hip.hipMemset.argtypes = [c.c_void_p, c.c_int, c.c_size_t]
    hip.hipMemcpy.argtypes = [c.c_void_p, c.c_void_p, c.c_size_t, c.c_int]
    hip.hipDeviceSynchronize.argtypes = []
    hip.hipHostMalloc.argtypes = [c.POINTER(c.c_void_p), c.c_size_t, c.c_uint]
    hip.hipHostFree.argtypes = [c.c_void_p]

    steps = []
    def check(name, function, *args):
        code = int(function(*args))
        steps.append({'step': name, 'code': code,
                      'name': hip.hipGetErrorName(code).decode(),
                      'message': hip.hipGetErrorString(code).decode()})
        return code == 0

    count = c.c_int()
    device = c.c_void_p()
    pinned = c.c_void_p()
    host = (c.c_float * 8)(1, 3, 2, 4, 5, 7, 6, 8)
    output = (c.c_float * 8)()
    try:
        if check('device_count', hip.hipGetDeviceCount, c.byref(count)) and count.value == 1:
            if check('set_device', hip.hipSetDevice, 0):
                if check('malloc_48', hip.hipMalloc, c.byref(device), 48):
                    check('memset_48', hip.hipMemset, device, 0, 48)
                    check('copy_pageable_h2d_32', hip.hipMemcpy, device, c.cast(host, c.c_void_p), 32, 1)
                    check('copy_pageable_h2d_8', hip.hipMemcpy, device, c.cast(host, c.c_void_p), 8, 1)
                    if check('host_malloc_32', hip.hipHostMalloc, c.byref(pinned), 32, 0):
                        c.memmove(pinned, host, 32)
                        check('copy_pinned_h2d_32', hip.hipMemcpy, device, pinned, 32, 1)
                    check('copy_d2h_32', hip.hipMemcpy, c.cast(output, c.c_void_p), device, 32, 2)
                    check('synchronize', hip.hipDeviceSynchronize)
    finally:
        if pinned.value: check('host_free', hip.hipHostFree, pinned)
        if device.value: check('device_free', hip.hipFree, device)
    return emit(steps, count.value, device, pinned, list(output))


def emit(steps, device_count, device, pinned, output=None):
    record = {'scope': 'GPU_RUNTIME_DIAGNOSTIC_NO_MODEL', 'device_count': device_count,
              'device_pointer_nonzero': bool(device.value),
              'pinned_pointer_nonzero': bool(pinned.value),
              'steps': steps, 'output': output}
    print(json.dumps(record), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
