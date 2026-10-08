#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Apply only fan curves from the existing AXB35 JSON; preserve APU policy."""
import json
from pathlib import Path
import re
import subprocess
import sys


def thresholds(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]+(?:,[0-9]+){4}', value):
        raise ValueError('Expected five comma-separated integer temperatures')
    result = [int(x) for x in value.split(',')]
    if not all(0 <= x <= 100 for x in result) or any(a >= b for a, b in zip(result, result[1:])):
        raise ValueError('Fan thresholds must strictly increase within 0..100 C')
    return result


def commands(config):
    if not isinstance(config, dict):
        raise ValueError('Expected a fan configuration object')
    result = []
    for number in range(1, 4):
        fan = config.get('fan' + str(number))
        if not isinstance(fan, dict) or fan.get('mode') != 'curve':
            raise ValueError('All three fans must use curve mode')
        up, down = thresholds(fan.get('rampup_curve')), thresholds(fan.get('rampdown_curve'))
        if any(a >= b for a, b in zip(down, up)):
            raise ValueError('Each ramp-down threshold must be below ramp-up')
        for setting, value in [('rampdown', fan['rampdown_curve']),
                               ('rampup', fan['rampup_curve']), ('mode', 'curve')]:
            result.append(['/usr/bin/axb35-ctl', 'set', 'fan', str(number), setting, value])
    return result


def main():
    if len(sys.argv) != 2:
        raise ValueError('Usage: axb35-fan-curves.py <configuration.json>')
    if Path('/sys/class/dmi/id/board_name').read_text().strip() != 'AXB35-02':
        raise ValueError('Unsupported board')
    with Path(sys.argv[1]).open('rb') as stream:
        data = stream.read(65537)
    if len(data) > 65536:
        raise ValueError('Oversized fan configuration')
    # Validate every fan before the first hardware mutation. APU/level fields
    # are deliberately not applied: curve mode selects its level dynamically.
    for argv in commands(json.loads(data)):
        subprocess.run(argv, check=True, timeout=5)
    print('Applied all three AXB35 fan curves; APU power mode preserved.')


if __name__ == '__main__':
    main()
