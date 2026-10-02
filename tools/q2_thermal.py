# SPDX-License-Identifier: MIT
"""Read AMD CPU/GPU thermal sensors without changing device policy."""
from pathlib import Path


def sample(root=Path('/sys/class/hwmon'), limit_mc=98000):
    rows = []
    for device in sorted(root.glob('hwmon*')):
        try:
            name = (device / 'name').read_text().strip()
        except FileNotFoundError:
            continue
        if name not in ('amdgpu', 'k10temp'):
            continue
        for path in sorted(device.glob('temp*_input')):
            value = int(path.read_text().strip())
            if not -20000 <= value <= 150000:
                raise RuntimeError('Invalid thermal sensor value')
            limit = limit_mc
            inclusive = True
            for suffix in ('crit', 'max'):
                threshold = path.with_name(path.name.removesuffix('input') + suffix)
                if threshold.exists():
                    candidate = int(threshold.read_text().strip())
                    if 0 < candidate < limit:
                        limit = candidate
                        inclusive = False
            rows.append({'path': str(path), 'device': name, 'temperature_mc': value,
                         'limit_mc': limit, 'inclusive': inclusive,
                         'over_limit': value > limit if inclusive else value >= limit})
    if not {'amdgpu', 'k10temp'}.issubset({r['device'] for r in rows}):
        raise RuntimeError('Required CPU/GPU thermal sensors unavailable')
    return rows


def enforce(rows):
    if any(row['over_limit'] for row in rows):
        raise RuntimeError('Thermal limit exceeded; stop owned command')
