#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only sampled GPU/sysfs and pinned LIE process telemetry, no device opens."""
import datetime
import json
import os
from pathlib import Path
import sys
import time


def ticks(pid):
    return int(Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[19])


def main():
    run=Path(sys.argv[1]).resolve()
    result=json.loads((run/'results/result.json').read_text())
    pid,expected=result['server_pid'],result['server_start_ticks']
    device=Path('/sys/class/drm/card1/device')
    paths=[device/n for n in ('gpu_busy_percent','gpu_busy_percent','mem_info_gtt_used','mem_info_vram_used','pp_dpm_sclk','pp_dpm_mclk')]
    paths+=sorted((device/'hwmon').glob('hwmon*/temp*_input'))
    paths+=sorted((device/'hwmon').glob('hwmon*/power*_average'))
    paths+=sorted((device/'hwmon').glob('hwmon*/power*_input'))
    paths=list(dict.fromkeys(paths))
    metadata={'pid':os.getpid(),'start_ticks':ticks(os.getpid()),'server_pid':pid,'server_start_ticks':expected,
              'argv':sys.argv,'read_only':True,'sampling_seconds':1,'paths':[str(p) for p in paths]}
    with (run/'observer-start.json').open('x') as f: json.dump(metadata,f,indent=2)
    with (run/'resource-telemetry.jsonl').open('x') as f:
        deadline=time.monotonic()+1900
        while time.monotonic()<deadline:
            try:
                if ticks(pid)!=expected: break
            except FileNotFoundError: break
            row={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'device':{},'process':{}}
            for p in paths:
                try: row['device'][str(p)]=p.read_text()[:4096].strip()
                except OSError: row['device'][str(p)]=None
            try:
                for line in Path(f'/proc/{pid}/status').read_text().splitlines():
                    if line.split(':',1)[0] in ('VmRSS','VmHWM','VmSwap','Threads'):
                        k,v=line.split(':',1);row['process'][k]=v.strip()
            except FileNotFoundError: break
            f.write(json.dumps(row)+'\n');f.flush();time.sleep(1)
    with (run/'observer-exit.json').open('x') as f: json.dump({'finished_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exit_code':0},f)

if __name__=='__main__':main()
