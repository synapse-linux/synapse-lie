#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run the isolated exact-prompt CTest cohort on the authorized host."""
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == '8b9cbb46-c7d4-47c3-b5cc-32e1fdad0653'
for name, digest in json.loads((root / 'manifest.json').read_text()).items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, name
fd = os.open(root.parent / 'root-terminal-bench-r16/client.lock', os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW)
st = os.fstat(fd)
assert (st.st_dev, st.st_ino) == (54, 4486194)
fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
for variant in ('debug', 'asan'):
    (root / ('bench-' + variant)).chmod(0o700)
argv = ['ctest', '--test-dir', str(root), '--output-on-failure', '-V']
start = datetime.datetime.now(datetime.timezone.utc).isoformat()
with (root / 'ctest.stdout').open('x') as out, (root / 'ctest.stderr').open('x') as err:
    p = subprocess.run(argv, stdout=out, stderr=err)
record = dict(argv=argv, started_at=start, finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              exit_code=p.returncode, synthetic=True, gpu_access=False, model_access=False)
with (root / 'ctest.json').open('x') as f:
    json.dump(record, f, indent=2)
os.close(fd)
print(json.dumps(record))
sys.exit(p.returncode)
