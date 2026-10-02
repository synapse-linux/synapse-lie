#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Restore only the configuration introduced by this exact maintenance run.
import fcntl,hashlib,json,os,subprocess
from pathlib import Path
root=Path('/home/pop/workspace/synapse-lie/strix-point-ttm96-r1')
assert os.geteuid()==0
r=json.loads((root/'prepare-result.json').read_text())
target=Path(r['config']['path'])
assert target==Path('/etc/modprobe.d/90-synapse-lie-ttm.conf') and not target.is_symlink()
assert hashlib.sha256(target.read_bytes()).hexdigest()==r['config']['sha256']
fd=os.open(root.parent/'campaign.lock',os.O_RDWR|os.O_NOFOLLOW)
fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert r['before']['config_absent']
target.unlink()
with (root/'rollback-initramfs.log').open('x') as log:
 p=subprocess.run(['update-initramfs','-u','-k',r['before']['kernel']],stdout=log,stderr=subprocess.STDOUT)
(root/'rollback-result.json').write_text(json.dumps({'exit_code':p.returncode,'reboot_required':True})+'\n')
os.sync(); os.close(fd)
raise SystemExit(p.returncode)
