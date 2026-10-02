#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Save only intentional changes relative to the independently fetched Gufo pin."""
from pathlib import Path
import difflib

root = Path(__file__).resolve().parents[1]
base = root/'.deps/gufo-base'
candidate = root/'.deps/gufo-q2'
chunks = []
changed = []
for file in sorted(base.rglob('*')):
    if not file.is_file(): continue
    rel = file.relative_to(base)
    other = candidate/rel
    if file.read_bytes() == other.read_bytes(): continue
    changed.append(str(rel))
    chunks.extend(difflib.unified_diff(file.read_text().splitlines(True),
                                      other.read_text().splitlines(True),
                                      fromfile='a/'+str(rel),tofile='b/'+str(rel)))
(root/'patches/gufo-q2.patch').write_text(''.join(chunks))
print('\n'.join(changed))
