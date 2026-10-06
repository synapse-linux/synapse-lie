#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fixed isolated checks. GPU work requires all four existing nonblocking leases."""
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

from q2_process import supervise
from q2_counter_calibration import execute as counter_calibration
from q2_thermal import sample as thermal_sample, enforce as thermal_enforce
from q2_reuse import verify_sources
from q2_binary_replay import verify_replay, libraries
from q2_oracle_replay import verify as verify_oracle_replay
from q2_native_curve import MODES as NATIVE_CURVE_MODES, POINT_MODES, verify_source as verify_native_curve

ROOT = Path(__file__).resolve().parents[1]
LOCKS = [
    '/home/paperboy/workspace/projects/cachyos/ai/ds4-gufo/qualification/.pipeline.lock',
    '/home/paperboy/.local/state/ds4-kernel-work/20260927T161150Z-qwen-hip-prefill/download-gufo-native/download.lock',
    '/home/paperboy/.local/state/ds4-kernel-work/20260927T161150Z-qwen-hip-prefill/.qualification.lock',
    '/tmp/synapse-lie-ds4-gpu.lock',
]


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def main():
    mode = sys.argv[1]
    routing_mode = mode == 'q2-current-routing'
    counter_mode = mode == 'counter-calibration'
    if counter_mode and len(sys.argv) != 2:
        raise SystemExit('Counter calibration accepts no model or build variants')
    saved_profile = {
        'q2-fixed-moe-profile': ('q2-hc-moe-deferred-model-r1',
            'q2-counting-hc-moe-deferred', 'q2-fixed-moe-profile-binary.json'),
        'q2-current-best-profile': ('q2-half-consumer-eight-model-r1',
            'q2-counting-half-consumer-eight', 'q2-current-best-profile-binary.json'),
        'q2-current-routing': ('q2-ssm-fixed-bounds-model-r1',
            'q2-counting-ssm-fixed-bounds', 'q2-current-routing-binary.json'),
    }.get(mode)
    if saved_profile and len(sys.argv) != 2:
        raise SystemExit('Fixed MoE profile requires the saved candidate binary only')
    if mode == 'iq2-signs-check' and '--rebuild-mmq' not in sys.argv[2:]:
        raise SystemExit('IQ2 signs requires a full MMQ rebuild')
    native_curve = '--native-curve' in sys.argv[2:]
    point_only = '--point-only' in sys.argv[2:]
    if point_only and (not native_curve or mode not in POINT_MODES):
        raise SystemExit('Focused point requires a native point mode')
    if mode == 'q2-point-norm' and not point_only:
        raise SystemExit('Paired norm model requires the focused native point')
    if native_curve and mode not in NATIVE_CURVE_MODES:
        raise SystemExit('Native curve requires an uninstrumented canonical mode')
    if mode == 'q2-curve-scale' and not native_curve:
        raise SystemExit('Scale model comparison requires the native C canonical benchmark')
    full_prefill128 = mode == 'q2-prefill128'
    prefill_depth = int(sys.argv[sys.argv.index('--prefill-only-depth')+1]) if '--prefill-only-depth' in sys.argv else None
    if prefill_depth is not None and (not full_prefill128 or not native_curve or prefill_depth not in (65536,131072)):
        raise SystemExit('Saved prefill depth requires the matched native full-prefill mode')
    curve128 = full_prefill128 or mode == 'q2-curve128'
    if curve128 and (not native_curve or '--rebuild-mmq' in sys.argv[2:] or point_only or '--replay-from' in sys.argv[2:]):
        raise SystemExit('Curve128 requires the native full curve and pinned binaries without builds')
    curve256 = mode in ('q2-curve256', 'ud-curve256')
    curve256_cpu = mode == 'curve256-cpu'
    if curve256 and (not native_curve or '--rebuild-mmq' in sys.argv[2:] or point_only):
        raise SystemExit('Curve256 requires the native full curve and pinned MMQ reuse')
    curve_mode = curve128 or curve256 or mode in ('q2-curve', 'ud-curve', 'q2-curve-ple', 'ud-curve-ple', 'q2-curve-iq2', 'q2-curve-ple-cache-first', 'q2-curve-routes', 'q2-curve-iq2-mixed', 'q2-curve-scale', 'q2-curve-row', 'q2-point-norm')
    curve_routes = mode == 'q2-curve-routes'
    curve_cache_first = mode == 'q2-curve-ple-cache-first'
    curve_mixed = mode == 'q2-curve-iq2-mixed'
    point_norm = mode == 'q2-point-norm'
    curve_row = mode == 'q2-curve-row'
    if curve_row and not native_curve:
        raise SystemExit('Scaled row model comparison requires the native C canonical benchmark')
    curve_scale = mode == 'q2-curve-scale'
    curve_iq2 = point_norm or curve_row or curve_scale or mode == 'q2-curve-iq2' or curve_cache_first or curve_routes or curve_mixed
    curve_profile = curve_mode and mode.endswith('-ple')
    if curve_mode and not (curve128 or curve256) and '--rebuild-mmq' not in sys.argv[2:]:
        raise SystemExit('Canonical curve requires a full MMQ rebuild')
    replay_label = sys.argv[sys.argv.index('--replay-from')+1] if '--replay-from' in sys.argv[2:] else None
    replay_modes = {'q2-norm-fixed-model-before-r1': 'q2-counting-iq2-mixed',
                    'q2-norm-fixed-model-ud-r1': 'ud-counting-legacy'}
    if replay_label and (replay_modes.get(replay_label) != mode or '--rebuild-mmq' in sys.argv[2:]):
        raise SystemExit('Binary replay requires its qualified unchanged counting control and no build')
    if saved_profile:
        replay_label = saved_profile[0]
    counting_mode = mode in ('q2-counting-down-fixed-contract', 'q2-counting-down-fixed-bounds', 'q2-counting-hc-inject-raw-q8', 'q2-counting-iq2-table-lds', 'q2-counting-iq2-dpp-commit', 'q2-counting-iq2-fixed-bounds', 'q2-counting-iq2-half-sign-arithmetic', 'q2-counting-hc-rms-owner-ordinary', 'q2-counting-legacy', 'q2-counting-iq2', 'q2-counting-iq2-mixed', 'q2-counting-norm-fixed', 'q2-counting-shared-q8', 'q2-counting-reaudit-exact', 'q2-counting-reaudit-norm', 'q2-counting-hc-bk256-initial', 'q2-counting-hc-bk256-bounded', 'q2-counting-hc-bk128-single', 'q2-counting-hc-bk128-double', 'q2-counting-hc-bn64-token', 'q2-counting-hc-bn64-output', 'q2-counting-hc-moe-deferred', 'q2-counting-q8-grouped', 'q2-counting-scaled-selective', 'q2-counting-iq2-live-compose', 'q2-counting-iq2-raw-selective', 'q2-counting-iq2-halfstage', 'q2-counting-iq2-halfbyte', 'q2-counting-q8-halfpair', 'q2-counting-ssm-row128', 'q2-counting-iq2-fused-grid', 'q2-counting-half-fixed-width', 'q2-counting-half-consumer-eight', 'q2-counting-ssm-row-group', 'q2-counting-ssm-fixed-shape', 'q2-counting-ssm-fixed-bounds', 'q2-counting-ssm-channel-bounds', 'q2-counting-ssm-compact-lds', 'q2-counting-ssm-pingpong', 'q2-counting-down-register-scatter', 'q2-counting-down-half-vector', 'q2-counting-down-half-pair', 'q2-counting-down-half-storage', 'q2-counting-down-live-stage', 'q2-counting-down-output-reuse', 'q2-counting-iq2-wide-pair', 'q2-counting-iq2-four-wave', 'q2-counting-iq2-lane-commit', 'q2-counting-iq2-short-tiles', 'q2-counting-iq2-tail16', 'q2-counting-iq2-register-stage', 'q2-counting-down-register-palette', 'q2-counting-iq2-slice-commit', 'q2-counting-iq2-pair-commit', 'q2-counting-iq2-sign-mask', 'q2-counting-iq2-raw-prefetch', 'q2-counting-down-raw-prefetch', 'q2-counting-expert-cache', 'q2-counting-compressed-cache', 'q2-counting-q8-mirror', 'q2-counting-scaled-wave-pack', 'q2-counting-scaled-expert-order', 'q2-counting-compact-expert-chain', 'q2-counting-producer-q8', 'q2-counting-shared-q8-pair', 'q2-counting-q8-aligned-pair', 'q2-counting-q8-k16-phases', 'ud-counting-legacy')
    if counting_mode and '--rebuild-mmq' not in sys.argv[2:] and not replay_label:
        raise SystemExit('Historical counting requires a full MMQ rebuild')
    original_mode = mode in ('q2-original-baseline', 'ud-original-baseline')
    if original_mode and '--rebuild-mmq' not in sys.argv[2:]:
        raise SystemExit('Original baseline requires a full MMQ rebuild')
    terminal_run = mode in ('q2-terminal-probe', 'q2-terminal-smoke', 'q2-terminal-full')
    terminal_build = mode in ('q2-terminal-build', 'q2-terminal-probe', 'q2-terminal-smoke', 'q2-terminal-full')
    terminal_cpu = mode == 'terminal-cpu'
    native_cpu = mode == 'native-curve-cpu'
    cpu_mode = curve256_cpu or native_cpu or mode in ('ple-cache-first-cpu', 'terminal-cpu', 'cpu', 'ple-cpu', 'ple-io-cpu', 'ple-cache-cpu', 'ple-lookahead-cpu')
    io_mode = mode in ('q2-ple-io', 'ud-ple-io')
    ple_mode = mode in ('q2-ple', 'ud-ple', 'q2-ple-cache64k', 'q2-ple-lookahead', 'q2-ple-first-access')
    ple_target = 'q2_ple_lookahead' if mode in ('q2-ple-lookahead', 'q2-ple-first-access') else 'q2_ple'
    model_mode = bool(saved_profile) or counting_mode or curve_mode or original_mode or terminal_run or io_mode or ple_mode or mode in ('q2-smoke','q2-bench','q2-bench2k','ud-bench2k','q2-decode-baseline','ud-decode-baseline','q2-profile','ud-profile','ud-base','ud-patched')
    profile_mode = (bool(saved_profile) and not routing_mode) or mode in ('q2-profile','ud-profile')
    mixed_mode = mode in ('iq2-mixed-reference-check', 'iq2-mixed-check')
    hc_mode = mixed_mode or mode in ('iq2-whole640-wave16-check', 'iq2-whole640-check', 'attention-capacity-check', 'down-fixed-contract-check', 'down-fixed-bounds-check', 'iq2-table-lds-check', 'iq2-dpp-commit-check', 'iq2-fixed-bounds-check', 'iq2-half-sign-arithmetic-check', 'hc-norm-owner-check', 'hc-inject-reuse-check', 'compressed-cache-check', 'expert-cache-check', 'q8-mirror-check', 'scaled-wave-pack-check', 'scaled-expert-order-check', 'compact-expert-chain-check', 'producer-q8-check', 'shared-q8-pair-check', 'q8-aligned-pair-check', 'q8-k16-phases-check', 'down-raw-prefetch-check', 'iq2-fused-grid-check', 'half-fixed-width-check', 'half-consumer-eight-check', 'shared-down-fixed-check', 'shared-down-n64-check', 'ssm-row-group-check', 'ssm-fixed-shape-check', 'ssm-fixed-bounds-check', 'ssm-channel-bounds-check', 'ssm-compact-lds-check', 'ssm-pingpong-check', 'down-register-scatter-check', 'down-half-vector-check', 'down-half-pair-check', 'down-half-storage-check', 'down-live-stage-check', 'down-output-reuse-check', 'iq2-wide-pair-check', 'iq2-four-wave-check', 'iq2-lane-commit-check', 'iq2-short-tiles-check', 'iq2-tail16-check', 'iq2-register-stage-check', 'down-register-palette-check', 'iq2-slice-commit-check', 'iq2-sign-mask-check', 'iq2-raw-prefetch-check', 'ssm-row128-check', 'q8-halfpair-check', 'iq2-halfbyte-check', 'iq2-halfstage-check', 'q8-grouped-check', 'hc-bk256-bench', 'shared-q8-oracle-replay', 'shared-q8-producer-check', 'scaled-row-check', 'iq2-live-epilogue-check', 'iq2-wmma-signs-check', 'iq2-signs-check', 'hc-operators', 'hc-bench', 'hc-pp-operators', 'hc-pp-bench', 'hc-library-bench', 'hc-library-norm-bench', 'hc-norm-ragged-bench', 'hc-library-ragged-bench', 'hc-decode-reduce-bench', 'hc-input-bench', 'hc-up-chain-bench', 'hc-up-operators', 'hc-up-bench', 'hc-moe-operators', 'hc-moe-bench', 'hc-norm-operators', 'hc-norm-bench', 'hc-sequence-bench', 'hc-deferred-bench', 'routed-operators', 'iq2-pair-operators', 'shared-fork-check', 'scaled-input-check', 'scaled-tiles-check', 'narrow-vector-check', 'packed-operators', 'packed-bench', 'packed-tiles-bench', 'packed-tiles16-bench')
    hc_target = 'q2_iq2_whole640_wave16_check' if mode == 'iq2-whole640-wave16-check' else 'q2_iq2_whole640_check' if mode == 'iq2-whole640-check' else 'q2_attention_capacity_check' if mode == 'attention-capacity-check' else 'q2_down_fixed_contract_check' if mode == 'down-fixed-contract-check' else 'q2_down_fixed_bounds_check' if mode == 'down-fixed-bounds-check' else 'q2_iq2_table_lds_check' if mode == 'iq2-table-lds-check' else 'q2_iq2_dpp_commit_check' if mode == 'iq2-dpp-commit-check' else 'q2_iq2_fixed_bounds_check' if mode == 'iq2-fixed-bounds-check' else 'q2_iq2_half_sign_arithmetic_check' if mode == 'iq2-half-sign-arithmetic-check' else 'q2_hc_norm_owner' if mode == 'hc-norm-owner-check' else 'q2_hc_inject_reuse' if mode == 'hc-inject-reuse-check' else 'q2_compressed_cache' if mode == 'compressed-cache-check' else 'q2_expert_cache' if mode == 'expert-cache-check' else 'q2_shared_down_mirror' if mode in ('shared-down-fixed-check', 'shared-down-n64-check') else 'q2_ssm_compact_lds' if mode in ('ssm-compact-lds-check', 'ssm-pingpong-check') else 'q2_ssm_row_group' if mode in ('ssm-fixed-shape-check', 'ssm-fixed-bounds-check', 'ssm-channel-bounds-check') else 'q2_ssm_row_group' if mode == 'ssm-row-group-check' else 'q2_down_register_scatter' if mode == 'down-register-scatter-check' else 'q2_producer_q8' if mode == 'producer-q8-check' else 'q2_compact_expert_chain' if mode == 'compact-expert-chain-check' else 'q2_scaled_expert_order' if mode == 'scaled-expert-order-check' else 'q2_scaled_wave_pack' if mode == 'scaled-wave-pack-check' else 'q2_shared_q8_pair' if mode == 'shared-q8-pair-check' else 'q2_q8_aligned_pair' if mode == 'q8-aligned-pair-check' else 'q2_half_fixed_width' if mode == 'half-fixed-width-check' else 'q2_half_consumer_eight' if mode == 'half-consumer-eight-check' else 'q2_down_half_vector' if mode == 'down-half-vector-check' else 'q2_down_half_pair' if mode == 'down-half-pair-check' else 'q2_down_half_storage' if mode == 'down-half-storage-check' else 'q2_down_live_stage' if mode == 'down-live-stage-check' else 'q2_down_output_reuse' if mode == 'down-output-reuse-check' else 'q2_iq2_four_wave' if mode == 'iq2-four-wave-check' else 'q2_iq2_wide_pair' if mode == 'iq2-wide-pair-check' else 'q2_iq2_lane_commit' if mode == 'iq2-lane-commit-check' else 'q2_down_register_palette_check' if mode=='down-register-palette-check' else 'q2_iq2_register_stage_check' if mode=='iq2-register-stage-check' else 'q2_iq2_tail16_check' if mode == 'iq2-tail16-check' else 'q2_iq2_short_tiles_check' if mode == 'iq2-short-tiles-check' else 'q2_iq2_slice_commit' if mode == 'iq2-slice-commit-check' else 'q2_q8_mirror' if mode == 'q8-mirror-check' else 'q2_iq2_sign_mask' if mode == 'iq2-sign-mask-check' else 'q2_iq2_fused_grid' if mode == 'iq2-fused-grid-check' else 'q2_q8_k16_phases' if mode == 'q8-k16-phases-check' else 'q2_down_raw_prefetch' if mode == 'down-raw-prefetch-check' else 'q2_iq2_raw_prefetch' if mode == 'iq2-raw-prefetch-check' else 'q2_ssm_row128' if mode == 'ssm-row128-check' else 'q2_q8_halfpair' if mode == 'q8-halfpair-check' else 'q2_iq2_halfbyte' if mode == 'iq2-halfbyte-check' else 'q2_iq2_halfstage' if mode == 'iq2-halfstage-check' else 'q2_q8_grouped' if mode == 'q8-grouped-check' else 'q2_hc_bk256' if mode == 'hc-bk256-bench' else 'q2_shared_q8_oracle_replay' if mode == 'shared-q8-oracle-replay' else 'q2_shared_q8_producer' if mode == 'shared-q8-producer-check' else 'q2_scaled_row_reuse' if mode == 'scaled-row-check' else 'q2_iq2_mixed_tiles' if mixed_mode else 'q2_iq2_live_epilogue' if mode == 'iq2-live-epilogue-check' else 'q2_iq2_wmma_signs' if mode == 'iq2-wmma-signs-check' else 'q2_iq2_signs' if mode == 'iq2-signs-check' else 'q2_hc_library_ragged' if mode == 'hc-library-ragged-bench' else 'q2_hc_decode_reduce' if mode == 'hc-decode-reduce-bench' else 'q2_hc_library_norm' if mode in ('hc-library-norm-bench', 'hc-norm-ragged-bench') else 'q2_narrow_vector' if mode == 'narrow-vector-check' else 'q2_scaled_tiles' if mode == 'scaled-tiles-check' else 'q2_scaled' if mode == 'scaled-input-check' else 'q2_shared_fork' if mode == 'shared-fork-check' else 'q2_hc_deferred_norm' if mode == 'hc-deferred-bench' else 'q2_hc_sequence' if mode == 'hc-sequence-bench' else 'q2_hc_up_chains' if mode == 'hc-up-chain-bench' else 'q2_hc_input' if mode == 'hc-input-bench' else 'q2_hc_norm_half' if mode.startswith('hc-norm-') else 'q2_hc_moe_fused' if mode.startswith('hc-moe-') else 'q2_hc_up_fused' if mode == 'hc-up-operators' else 'q2_packed_bench' if mode in ('packed-bench', 'packed-tiles-bench', 'packed-tiles16-bench') else 'q2_packed' if mode == 'packed-operators' else 'q2_iq2_pair' if mode == 'iq2-pair-operators' else 'q2_routed' if mode == 'routed-operators' else 'q2_hc_pp' if mode.startswith('hc-pp-') or mode == 'hc-library-bench' else 'q2_hc'
    if not cpu_mode and not counter_mode and mode not in ('hip-build', 'operators', 'operators-reference') and not model_mode and not hc_mode and not terminal_build:
        raise SystemExit('Unsupported mode')
    result = {'state': 'RUNNING', 'mode': mode, 'started_at': now(),
              'pid': os.getpid(), 'commands': [], 'locks': [], 'model_access': False}
    if counting_mode:
        result['timed_scope'] = 'Frozen historical counting pp2048/tg128: one warmup, three measurements, 127 timed decode calls, 15-second pauses outside timing; not canonical HTTP'
    if mode.endswith('decode-baseline'):
        result['timed_scope'] = 'pp2048/tg127-forward legacy scope plus historical2042/tg128-completed; full finite checks retained in both; no MTP'
    if original_mode:
        result['timed_scope'] = 'Unchanged historical C17 ABI benchmark: physical prompts up to 512/2048/8192, 128 completed steps, production greedy, EOS honored; finite frontier checks outside timers'
    results = ROOT/'results'; results.mkdir()
    held = []
    model_paths = []
    registered = False
    def clients():
        return sorted(int(p.name) for p in Path('/sys/class/kfd/kfd/proc').glob('*') if p.name.isdecimal())
    def observation(pid=None):
        row={'at':now(),'kfd':clients(),'thermal':thermal_sample()}
        for name in ['meminfo']:
            row[name]=Path('/proc',name).read_text()
        row['sensors']={}
        for pattern in ['card*/device/gpu_busy_percent','card*/device/pp_dpm_sclk',
                        'card*/device/hwmon/hwmon*/temp*_input','card*/device/hwmon/hwmon*/power*_average']:
            for path in Path('/sys/class/drm').glob(pattern):
                try: row['sensors'][str(path)]=path.read_text().strip()
                except OSError as ex: row['sensors'][str(path)]=str(ex)
        if pid:
            for name in ['status','io','stat']:
                try: row[name]=Path('/proc',str(pid),name).read_text()
                except OSError as ex: row[name]=str(ex)
        with (results/'telemetry.jsonl').open('a') as stream: stream.write(json.dumps(row)+'\n')
        if any(sensor['over_limit'] for sensor in row['thermal']):
            result['thermal_stop'] = row['thermal']
            save()
        thermal_enforce(row['thermal'])
    def device_observers():
        observers=[];denied=0
        for proc in Path('/proc').glob('[0-9]*'):
            try:
                found=[]
                for fd in (proc/'fd').iterdir():
                    try: target=os.readlink(fd)
                    except FileNotFoundError: continue
                    if target=='/dev/kfd' or target.startswith('/dev/dri/') or target.endswith('.gguf'): found.append(target)
                if found: observers.append({'pid':int(proc.name),'comm':(proc/'comm').read_text().strip(),'handles':sorted(set(found))})
            except (PermissionError,FileNotFoundError): denied+=1
        return {'observers':observers,'unreadable_or_retired_processes':denied}
    def register(event):
        row = {'event': event, 'owner': 'synapse-lie-q2', 'label': ROOT.name,
               'pid': os.getpid(), 'start_ticks': Path('/proc/self/stat').read_text().split(') ',1)[1].split()[19],
               'at': now(), 'mode': mode, 'source_pin': 'f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
               'model_access': result['model_access'], 'state': result['state']}
        fd = os.open('/tmp/synapse-lie-ds4-coordination/runs.jsonl',os.O_WRONLY|os.O_APPEND|os.O_CREAT,0o600)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX);os.write(fd,(json.dumps(row)+'\n').encode());os.fsync(fd)
        finally: os.close(fd)
    def save():
        (results/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    def stat_model(path):
        st=Path(path).stat()
        return {'path':path,'bytes':st.st_size,'device':st.st_dev,'inode':st.st_ino,
                'mtime_ns':st.st_mtime_ns,'ctime_ns':st.st_ctime_ns}
    def run(argv, env, limit=1800):
        observation()
        row = {'argv': argv, 'started_at': now()}; result['commands'].append(row); save()
        logfile = results/f'{len(result["commands"]):02}.log'
        with logfile.open('wb') as log:
            try:
                supervise(argv,cwd=ROOT,env=env,log=log,row=row,timeout=limit,save=save,
                          clients=clients if not cpu_mode else lambda: (),
                          observe=observation,
                          allow_child_groups=routing_mode and argv[0] == 'gdb')
            finally:
                row['finished_at']=now();save()
        row['finished_at'] = now(); save()
        print(json.dumps(row),flush=True)
        print(logfile.read_text(),flush=True)
        if row['exit_code'] or row.get('timeout'):
            raise RuntimeError('Qualification command failed')
    save()
    try:
        if not cpu_mode:
            for name in LOCKS:
                before=os.stat(name,follow_symlinks=False)
                fd=os.open(name,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW)
                try: fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BaseException: os.close(fd);raise
                held.append(fd);after=os.fstat(fd);live=os.stat(name,follow_symlinks=False)
                if (before.st_dev,before.st_ino)!=(after.st_dev,after.st_ino) or (after.st_dev,after.st_ino)!=(live.st_dev,live.st_ino):
                    raise RuntimeError('Lease identity changed')
                expected=[(52,3232146),(52,3206482),(52,3228451),(55,45067)][len(held)-1]
                if (after.st_dev,after.st_ino)!=expected: raise RuntimeError('Unexpected lease identity')
                result['locks'].append({'path':name,'device':after.st_dev,'inode':after.st_ino})
            result['preflight_kfd']=clients()
            result['meminfo']=Path('/proc/meminfo').read_text()
            result['power']={str(p):p.read_text() for pattern in ['card*/device/gpu_busy_percent','card*/device/power_dpm_force_performance_level','card*/device/pp_dpm_sclk'] for p in Path('/sys/class/drm').glob(pattern)}
            result['visibility_limit']='KFD and readable proc/sysfs only; desktop and denied FD coverage not exclusivity proof'
            result['preflight_observers']=device_observers()
            if result['preflight_kfd']: raise RuntimeError('Foreign KFD client before build/launch')
            if any(handle.endswith('.gguf') for proc in result['preflight_observers']['observers'] for handle in proc['handles']):
                raise RuntimeError('Foreign model handle before build/launch')
            register('start');registered=True
        if mode == 'shared-q8-oracle-replay':
            result['oracle_replay_data'] = verify_oracle_replay(ROOT, staged=True)
            save()
        if model_mode:
            if profile_mode:
                profiler=shutil.which('rocprofv3')
                if profiler is None and Path('/opt/rocm/bin/rocprofv3').is_file(): profiler='/opt/rocm/bin/rocprofv3'
                if profiler is None: raise RuntimeError('Installed rocprofv3 unavailable; no dependency installation attempted')
                result['profiler']=profiler
            inventory=json.loads((ROOT/'config/models-157.inventory.json').read_text())['files']
            if mode.startswith('q2-'):
                selected=[f for f in inventory if f['path'].endswith('/Qwen3.8-Flash-Next-Q2.gguf')]
            else:
                selected=[f for f in inventory if '/Qwen3.8-Flash-Next-UD-Q4_K_XL-' in f['path']]
            if len(selected)!=(1 if mode.startswith('q2-') else 4): raise RuntimeError('Incomplete model inventory')
            model_paths=[f['path'] for f in selected]
            result['models_before']=[stat_model(p) for p in model_paths]
            for actual,expected in zip(result['models_before'],selected):
                if any(actual[k]!=expected[k] for k in actual): raise RuntimeError('Model identity differs from inventory')
            result['model_hash_scope']='Stat inventory; no full payload rehash'
            result['resource_scope']='Quantized AR weights only; PLE read through upstream bounded row cache; MTP disabled; context 9216/chunk 2048'
            if mode in ('q2-ple-lookahead', 'q2-ple-first-access'):
                result['resource_scope']='Original Q2 AR weights; native/prepared-serial/C17-lookahead; unchanged kernels/cache; context 8224/chunk 2048; two bounded pinned PLE buffers; no page eviction'
            if mode == 'q2-ple-first-access':
                result['resource_scope']='Original Q2 AR weights; eight new input sets with native/C17-lookahead first order ABBAABBA; warmup on padding; page residency observed; context 8224/chunk 2048; two bounded pinned PLE buffers; no page eviction'
            if io_mode:
                result['resource_scope']='Original PLE rows only; no model upload or forward; descriptor-local advice and bounded BF16 cache capacity; no cache eviction or file mutation'
            save()
        env = {k:v for k,v in os.environ.items() if not k.startswith(('GUFO_','DS4_','HIP_','ROCR_','HSA_','CUDA_')) and k not in ('LD_PRELOAD','LD_LIBRARY_PATH')}
        env.update(LC_ALL='C',HIP_VISIBLE_DEVICES='-1',ROCR_VISIBLE_DEVICES='-1',
                   ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
        replay_binary = None
        if replay_label:
            replay_binary, replay = verify_replay(ROOT, replay_label,
                saved_profile[1] if saved_profile else mode, env,
                **({'manifest_name': saved_profile[2]} if saved_profile else {}))
            result['qualified_binary_replay'] = replay
            if saved_profile:
                result['timed_scope'] = 'Diagnostic-only original counting input2048/capacity9216/chunk2048; existing builtin profile warmup16/output16/decode15; not bench2k or a new throughput comparison'
                result['headline_eligible'] = False
            save()
        reuse_args=[]
        if mode.endswith('bench2k') and '--rebuild-mmq' not in sys.argv[2:]:
            observation()
            previous=ROOT.parent/('q2-explore-reference-r1' if mode.startswith('q2-') else 'q2-explore-ud-r1')
            receipt=json.loads((previous/'results/result.json').read_text())
            if receipt['state']!='MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT' or any(c['exit_code'] for c in receipt['commands']):
                raise RuntimeError('MMQ reuse reference was not qualified')
            identity=verify_sources(previous/'source', ROOT/'source')
            prior_binary=previous/'build/hip/cmake/hip/q2_model'
            if hashlib.sha256(prior_binary.read_bytes()).hexdigest()!=receipt['binary_sha256_after']:
                raise RuntimeError('MMQ reuse reference binary changed')
            archive=previous/'build/hip/cmake/hip/qwen/libgufo_qwen38_flash_next_mmq.a'
            digest=hashlib.sha256(archive.read_bytes()).hexdigest()
            reuse=ROOT/'reuse';reuse.mkdir()
            copied=reuse/'libgufo_qwen38_flash_next_mmq.a'
            shutil.copyfile(archive,copied)
            if hashlib.sha256(copied.read_bytes()).hexdigest()!=digest:
                raise RuntimeError('MMQ archive copy differs')
            result['mmq_reuse']=dict(identity,reference=str(previous),archive=str(archive),sha256=digest,
                                     reference_binary_sha256=receipt['binary_sha256_after'])
            reuse_args=['-DQ2_MMQ_ARCHIVE='+str(copied)]
            save()
        if curve256:
            pins=json.loads((ROOT/'config/q2-curve256-binaries.json').read_text())['providers'][mode]
            previous=ROOT.parent/pins['label']
            old_receipt=previous/'results/result.json'
            if hashlib.sha256(old_receipt.read_bytes()).hexdigest()!=pins['receipt_sha256']:
                raise RuntimeError('Matched MMQ qualification changed')
            old=json.loads(old_receipt.read_text())
            if not old.get('finished_at') or any(c['exit_code'] for c in old['commands']):
                raise RuntimeError('Matched MMQ source cohort is incomplete')
            identity=verify_sources(previous/'source', ROOT/'source', curve_headroom=True)
            archive=previous/'build/hip/cmake/hip/qwen/libgufo_qwen38_flash_next_mmq.a'
            digest=hashlib.sha256(archive.read_bytes()).hexdigest()
            reuse=ROOT/'reuse';reuse.mkdir()
            copied=reuse/'libgufo_qwen38_flash_next_mmq.a'
            shutil.copyfile(archive,copied)
            if hashlib.sha256(copied.read_bytes()).hexdigest()!=digest:
                raise RuntimeError('Matched MMQ copy differs')
            result['mmq_reuse']=dict(identity, reference=str(previous), archive=str(archive), sha256=digest,
                                    receipt_sha256=pins['receipt_sha256'], original_build_unchanged=True)
            reuse_args=['-DQ2_MMQ_ARCHIVE='+str(copied)]
            save()
        if curve128:
            from q2_curve128 import verify_server
            reused_curve_binary, result['curve_server_reuse'] = verify_server(ROOT)
            save()
        if native_cpu:
            _, bench_manifest = verify_native_curve(ROOT, staged=True)
            result['native_bench_commit'] = bench_manifest['commit']
            save()
        if native_curve:
            bench_source, bench_manifest = verify_native_curve(ROOT, staged=True)
            if curve256 or curve128:
                pins=json.loads((ROOT/('config/q2-curve128-binaries.json' if curve128 else 'config/q2-curve256-binaries.json')).read_text())['native_bench']
                previous=ROOT.parent/pins['label']
                if hashlib.sha256((previous/'results/result.json').read_bytes()).hexdigest()!=pins['receipt_sha256']:
                    raise RuntimeError('Native benchmark qualification changed')
                bench_binary=previous/'build/native-bench/synapse-lie-bench'
                if hashlib.sha256(bench_binary.read_bytes()).hexdigest()!=pins['binary_sha256']:
                    raise RuntimeError('Qualified native benchmark binary changed')
                result['native_bench_binary_sha256']=pins['binary_sha256']
                result['native_bench_reused']=True
            else:
                bench_build = ROOT/'build/native-bench'
                run(['cmake', '-S', str(bench_source), '-B', str(bench_build), '-G', 'Ninja',
                     '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_TESTING=OFF',
                     '-DLIE_GUFO_RUNTIME=OFF', '-DLIE_LEGACY_PYTHON_TESTS=OFF',
                     '-DLIE_BUILD_ID=q2-native-canonical-bench'], env)
                run(['cmake', '--build', str(bench_build), '--parallel', '2',
                     '--target', 'synapse-lie-bench'], env)
                bench_binary = bench_build/'synapse-lie-bench'
                result['native_bench_binary_sha256'] = hashlib.sha256(bench_binary.read_bytes()).hexdigest()
            result['native_bench_commit'] = bench_manifest['commit']
            run([str(bench_binary), '--suite', 'http-curve', '--help'], env, 30)
            save()
        if counter_mode:
            counter_calibration(ROOT, result, run, env, save)
        profiles=[] if counter_mode else [('debug',False),('sanitize',True)] if cpu_mode else [('io' if io_mode else 'hip',False)]
        for name,sanitize in profiles:
            build = ROOT/'build'/name
            if not replay_label and not curve128:
                run(['cmake','-S',str(ROOT/'curve-core' if curve256_cpu else ROOT/'native-bench-core' if native_cpu else ROOT/'terminal-core' if terminal_cpu else ROOT),'-B',str(build),'-G','Ninja',
                     '-DCMAKE_BUILD_TYPE='+('Debug' if cpu_mode else 'RelWithDebInfo'),
                     '-DQ2_SANITIZERS='+('ON' if sanitize else 'OFF'),
                     '-DQ2_HIP='+('OFF' if cpu_mode or io_mode else 'ON'),
                     '-DCMAKE_HIP_ARCHITECTURES=gfx1151']+(['-DLIE_SANITIZERS='+('ON' if sanitize else 'OFF')] if terminal_cpu or native_cpu or curve256_cpu else [])+(['-DLIE_LEGACY_PYTHON_TESTS=OFF', '-DLIE_GUFO_RUNTIME=OFF'] if native_cpu or curve256_cpu else [])+(['-DQ2_CURVE_RETAINED256=ON', '-DQ2_CURVE_RETAINED256_Q2='+('ON' if mode=='q2-curve256' else 'OFF')] if curve256 else [])+(['-DQ2_TERMINAL_SERVER=ON'] if terminal_build else [])+(['-DQ2_COUNTING_BASELINE=ON'] if counting_mode else [])+(['-DQ2_ORIGINAL_BASELINE=ON'] if original_mode else [])+(['-DQ2_CURVE_SERVER=ON'] if curve_mode else [])+(['-DQ2_CURVE_IQ2_SIGNS=ON'] if curve_iq2 else [])+(['-DQ2_POINT_NORM=ON'] if point_norm else [])+(['-DQ2_CURVE_SCALED_ROW=ON'] if curve_row else [])+(['-DQ2_CURVE_IQ2_SCALE=ON'] if curve_scale else [])+(['-DQ2_CURVE_IQ2_MIXED=ON'] if curve_mixed else [])+(['-DQ2_CURVE_PLE_CACHE_FIRST=ON'] if curve_cache_first else [])+(['-DQ2_CURVE_ROUTE_PROFILE=ON'] if curve_routes else [])+(['-DQ2_PLE_CACHE_FIRST_CHECKS=ON'] if mode == 'ple-cache-first-cpu' else [])+reuse_args,env)
                # Bound CPU build pressure after the recorded two-job thermal
                # stop. This changes build concurrency, not runtime device policy.
                build_args=['cmake','--build',str(build),'--parallel','1' if model_mode or terminal_build else '2']
                if native_cpu:
                    build_args += ['--target', 'synapse-lie-bench', 'test-native-bench',
                                   'test-http-multi-native', 'test-http-curve-native',
                                   'test-ssd-http-server', 'test-synthetic-lie-bench']
                if not cpu_mode:build_args+=['--target','synapse-lie-server' if terminal_build or curve_mode else 'q2_original_baseline' if original_mode else 'q2_ple_io' if io_mode else ple_target if ple_mode else 'q2_model' if model_mode else hc_target if hc_mode else 'q2_operators']
                if mode == 'iq2-signs-check':build_args+=['q2_operators']
                run(build_args,env)
            if cpu_mode:
                run(['ctest','--test-dir',str(build),'--output-on-failure']+
                    (['-R', '^native-(http-curve|http-multi|benchmark)-contract$'] if native_cpu else [])+
                    (['--verbose'] if mode == 'ple-cache-first-cpu' else []),env)
            elif terminal_build:
                binary=build/'cmake/terminal/core/synapse-lie-server'
                result['binary_sha256']=hashlib.sha256(binary.read_bytes()).hexdigest()
                run([str(binary),'--build-info'],env,30)
                run([str(binary),'--help'],env,30)
                result['binary_sha256_after']=hashlib.sha256(binary.read_bytes()).hexdigest()
                if result['binary_sha256']!=result['binary_sha256_after']: raise RuntimeError('Binary changed')
                if terminal_run:
                    result['resource_scope']='Original Q2 AR weights; C17 HTTP, capacity 262144/chunk2048; C1, MTP/prefix/thinking off; default/maximum output4096; request timeout1800s'
                    result['model_access']=True
                    save()
                    run(['python3',str(ROOT/'tools/q2-terminal-session.py'),str(binary),model_paths[0],mode.removeprefix('q2-terminal-')],
                        dict(env,HIP_VISIBLE_DEVICES='0',ROCR_VISIBLE_DEVICES='0'),
                        1800 if mode.endswith('probe') else 2*10800*(19 if mode.endswith('full') else 1)+3600)
                    result['binary_sha256_after']=hashlib.sha256(binary.read_bytes()).hexdigest()
                    if result['binary_sha256']!=result['binary_sha256_after']: raise RuntimeError('Binary changed')
            elif curve_mode:
                binary=reused_curve_binary if curve128 else build/'cmake/curve/core/synapse-lie-server'
                result['binary_sha256']=hashlib.sha256(binary.read_bytes()).hexdigest()
                run([str(binary),'--build-info'],env,30)
                run([str(binary),'--help'],env,30)
                result['resource_scope']=('Pinned Gufo AR prose depth recipe through262144 over common C17 HTTP, capacity266240/chunk2048/C1, RAM prefix enabled, SSD/MTP/vision off; completed executor-call timers' if curve256 else 'Pinned Gufo AR prose depth recipe over common C17 HTTP, context133760/chunk2048/C1, RAM prefix enabled, SSD/MTP/vision off; LIE completed executor-call timers')
                result['model_access']=True
                save()
                try:
                    run(['python3','-B',str(ROOT/('tools/q2-curve256-session.py' if curve256 else 'tools/q2-curve-session.py')),str(binary),model_paths[0],
                         'q2' if mode.startswith('q2-') else 'ud']+(['--native-bench', str(bench_binary)] if native_curve else [])+(['--point-only'] if point_only else [])+(['--prefill-only-depth',str(prefill_depth)] if prefill_depth else [])+(['--retained-prefill'] if full_prefill128 else ['--retained-128'] if curve128 else ['--iq2-signs'] if mode=='q2-curve256' else ['--norm-ragged'] if point_norm else ['--scaled-row'] if curve_row else ['--iq2-scale'] if curve_scale else ['--iq2-mixed'] if curve_mixed else ['--profile-routes'] if curve_routes else ['--profile-ple'] if curve_profile else ['--ple-cache-first'] if curve_cache_first else ['--iq2-signs'] if curve_iq2 else []),
                        dict(env,HIP_VISIBLE_DEVICES='0',ROCR_VISIBLE_DEVICES='0'),18000 if curve256 else 3000)
                finally:
                    result['binary_sha256_after']=hashlib.sha256(binary.read_bytes()).hexdigest()
                    if result['binary_sha256_after']!=result['binary_sha256']:raise RuntimeError('Binary changed')
                    if native_curve:
                        result['native_bench_binary_sha256_after'] = hashlib.sha256(bench_binary.read_bytes()).hexdigest()
                        if result['native_bench_binary_sha256_after'] != result['native_bench_binary_sha256']:
                            raise RuntimeError('Native benchmark binary changed')
            elif original_mode:
                binary=build/'cmake/original-baseline/q2_original_baseline'
                result['binary_sha256']=hashlib.sha256(binary.read_bytes()).hexdigest()
                try:
                    run(['ldd',str(binary)],env,30)
                    run([str(binary),'--build-info'],env,30)
                    result['model_access']=True
                    save()
                    run([str(binary),'--model',model_paths[0],'--output',str(results/'measurements.jsonl')],
                        dict(env,HIP_VISIBLE_DEVICES='0',ROCR_VISIBLE_DEVICES='0'),1800)
                finally:
                    result['binary_sha256_after']=hashlib.sha256(binary.read_bytes()).hexdigest()
                    if result['binary_sha256_after']!=result['binary_sha256']: raise RuntimeError('Binary changed')
            elif io_mode:
                binary=build/'q2_ple_io'
                result['binary_sha256']=hashlib.sha256(binary.read_bytes()).hexdigest()
                result['model_access']=True
                save()
                try:
                    run([str(binary),model_paths[0]],env,600)
                finally:
                    result['binary_sha256_after']=hashlib.sha256(binary.read_bytes()).hexdigest()
                    if result['binary_sha256_after']!=result['binary_sha256']: raise RuntimeError('Binary changed')
            elif mode in ('operators','operators-reference'):
                gpu_env=dict(env,HIP_VISIBLE_DEVICES='0',ROCR_VISIBLE_DEVICES='0')
                run([str(build/'cmake/hip/q2_operators')],gpu_env,120)
            elif hc_mode:
                binary=build/'cmake/hip'/hc_target
                if mode == 'iq2-signs-check':
                    run([str(build/'cmake/hip/q2_operators')],
                        dict(env,HIP_VISIBLE_DEVICES='0',ROCR_VISIBLE_DEVICES='0'),120)
                if mode == 'hc-library-bench': run(['ldd',str(binary)],env,30)
                result['binary_sha256']=hashlib.sha256(binary.read_bytes()).hexdigest()
                try:
                    run([str(binary)] + ([('mixed' if mode == 'iq2-mixed-check' else 'reference')] if mixed_mode else ['tiles16'] if mode == 'packed-tiles16-bench' else ['tiles'] if mode == 'packed-tiles-bench' else [] if mode in ('iq2-whole640-wave16-check', 'iq2-whole640-check', 'attention-capacity-check', 'down-fixed-contract-check', 'down-fixed-bounds-check', 'iq2-table-lds-check', 'iq2-dpp-commit-check', 'iq2-fixed-bounds-check', 'iq2-half-sign-arithmetic-check', 'hc-norm-owner-check', 'hc-inject-reuse-check', 'compressed-cache-check', 'expert-cache-check', 'q8-mirror-check', 'scaled-wave-pack-check', 'scaled-expert-order-check', 'compact-expert-chain-check', 'producer-q8-check', 'shared-q8-pair-check', 'q8-aligned-pair-check', 'q8-k16-phases-check', 'down-raw-prefetch-check', 'iq2-fused-grid-check', 'half-fixed-width-check', 'half-consumer-eight-check', 'shared-down-fixed-check', 'shared-down-n64-check', 'ssm-row-group-check', 'ssm-fixed-shape-check', 'ssm-fixed-bounds-check', 'ssm-channel-bounds-check', 'ssm-compact-lds-check', 'ssm-pingpong-check', 'down-register-scatter-check', 'down-half-vector-check', 'down-half-pair-check', 'down-half-storage-check', 'down-live-stage-check', 'down-output-reuse-check', 'iq2-wide-pair-check', 'iq2-four-wave-check', 'iq2-lane-commit-check', 'iq2-short-tiles-check', 'iq2-tail16-check', 'iq2-register-stage-check', 'down-register-palette-check', 'iq2-slice-commit-check', 'iq2-sign-mask-check', 'iq2-raw-prefetch-check', 'ssm-row128-check', 'q8-halfpair-check', 'iq2-halfbyte-check', 'iq2-halfstage-check', 'q8-grouped-check', 'hc-bk256-bench', 'shared-q8-oracle-replay', 'shared-q8-producer-check', 'scaled-row-check', 'iq2-live-epilogue-check', 'iq2-wmma-signs-check', 'iq2-signs-check', 'hc-input-bench', 'hc-up-chain-bench', 'hc-up-operators', 'routed-operators', 'iq2-pair-operators', 'shared-fork-check', 'scaled-input-check', 'scaled-tiles-check', 'narrow-vector-check', 'packed-operators', 'packed-bench') else ['ragged' if mode == 'hc-norm-ragged-bench' else 'library' if mode == 'hc-library-bench' else 'bench-up' if mode == 'hc-up-bench' else 'bench' if mode.endswith('-bench') else 'operators']),
                        dict(env,HIP_VISIBLE_DEVICES='0',ROCR_VISIBLE_DEVICES='0'),
                        600 if mode == 'attention-capacity-check' else 300 if mode in ('iq2-whole640-wave16-check', 'iq2-whole640-check', 'down-fixed-contract-check', 'down-fixed-bounds-check', 'iq2-table-lds-check', 'iq2-dpp-commit-check', 'iq2-fixed-bounds-check', 'iq2-half-sign-arithmetic-check', 'hc-norm-owner-check', 'hc-bk256-bench', 'hc-library-bench', 'hc-library-ragged-bench', 'hc-norm-ragged-bench') else 120)
                finally:
                    result['binary_sha256_after']=hashlib.sha256(binary.read_bytes()).hexdigest()
                    if result['binary_sha256_after']!=result['binary_sha256']: raise RuntimeError('Binary changed')
            elif model_mode:
                binary=replay_binary if replay_binary else build/'cmake/hip'/(ple_target if ple_mode else 'q2_model')
                result['binary_sha256']=hashlib.sha256(binary.read_bytes()).hexdigest()
                run(['ldd',str(binary)],env,30)
                result['model_access']=True
                save()
                if ple_mode:
                    run([str(binary),model_paths[0]] + (['--first-access'] if mode == 'q2-ple-first-access' else []),dict(env,HIP_VISIBLE_DEVICES='0',ROCR_VISIBLE_DEVICES='0'),1800)
                elif routing_mode:
                    result['diagnostic_scope'] = 'Host routing counts through GDB entry breakpoint; no performance claim or device trace'
                    save()
                    run(['gdb', '-nx', '-nh', '--batch', '-iex', 'set auto-load off',
                         '-ex', 'set pagination off', '-ex', 'set confirm off',
                         '-ex', 'set print thread-events off', '-ex', 'set disable-randomization off',
                         '-x', str(ROOT/'tools/q2_capture_routes.py'), '--args',
                         str(binary), model_paths[0], 'profile'],
                        dict(env, HIP_VISIBLE_DEVICES='0', ROCR_VISIBLE_DEVICES='0',
                             LIE_Q2_ROUTING_OUTPUT=str(results)), 300)
                elif profile_mode:
                    run([profiler,'--kernel-trace','-d',str(results/'profile'),'-o','q2','--',
                         str(binary),model_paths[0],'profile'],dict(env,HIP_VISIBLE_DEVICES='0',ROCR_VISIBLE_DEVICES='0'),1800)
                    run(['python3',str(ROOT/'source/tools/prof/prof.py'),'show',str(results/'profile/q2_results.db'),'--json'],env,120)
                    run(['python3',str(ROOT/'tools/analyze-q2-profile.py'),str(results/'profile/q2_results.db'),
                         str(results/'profile-phases.json')],env,120)
                    run(['python3',str(ROOT/'tools/q2-resource-report.py'),str(results/'profile/q2_results.db'),
                         str(results/'profile-resources.json')],env,120)
                else:
                    run([str(binary),model_paths[0],'smoke' if mode=='q2-smoke' else 'decode-baseline' if mode.endswith('decode-baseline') else 'bench2k' if counting_mode or mode.endswith('bench2k') else 'bench'],
                        dict(env,HIP_VISIBLE_DEVICES='0',ROCR_VISIBLE_DEVICES='0'),1800)
                result['binary_sha256_after']=hashlib.sha256(binary.read_bytes()).hexdigest()
                if result['binary_sha256_after']!=result['binary_sha256']: raise RuntimeError('Binary changed')
                result['runtime_libraries'] = libraries(binary, env)
                if replay_label and result['runtime_libraries'] != replay['libraries']:
                    raise RuntimeError('Replay libraries changed during model run')
        result['state'] = 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' if cpu_mode else 'HIP_BUILD_PASS_NOT_MODEL_QUALIFIED' if mode=='hip-build' else 'SYNTHETIC_OPERATORS_PASS_NOT_MODEL_QUALIFIED'
        if counter_mode: result['state']='SYNTHETIC_COUNTER_COLLECTION_COMPLETE_NOT_MODEL_INFERENCE'
        if terminal_build: result['state']='TERMINAL_SERVER_BUILT_NO_MODEL_EXECUTION'
        if model_mode: result['state']='MODEL_SMOKE_PASS' if mode=='q2-smoke' else 'MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT'
        if original_mode: result['state']='ORIGINAL_C17_BASELINE_COMPLETE_NOT_QUALITY_VERDICT'
        if curve_mode: result['state']='CANONICAL_ROUTE_PROFILE_COMPLETE_NOT_BENCHMARK' if curve_routes else 'CANONICAL_PLE_PROFILE_COMPLETE_NOT_BENCHMARK' if curve_profile else 'CANONICAL_HTTP_WORKLOAD_COMPLETE_NOT_PARITY_VERDICT'
        if terminal_run: result['state']='TERMINAL_ENDPOINT_PROBE_COMPLETE_NOT_TASK_SCORE' if mode.endswith('probe') else 'TERMINAL_BENCH_COMMAND_COMPLETE_INSPECT_REWARDS'
        if profile_mode: result['state']='DIAGNOSTIC_PROFILE_COMPLETE_NOT_WALL_BENCHMARK'
        if routing_mode: result['state']='DIAGNOSTIC_ROUTING_COMPLETE_NOT_WALL_BENCHMARK'
        if ple_mode: result['state']='PLE_DIAGNOSTIC_COMPLETE_NOT_PERFORMANCE_VERDICT'
        if io_mode: result['state']='PLE_ROW_IO_COMPLETE_NO_MODEL_FORWARD'
        if mixed_mode: result['state']='SYNTHETIC_IQ2_MIXED_CYCLE_COMPLETE_NOT_MODEL_THROUGHPUT'
        if mode == 'ssm-row128-check': result['state']='SYNTHETIC_SSM_ROW128_COMPLETE_NOT_MODEL_THROUGHPUT'
        if mode == 'q8-halfpair-check': result['state']='SYNTHETIC_Q8_HALFPAIR_COMPLETE_NOT_MODEL_THROUGHPUT'
        if mode == 'q8-grouped-check': result['state']='SYNTHETIC_Q8_GROUPED_COMPLETE_NOT_MODEL_THROUGHPUT'
        if mode == 'iq2-fused-grid-check': result['state']='SYNTHETIC_IQ2_FUSED_GRID_COMPLETE_NOT_MODEL_THROUGHPUT'
        if mode == 'q8-mirror-check': result['state']='SYNTHETIC_Q8_MIRROR_COMPLETE_NOT_MODEL_THROUGHPUT'
        if mode == 'iq2-tail16-check': result['state']='SYNTHETIC_IQ2_TAIL16_COMPLETE_NOT_MODEL_THROUGHPUT'
        if mode == 'iq2-slice-commit-check': result['state']='SYNTHETIC_IQ2_SLICE_COMMIT_COMPLETE_NOT_MODEL_THROUGHPUT'
        if mode == 'iq2-sign-mask-check': result['state']='SYNTHETIC_IQ2_SIGN_MASK_COMPLETE_NOT_MODEL_THROUGHPUT'
        if mode == 'iq2-halfbyte-check': result['state']='SYNTHETIC_IQ2_HALFBYTE_COMPLETE_NOT_MODEL_THROUGHPUT'
        if mode == 'iq2-halfstage-check': result['state']='SYNTHETIC_IQ2_HALFSTAGE_COMPLETE_NOT_MODEL_THROUGHPUT'
        if mode == 'shared-q8-oracle-replay': result['state']='SAVED_ARRAY_ORACLE_REPLAY_COMPLETE_NOT_MODEL_QUALITY'
        if mode == 'iq2-live-epilogue-check': result['state']='SYNTHETIC_IQ2_EPILOGUE_CYCLE_COMPLETE_NOT_MODEL_THROUGHPUT'
        if mode == 'iq2-wmma-signs-check': result['state']='SYNTHETIC_IQ2_WMMA_CYCLE_COMPLETE_NOT_MODEL_THROUGHPUT'
        if mode == 'iq2-signs-check': result['state']='SYNTHETIC_IQ2_SIGN_CYCLE_COMPLETE_NOT_MODEL_THROUGHPUT'
        if mode == 'packed-bench': result['state']='SYNTHETIC_Q2_PACKED_MICROBENCH_COMPLETE_NOT_MODEL_THROUGHPUT'
        if mode in ('packed-tiles-bench', 'packed-tiles16-bench'): result['state']='SYNTHETIC_Q2_TILE_MICROBENCH_COMPLETE_NOT_MODEL_THROUGHPUT'
        if mode in ('hc-bk256-bench','hc-bench','hc-pp-bench','hc-library-bench','hc-library-norm-bench','hc-norm-ragged-bench','hc-library-ragged-bench','hc-decode-reduce-bench','hc-input-bench','hc-up-chain-bench','hc-up-bench','hc-moe-bench','hc-norm-bench','hc-sequence-bench','hc-deferred-bench'): result['state']='SYNTHETIC_HC_MICROBENCH_COMPLETE_NOT_MODEL_THROUGHPUT'
    except Exception as ex:
        result['state'] = 'FAILED'; result['error'] = repr(ex)
    finally:
        try:
            if 'oracle_replay_data' in result:
                result['oracle_replay_data_after'] = verify_oracle_replay(ROOT, staged=True)
                if result['oracle_replay_data_after'] != result['oracle_replay_data']:
                    raise RuntimeError('Q8 replay corpus changed during run')
            if terminal_run and result['model_access'] and not mode.endswith('probe'):
                run(['python3',str(ROOT/'tools/q2-terminal-session.py'),'--cleanup'],env,120)
            if 'mmq_reuse' in result:
                for archive_path in (Path(result['mmq_reuse']['archive']), ROOT/'reuse/libgufo_qwen38_flash_next_mmq.a'):
                    if hashlib.sha256(archive_path.read_bytes()).hexdigest()!=result['mmq_reuse']['sha256']:
                        raise RuntimeError('MMQ archive changed during run')
                result['mmq_reuse']['unchanged_after']=True
            if model_paths:
                result['models_after']=[stat_model(p) for p in model_paths]
                if result['models_after']!=result['models_before']: raise RuntimeError('Model identity changed')
            if not cpu_mode:
                result['postflight_kfd']=clients()
                result['postflight_observers']=device_observers()
                result['postflight_locks']=[{'path':name,'device':os.stat(name).st_dev,'inode':os.stat(name).st_ino} for name in LOCKS[:len(held)]]
                if result['postflight_locks']!=result['locks']: raise RuntimeError('Lease identity changed after run')
            result['artifacts']={str(p.relative_to(results)):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in results.rglob('*') if p.is_file() and p.name!='result.json'}
        except Exception as ex:
            result['state']='FAILED';result['postflight_error']=repr(ex)
        finally:
            try:
                if registered:register('end')
            finally:
                for fd in reversed(held): os.close(fd)
        result['finished_at'] = now(); save()
        print(json.dumps(result),flush=True)
    raise SystemExit(1 if result['state']=='FAILED' else 0)


if __name__ == '__main__':
    main()
