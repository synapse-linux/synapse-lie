# SPDX-License-Identifier: MIT
"""Pure receipt checks: no source, device or model access."""

def validate_target(receipt, cache_text, expected):
    if expected not in ('gfx1150', 'gfx1151'):
        raise ValueError('Unsupported HIP target')
    values = {}
    for line in cache_text.splitlines():
        if line.startswith(('CMAKE_HIP_ARCHITECTURES:', 'LIE_HIP_ARCHITECTURE:')):
            key, value = line.split('=', 1)
            key = key.split(':', 1)[0]
            if key in values:
                raise ValueError('Duplicate HIP target cache entry')
            values[key] = value
    if values.get('CMAKE_HIP_ARCHITECTURES') != expected:
        raise ValueError('Numerical archive HIP target does not match the requested provider')
    declared = receipt.get('hip_architecture')
    # Historical gfx1151 receipts predate this field; their hashed cache is required.
    if declared != expected and not (declared is None and expected == 'gfx1151'):
        raise ValueError('Build receipt HIP target mismatch or missing target')
    if 'LIE_HIP_ARCHITECTURE' in values and values['LIE_HIP_ARCHITECTURE'] != expected:
        raise ValueError('LIE HIP target cache mismatch')
