# SPDX-License-Identifier: MIT
"""Read AMD CPU/GPU thermal sensors without changing device policy."""
from pathlib import Path


def sample(root=Path('/sys/class/hwmon'), cpu_limit_mc=98000):
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
            # The owner's 98 C limit applies to CPU Tctl, not GPU edge.
            # GPU readings remain mandatory; use exposed thresholds if present.
            limit = cpu_limit_mc if name == 'k10temp' else None
            inclusive = limit is not None
            source = 'owner_cpu_limit' if limit is not None else 'no_exposed_gpu_threshold'
            for suffix in ('crit', 'max'):
                threshold = path.with_name(path.name.removesuffix('input') + suffix)
                if threshold.exists():
                    candidate = int(threshold.read_text().strip())
                    if candidate > 0 and (limit is None or candidate <= limit):
                        limit = candidate
                        inclusive = False
                        source = str(threshold)
            rows.append({'path': str(path), 'device': name, 'temperature_mc': value,
                         'limit_mc': limit, 'inclusive': inclusive, 'limit_source': source,
                         'over_limit': limit is not None and
                         (value > limit if inclusive else value >= limit)})
    if not {'amdgpu', 'k10temp'}.issubset({r['device'] for r in rows}):
        raise RuntimeError('Required CPU/GPU thermal sensors unavailable')
    return rows


def enforce(rows):
    if any(row['over_limit'] for row in rows):
        raise RuntimeError('Thermal limit exceeded; stop owned command')
