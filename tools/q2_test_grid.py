#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Extract only the pinned licensed IQ2 codebook into a private CPU-test header."""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
TABLE = 'src/models/qwen38_flash_next/kernels/rocm/mmq/ggml-common.h'

def generate(source, output):
    data = (Path(source) / TABLE).read_bytes()
    expected = json.loads((ROOT / 'third_party/gufo-source.json').read_text())['files'][TABLE]
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('IQ2 codebook source drift')
    matches = re.findall(rb'GGML_TABLE_BEGIN\(uint64_t, iq2xxs_grid, 256\)\s*(.*?)GGML_TABLE_END\(\)', data, re.S)
    if len(matches) != 1:
        raise ValueError('IQ2 codebook marker mismatch')
    fields = matches[0].decode().replace('\n', '').split(',')
    values = [int(x.strip(), 16) for x in fields if x.strip()]
    if len(values) != 256 or values[0] != 0x0808080808080808 or values[2] != 0x0808080808081919:
        raise ValueError('IQ2 codebook geometry/goldens mismatch')
    if any((v >> (8 * j)) & 255 not in (8, 25, 43) for v in values for j in range(8)):
        raise ValueError('IQ2 codebook alphabet mismatch')
    # The data retain the original llama.cpp MIT attribution, not new ownership.
    text = ('// Generated test data from pinned Gufo/llama.cpp ggml-common.h.\n'
            '// MIT; see that component\'s VENDOR.md and LICENSE.\n'
            '// Original file SHA256: ' + expected + '\n'
            '#include <cstdint>\n'
            'static constexpr std::uint64_t oracle_iq2_grid[256] = {\n')
    text += ''.join('  0x%016xULL,\n' % v for v in values) + '};\n'
    with Path(output).open('x') as f:
        f.write(text)
    return expected

if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: q2_test_grid.py PINNED-SOURCE NEW-HEADER')
    print(generate(sys.argv[1], sys.argv[2]))
