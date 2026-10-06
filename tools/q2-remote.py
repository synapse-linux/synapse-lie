#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Stage task-owned sources and fixed qualification jobs on .157 only."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
from q2_native_curve import MODES as NATIVE_CURVE_MODES, POINT_MODES, verify_source as verify_native_curve
import re
import shlex
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
HOST = 'paperboy@192.168.5.157'
REMOTE = '/home/paperboy/workspace/projects/synapse-linux/synapse-lie/run/'
COMBINED_VARIANTS = ('combined-retained', 'combined-scaled')
ORIGINAL_BASELINE_MODES = ('q2-original-baseline', 'ud-original-baseline')
SIGN_VARIANTS = ('iq2-signs-reference', 'iq2-signs-candidate', 'iq2-signs-ordered')
WMMA_SIGN_VARIANTS = ('iq2-wmma-reference', 'iq2-wmma-signs')
EPILOGUE_VARIANTS = ('iq2-epilogue-reference', 'iq2-live-epilogue', 'iq2-epilogue-break', 'iq2-live-stage',
                     'iq2-prefill-scale-reuse', 'iq2-prefill-grid-lds')
ROW_VARIANTS = ('scaled-row-reference', 'scaled-row-reuse')
NORM_SHAPE_VARIANTS = ('norm-shape-reference', 'norm-fixed-shape')
Q8_PRODUCER_VARIANT = 'shared-q8-producer'
HC_BK_VARIANTS = ('hc-bk256-initial', 'hc-bk256-bounded', 'hc-bk128-single', 'hc-bk128-double',
                  'hc-bn64-token', 'hc-bn64-output')
HC_BK_MODE = 'hc-bk256-bench'
HC_BK_COUNTING = {'q2-counting-hc-bk256-initial': 'hc-bk256-initial',
                  'q2-counting-hc-bk256-bounded': 'hc-bk256-bounded',
                  'q2-counting-hc-bk128-single': 'hc-bk128-single',
                  'q2-counting-hc-bk128-double': 'hc-bk128-double',
                  'q2-counting-hc-bn64-token': 'hc-bn64-token',
                  'q2-counting-hc-bn64-output': 'hc-bn64-output'}
HC_BK_MANIFESTS = {v: 'config/q2-hc-bn64-source.json' if v.startswith('hc-bn64-')
                     else 'config/q2-hc-bk128-source.json' if v.startswith('hc-bk128-')
                     else 'config/q2-hc-bk256-run-source.json' for v in HC_BK_VARIANTS}
DEFERRED_SOURCES = {'q2-counting-hc-moe-deferred': 'hc-moe-deferred'}
FIXED_PROFILE_MODE = 'q2-fixed-moe-profile'
CURRENT_PROFILE_MODE = 'q2-current-best-profile'
CURRENT_ROUTING_MODE = 'q2-current-routing'
EXPERT_CACHE_MANIFEST = 'config/q2-expert-cache-source-v3.json'
EXPERT_CACHE_MODE = 'expert-cache-check'
EXPERT_CACHE_MANIFESTS = {'expert-cache': EXPERT_CACHE_MANIFEST, 'compressed-cache': 'config/q2-compressed-cache-source-v2.json'}
EXPERT_CACHE_MODES = {name + '-check': name for name in EXPERT_CACHE_MANIFESTS}
EXPERT_CACHE_SOURCES = {'q2-counting-' + name: name for name in EXPERT_CACHE_MANIFESTS}
Q8_MIRROR_MANIFEST = 'config/q2-q8-mirror-source.json'
Q8_MIRROR_MODE = 'q8-mirror-check'
Q8_MIRROR_SOURCES = {'q2-counting-q8-mirror': 'q8-mirror'}
SCALED_WAVE_PACK_MANIFEST = 'config/q2-scaled-wave-pack-source.json'
SCALED_WAVE_PACK_MODE = 'scaled-wave-pack-check'
SCALED_WAVE_PACK_SOURCES = {'q2-counting-scaled-wave-pack': 'scaled-wave-pack'}
SCALED_EXPERT_ORDER_MANIFEST = 'config/q2-scaled-expert-order-source.json'
SCALED_EXPERT_ORDER_MODE = 'scaled-expert-order-check'
SCALED_EXPERT_ORDER_SOURCES = {'q2-counting-scaled-expert-order': 'scaled-expert-order'}
COMPACT_EXPERT_CHAIN_MANIFEST = 'config/q2-compact-expert-chain-source.json'
COMPACT_EXPERT_CHAIN_MODE = 'compact-expert-chain-check'
COMPACT_EXPERT_CHAIN_SOURCES = {'q2-counting-compact-expert-chain': 'compact-expert-chain'}
PRODUCER_Q8_MANIFEST = 'config/q2-producer-q8-source-v2.json'
PRODUCER_Q8_MODE = 'producer-q8-check'
PRODUCER_Q8_SOURCES = {'q2-counting-producer-q8': 'producer-q8'}
SHARED_Q8_PAIR_MANIFEST = 'config/q2-shared-q8-pair-source.json'
SHARED_Q8_PAIR_MODE = 'shared-q8-pair-check'
SHARED_Q8_PAIR_SOURCES = {'q2-counting-shared-q8-pair': 'shared-q8-pair'}
Q8_ALIGNED_PAIR_MANIFEST = 'config/q2-q8-aligned-pair-source.json'
Q8_ALIGNED_PAIR_MODE = 'q8-aligned-pair-check'
Q8_ALIGNED_PAIR_SOURCES = {'q2-counting-q8-aligned-pair': 'q8-aligned-pair'}
Q8_K16_PHASES_MANIFEST = 'config/q2-q8-k16-phases-source.json'
Q8_K16_PHASES_MODE = 'q8-k16-phases-check'
Q8_K16_PHASES_SOURCES = {'q2-counting-q8-k16-phases': 'q8-k16-phases'}
DOWN_RAW_PREFETCH_MANIFEST = 'config/q2-down-raw-prefetch-source.json'
DOWN_RAW_PREFETCH_MODE = 'down-raw-prefetch-check'
DOWN_RAW_PREFETCH_SOURCES = {'q2-counting-down-raw-prefetch': 'down-raw-prefetch'}
IQ2_FUSED_GRID_MANIFEST = 'config/q2-iq2-fused-grid-source.json'
IQ2_FUSED_GRID_MODE = 'iq2-fused-grid-check'
IQ2_FUSED_GRID_SOURCES = {'q2-counting-iq2-fused-grid': 'iq2-fused-grid'}
IQ2_SLICE_COMMIT_MANIFEST = 'config/q2-iq2-slice-commit-source.json'
IQ2_SLICE_COMMIT_MODE = 'iq2-slice-commit-check'
IQ2_SLICE_COMMIT_SOURCES = {'q2-counting-iq2-slice-commit': 'iq2-slice-commit', 'q2-counting-iq2-pair-commit': 'iq2-pair-commit'}
IQ2_SHORT_TILES_MANIFEST = 'config/q2-iq2-short-tiles-source-v2.json'
IQ2_SHORT_TILES_MODE = 'iq2-short-tiles-check'
IQ2_SHORT_TILES_SOURCES = {'q2-counting-iq2-short-tiles': 'iq2-short-tiles'}
HC_REUSE_MODE = 'hc-inject-reuse-check'
HC_REUSE_VARIANT = 'hc-inject-reuse-draft'
HC_REUSE_MANIFEST = 'config/q2-hc-inject-reuse-component-source-v2.json'
HC_OWNER_MODE = 'hc-norm-owner-check'
HC_OWNER_VARIANT = 'hc-norm-owner-draft'
HC_OWNER_MANIFEST = 'config/q2-hc-norm-owner-component-source.json'
HC_RMS_ORDINARY_MODE = 'q2-counting-hc-rms-owner-ordinary'
HC_RMS_ORDINARY_VARIANT = 'hc-rms-owner-ordinary'
HC_RMS_ORDINARY_MANIFEST = 'config/q2-hc-rms-owner-ordinary-source.json'
IQ2_HALF_SIGN_VARIANT = 'iq2-half-sign-arithmetic'
IQ2_HALF_SIGN_MODE = 'iq2-half-sign-arithmetic-check'
IQ2_HALF_SIGN_MODEL = 'q2-counting-iq2-half-sign-arithmetic'
IQ2_HALF_SIGN_MANIFEST = 'config/q2-iq2-half-sign-arithmetic-source.json'
IQ2_TABLE_LDS_VARIANT = 'iq2-table-lds'
IQ2_TABLE_LDS_MODE = 'iq2-table-lds-check'
IQ2_TABLE_LDS_MODEL = 'q2-counting-iq2-table-lds'
IQ2_TABLE_LDS_MANIFEST = 'config/q2-iq2-table-lds-source.json'
IQ2_DPP_COMMIT_VARIANT = 'iq2-dpp-commit'
IQ2_DPP_COMMIT_MODE = 'iq2-dpp-commit-check'
IQ2_DPP_COMMIT_MODEL = 'q2-counting-iq2-dpp-commit'
IQ2_DPP_COMMIT_MANIFEST = 'config/q2-iq2-dpp-commit-source.json'
IQ2_FIXED_BOUNDS_VARIANT = 'iq2-fixed-bounds'
IQ2_FIXED_BOUNDS_MODE = 'iq2-fixed-bounds-check'
IQ2_FIXED_BOUNDS_MODEL = 'q2-counting-iq2-fixed-bounds'
IQ2_FIXED_BOUNDS_MANIFEST = 'config/q2-iq2-fixed-bounds-source.json'
DOWN_REGISTER_PALETTE_MANIFEST = 'config/q2-down-register-palette-source.json'
DOWN_REGISTER_PALETTE_MODE = 'down-register-palette-check'
DOWN_REGISTER_PALETTE_SOURCES = {'q2-counting-down-register-palette': 'down-register-palette'}
IQ2_REGISTER_STAGE_MANIFEST = 'config/q2-iq2-register-stage-source-v2.json'
IQ2_REGISTER_STAGE_MODE = 'iq2-register-stage-check'
IQ2_REGISTER_STAGE_SOURCES = {'q2-counting-iq2-register-stage': 'iq2-register-stage'}
IQ2_TAIL16_MANIFEST = 'config/q2-iq2-tail16-source-v2.json'
IQ2_TAIL16_MODE = 'iq2-tail16-check'
IQ2_TAIL16_SOURCES = {'q2-counting-iq2-tail16': 'iq2-tail16'}
HALF_FIXED_WIDTH_MANIFEST = 'config/q2-half-fixed-width-source.json'
HALF_FIXED_WIDTH_MODE = 'half-fixed-width-check'
HALF_FIXED_WIDTH_SOURCES = {'q2-counting-half-fixed-width': 'half-fixed-width'}
HALF_CONSUMER_EIGHT_MANIFEST = 'config/q2-half-consumer-eight-source.json'
HALF_CONSUMER_EIGHT_MODE = 'half-consumer-eight-check'
HALF_CONSUMER_EIGHT_SOURCES = {'q2-counting-half-consumer-eight': 'half-consumer-eight'}
SSM_ROW_GROUP_MANIFEST = 'config/q2-ssm-row-group-compose-source.json'
SSM_ROW_GROUP_MODE = 'ssm-row-group-check'
SSM_ROW_GROUP_SOURCES = {'q2-counting-ssm-row-group': 'ssm-row-group'}
SHARED_DOWN_MANIFEST = 'config/q2-shared-down-runtime-source.json'
SHARED_DOWN_MODE = 'shared-down-fixed-check'
SHARED_DOWN_VARIANT = 'shared-down-fixed'
SHARED_DOWN_MANIFESTS = {
    SHARED_DOWN_VARIANT: SHARED_DOWN_MANIFEST,
    'shared-down-n64': 'config/q2-shared-down-n64-runtime-source.json',
}
SHARED_DOWN_MODES = {name + '-check': name for name in SHARED_DOWN_MANIFESTS}
SSM_FOLLOWUP_MANIFEST = 'config/q2-ssm-followup-runtime-source.json'
SSM_CHANNEL_MANIFEST = 'config/q2-ssm-channel-bounds-runtime-source.json'
SSM_FOLLOWUP_VARIANTS = ('ssm-fixed-shape', 'ssm-fixed-bounds', 'ssm-compact-lds', 'ssm-pingpong', 'ssm-channel-bounds')
SSM_FOLLOWUP_SOURCES = {'q2-counting-' + v: v for v in SSM_FOLLOWUP_VARIANTS}
SSM_FOLLOWUP_MODES = {v + '-check': v for v in SSM_FOLLOWUP_VARIANTS}
DOWN_REGISTER_SCATTER_MANIFEST = 'config/q2-down-register-scatter-pair-source.json'
DOWN_REGISTER_SCATTER_MODE = 'down-register-scatter-check'
DOWN_REGISTER_SCATTER_SOURCES = {'q2-counting-down-register-scatter': 'down-register-scatter'}
DOWN_HALF_VECTOR_MANIFEST = 'config/q2-down-half-vector-source.json'
DOWN_HALF_VECTOR_MODE = 'down-half-vector-check'
DOWN_HALF_VECTOR_SOURCES = {'q2-counting-down-half-vector': 'down-half-vector'}
DOWN_HALF_PAIR_MANIFEST = 'config/q2-down-half-pair-source.json'
DOWN_HALF_PAIR_MODE = 'down-half-pair-check'
DOWN_HALF_PAIR_SOURCES = {'q2-counting-down-half-pair': 'down-half-pair'}
DOWN_HALF_STORAGE_MANIFEST = 'config/q2-down-half-storage-source.json'
DOWN_HALF_STORAGE_MODE = 'down-half-storage-check'
DOWN_HALF_STORAGE_SOURCES = {'q2-counting-down-half-storage': 'down-half-storage'}
DOWN_LIVE_STAGE_MANIFEST = 'config/q2-down-live-stage-source.json'
DOWN_LIVE_STAGE_MODE = 'down-live-stage-check'
DOWN_LIVE_STAGE_SOURCES = {'q2-counting-down-live-stage': 'down-live-stage'}
DOWN_OUTPUT_REUSE_MANIFEST = 'config/q2-down-output-reuse-source.json'
DOWN_OUTPUT_REUSE_MODE = 'down-output-reuse-check'
DOWN_OUTPUT_REUSE_SOURCES = {'q2-counting-down-output-reuse': 'down-output-reuse'}
IQ2_WIDE_PAIR_MANIFEST = 'config/q2-iq2-wide-pair-source.json'
IQ2_WIDE_PAIR_MODE = 'iq2-wide-pair-check'
IQ2_WIDE_PAIR_SOURCES = {'q2-counting-iq2-wide-pair': 'iq2-wide-pair'}
IQ2_FOUR_WAVE_MANIFEST = 'config/q2-iq2-four-wave-source.json'
IQ2_FOUR_WAVE_MODE = 'iq2-four-wave-check'
IQ2_FOUR_WAVE_SOURCES = {'q2-counting-iq2-four-wave': 'iq2-four-wave'}
IQ2_LANE_COMMIT_MANIFEST = 'config/q2-iq2-lane-commit-source.json'
IQ2_LANE_COMMIT_MODE = 'iq2-lane-commit-check'
IQ2_LANE_COMMIT_SOURCES = {'q2-counting-iq2-lane-commit': 'iq2-lane-commit'}
IQ2_SIGN_MASK_MANIFEST = 'config/q2-iq2-sign-mask-source.json'
IQ2_SIGN_MASK_MODE = 'iq2-sign-mask-check'
IQ2_SIGN_MASK_SOURCES = {'q2-counting-iq2-sign-mask': 'iq2-sign-mask'}
IQ2_RAW_PREFETCH_MANIFEST = 'config/q2-iq2-raw-prefetch-source.json'
IQ2_RAW_PREFETCH_MODE = 'iq2-raw-prefetch-check'
IQ2_RAW_PREFETCH_SOURCES = {'q2-counting-iq2-raw-prefetch': 'iq2-raw-prefetch'}
SSM_ROW128_MODE = 'ssm-row128-check'
SSM_ROW128_SOURCES = {'q2-counting-ssm-row128': 'ssm-row128'}
Q8_HALFPAIR_MODE = 'q8-halfpair-check'
Q8_HALFPAIR_SOURCES = {'q2-counting-q8-halfpair': 'q8-halfpair'}
Q8_GROUPED_MODE = 'q8-grouped-check'
Q8_GROUPED_SOURCES = {'q2-counting-q8-grouped': 'q8-grouped-store'}
IQ2_HALFSTAGE_MODE = 'iq2-halfstage-check'
IQ2_HALFSTAGE_SOURCES = {'q2-counting-iq2-halfstage': 'iq2-halfstage'}
IQ2_HALFBYTE_MODE = 'iq2-halfbyte-check'
IQ2_HALFBYTE_SOURCES = {'q2-counting-iq2-halfbyte': 'iq2-halfbyte-perm'}
IQ2_LIVE_COMPOSE_MANIFEST = 'config/q2-iq2-live-compose-source.json'
IQ2_LIVE_COMPOSE_SOURCES = {'q2-counting-iq2-live-compose': 'iq2-live-compose'}
IQ2_RAW_SELECTIVE_MANIFEST = 'config/q2-iq2-raw-selective-source.json'
IQ2_RAW_SELECTIVE_SOURCES = {'q2-counting-iq2-raw-selective': 'iq2-raw-selective'}
SCALED_SELECTIVE_SOURCES = {'q2-counting-scaled-selective': 'scaled-selective'}
REAUDIT_SOURCES = {'q2-counting-reaudit-exact': 'reaudit-q8-row',
                   'q2-counting-reaudit-norm': 'reaudit-q8-row-norm'}
MIXED_TILE_MODES = ('iq2-mixed-reference-check', 'iq2-mixed-check')
CURVE_MODES = ('q2-curve', 'ud-curve', 'q2-curve-ple', 'ud-curve-ple', 'q2-curve-iq2', 'q2-curve-ple-cache-first', 'q2-curve-routes', 'q2-curve-iq2-mixed', 'q2-curve-scale', 'q2-curve-row', 'q2-point-norm')
CURVE_VARIANTS = ('curve-q2', 'curve-ud', 'curve-ple-q2', 'curve-ple-ud', 'curve-iq2-q2', 'curve-ple-cache-first-q2', 'curve-routes-q2', 'curve-iq2-mixed-q2', 'curve-scale-q2', 'curve-row-q2', 'point-norm-q2')
COUNTING_SOURCES = {IQ2_TABLE_LDS_MODEL: IQ2_TABLE_LDS_VARIANT, IQ2_DPP_COMMIT_MODEL: IQ2_DPP_COMMIT_VARIANT, IQ2_FIXED_BOUNDS_MODEL: IQ2_FIXED_BOUNDS_VARIANT, IQ2_HALF_SIGN_MODEL: IQ2_HALF_SIGN_VARIANT, HC_RMS_ORDINARY_MODE: HC_RMS_ORDINARY_VARIANT, 'q2-counting-legacy': 'library-norm-cycle',
                    'q2-counting-iq2': 'curve-iq2-q2',
                    'q2-counting-iq2-mixed': 'curve-iq2-mixed-q2',
                    'q2-counting-norm-fixed': 'norm-fixed-shape',
                    'q2-counting-shared-q8': 'shared-q8-producer',
                    **REAUDIT_SOURCES, **HC_BK_COUNTING, **DEFERRED_SOURCES, **Q8_GROUPED_SOURCES,
                    **SCALED_SELECTIVE_SOURCES, **IQ2_LIVE_COMPOSE_SOURCES, **IQ2_RAW_SELECTIVE_SOURCES, **IQ2_HALFSTAGE_SOURCES, **IQ2_HALFBYTE_SOURCES, **Q8_HALFPAIR_SOURCES, **SSM_ROW128_SOURCES, **IQ2_FUSED_GRID_SOURCES, **IQ2_SLICE_COMMIT_SOURCES, **IQ2_SHORT_TILES_SOURCES, **IQ2_TAIL16_SOURCES, **IQ2_REGISTER_STAGE_SOURCES, **DOWN_REGISTER_PALETTE_SOURCES, **HALF_FIXED_WIDTH_SOURCES, **HALF_CONSUMER_EIGHT_SOURCES, **SSM_ROW_GROUP_SOURCES, **SSM_FOLLOWUP_SOURCES, **DOWN_REGISTER_SCATTER_SOURCES, **DOWN_HALF_VECTOR_SOURCES, **DOWN_HALF_PAIR_SOURCES, **DOWN_HALF_STORAGE_SOURCES, **DOWN_LIVE_STAGE_SOURCES, **DOWN_OUTPUT_REUSE_SOURCES, **IQ2_WIDE_PAIR_SOURCES, **IQ2_FOUR_WAVE_SOURCES, **IQ2_LANE_COMMIT_SOURCES, **IQ2_SIGN_MASK_SOURCES, **IQ2_RAW_PREFETCH_SOURCES, **DOWN_RAW_PREFETCH_SOURCES, **EXPERT_CACHE_SOURCES, **Q8_MIRROR_SOURCES, **SCALED_WAVE_PACK_SOURCES, **SCALED_EXPERT_ORDER_SOURCES, **COMPACT_EXPERT_CHAIN_SOURCES, **PRODUCER_Q8_SOURCES, **SHARED_Q8_PAIR_SOURCES, **Q8_ALIGNED_PAIR_SOURCES, **Q8_K16_PHASES_SOURCES,
                    'ud-counting-legacy': 'qualified'}
COUNTING_CURVES = {'q2-counting-iq2': 'q2-curve-iq2',
                   'q2-counting-iq2-mixed': 'q2-curve-iq2-mixed'}


def file_sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def source_data_limits(mode):
    # The unchanged2048x2560 F32 replay array is data, not project source.
    # Keep every other member at the original16MB cap.
    return ({'oracle-replay-data/shared-q8-n2048-p0-mixed-reference.bin': 2048*2560*4}
            if mode == 'shared-q8-oracle-replay' else {})


def collection_receipt(archive):
    members = archive.getmembers()
    names = set()
    for member in members:
        path = Path(member.name)
        if (path.is_absolute() or '..' in path.parts or not path.parts or
                path.parts[0] != 'results' or path in names or member.size < 0 or
                not (member.isdir() or member.isfile())):
            raise ValueError('Unsafe collection')
        names.add(path)
    receipts = [member for member in members if member.name == 'results/result.json']
    if len(receipts) != 1 or not receipts[0].isfile() or receipts[0].size > 1000000:
        raise ValueError('Missing or oversized collection receipt')
    receipt = json.load(archive.extractfile(receipts[0]))
    if not receipt.get('finished_at') or any(type(row.get('exit_code')) is not int for row in receipt.get('commands', [])):
        raise ValueError('Refusing incomplete collection')
    # Eight complete 36-row outputs alone occupy 286 MB in this fixed probe.
    # Keep other modes at their existing bound and retain a finite total cap.
    # Full Core-19 permits 19 x two three-hour attempts. Preserve its two-second
    # telemetry samples instead of silently dropping them after a short-run cap.
    # The ragged HC fixture retains 2040/2047-row norm/half/down pairs as well
    # as small cases: 1,106,304,168 bytes in the first complete archive.
    limits = {HC_OWNER_MODE: 2 * 1024**3, HC_REUSE_MODE: 2 * 1024**3, **{mode: 8 * 1024**3 for mode in EXPERT_CACHE_MODES}, **{mode: 4 * 1024**3 for mode in SHARED_DOWN_MODES}, HALF_FIXED_WIDTH_MODE: 4 * 1024**3, HALF_CONSUMER_EIGHT_MODE: 4 * 1024**3, SSM_ROW_GROUP_MODE: 8 * 1024**3, **{mode: 8 * 1024**3 for mode in SSM_FOLLOWUP_MODES}, DOWN_REGISTER_SCATTER_MODE: 8 * 1024**3, DOWN_HALF_VECTOR_MODE: 8 * 1024**3, DOWN_HALF_PAIR_MODE: 8 * 1024**3, DOWN_HALF_STORAGE_MODE: 8 * 1024**3, DOWN_LIVE_STAGE_MODE: 8 * 1024**3, DOWN_OUTPUT_REUSE_MODE: 4 * 1024**3, IQ2_WIDE_PAIR_MODE: 4 * 1024**3, IQ2_FOUR_WAVE_MODE: 4 * 1024**3, IQ2_LANE_COMMIT_MODE: 2 * 1024**3, IQ2_SLICE_COMMIT_MODE: 2 * 1024**3, Q8_MIRROR_MODE: 6 * 1024**3, IQ2_SIGN_MASK_MODE: 2 * 1024**3, IQ2_FUSED_GRID_MODE: 2 * 1024**3, SCALED_WAVE_PACK_MODE: 2 * 1024**3, SCALED_EXPERT_ORDER_MODE: 2 * 1024**3, COMPACT_EXPERT_CHAIN_MODE: 4 * 1024**3, PRODUCER_Q8_MODE: 6 * 1024**3, SHARED_Q8_PAIR_MODE: 4 * 1024**3, Q8_ALIGNED_PAIR_MODE: 6 * 1024**3, Q8_K16_PHASES_MODE: 6 * 1024**3, DOWN_RAW_PREFETCH_MODE: 2 * 1024**3, IQ2_RAW_PREFETCH_MODE: 2 * 1024**3, SSM_ROW128_MODE: 4 * 1024**3, Q8_HALFPAIR_MODE: 2 * 1024**3, IQ2_HALFSTAGE_MODE: 2 * 1024**3, **{mode: 384000000 for mode in MIXED_TILE_MODES}, 'iq2-live-epilogue-check': 384000000, 'q2-ple-first-access': 384000000, 'q2-terminal-full': 2 * 1024**3, 'hc-norm-ragged-bench': 1120000000, 'shared-q8-producer-check': 384000000}
    limit = limits.get(receipt.get('mode'), 128000000)
    if sum(member.size for member in members) > limit:
        raise ValueError('Oversized collection')
    return receipt


def ssm_followup_source(parser, name):
    registry = SSM_CHANNEL_MANIFEST if name == 'ssm-channel-bounds' else SSM_FOLLOWUP_MANIFEST
    info = json.loads((ROOT / registry).read_text())['variants'][name]
    for path, digest in info['bindings'].items():
        if file_sha256(ROOT / path) != digest:
            parser.error('Q2 SSM follow-up source or fixture binding changed')
    variant = json.loads((ROOT / info['manifest']).read_text())['variants'][name]
    for key, digest in variant.items():
        if key.endswith('_sha256'):
            if file_sha256(ROOT / variant[key[:-7]]) != digest:
                parser.error('Q2 SSM follow-up measured source reference changed')
    source = variant['source']
    actual = {str(f.relative_to(ROOT / source)): file_sha256(f)
              for f in (ROOT / source).rglob('*') if f.is_file()}
    if actual != variant['files'] or len(actual) != 1027:
        parser.error('Q2 SSM follow-up provider inventory changed')
    return source


def shared_down_source(parser, name=SHARED_DOWN_VARIANT):
    binding = json.loads((ROOT / SHARED_DOWN_MANIFESTS[name]).read_text())
    for path, digest in binding['bindings'].items():
        if file_sha256(ROOT / path) != digest:
            parser.error('Shared-down source or fixture binding changed')
    variant = json.loads((ROOT / binding['manifest']).read_text())['variants'][name]
    for key, digest in variant.items():
        if key.endswith('_sha256') and file_sha256(ROOT / variant[key[:-7]]) != digest:
            parser.error('Shared-down source provenance changed')
    source = variant['source']
    actual = {str(f.relative_to(ROOT / source)): file_sha256(f)
              for f in (ROOT / source).rglob('*') if f.is_file()}
    if actual != variant['files'] or len(actual) != 1028:
        parser.error('Shared-down provider inventory changed')
    return source


def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=[IQ2_TABLE_LDS_MODE, IQ2_DPP_COMMIT_MODE, IQ2_FIXED_BOUNDS_MODE, IQ2_HALF_SIGN_MODE, HC_OWNER_MODE, HC_REUSE_MODE, 'counter-calibration', *EXPERT_CACHE_MODES, *SHARED_DOWN_MODES, HALF_FIXED_WIDTH_MODE, HALF_CONSUMER_EIGHT_MODE, SSM_ROW_GROUP_MODE, *SSM_FOLLOWUP_MODES, DOWN_REGISTER_SCATTER_MODE, DOWN_HALF_VECTOR_MODE, DOWN_HALF_PAIR_MODE, DOWN_HALF_STORAGE_MODE, DOWN_LIVE_STAGE_MODE, DOWN_OUTPUT_REUSE_MODE, IQ2_WIDE_PAIR_MODE, IQ2_FOUR_WAVE_MODE, IQ2_LANE_COMMIT_MODE, IQ2_SHORT_TILES_MODE, IQ2_TAIL16_MODE, IQ2_REGISTER_STAGE_MODE, DOWN_REGISTER_PALETTE_MODE, IQ2_SLICE_COMMIT_MODE, Q8_MIRROR_MODE, IQ2_SIGN_MASK_MODE, IQ2_FUSED_GRID_MODE, SCALED_WAVE_PACK_MODE, SCALED_EXPERT_ORDER_MODE, COMPACT_EXPERT_CHAIN_MODE, PRODUCER_Q8_MODE, SHARED_Q8_PAIR_MODE, Q8_ALIGNED_PAIR_MODE, Q8_K16_PHASES_MODE, DOWN_RAW_PREFETCH_MODE, IQ2_RAW_PREFETCH_MODE, SSM_ROW128_MODE, Q8_HALFPAIR_MODE, IQ2_HALFBYTE_MODE, IQ2_HALFSTAGE_MODE, Q8_GROUPED_MODE, FIXED_PROFILE_MODE, CURRENT_PROFILE_MODE, CURRENT_ROUTING_MODE, HC_BK_MODE, 'shared-q8-oracle-replay', 'shared-q8-producer-check', *COUNTING_SOURCES, *MIXED_TILE_MODES, 'native-curve-cpu', 'cpu', 'ple-cache-first-cpu', 'ple-lookahead-cpu', 'q2-ple-lookahead', 'q2-ple-first-access', 'ple-cpu', 'ple-cache-cpu', 'q2-ple-cache64k', 'ple-io-cpu', 'q2-ple-io', 'ud-ple-io', 'q2-ple', 'ud-ple', 'hip-build', 'operators', 'operators-reference', 'iq2-signs-check', 'iq2-wmma-signs-check', 'iq2-live-epilogue-check', 'scaled-row-check', 'hc-operators', 'hc-bench', 'hc-pp-operators', 'hc-pp-bench', 'hc-library-bench', 'hc-library-norm-bench', 'hc-norm-ragged-bench', 'hc-library-ragged-bench', 'hc-decode-reduce-bench', 'hc-input-bench', 'hc-up-chain-bench', 'hc-up-operators', 'hc-up-bench', 'hc-moe-operators', 'hc-moe-bench', 'hc-norm-operators', 'hc-norm-bench', 'hc-sequence-bench', 'hc-deferred-bench', 'routed-operators', 'iq2-pair-operators', 'shared-fork-check', 'scaled-input-check', 'scaled-tiles-check', 'narrow-vector-check', 'packed-operators', 'packed-bench', 'packed-tiles-bench', 'packed-tiles16-bench', 'terminal-cpu', 'q2-terminal-build', 'q2-terminal-probe', 'q2-terminal-smoke', 'q2-terminal-full', 'q2-smoke', 'q2-bench', 'q2-bench2k', 'ud-bench2k', 'q2-decode-baseline', 'ud-decode-baseline', *ORIGINAL_BASELINE_MODES, *CURVE_MODES, 'q2-profile', 'ud-profile', 'ud-base', 'ud-patched', 'status', 'collect'])
    p.add_argument('label')
    p.add_argument('--source-variant', choices=[IQ2_TABLE_LDS_VARIANT, IQ2_DPP_COMMIT_VARIANT, IQ2_FIXED_BOUNDS_VARIANT, IQ2_HALF_SIGN_VARIANT, HC_RMS_ORDINARY_VARIANT, HC_OWNER_VARIANT, HC_REUSE_VARIANT, 'expert-cache', 'compressed-cache', 'iq2-mixed', 'qualified', 'bounded-k', 'wide-barrier', 'hc', 'hc-prefill', 'stack', 'iq2-pair', 'packed', 'hc-up-fused', 'hc-up-vec', 'hc-up-vec-exact', 'hc-moe-fused', 'hc-norm-half', 'hc-down64', 'hc-down64-wave4', 'hc-down64-k4', 'hc-down128-wave4', 'hc-down-coalesced', 'staged-weights', 'code-reuse', 'half-wave', 'half-wave-permlane', 'hc-prefetch', 'hc-prefetch2', 'hc-decode8', 'hc-decode16', 'hc-decode32', 'affine-palette', 'staged-palette', 'down-scatter', 'shared-overlap', 'scaled-input', 'scaled-tiles', 'narrow-vector', 'hc-down-phased', 'hc-down-phased-free', 'hc-row160-wide', 'hc-row160-loads', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-sequence', 'hc-sequence-half-row', 'hc-deferred-norm', 'hc-single-chain', 'hc-full-row', 'hc-half-row', 'hc-row80', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced', *COMBINED_VARIANTS, 'scaled-library', 'library-norm-cycle', 'library-norm-bound', 'hc-decode-reduce', 'hc-library-ragged', 'hc-norm-ragged', *CURVE_VARIANTS, *SIGN_VARIANTS, *WMMA_SIGN_VARIANTS, *EPILOGUE_VARIANTS, *ROW_VARIANTS, *NORM_SHAPE_VARIANTS, Q8_PRODUCER_VARIANT, *REAUDIT_SOURCES.values(), *HC_BK_VARIANTS, *DEFERRED_SOURCES.values(), *Q8_GROUPED_SOURCES.values(), *SCALED_SELECTIVE_SOURCES.values(), *IQ2_LIVE_COMPOSE_SOURCES.values(), *IQ2_RAW_SELECTIVE_SOURCES.values(), *IQ2_HALFSTAGE_SOURCES.values(), *IQ2_HALFBYTE_SOURCES.values(), *Q8_HALFPAIR_SOURCES.values(), *SSM_ROW128_SOURCES.values(), *IQ2_FUSED_GRID_SOURCES.values(), *IQ2_SLICE_COMMIT_SOURCES.values(), *IQ2_SHORT_TILES_SOURCES.values(), *IQ2_TAIL16_SOURCES.values(), *IQ2_REGISTER_STAGE_SOURCES.values(), *DOWN_REGISTER_PALETTE_SOURCES.values(), *HALF_FIXED_WIDTH_SOURCES.values(), *HALF_CONSUMER_EIGHT_SOURCES.values(), *SSM_ROW_GROUP_SOURCES.values(), *SSM_FOLLOWUP_VARIANTS, *SHARED_DOWN_MANIFESTS, *DOWN_REGISTER_SCATTER_SOURCES.values(), *DOWN_HALF_VECTOR_SOURCES.values(), *DOWN_HALF_PAIR_SOURCES.values(), *DOWN_HALF_STORAGE_SOURCES.values(), *DOWN_LIVE_STAGE_SOURCES.values(), *DOWN_OUTPUT_REUSE_SOURCES.values(), *IQ2_WIDE_PAIR_SOURCES.values(), *IQ2_FOUR_WAVE_SOURCES.values(), *IQ2_LANE_COMMIT_SOURCES.values(), *IQ2_SIGN_MASK_SOURCES.values(), *IQ2_RAW_PREFETCH_SOURCES.values(), *DOWN_RAW_PREFETCH_SOURCES.values(), *Q8_MIRROR_SOURCES.values(), *SCALED_WAVE_PACK_SOURCES.values(), *SCALED_EXPERT_ORDER_SOURCES.values(), *COMPACT_EXPERT_CHAIN_SOURCES.values(), *PRODUCER_Q8_SOURCES.values(), *SHARED_Q8_PAIR_SOURCES.values(), *Q8_ALIGNED_PAIR_SOURCES.values(), *Q8_K16_PHASES_SOURCES.values()],
                   default='qualified', help='Isolated source; hc also supports HC operators and microbenchmark')
    p.add_argument('--point-only', action='store_true', help='One canonical d0 point, one warmup and three measured repetitions; native client only')
    p.add_argument('--native-curve', action='store_true', help='Use the frozen native C canonical benchmark; no Python curve fallback')
    p.add_argument('--detach', action='store_true', help='Persistent supervisor for Terminal-Bench tasks only')
    p.add_argument('--replay-from', choices=['q2-norm-fixed-model-before-r1', 'q2-norm-fixed-model-ud-r1'],
                   help='Replay an immutable qualified counting control without compiling')
    p.add_argument('--rebuild-mmq', action='store_true',
                   help='Recompile all MMQ sources for bench2k, decode-baseline or original-baseline; no prior archive reuse')
    p.add_argument('--existing-collection', action='store_true',
                   help='Validate/extract an already downloaded collection; no SSH or overwriting results')
    args = p.parse_args()
    if args.mode == HC_REUSE_MODE or args.source_variant == HC_REUSE_VARIANT:
        if args.mode != HC_REUSE_MODE or args.source_variant != HC_REUSE_VARIANT:
            p.error('HC injection reuse requires its component-only draft provider')
        if args.rebuild_mmq or args.detach or args.native_curve or args.point_only or args.replay_from:
            p.error('HC injection reuse component accepts no model, replay or persistent modes')
    if args.mode == HC_OWNER_MODE or args.source_variant == HC_OWNER_VARIANT:
        if args.mode != HC_OWNER_MODE or args.source_variant != HC_OWNER_VARIANT:
            p.error('HC RMS ownership requires its component-only draft provider')
        if args.rebuild_mmq or args.detach or args.native_curve or args.point_only or args.replay_from:
            p.error('HC RMS ownership component accepts no model, replay or persistent modes')
    if args.source_variant == HC_RMS_ORDINARY_VARIANT and args.mode != HC_RMS_ORDINARY_MODE:
        p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                else 'HC ordinary RMS requires its matched historical counting provider')
    if args.mode == HC_RMS_ORDINARY_MODE and args.source_variant == HC_RMS_ORDINARY_VARIANT:
        if not args.rebuild_mmq:
            p.error('Historical counting requires a full MMQ rebuild')
        if args.native_curve or args.point_only or args.replay_from:
            p.error('HC ordinary RMS accepts no curve, replay or persistent mode')
    if args.mode == IQ2_HALF_SIGN_MODE or args.source_variant == IQ2_HALF_SIGN_VARIANT:
        if args.mode not in (IQ2_HALF_SIGN_MODE, IQ2_HALF_SIGN_MODEL) or args.source_variant != IQ2_HALF_SIGN_VARIANT:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'IQ2 sign arithmetic requires its component or matched counting provider')
        if args.mode == IQ2_HALF_SIGN_MODE and (args.rebuild_mmq or args.detach or args.native_curve or args.point_only or args.replay_from):
            p.error('IQ2 sign arithmetic component accepts no model or replay modes')
        if args.native_curve or args.point_only or args.replay_from:
            p.error('IQ2 sign arithmetic accepts no curve or replay modes')
    if args.mode == IQ2_TABLE_LDS_MODE or args.source_variant == IQ2_TABLE_LDS_VARIANT:
        if args.mode not in (IQ2_TABLE_LDS_MODE, IQ2_TABLE_LDS_MODEL) or args.source_variant != IQ2_TABLE_LDS_VARIANT:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'IQ2 table LDS requires its component or matched counting provider')
        if args.mode == IQ2_TABLE_LDS_MODE and (args.rebuild_mmq or args.detach or args.native_curve or args.point_only or args.replay_from):
            p.error('IQ2 table LDS component accepts no model or replay modes')
        if args.native_curve or args.point_only or args.replay_from:
            p.error('IQ2 table LDS accepts no curve or replay modes')
    if args.mode == IQ2_DPP_COMMIT_MODE or args.source_variant == IQ2_DPP_COMMIT_VARIANT:
        if args.mode not in (IQ2_DPP_COMMIT_MODE, IQ2_DPP_COMMIT_MODEL) or args.source_variant != IQ2_DPP_COMMIT_VARIANT:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'IQ2 DPP commit requires its component or matched counting provider')
        if args.mode == IQ2_DPP_COMMIT_MODE and (args.rebuild_mmq or args.detach or args.native_curve or args.point_only or args.replay_from):
            p.error('IQ2 DPP commit component accepts no model or replay modes')
        if args.native_curve or args.point_only or args.replay_from:
            p.error('IQ2 DPP commit accepts no curve or replay modes')
    if args.mode == IQ2_FIXED_BOUNDS_MODE or args.source_variant == IQ2_FIXED_BOUNDS_VARIANT:
        if args.mode not in (IQ2_FIXED_BOUNDS_MODE, IQ2_FIXED_BOUNDS_MODEL) or args.source_variant != IQ2_FIXED_BOUNDS_VARIANT:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'IQ2 fixed bounds requires its component or matched counting provider')
        if args.mode == IQ2_FIXED_BOUNDS_MODE and (args.rebuild_mmq or args.detach or args.native_curve or args.point_only or args.replay_from):
            p.error('IQ2 fixed bounds component accepts no model or replay modes')
        if args.native_curve or args.point_only or args.replay_from:
            p.error('IQ2 fixed bounds accepts no curve or replay modes')
    if args.mode == 'counter-calibration' and (args.source_variant != 'qualified' or args.rebuild_mmq or args.detach or args.native_curve or args.point_only or args.replay_from):
        p.error('Counter calibration requires its standalone fixture without model variants')
    if args.mode in SHARED_DOWN_MODES or args.source_variant in SHARED_DOWN_MANIFESTS:
        if SHARED_DOWN_MODES.get(args.mode) != args.source_variant:
            p.error('Shared-down preparation requires its matched component and provider')
        if args.rebuild_mmq or args.detach or args.native_curve or args.point_only or args.replay_from:
            p.error('Shared-down preparation is component-only with a direct numerical build')
    if args.mode == CURRENT_PROFILE_MODE:
        if (args.source_variant != 'half-consumer-eight' or args.rebuild_mmq or args.replay_from
                or args.detach or args.native_curve or args.point_only):
            p.error('Current best profile requires the saved candidate binary only; no build or control replay')
    if args.mode == CURRENT_ROUTING_MODE:
        if (args.source_variant != 'ssm-fixed-bounds' or args.rebuild_mmq or args.replay_from
                or args.detach or args.native_curve or args.point_only):
            p.error('Current routing requires the saved1585 binary only; no build or control replay')
    if args.mode == FIXED_PROFILE_MODE:
        if (args.source_variant != 'hc-moe-deferred' or args.rebuild_mmq or args.replay_from
                or args.detach or args.native_curve or args.point_only):
            p.error('Fixed MoE profile requires the saved candidate binary only; no build or control replay')
    if args.replay_from:
        expected = {'q2-norm-fixed-model-before-r1': ('q2-counting-iq2-mixed', 'curve-iq2-mixed-q2'),
                    'q2-norm-fixed-model-ud-r1': ('ud-counting-legacy', 'qualified')}
        if ((args.mode, args.source_variant) != expected[args.replay_from] or args.rebuild_mmq
                or args.detach or args.native_curve or args.point_only):
            p.error('Binary replay requires its qualified unchanged counting control and no build')
    if args.point_only and (not args.native_curve or args.mode not in POINT_MODES):
        p.error('Focused point requires the native ordered Q2, paired norm Q2 or UD mode')
    if args.mode == 'q2-point-norm' and not args.point_only:
        p.error('Paired norm model requires the focused native point')
    if args.source_variant in NORM_SHAPE_VARIANTS:
        if args.mode == 'q2-counting-norm-fixed' and args.source_variant == 'norm-fixed-shape':
            pass  # Explicit owner-requested fixed-input model exploration; rebuild guard below.
        elif args.mode != 'hc-library-norm-bench':
            p.error('Fixed norm shape requires the existing library component only')
        elif args.rebuild_mmq:
            p.error('Fixed norm shape builds its kernels directly')
    if args.mode == 'hc-norm-ragged-bench' or args.source_variant == 'hc-norm-ragged':
        if args.mode != 'hc-norm-ragged-bench' or args.source_variant != 'hc-norm-ragged':
            p.error('Ragged paired norm requires its isolated component mode and source')
        if args.rebuild_mmq:
            p.error('Ragged paired norm component builds its kernels directly')
    if args.mode == 'native-curve-cpu' and (args.source_variant != 'qualified' or args.rebuild_mmq):
        p.error('Native curve host conformance requires its fixed client and no GPU build')
    if args.native_curve and args.mode not in NATIVE_CURVE_MODES:
        p.error('Native curve requires an uninstrumented ordered Q2, scale Q2 or UD curve')
    if args.mode == 'q2-curve-row' and not args.native_curve:
        p.error('Scaled row model comparison requires the native C canonical benchmark')
    if args.mode == 'q2-curve-scale' and not args.native_curve:
        p.error('Scale model comparison requires the native C canonical benchmark')
    if args.source_variant in IQ2_LIVE_COMPOSE_SOURCES.values():
        if IQ2_LIVE_COMPOSE_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'IQ2 live composition requires its matched historical counting provider')

    if args.source_variant in IQ2_RAW_SELECTIVE_SOURCES.values():
        if IQ2_RAW_SELECTIVE_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'IQ2 raw selective composition requires its matched historical counting provider')

    if args.source_variant in SCALED_SELECTIVE_SOURCES.values():
        if SCALED_SELECTIVE_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'Selective scaled tiles require their matched historical counting provider')
    if args.source_variant in EXPERT_CACHE_SOURCES.values() or args.mode in EXPERT_CACHE_MODES:
        if EXPERT_CACHE_MODES.get(args.mode) == args.source_variant:
            if args.rebuild_mmq or args.detach or args.native_curve or args.point_only:
                p.error('Expert cache component builds its numerical kernels directly')
        elif EXPERT_CACHE_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'Expert cache requires its component or matched historical counting provider')
    if args.source_variant in Q8_MIRROR_SOURCES.values() or args.mode == Q8_MIRROR_MODE:
        if args.mode == Q8_MIRROR_MODE and args.source_variant == 'q8-mirror':
            if args.rebuild_mmq:
                p.error('Q8 mirror component builds its numerical kernels directly')
        elif Q8_MIRROR_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'Q8 mirror requires its component or matched historical counting provider')
    if args.source_variant in SCALED_WAVE_PACK_SOURCES.values() or args.mode == SCALED_WAVE_PACK_MODE:
        if args.mode == SCALED_WAVE_PACK_MODE and args.source_variant == 'scaled-wave-pack':
            if args.rebuild_mmq:
                p.error('Scaled wave pack component builds its numerical kernels directly')
        elif SCALED_WAVE_PACK_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'Scaled wave pack requires its component or matched historical counting provider')
    if args.source_variant in SCALED_EXPERT_ORDER_SOURCES.values() or args.mode == SCALED_EXPERT_ORDER_MODE:
        if args.mode == SCALED_EXPERT_ORDER_MODE and args.source_variant == 'scaled-expert-order':
            if args.rebuild_mmq:
                p.error('Scaled expert order component builds its numerical kernels directly')
        elif SCALED_EXPERT_ORDER_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'Scaled expert order requires its component or matched historical counting provider')
    if args.source_variant in COMPACT_EXPERT_CHAIN_SOURCES.values() or args.mode == COMPACT_EXPERT_CHAIN_MODE:
        if args.mode == COMPACT_EXPERT_CHAIN_MODE and args.source_variant == 'compact-expert-chain':
            if args.rebuild_mmq:
                p.error('Compact expert chain component builds its numerical kernels directly')
        elif COMPACT_EXPERT_CHAIN_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'Compact expert chain requires its component or matched historical counting provider')
    if args.source_variant in PRODUCER_Q8_SOURCES.values() or args.mode == PRODUCER_Q8_MODE:
        if args.mode == PRODUCER_Q8_MODE and args.source_variant == 'producer-q8':
            if args.rebuild_mmq:
                p.error('Producer Q8 component builds its numerical kernels directly')
        elif PRODUCER_Q8_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'Producer Q8 requires its component or matched historical counting provider')
    if args.source_variant in SHARED_Q8_PAIR_SOURCES.values() or args.mode == SHARED_Q8_PAIR_MODE:
        if args.mode == SHARED_Q8_PAIR_MODE and args.source_variant == 'shared-q8-pair':
            if args.rebuild_mmq:
                p.error('Shared Q8 pair component builds its numerical kernels directly')
        elif SHARED_Q8_PAIR_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'Shared Q8 pair requires its component or matched historical counting provider')
    if args.source_variant in Q8_ALIGNED_PAIR_SOURCES.values() or args.mode == Q8_ALIGNED_PAIR_MODE:
        if args.mode == Q8_ALIGNED_PAIR_MODE and args.source_variant == 'q8-aligned-pair':
            if args.rebuild_mmq:
                p.error('Q8 aligned pair component builds its numerical kernels directly')
        elif Q8_ALIGNED_PAIR_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'Q8 aligned pair requires its component or matched historical counting provider')
    if args.source_variant in Q8_K16_PHASES_SOURCES.values() or args.mode == Q8_K16_PHASES_MODE:
        if args.mode == Q8_K16_PHASES_MODE and args.source_variant == 'q8-k16-phases':
            if args.rebuild_mmq:
                p.error('Q8 K16 phases component builds its numerical kernels directly')
        elif Q8_K16_PHASES_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'Q8 K16 phases requires its component or matched historical counting provider')
    if args.source_variant in DOWN_RAW_PREFETCH_SOURCES.values() or args.mode == DOWN_RAW_PREFETCH_MODE:
        if args.mode == DOWN_RAW_PREFETCH_MODE and args.source_variant == 'down-raw-prefetch':
            if args.rebuild_mmq:
                p.error('Q2 down raw prefetch component builds its numerical kernels directly')
        elif DOWN_RAW_PREFETCH_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'Q2 down raw prefetch requires its component or matched historical counting provider')
    if args.source_variant in IQ2_FUSED_GRID_SOURCES.values() or args.mode == IQ2_FUSED_GRID_MODE:
        if args.mode == IQ2_FUSED_GRID_MODE and args.source_variant == 'iq2-fused-grid':
            if args.rebuild_mmq:
                p.error('IQ2 fused grid component builds its numerical kernels directly')
        elif IQ2_FUSED_GRID_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'IQ2 fused grid requires its component or matched historical counting provider')
    if args.source_variant in HALF_FIXED_WIDTH_SOURCES.values() or args.mode == HALF_FIXED_WIDTH_MODE:
        if args.mode == HALF_FIXED_WIDTH_MODE and args.source_variant == 'half-fixed-width':
            if args.rebuild_mmq:
                p.error('Q2 half fixed width component builds its numerical kernels directly')
        elif HALF_FIXED_WIDTH_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'Q2 half fixed width requires its component or matched historical counting provider')
    if args.source_variant in HALF_CONSUMER_EIGHT_SOURCES.values() or args.mode == HALF_CONSUMER_EIGHT_MODE:
        if args.mode == HALF_CONSUMER_EIGHT_MODE and args.source_variant == 'half-consumer-eight':
            if args.rebuild_mmq:
                p.error('Q2 half consumer eight component builds its numerical kernels directly')
        elif args.mode != CURRENT_PROFILE_MODE and HALF_CONSUMER_EIGHT_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'Q2 half consumer eight requires its component or matched historical counting provider')
    if args.source_variant in SSM_FOLLOWUP_VARIANTS or args.mode in SSM_FOLLOWUP_MODES:
        if SSM_FOLLOWUP_MODES.get(args.mode) == args.source_variant:
            if args.rebuild_mmq:
                p.error('Q2 SSM follow-up component builds its numerical kernels directly')
        elif args.mode != CURRENT_ROUTING_MODE and SSM_FOLLOWUP_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'Q2 SSM follow-up requires its component or matched historical counting provider')
    if args.source_variant in SSM_ROW_GROUP_SOURCES.values() or args.mode == SSM_ROW_GROUP_MODE:
        if args.mode == SSM_ROW_GROUP_MODE and args.source_variant == 'ssm-row-group':
            if args.rebuild_mmq:
                p.error('Q2 SSM row group component builds its numerical kernels directly')
        elif SSM_ROW_GROUP_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'Q2 SSM row group requires its component or matched historical counting provider')
    if args.source_variant in DOWN_REGISTER_SCATTER_SOURCES.values() or args.mode == DOWN_REGISTER_SCATTER_MODE:
        if args.mode == DOWN_REGISTER_SCATTER_MODE and args.source_variant == 'down-register-scatter':
            if args.rebuild_mmq:
                p.error('Q2 down register scatter component builds its numerical kernels directly')
        elif DOWN_REGISTER_SCATTER_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'Q2 down register scatter requires its component or matched historical counting provider')
    if args.source_variant in DOWN_HALF_VECTOR_SOURCES.values() or args.mode == DOWN_HALF_VECTOR_MODE:
        if args.mode == DOWN_HALF_VECTOR_MODE and args.source_variant == 'down-half-vector':
            if args.rebuild_mmq:
                p.error('Q2 down half vector component builds its numerical kernels directly')
        elif DOWN_HALF_VECTOR_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'Q2 down half vector requires its component or matched historical counting provider')
    if args.source_variant in DOWN_HALF_PAIR_SOURCES.values() or args.mode == DOWN_HALF_PAIR_MODE:
        if args.mode == DOWN_HALF_PAIR_MODE and args.source_variant == 'down-half-pair':
            if args.rebuild_mmq:
                p.error('Q2 down half pair component builds its numerical kernels directly')
        elif DOWN_HALF_PAIR_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'Q2 down half pair requires its component or matched historical counting provider')
    if args.source_variant in DOWN_HALF_STORAGE_SOURCES.values() or args.mode == DOWN_HALF_STORAGE_MODE:
        if args.mode == DOWN_HALF_STORAGE_MODE and args.source_variant == 'down-half-storage':
            if args.rebuild_mmq:
                p.error('Q2 down half storage component builds its numerical kernels directly')
        elif DOWN_HALF_STORAGE_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'Q2 down half storage requires its component or matched historical counting provider')
    if args.source_variant in DOWN_LIVE_STAGE_SOURCES.values() or args.mode == DOWN_LIVE_STAGE_MODE:
        if args.mode == DOWN_LIVE_STAGE_MODE and args.source_variant == 'down-live-stage':
            if args.rebuild_mmq:
                p.error('Q2 down live stage component builds its numerical kernels directly')
        elif DOWN_LIVE_STAGE_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'Q2 down live stage requires its component or matched historical counting provider')
    if args.source_variant in DOWN_OUTPUT_REUSE_SOURCES.values() or args.mode == DOWN_OUTPUT_REUSE_MODE:
        if args.mode == DOWN_OUTPUT_REUSE_MODE and args.source_variant == 'down-output-reuse':
            if args.rebuild_mmq:
                p.error('Q2 down output reuse component builds its numerical kernels directly')
        elif DOWN_OUTPUT_REUSE_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'Q2 down output reuse requires its component or matched historical counting provider')
    if args.source_variant in IQ2_WIDE_PAIR_SOURCES.values() or args.mode == IQ2_WIDE_PAIR_MODE:
        if args.mode == IQ2_WIDE_PAIR_MODE and args.source_variant == 'iq2-wide-pair':
            if args.rebuild_mmq:
                p.error('IQ2 wide pair component builds its numerical kernels directly')
        elif IQ2_WIDE_PAIR_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'IQ2 wide pair requires its component or matched historical counting provider')
    if args.source_variant in IQ2_FOUR_WAVE_SOURCES.values() or args.mode == IQ2_FOUR_WAVE_MODE:
        if args.mode == IQ2_FOUR_WAVE_MODE and args.source_variant == 'iq2-four-wave':
            if args.rebuild_mmq:
                p.error('IQ2 four wave component builds its numerical kernels directly')
        elif IQ2_FOUR_WAVE_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'IQ2 four wave requires its component or matched historical counting provider')
    if args.source_variant in IQ2_LANE_COMMIT_SOURCES.values() or args.mode == IQ2_LANE_COMMIT_MODE:
        if args.mode == IQ2_LANE_COMMIT_MODE and args.source_variant == 'iq2-lane-commit':
            if args.rebuild_mmq:
                p.error('IQ2 lane commit component builds its numerical kernels directly')
        elif IQ2_LANE_COMMIT_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'IQ2 lane commit requires its component or matched historical counting provider')
    if args.source_variant in IQ2_SHORT_TILES_SOURCES.values() or args.mode == IQ2_SHORT_TILES_MODE:
        if args.mode == IQ2_SHORT_TILES_MODE and args.source_variant == 'iq2-short-tiles':
            if args.rebuild_mmq:
                p.error('IQ2 short tiles component builds its numerical kernels directly')
        elif IQ2_SHORT_TILES_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'IQ2 short tiles requires its component or matched historical counting provider')
    if args.source_variant in IQ2_TAIL16_SOURCES.values() or args.mode == IQ2_TAIL16_MODE:
        if args.mode == IQ2_TAIL16_MODE and args.source_variant == 'iq2-tail16':
            if args.rebuild_mmq:
                p.error('IQ2 tail16 component builds its numerical kernels directly')
        elif IQ2_TAIL16_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'IQ2 tail16 requires its component or matched historical counting provider')
    if args.source_variant in IQ2_REGISTER_STAGE_SOURCES.values() or args.mode == IQ2_REGISTER_STAGE_MODE:
        if args.mode == IQ2_REGISTER_STAGE_MODE and args.source_variant == 'iq2-register-stage':
            if args.rebuild_mmq:
                p.error('IQ2 register stage component builds its numerical kernels directly')
        elif IQ2_REGISTER_STAGE_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'IQ2 register stage requires its component or matched historical counting provider')
    if args.source_variant in DOWN_REGISTER_PALETTE_SOURCES.values() or args.mode == DOWN_REGISTER_PALETTE_MODE:
        if args.mode == DOWN_REGISTER_PALETTE_MODE and args.source_variant == 'down-register-palette':
            if args.rebuild_mmq:
                p.error('Q2 down register palette component builds its numerical kernels directly')
        elif DOWN_REGISTER_PALETTE_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'Q2 down register palette requires its component or matched historical counting provider')
    if args.source_variant in IQ2_SLICE_COMMIT_SOURCES.values() or args.mode == IQ2_SLICE_COMMIT_MODE:
        if args.mode == IQ2_SLICE_COMMIT_MODE and args.source_variant in IQ2_SLICE_COMMIT_SOURCES.values():
            if args.rebuild_mmq:
                p.error('IQ2 slice commit component builds its numerical kernels directly')
        elif IQ2_SLICE_COMMIT_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'IQ2 slice commit requires its component or matched historical counting provider')
    if args.source_variant in IQ2_SIGN_MASK_SOURCES.values() or args.mode == IQ2_SIGN_MASK_MODE:
        if args.mode == IQ2_SIGN_MASK_MODE and args.source_variant == 'iq2-sign-mask':
            if args.rebuild_mmq:
                p.error('IQ2 sign mask component builds its numerical kernels directly')
        elif IQ2_SIGN_MASK_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'IQ2 sign mask requires its component or matched historical counting provider')
    if args.source_variant in IQ2_RAW_PREFETCH_SOURCES.values() or args.mode == IQ2_RAW_PREFETCH_MODE:
        if args.mode == IQ2_RAW_PREFETCH_MODE and args.source_variant == 'iq2-raw-prefetch':
            if args.rebuild_mmq:
                p.error('IQ2 raw prefetch component builds its numerical kernels directly')
        elif IQ2_RAW_PREFETCH_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'IQ2 raw prefetch requires its component or matched historical counting provider')
    if args.source_variant in SSM_ROW128_SOURCES.values() or args.mode == SSM_ROW128_MODE:
        if args.mode == SSM_ROW128_MODE and args.source_variant == 'ssm-row128':
            if args.rebuild_mmq:
                p.error('SSM row128 component builds its numerical kernels directly')
        elif SSM_ROW128_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'SSM row128 requires its component or matched historical counting provider')
    if args.source_variant in Q8_HALFPAIR_SOURCES.values() or args.mode == Q8_HALFPAIR_MODE:
        if args.mode == Q8_HALFPAIR_MODE and args.source_variant == 'q8-halfpair':
            if args.rebuild_mmq:
                p.error('Q8 halfpair component builds its numerical kernels directly')
        elif Q8_HALFPAIR_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'Q8 halfpair requires its component or matched historical counting provider')
    if args.source_variant in IQ2_HALFBYTE_SOURCES.values() or args.mode == IQ2_HALFBYTE_MODE:
        if args.mode == IQ2_HALFBYTE_MODE and args.source_variant == 'iq2-halfbyte-perm':
            if args.rebuild_mmq:
                p.error('IQ2 halfbyte component builds its numerical kernels directly')
        elif IQ2_HALFBYTE_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'IQ2 halfbyte requires its component or matched historical counting provider')
    if args.source_variant in IQ2_HALFSTAGE_SOURCES.values() or args.mode == IQ2_HALFSTAGE_MODE:
        if args.mode == IQ2_HALFSTAGE_MODE and args.source_variant == 'iq2-halfstage':
            if args.rebuild_mmq:
                p.error('IQ2 halfstage component builds its numerical kernels directly')
        elif IQ2_HALFSTAGE_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'IQ2 halfstage requires its component or matched historical counting provider')
    if args.source_variant in DEFERRED_SOURCES.values():
        if args.mode != FIXED_PROFILE_MODE and DEFERRED_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'MoE deferred norm requires its matched historical counting provider')
    if args.source_variant in Q8_GROUPED_SOURCES.values() or args.mode == Q8_GROUPED_MODE:
        if args.mode == Q8_GROUPED_MODE and args.source_variant == 'q8-grouped-store':
            if args.rebuild_mmq:
                p.error('Q8 grouped component builds its numerical kernels directly')
        elif Q8_GROUPED_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'Q8 grouped requires its component or matched historical counting provider')
    if args.source_variant in HC_BK_VARIANTS:
        if args.mode == HC_BK_MODE:
            if args.rebuild_mmq:
                p.error('HC BK256 component builds kernels directly')
        elif HC_BK_COUNTING.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'HC BK256 requires its component or matched counting mode')
    if args.mode == HC_BK_MODE and args.source_variant not in HC_BK_VARIANTS:
        p.error('HC BK256 requires its component or matched counting mode')
    if args.source_variant in REAUDIT_SOURCES.values():
        if REAUDIT_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider')
    if args.mode == 'shared-q8-oracle-replay' and args.source_variant != Q8_PRODUCER_VARIANT:
        p.error('Q8 oracle replay requires its saved-array provider')
    if args.mode == 'shared-q8-producer-check' or args.source_variant == Q8_PRODUCER_VARIANT:
        if args.mode not in ('shared-q8-oracle-replay', 'shared-q8-producer-check', 'q2-counting-shared-q8') or args.source_variant != Q8_PRODUCER_VARIANT:
            p.error('Shared Q8 producer requires its isolated component mode and source')
        if args.rebuild_mmq and args.mode in ('shared-q8-producer-check', 'shared-q8-oracle-replay'):
            p.error('Shared Q8 producer builds kernels directly; no MMQ selection')
    if args.mode == 'scaled-row-check' or args.source_variant in ROW_VARIANTS:
        if args.mode != 'scaled-row-check' or args.source_variant not in ROW_VARIANTS:
            p.error('Scaled row reuse requires its isolated component mode and source')
        if args.rebuild_mmq:
            p.error('Scaled row component builds kernels directly; no MMQ selection')
    if args.mode in MIXED_TILE_MODES or args.source_variant == 'iq2-mixed':
        if args.mode not in MIXED_TILE_MODES or args.source_variant != 'iq2-mixed':
            p.error('IQ2 mixed tiles requires its isolated component mode and source')
        if args.rebuild_mmq:
            p.error('IQ2 mixed tiles builds its kernels directly; no MMQ selection')
    if args.mode == 'iq2-live-epilogue-check' or args.source_variant in EPILOGUE_VARIANTS:
        if args.mode != 'iq2-live-epilogue-check' or args.source_variant not in EPILOGUE_VARIANTS:
            p.error('IQ2 live epilogue requires its isolated component mode and source')
        if args.rebuild_mmq:
            p.error('IQ2 epilogue component builds its kernel directly; no MMQ selection')
    if args.mode == 'iq2-wmma-signs-check' or args.source_variant in WMMA_SIGN_VARIANTS:
        if args.mode != 'iq2-wmma-signs-check' or args.source_variant not in WMMA_SIGN_VARIANTS:
            p.error('IQ2 WMMA signs requires its isolated component mode and source')
        if args.rebuild_mmq:
            p.error('IQ2 WMMA component builds its kernel directly; no MMQ selection')
    if args.mode == 'ple-cache-first-cpu' and (args.source_variant != 'qualified' or args.rebuild_mmq):
        p.error('PLE cache-first host checks require their fixed source and no GPU build')
    if args.mode == 'iq2-signs-check' or args.source_variant in SIGN_VARIANTS:
        if args.mode != 'iq2-signs-check' or args.source_variant not in SIGN_VARIANTS:
            p.error('IQ2 signs source requires its isolated component mode')
        if not args.rebuild_mmq:
            p.error('IQ2 signs requires a full MMQ rebuild')
    provider_mode = COUNTING_CURVES.get(args.mode, args.mode)
    if args.mode in COUNTING_SOURCES:
        if args.source_variant != COUNTING_SOURCES[args.mode]:
            p.error('Historical counting requires its matched provider')
        if not args.rebuild_mmq and not args.replay_from:
            p.error('Historical counting requires a full MMQ rebuild')
    if provider_mode in CURVE_MODES or args.source_variant in CURVE_VARIANTS:
        expected = {'q2-curve': 'curve-q2', 'ud-curve': 'curve-ud',
                    'q2-curve-ple': 'curve-ple-q2', 'ud-curve-ple': 'curve-ple-ud',
                    'q2-curve-iq2': 'curve-iq2-q2',
                    'q2-curve-scale': 'curve-scale-q2',
                    'q2-curve-row': 'curve-row-q2',
                    'q2-point-norm': 'point-norm-q2',
                    'q2-curve-iq2-mixed': 'curve-iq2-mixed-q2',
                    'q2-curve-ple-cache-first': 'curve-ple-cache-first-q2',
                    'q2-curve-routes': 'curve-routes-q2'}.get(provider_mode)
        if args.source_variant != expected:
            p.error('Canonical curve requires its matched Q2 or UD composition')
        if not args.rebuild_mmq and not args.replay_from:
            p.error('Canonical curve requires a full MMQ rebuild')
    if args.detach and args.mode not in ('q2-terminal-smoke', 'q2-terminal-full'):
        p.error('Persistent launch is limited to Terminal-Bench task runs')
    if args.mode in ('q2-terminal-smoke', 'q2-terminal-full') and not args.detach:
        p.error('Terminal-Bench task runs require the persistent supervisor')
    if args.mode in ('terminal-cpu', 'q2-terminal-build', 'q2-terminal-probe', 'q2-terminal-smoke', 'q2-terminal-full') and args.source_variant not in ('qualified', 'hc-up-chains', 'scaled-input'):
        p.error('Terminal benchmark requires one of its three frozen Q2 variants')
    if args.existing_collection and args.mode != 'collect':
        p.error('Existing collection requires collect mode')
    if args.mode == 'hc-library-ragged-bench' and args.source_variant != 'hc-library-ragged':
        p.error('Ragged HC library requires its isolated source')
    if args.source_variant == 'hc-library-ragged' and args.mode not in ('hc-library-ragged-bench', 'q2-original-baseline'):
        p.error('Ragged HC library requires its component or original Q2 baseline experiment')
    if args.mode == 'hc-decode-reduce-bench' and args.source_variant != 'hc-decode-reduce':
        p.error('HC decode reduction requires its preserved-control source')
    if args.source_variant == 'hc-decode-reduce' and args.mode != 'hc-decode-reduce-bench':
        p.error('HC decode reduction is component-only')
    if args.mode in ORIGINAL_BASELINE_MODES:
        expected = ('library-norm-bound', 'hc-library-ragged') if args.mode.startswith('q2-') else ('qualified',)
        if args.source_variant not in expected:
            p.error('Original baseline requires its fixed Q2 or pristine UD source')
        if not args.rebuild_mmq:
            p.error('Original baseline requires a full MMQ rebuild')
    if args.mode in ('q2-decode-baseline', 'ud-decode-baseline'):
        expected = 'library-norm-bound' if args.mode.startswith('q2-') else 'qualified'
        if args.source_variant != expected:
            p.error('Decode baseline requires its fixed Q2 or pristine UD source')
        if not args.rebuild_mmq:
            p.error('Decode baseline requires a full MMQ rebuild')
    if args.source_variant == 'library-norm-bound' and args.mode not in ('q2-decode-baseline', 'q2-original-baseline'):
        p.error('Bound library norm requires the Q2 decode baseline experiment or original baseline')
    if args.mode == 'hc-library-norm-bench' and args.source_variant not in ('library-norm-cycle', *NORM_SHAPE_VARIANTS):
        p.error('Library norm cycle requires its preserved-control source')
    if args.source_variant == 'library-norm-cycle':
        if args.mode not in ('hc-library-norm-bench', 'q2-bench2k', 'q2-counting-legacy'):
            p.error('Library norm cycle requires its explicit component or bench2k experiment')
        if args.mode == 'q2-bench2k' and not args.rebuild_mmq:
            p.error('Library norm cycle requires a full MMQ rebuild')
    if args.source_variant == 'scaled-library':
        if args.mode not in ('hc-pp-bench', 'q2-bench2k', 'q2-profile'):
            p.error('Scaled library source requires its explicit component, bench2k or profile experiment')
        # Profile modes always build MMQ from source; the flag is bench2k-only.
        if args.mode == 'q2-bench2k' and not args.rebuild_mmq:
            p.error('Scaled library source requires a full MMQ rebuild')
    if args.source_variant in COMBINED_VARIANTS:
        if args.mode not in ('q2-bench2k', 'q2-ple-lookahead', 'q2-ple-first-access', 'narrow-vector-check'):
            p.error('Combined source requires its explicit Q2 model or conversion checks')
        if args.mode == 'q2-bench2k' and not args.rebuild_mmq:
            p.error('Combined source requires a full MMQ rebuild for bench2k')
    if args.mode in ('ple-cpu', 'q2-ple', 'ud-ple', 'ple-io-cpu', 'q2-ple-io', 'ud-ple-io', 'ple-cache-cpu', 'q2-ple-cache64k', 'ple-lookahead-cpu', 'q2-ple-lookahead', 'q2-ple-first-access') and args.source_variant != 'qualified' and not (args.source_variant in COMBINED_VARIANTS and args.mode in ('q2-ple-lookahead', 'q2-ple-first-access')):
        p.error('PLE diagnostics select their fixed instrumented Q2/UD source')
    if args.rebuild_mmq and args.mode not in ('q2-bench2k', 'ud-bench2k', 'q2-decode-baseline', 'ud-decode-baseline', *ORIGINAL_BASELINE_MODES, *CURVE_MODES, *COUNTING_SOURCES, 'iq2-signs-check'):
        p.error('Full MMQ rebuild selection requires bench2k or decode-baseline or original-baseline')
    if args.source_variant in ('hc-down-phased', 'hc-down-phased-free', 'hc-row160-wide', 'hc-row160-loads') and args.mode not in ('hc-pp-operators', 'hc-pp-bench'):
        p.error('Phased HC source is component-only; no model dispatch')
    if args.mode == 'narrow-vector-check' and args.source_variant not in ('narrow-vector', *COMBINED_VARIANTS):
        p.error('Narrow checks require the isolated narrow-vector source')
    if args.source_variant == 'narrow-vector' and args.mode != 'narrow-vector-check':
        p.error('Narrow vector source is component-only; no model dispatch')
    if args.mode == 'scaled-tiles-check' and args.source_variant != 'scaled-tiles':
        p.error('Scaled tile checks require the isolated scaled-tiles source')
    if args.source_variant == 'scaled-tiles' and args.mode != 'scaled-tiles-check':
        p.error('Scaled tile source is component-only; no model dispatch')
    if args.mode == 'hc-deferred-bench' and args.source_variant != 'hc-deferred-norm':
        p.error('Deferred HC benchmark requires the isolated hc-deferred-norm source')
    if args.source_variant == 'hc-deferred-norm' and args.mode != 'hc-deferred-bench':
        p.error('Deferred HC source is not wired for model measurements')
    if args.mode == 'hc-sequence-bench' and args.source_variant not in ('hc-sequence', 'hc-sequence-half-row'):
        p.error('HC sequence benchmark requires the isolated hc-sequence source')
    if args.mode in ('hc-norm-operators', 'hc-norm-bench') and args.source_variant != 'hc-norm-half':
        p.error('F32/F16 norm checks require the isolated hc-norm-half source')
    if args.mode in ('hc-moe-operators', 'hc-moe-bench') and args.source_variant != 'hc-moe-fused':
        p.error('F32 MoE/HC checks require the isolated hc-moe-fused source')
    if args.mode == 'hc-up-operators' and args.source_variant not in ('hc-up-fused', 'hc-up-vec', 'hc-up-vec-exact', 'hc-moe-fused', 'hc-norm-half'):
        p.error('Fused HC up operators require the isolated hc-up-fused source or hc-up-vec candidate')
    if args.mode == 'hc-up-bench' and args.source_variant not in ('hc-up-fused', 'hc-up-vec', 'hc-up-vec-exact', 'hc-moe-fused', 'hc-norm-half'):
        p.error('HC up benchmark requires the measured hc-up-fused source or hc-up-vec candidate')
    if args.mode == 'hc-up-chain-bench' and args.source_variant not in ('affine-palette', 'hc-up-chains'):
        p.error('HC up chain benchmark requires palette or hc-up-chains')
    if args.mode == 'hc-input-bench' and args.source_variant != 'hc-input':
        p.error('HC input benchmark requires the isolated hc-input source')
    if args.mode == 'hc-library-bench' and args.source_variant != 'affine-palette':
        p.error('HC library sweep requires the measured affine-palette source')
    if args.mode in ('packed-tiles-bench', 'packed-tiles16-bench') and args.source_variant != 'hc-up-chains':
        p.error('Tile benchmark requires retained hc-up-chains source')
    if args.mode == 'scaled-input-check' and args.source_variant != 'scaled-input':
        p.error('Scaled checks require the isolated scaled-input source')
    if args.mode == 'shared-fork-check' and args.source_variant != 'shared-overlap':
        p.error('Shared fork checks require the isolated shared-overlap source')
    if args.mode == 'packed-bench' and args.source_variant not in ('hc-decode16', 'affine-palette', 'staged-palette', 'down-scatter', 'shared-overlap', 'scaled-input', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-single-chain', 'hc-full-row', 'hc-half-row', 'hc-row80', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced', 'hc-moe-fused', 'staged-weights', 'code-reuse', 'half-wave', 'half-wave-permlane'):
        p.error('Packed benchmark requires a measured or isolated Q2 decode source')
    if args.mode == 'packed-operators' and args.source_variant not in ('packed', 'hc-up-fused', 'hc-up-vec', 'hc-up-vec-exact', 'hc-moe-fused', 'hc-norm-half', 'hc-down64', 'hc-down64-wave4', 'hc-down64-k4', 'hc-down128-wave4', 'hc-down-coalesced', 'staged-weights', 'code-reuse', 'half-wave', 'half-wave-permlane', 'hc-prefetch', 'hc-prefetch2', 'hc-decode8', 'hc-decode16', 'hc-decode32', 'affine-palette', 'staged-palette', 'down-scatter', 'shared-overlap', 'scaled-input', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-single-chain', 'hc-full-row', 'hc-half-row', 'hc-row80', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced'):
        p.error('Packed operators require the isolated packed source')
    if args.mode == 'routed-operators' and args.source_variant not in ('stack', 'iq2-pair', 'packed', 'hc-up-fused', 'hc-up-vec', 'hc-up-vec-exact', 'hc-moe-fused', 'hc-norm-half', 'hc-down64', 'hc-down64-wave4', 'hc-down64-k4', 'hc-down128-wave4', 'hc-down-coalesced', 'staged-weights', 'code-reuse', 'half-wave', 'half-wave-permlane', 'hc-prefetch', 'hc-prefetch2', 'hc-decode8', 'hc-decode16', 'hc-decode32', 'affine-palette', 'staged-palette', 'down-scatter', 'shared-overlap', 'scaled-input', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-single-chain', 'hc-full-row', 'hc-half-row', 'hc-row80', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced'):
        p.error('Compensated routed operators require the isolated stack source')
    if args.mode == 'iq2-pair-operators' and args.source_variant not in ('iq2-pair', 'packed', 'hc-up-fused', 'hc-up-vec', 'hc-up-vec-exact', 'hc-moe-fused', 'hc-norm-half', 'hc-down64', 'hc-down64-wave4', 'hc-down64-k4', 'hc-down128-wave4', 'hc-down-coalesced', 'staged-weights', 'code-reuse', 'half-wave', 'half-wave-permlane', 'hc-prefetch', 'hc-prefetch2', 'hc-decode8', 'hc-decode16', 'hc-decode32', 'affine-palette', 'staged-palette', 'down-scatter', 'shared-overlap', 'scaled-input', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-single-chain', 'hc-full-row', 'hc-half-row', 'hc-row80', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced'):
        p.error('Paired IQ2 operators require the isolated IQ2 source')
    hc_component = args.source_variant in ('packed', 'hc-moe-fused', 'hc-prefetch', 'hc-prefetch2', 'hc-decode8', 'hc-decode16', 'hc-decode32', 'affine-palette', 'staged-palette', 'down-scatter', 'shared-overlap', 'scaled-input', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-single-chain', 'hc-full-row', 'hc-half-row', 'hc-row80', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced') and args.mode in ('hc-operators', 'hc-bench')
    hc_component = hc_component or (args.source_variant in ('affine-palette', 'staged-palette', 'down-scatter', 'shared-overlap', 'scaled-input', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-single-chain', 'hc-full-row', 'hc-half-row', 'hc-row80', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced', 'hc-moe-fused', 'hc-down64', 'hc-down64-wave4', 'hc-down64-k4', 'hc-down128-wave4', 'hc-down-coalesced') and args.mode in ('hc-pp-operators', 'hc-pp-bench'))
    hc_component = hc_component or (args.mode == 'hc-library-bench' and args.source_variant == 'affine-palette')
    hc_component = hc_component or (args.mode == 'hc-input-bench' and args.source_variant == 'hc-input')
    hc_component = hc_component or (args.mode == 'hc-up-chain-bench' and args.source_variant in ('affine-palette', 'hc-up-chains'))
    hc_component = hc_component or (args.mode in ('packed-tiles-bench', 'packed-tiles16-bench') and args.source_variant == 'hc-up-chains')
    if args.source_variant in ('stack', 'iq2-pair', 'packed', 'hc-up-fused', 'hc-up-vec', 'hc-up-vec-exact', 'hc-moe-fused', 'hc-norm-half', 'hc-down64', 'hc-down64-wave4', 'hc-down64-k4', 'hc-down128-wave4', 'hc-down-coalesced', 'staged-weights', 'code-reuse', 'half-wave', 'half-wave-permlane', 'hc-prefetch', 'hc-prefetch2', 'hc-decode8', 'hc-decode16', 'hc-decode32', 'affine-palette', 'staged-palette', 'down-scatter', 'shared-overlap', 'scaled-input', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-sequence', 'hc-sequence-half-row', 'hc-deferred-norm', 'hc-single-chain', 'hc-full-row', 'hc-half-row', 'hc-row80', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced') and not hc_component and args.mode not in ('hc-up-operators', 'hc-up-bench', 'hc-moe-operators', 'hc-moe-bench', 'hc-norm-operators', 'hc-norm-bench', 'hc-sequence-bench', 'hc-deferred-bench', 'iq2-pair-operators', 'routed-operators', 'shared-fork-check', 'scaled-input-check', 'packed-operators', 'packed-bench', 'operators', 'q2-bench', 'q2-bench2k', 'q2-profile', 'q2-terminal-build', 'q2-terminal-probe', 'q2-terminal-smoke', 'q2-terminal-full', 'terminal-cpu'):
        p.error('Stack source requires routed checks or Q2 model measurements')
    if args.source_variant in ('stack', 'iq2-pair', 'packed', 'hc-up-fused', 'hc-up-vec', 'hc-up-vec-exact', 'hc-moe-fused', 'hc-norm-half', 'hc-down64', 'hc-down64-wave4', 'hc-down64-k4', 'hc-down128-wave4', 'hc-down-coalesced', 'staged-weights', 'code-reuse', 'half-wave', 'half-wave-permlane', 'hc-prefetch', 'hc-prefetch2', 'hc-decode8', 'hc-decode16', 'hc-decode32', 'affine-palette', 'staged-palette', 'down-scatter', 'shared-overlap', 'scaled-input', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-sequence', 'hc-sequence-half-row', 'hc-deferred-norm', 'hc-single-chain', 'hc-full-row', 'hc-half-row', 'hc-row80', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced') and args.mode == 'q2-bench2k' and not args.rebuild_mmq:
        p.error('Stack changes executor/header; explicitly rebuild MMQ')
    if args.source_variant in ('hc', 'hc-prefill') and args.mode not in ('hc-operators', 'hc-bench', 'hc-pp-operators', 'hc-pp-bench', 'q2-bench', 'q2-bench2k', 'q2-profile', 'q2-terminal-build', 'q2-terminal-probe', 'q2-terminal-smoke', 'q2-terminal-full', 'terminal-cpu'):
        p.error('HC source requires HC checks or Q2 benchmark/profile')
    if args.source_variant not in (IQ2_TABLE_LDS_VARIANT, IQ2_DPP_COMMIT_VARIANT, IQ2_FIXED_BOUNDS_VARIANT, IQ2_HALF_SIGN_VARIANT, HC_REUSE_VARIANT, HC_OWNER_VARIANT, HC_RMS_ORDINARY_VARIANT) and args.source_variant not in ('expert-cache', 'compressed-cache', 'iq2-mixed', 'qualified', 'hc', 'hc-prefill', 'stack', 'iq2-pair', 'packed', 'hc-up-fused', 'hc-up-vec', 'hc-up-vec-exact', 'hc-moe-fused', 'hc-norm-half', 'hc-down64', 'hc-down64-wave4', 'hc-down64-k4', 'hc-down128-wave4', 'hc-down-coalesced', 'staged-weights', 'code-reuse', 'half-wave', 'half-wave-permlane', 'hc-prefetch', 'hc-prefetch2', 'hc-decode8', 'hc-decode16', 'hc-decode32', 'affine-palette', 'staged-palette', 'down-scatter', 'shared-overlap', 'scaled-input', 'scaled-tiles', 'narrow-vector', 'hc-down-phased', 'hc-down-phased-free', 'hc-row160-wide', 'hc-row160-loads', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-sequence', 'hc-sequence-half-row', 'hc-deferred-norm', 'hc-single-chain', 'hc-full-row', 'hc-half-row', 'hc-row80', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced', *COMBINED_VARIANTS, 'scaled-library', 'library-norm-cycle', 'library-norm-bound', 'hc-decode-reduce', 'hc-library-ragged', 'hc-norm-ragged', *CURVE_VARIANTS, *SIGN_VARIANTS, *WMMA_SIGN_VARIANTS, *EPILOGUE_VARIANTS, *ROW_VARIANTS, *NORM_SHAPE_VARIANTS, Q8_PRODUCER_VARIANT, *REAUDIT_SOURCES.values(), *HC_BK_VARIANTS, *DEFERRED_SOURCES.values(), *Q8_GROUPED_SOURCES.values(), *SCALED_SELECTIVE_SOURCES.values(), *IQ2_LIVE_COMPOSE_SOURCES.values(), *IQ2_RAW_SELECTIVE_SOURCES.values(), *IQ2_HALFSTAGE_SOURCES.values(), *IQ2_HALFBYTE_SOURCES.values(), *Q8_HALFPAIR_SOURCES.values(), *SSM_ROW128_SOURCES.values(), *IQ2_FUSED_GRID_SOURCES.values(), *IQ2_SLICE_COMMIT_SOURCES.values(), *IQ2_SHORT_TILES_SOURCES.values(), *IQ2_TAIL16_SOURCES.values(), *IQ2_REGISTER_STAGE_SOURCES.values(), *DOWN_REGISTER_PALETTE_SOURCES.values(), *HALF_FIXED_WIDTH_SOURCES.values(), *HALF_CONSUMER_EIGHT_SOURCES.values(), *SSM_ROW_GROUP_SOURCES.values(), *SSM_FOLLOWUP_VARIANTS, *SHARED_DOWN_MANIFESTS, *DOWN_REGISTER_SCATTER_SOURCES.values(), *DOWN_HALF_VECTOR_SOURCES.values(), *DOWN_HALF_PAIR_SOURCES.values(), *DOWN_HALF_STORAGE_SOURCES.values(), *DOWN_LIVE_STAGE_SOURCES.values(), *DOWN_OUTPUT_REUSE_SOURCES.values(), *IQ2_WIDE_PAIR_SOURCES.values(), *IQ2_FOUR_WAVE_SOURCES.values(), *IQ2_LANE_COMMIT_SOURCES.values(), *IQ2_SIGN_MASK_SOURCES.values(), *IQ2_RAW_PREFETCH_SOURCES.values(), *DOWN_RAW_PREFETCH_SOURCES.values(), *Q8_MIRROR_SOURCES.values(), *SCALED_WAVE_PACK_SOURCES.values(), *SCALED_EXPERT_ORDER_SOURCES.values(), *COMPACT_EXPERT_CHAIN_SOURCES.values(), *PRODUCER_Q8_SOURCES.values(), *SHARED_Q8_PAIR_SOURCES.values(), *Q8_ALIGNED_PAIR_SOURCES.values(), *Q8_K16_PHASES_SOURCES.values()) and args.mode != 'q2-bench':
        p.error('MMQ-changing source selection requires q2-bench')
    if not re.fullmatch(r'q2-[a-z0-9-]{1,48}', args.label):
        p.error('Label must start with q2- and contain lowercase letters/digits/hyphens')
    if args.mode == 'status':
        script = 'from pathlib import Path; import json; p=Path('+repr(REMOTE+args.label+'/results')+'); j=json.loads((p/"result.json").read_text()); print(json.dumps({k:j.get(k) for k in ["state","mode","pid","started_at","finished_at","commands","error","postflight_kfd"]},indent=2)); logs=sorted(p.glob("*.log")); print(logs[-1].read_text()[-3000:] if logs else "")'
        raise SystemExit(subprocess.run(['ssh','-F','/dev/null','-o','BatchMode=yes',HOST,'python3 -c '+shlex.quote(script)]).returncode)
    if args.mode == 'collect':
        out = ROOT/'evidence'/args.label
        archive_path = out/'results.tar.gz'
        if (out/'results').exists() or (out/'collection.json').exists():
            raise ValueError('Refusing to overwrite collected results')
        if not args.existing_collection:
            script = 'import tarfile,sys; a=tarfile.open(fileobj=sys.stdout.buffer,mode="w|gz"); a.add('+repr(REMOTE+args.label+'/results')+',arcname="results"); a.close()'
            with archive_path.open('xb') as stream:
                rc = subprocess.run(['ssh','-F','/dev/null','-o','BatchMode=yes',HOST,'python3 -c '+shlex.quote(script)],stdout=stream).returncode
            if rc: raise SystemExit(rc)
        with tarfile.open(archive_path) as a:
            receipt=collection_receipt(a)
            a.extractall(out,filter='data')
        for name,meta in receipt.get('artifacts',{}).items():
            if Path(name).is_absolute() or '..' in Path(name).parts: raise ValueError('Unsafe artifact name')
            payload=out/'results'/name
            if payload.stat().st_size!=meta['bytes'] or file_sha256(payload)!=meta['sha256']:
                raise ValueError('Artifact integrity mismatch')
        collected={'collected':str(archive_path),'sha256':file_sha256(archive_path),
                   'verified_artifacts':len(receipt.get('artifacts',{})),
                   'existing_archive':args.existing_collection}
        (out/'collection.json').write_text(json.dumps(collected,indent=2)+'\n')
        print(json.dumps(collected))
        return
    out = ROOT / 'evidence' / args.label
    out.mkdir()
    capsule = out / 'source.tar.gz'
    with tarfile.open(capsule, 'w:gz') as archive:
        for name in ('tools/prepare-q2-iq2-table-lds.py',
                     'tools/analyze-q2-iq2-table-lds-static.py',
                     'experiments/q2-iq2-table-lds.patch',
                     'tools/freeze-q2-iq2-table-lds-plan.py',
                     'tools/q2-iq2-table-lds-window.py',
                     'tools/q2-iq2-table-lds-phase.py',
                     'tools/prepare-q2-iq2-dpp-commit.py',
                     'tools/analyze-q2-iq2-dpp-commit-static.py',
                     'experiments/q2-iq2-dpp-commit.patch',
                     'tools/freeze-q2-iq2-dpp-commit-plan.py',
                     'tools/q2-iq2-dpp-commit-window.py',
                     'tools/q2-iq2-dpp-commit-phase.py',
                     'tools/prepare-q2-iq2-fixed-bounds.py',
                     'tools/analyze-q2-iq2-fixed-bounds-static.py',
                     'experiments/q2-iq2-fixed-bounds.patch',
                     'tools/freeze-q2-iq2-fixed-bounds-plan.py',
                     'tools/q2-iq2-fixed-bounds-window.py',
                     'tools/q2-iq2-fixed-bounds-phase.py',
                     'tools/prepare-q2-iq2-half-sign-arithmetic.py',
                     'tools/analyze-q2-iq2-half-sign-arithmetic-static.py',
                     'experiments/q2-iq2-half-sign-arithmetic.patch',
                     'tools/freeze-q2-iq2-half-sign-arithmetic-plan.py',
                     'tools/q2-iq2-half-sign-arithmetic-window.py',
                     'tools/q2-iq2-half-sign-arithmetic-phase.py',
                     'tools/prepare-q2-hc-rms-owner-ordinary.py',
                     'tools/analyze-q2-hc-rms-owner-ordinary-static.py',
                     'experiments/q2-hc-rms-owner-ordinary.patch',
                     'tools/freeze-q2-hc-rms-owner-ordinary-plan.py',
                     'tools/q2-hc-rms-owner-ordinary-window.py',
                     'tools/q2-hc-rms-owner-ordinary-phase.py',
                     'tools/prepare-q2-hc-norm-owner-source.py',
                     'tools/prepare-q2-hc-norm-owner-component.py',
                     'tools/analyze-q2-hc-norm-owner-component-preparation.py',
                     'experiments/q2-hc-norm-owner-draft.inc',
                     'tools/analyze-q2-hc-norm-owner-component.py',
                     'tools/freeze-q2-hc-norm-owner-plan.py',
                     'tools/q2-hc-norm-owner-window.py',
                     'tools/q2-hc-norm-owner-phase.py',
                     'tools/analyze-q2-hc-inject-reuse-component.py',
                     'tools/freeze-q2-hc-inject-reuse-plan.py',
                     'tools/q2-hc-inject-reuse-window.py',
                     'tools/q2-hc-inject-reuse-phase.py',
                     'tools/q2_window_registry.py'):
            archive.add(ROOT / name, arcname=name)
        for name in ['experiments/q2_compressed_cache.h', 'experiments/q2_expert_cache_policy.h', 'experiments/q2_expert_cache_iq2_grid.inc', 'experiments/q2_hc_blaslt_control.cpp', 'experiments/q2_hc_blaslt_control.hpp', 'experiments/q2-q8-grouped-control.inc', 'experiments/q2-iq2-halfstage-control.inc', 'experiments/q2-iq2-fused-grid-control.inc', 'experiments/q2-half-fixed-width-control.inc', 'experiments/q2-half-consumer-eight-control.inc', 'experiments/q2-ssm-row-group-control.inc', 'experiments/q2-ssm-row-group-oracle.inc', 'experiments/q2-ssm-compact-lds-oracle.inc', 'experiments/q2-down-register-scatter-pair-control.inc', 'experiments/q2-down-register-scatter-pair-epilogue.inc', 'experiments/q2-down-half-vector-control.inc', 'experiments/q2-down-half-pair-control.inc', 'experiments/q2-down-live-stage-control.inc', 'experiments/q2-down-output-reuse-control.inc', 'experiments/q2-iq2-wide-pair-control.inc', 'experiments/q2-iq2-four-wave-control.inc', 'experiments/q2-iq2-register-stage-control.inc', 'experiments/q2-down-register-palette-control.inc', 'experiments/q2-hc-inject-reuse-draft-v3.inc', 'experiments/q2-iq2-slice-commit-control.inc', 'experiments/q2-iq2-sign-mask-control.inc', 'experiments/q2-iq2-raw-prefetch-control.inc', 'experiments/q2-down-raw-prefetch-control.inc', 'experiments/q2_q8_mirror_policy.h', 'experiments/q2_q8_mirror_kernels.inc', 'experiments/q2-scaled-wave-pack-control.inc', 'experiments/q2-q8-aligned-pair-control.inc', 'experiments/q2-q8-k16-phases-control.inc', 'CMakeLists.txt', 'cmake', 'tests', 'config', 'experiments/q2_curve_profile.hpp', 'experiments/q2_route_profile.hpp', 'tools/analyze-q2-route-profile.py', 'experiments/iq2_mixed_tiles.c', 'experiments/iq2_mixed_tiles.h', 'experiments/q2_iq2_short_tiles.c', 'experiments/q2_iq2_short_tiles.h', 'experiments/q2_iq2_tail16.h', 'experiments/q2_iq2_tail16.c', 'experiments/q2_iq2_tail16_routes.inc', 'experiments/q2_scaled_tiles_map.c', 'experiments/q2_scaled_tiles_map.h', 'experiments/counting-baseline', 'experiments/ple_flow.c', 'experiments/ple_flow.h', 'experiments/gpu_fork.c', 'experiments/gpu_fork.h', 'experiments/q2_deferred_norm_state.h', 'experiments/q2_shared_fork.hpp', 'tools/analyze-q2-terminal.py', 'tools/collect-q2-terminal.py', 'tools/q2-terminal-session.py', 'tools/q2-down-register-palette-phase.py', 'tools/q2-runner.py', 'tools/q2-remote.py', 'tools/q2-canonical-http.py', 'tools/q2-curve-session.py', 'tools/analyze-q2-curve-profile.py', 'tools/analyze-q2-curve.py', 'tools/analyze-q2-iq2-curve.py', 'tools/analyze-q2-ple-cache-first.py', 'tools/analyze-q2-iq2-wmma-signs.py', 'tools/analyze-q2-iq2-live-epilogue.py', 'tools/analyze-q2-iq2-mixed.py', 'tools/q2_native_curve.py', 'tools/q2_process.py', 'tools/q2_counter_calibration.py', 'tools/q2_thermal.py', 'tools/axb35-fan-curves.py', 'tools/q2_reuse.py', 'tools/q2_binary_replay.py', 'tools/q2_capture_routes.py', 'tools/q2_oracle_replay.py', 'tools/analyze-q2-profile.py', 'tools/analyze-q2-expert-profile.py', 'tools/q2-resource-report.py', 'tools/analyze-q2-hc-up.py']:
            archive.add(ROOT / name, arcname=name)
        source = '.deps/gufo-base' if args.mode in ('ud-base','ud-profile','ud-bench2k','ud-decode-baseline','ud-original-baseline','ud-counting-legacy') else '.deps/gufo-q2-register-reference' if args.mode == 'operators-reference' else '.deps/gufo-q2'
        if args.source_variant != 'qualified':
            source = '.deps/gufo-q2-bench-' + args.source_variant
        if args.mode in ('ple-cpu', 'q2-ple', 'ud-ple'):
            source = '.deps/gufo-ple-' + ('ud' if args.mode == 'ud-ple' else 'q2')
        if args.mode in ('ple-io-cpu', 'q2-ple-io', 'ud-ple-io'):
            source = '.deps/gufo-ple-io-' + ('ud' if args.mode == 'ud-ple-io' else 'q2')
        if args.mode in ('ple-cache-cpu', 'q2-ple-cache64k'):
            source = '.deps/gufo-ple-cache64k'
        if args.mode == 'ple-cache-first-cpu':
            info = json.loads((ROOT/'config/q2-ple-cache-first-source.json').read_text())
            parent_path = ROOT/'config/q2-curve-source.json'
            if file_sha256(parent_path) != info['parent_manifest_sha256']:
                p.error('PLE cache-first canonical parent changed')
            parent = json.loads(parent_path.read_text())['variants']['q2']
            control = info['base']
            if control != parent['source']:
                p.error('PLE cache-first control source differs')
            control_files = {str(f.relative_to(ROOT/control)): file_sha256(f)
                             for f in (ROOT/control).rglob('*') if f.is_file()}
            if control_files != parent['files']:
                p.error('PLE cache-first control inventory changed')
            source = info['candidate']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != info['files']:
                p.error('PLE cache-first provider inventory changed')
            if (actual.keys() != control_files.keys() or
                    [k for k in actual if actual[k] != control_files[k]] !=
                    ['src/models/qwen38_flash_next/ngram.cpp']):
                p.error('PLE cache-first must change only row-read scheduling')
            archive.add(ROOT/control, arcname='ple-control-source')
        if args.source_variant in HC_BK_VARIANTS:
            info = json.loads((ROOT/HC_BK_MANIFESTS[args.source_variant]).read_text())
            variant = info['variants'][args.source_variant]
            if file_sha256(ROOT/variant['parent_manifest']) != variant['parent_manifest_sha256']:
                p.error('HC BK256 retained parent manifest changed')
            for name, row in info['control_files'].items():
                if file_sha256(ROOT/name) != row['sha256']:
                    p.error('HC BK256 library control changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files']:
                p.error('HC BK256 provider inventory changed')
        if args.source_variant in SCALED_SELECTIVE_SOURCES.values():
            info = json.loads((ROOT/'config/q2-scaled-selective-source.json').read_text())
            variant = info['variants'][args.source_variant]
            if file_sha256(ROOT/variant['parent_manifest']) != variant['parent_manifest_sha256']:
                p.error('Selective scaled measured parent manifest changed')
            for name, digest in variant['c17_policy_files'].items():
                if file_sha256(ROOT/'experiments'/name) != digest:
                    p.error('Selective scaled C17 policy changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files']:
                p.error('Selective scaled provider inventory changed')
        if args.source_variant in Q8_GROUPED_SOURCES.values():
            info = json.loads((ROOT/'config/q2-q8-grouped-source.json').read_text())
            variant = info['variants'][args.source_variant]
            if file_sha256(ROOT/variant['parent_manifest']) != variant['parent_manifest_sha256']:
                p.error('Q8 grouped measured parent manifest changed')
            if file_sha256(ROOT/variant['control_include']) != variant['control_include_sha256']:
                p.error('Q8 grouped numerical control changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files']:
                p.error('Q8 grouped provider inventory changed')
        if args.source_variant in IQ2_LIVE_COMPOSE_SOURCES.values():
            info = json.loads((ROOT/IQ2_LIVE_COMPOSE_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'retained_component',
                        'retained_patch', 'retained_transformer', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('IQ2 live composition retained source or evidence changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files']:
                p.error('IQ2 live composition provider inventory changed')

        if args.source_variant in IQ2_RAW_SELECTIVE_SOURCES.values():
            info = json.loads((ROOT/IQ2_RAW_SELECTIVE_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('IQ2 raw selective retained source reference changed')
            for key in ('measured_parent', 'retained_component', 'retained_selector_source', 'retained_selector_model'):
                if file_sha256(ROOT/info[key]) != info[key+'_sha256']:
                    p.error('IQ2 raw selective retained evidence changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files']:
                p.error('IQ2 raw selective provider inventory changed')

        if args.source_variant in EXPERT_CACHE_SOURCES.values():
            info = json.loads((ROOT/EXPERT_CACHE_MANIFESTS[args.source_variant]).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('Expert cache measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files']:
                p.error('Expert cache provider inventory changed')
        if args.source_variant in Q8_MIRROR_SOURCES.values():
            info = json.loads((ROOT/Q8_MIRROR_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'mirror_resource_policy', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('Q8 mirror measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files']:
                p.error('Q8 mirror provider inventory changed')
        if args.source_variant in SCALED_WAVE_PACK_SOURCES.values():
            info = json.loads((ROOT/SCALED_WAVE_PACK_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'control_include', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('Scaled wave pack measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files']:
                p.error('Scaled wave pack provider inventory changed')
        if args.source_variant in SCALED_EXPERT_ORDER_SOURCES.values():
            info = json.loads((ROOT/SCALED_EXPERT_ORDER_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('Scaled expert order measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files']:
                p.error('Scaled expert order provider inventory changed')
        if args.source_variant in COMPACT_EXPERT_CHAIN_SOURCES.values():
            info = json.loads((ROOT/COMPACT_EXPERT_CHAIN_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('Compact expert chain measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files']:
                p.error('Compact expert chain provider inventory changed')
        if args.source_variant in PRODUCER_Q8_SOURCES.values():
            info = json.loads((ROOT/PRODUCER_Q8_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'initial_source_manifest', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('Producer Q8 measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files']:
                p.error('Producer Q8 provider inventory changed')
        if args.source_variant in SHARED_Q8_PAIR_SOURCES.values():
            info = json.loads((ROOT/SHARED_Q8_PAIR_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('Shared Q8 pair measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files']:
                p.error('Shared Q8 pair provider inventory changed')
        if args.source_variant in Q8_ALIGNED_PAIR_SOURCES.values():
            info = json.loads((ROOT/Q8_ALIGNED_PAIR_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'control_include', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('Q8 aligned pair measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files']:
                p.error('Q8 aligned pair provider inventory changed')
        if args.source_variant in Q8_K16_PHASES_SOURCES.values():
            info = json.loads((ROOT/Q8_K16_PHASES_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'control_include', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('Q8 K16 phases measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files']:
                p.error('Q8 K16 phases provider inventory changed')
        if args.source_variant in DOWN_RAW_PREFETCH_SOURCES.values():
            info = json.loads((ROOT/DOWN_RAW_PREFETCH_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'control_include', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('Q2 down raw prefetch measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files']:
                p.error('Q2 down raw prefetch provider inventory changed')
        if args.source_variant in IQ2_FUSED_GRID_SOURCES.values():
            info = json.loads((ROOT/IQ2_FUSED_GRID_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'control_include', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('IQ2 fused grid measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files']:
                p.error('IQ2 fused grid provider inventory changed')
        if args.source_variant in HALF_FIXED_WIDTH_SOURCES.values():
            info = json.loads((ROOT/HALF_FIXED_WIDTH_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'control_include', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('Q2 half fixed width measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files'] or len(actual) != 1026:
                p.error('Q2 half fixed width provider inventory changed')
        if args.source_variant in HALF_CONSUMER_EIGHT_SOURCES.values():
            info = json.loads((ROOT/HALF_CONSUMER_EIGHT_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'control_include', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('Q2 half consumer eight measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files'] or len(actual) != 1026:
                p.error('Q2 half consumer eight provider inventory changed')
        if args.source_variant in SHARED_DOWN_MANIFESTS:
            source = shared_down_source(p, args.source_variant)
        if args.source_variant in SSM_FOLLOWUP_VARIANTS:
            source = ssm_followup_source(p, args.source_variant)
        if args.source_variant in SSM_ROW_GROUP_SOURCES.values():
            info = json.loads((ROOT/SSM_ROW_GROUP_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'parent_disposition', 'standalone_manifest', 'control_include', 'patch', 'fixture', 'oracle', 'fixture_contract'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('Q2 SSM row group measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files'] or len(actual) != 1027:
                p.error('Q2 SSM row group provider inventory changed')
        if args.source_variant in DOWN_REGISTER_SCATTER_SOURCES.values():
            info = json.loads((ROOT/DOWN_REGISTER_SCATTER_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'control_include', 'patch', 'fragment'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('Q2 down register scatter measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files'] or len(actual) != 1027:
                p.error('Q2 down register scatter provider inventory changed')
        if args.source_variant in DOWN_HALF_VECTOR_SOURCES.values():
            info = json.loads((ROOT/DOWN_HALF_VECTOR_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'control_include', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('Q2 down half vector measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files'] or len(actual) != 1026:
                p.error('Q2 down half vector provider inventory changed')
        if args.source_variant in DOWN_HALF_PAIR_SOURCES.values():
            info = json.loads((ROOT/DOWN_HALF_PAIR_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'control_include', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('Q2 down half pair measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files'] or len(actual) != 1026:
                p.error('Q2 down half pair provider inventory changed')
        if args.source_variant in DOWN_HALF_STORAGE_SOURCES.values():
            info = json.loads((ROOT/DOWN_HALF_STORAGE_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('Q2 down half storage measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files'] or len(actual) != 1026:
                p.error('Q2 down half storage provider inventory changed')
        if args.source_variant in DOWN_LIVE_STAGE_SOURCES.values():
            info = json.loads((ROOT/DOWN_LIVE_STAGE_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'control_include', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('Q2 down live stage measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files'] or len(actual) != 1025:
                p.error('Q2 down live stage provider inventory changed')
        if args.source_variant in DOWN_OUTPUT_REUSE_SOURCES.values():
            info = json.loads((ROOT/DOWN_OUTPUT_REUSE_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'control_include', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('Q2 down output reuse measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files'] or len(actual) != 1025:
                p.error('Q2 down output reuse provider inventory changed')
        if args.source_variant in IQ2_WIDE_PAIR_SOURCES.values():
            info = json.loads((ROOT/IQ2_WIDE_PAIR_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'control_include', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('IQ2 wide pair measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files'] or len(actual) != 1025:
                p.error('IQ2 wide pair provider inventory changed')
        if args.source_variant in IQ2_FOUR_WAVE_SOURCES.values():
            info = json.loads((ROOT/IQ2_FOUR_WAVE_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'control_include', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('IQ2 four wave measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files'] or len(actual) != 1027:
                p.error('IQ2 four wave provider inventory changed')
        if args.source_variant in IQ2_LANE_COMMIT_SOURCES.values():
            info = json.loads((ROOT/IQ2_LANE_COMMIT_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'control_include', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('IQ2 lane commit measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files'] or len(actual) != 1025:
                p.error('IQ2 lane commit provider inventory changed')
        if args.source_variant in IQ2_SHORT_TILES_SOURCES.values():
            info = json.loads((ROOT/IQ2_SHORT_TILES_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'routing_audit', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('IQ2 short tiles measured source reference changed')
            for name, digest in variant['c17_map_files'].items():
                if file_sha256(ROOT/name) != digest:
                    p.error('IQ2 short tiles C17 map changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files'] or len(actual) != 1027:
                p.error('IQ2 short tiles provider inventory changed')
            if not variant['bounded_host_usage_records']:
                p.error('IQ2 short tiles must record actual map usage outside timers')
        if args.source_variant == HC_REUSE_VARIANT:
            info = json.loads((ROOT/HC_REUSE_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'draft_manifest', 'draft_static',
                        'numerical_include', 'fixture', 'generator'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('HC injection reuse component identity changed')
            if variant['production_provider'] or variant['model_mode']:
                p.error('HC injection reuse draft must remain component only')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files'] or len(actual) != 1027:
                p.error('HC injection reuse retained provider inventory changed')
        if args.source_variant == IQ2_HALF_SIGN_VARIANT:
            variant = json.loads((ROOT / IQ2_HALF_SIGN_MANIFEST).read_text())['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'patch', 'generator'):
                if file_sha256(ROOT / variant[key]) != variant[key + '_sha256']:
                    p.error('IQ2 sign arithmetic source binding changed')
            if file_sha256(ROOT / variant['independently_pinned_sign_table']) != variant['original_sign_table_sha256']:
                p.error('Original IQ2 sign table changed')
            source = variant['source']
            if file_sha256(ROOT / source / variant['numerical_include']) != variant['numerical_include_sha256']:
                p.error('IQ2 sign arithmetic private body changed')
            actual = {str(f.relative_to(ROOT / source)): file_sha256(f)
                      for f in (ROOT / source).rglob('*') if f.is_file()}
            if actual != variant['files'] or len(actual) != 1028:
                p.error('IQ2 sign arithmetic provider inventory changed')
        if args.source_variant == IQ2_TABLE_LDS_VARIANT:
            variant = json.loads((ROOT / IQ2_TABLE_LDS_MANIFEST).read_text())['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'patch', 'generator'):
                if file_sha256(ROOT / variant[key]) != variant[key + '_sha256']:
                    p.error('IQ2 table LDS source binding changed')
            source = variant['source']
            if file_sha256(ROOT / source / variant['numerical_include']) != variant['numerical_include_sha256']:
                p.error('IQ2 table LDS private body changed')
            actual = {str(f.relative_to(ROOT / source)): file_sha256(f)
                      for f in (ROOT / source).rglob('*') if f.is_file()}
            if actual != variant['files'] or len(actual) != 1029:
                p.error('IQ2 table LDS provider inventory changed')
        if args.source_variant == IQ2_DPP_COMMIT_VARIANT:
            variant = json.loads((ROOT / IQ2_DPP_COMMIT_MANIFEST).read_text())['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'patch', 'generator'):
                if file_sha256(ROOT / variant[key]) != variant[key + '_sha256']:
                    p.error('IQ2 DPP commit source binding changed')
            source = variant['source']
            if file_sha256(ROOT / source / variant['numerical_include']) != variant['numerical_include_sha256']:
                p.error('IQ2 DPP commit private body changed')
            actual = {str(f.relative_to(ROOT / source)): file_sha256(f)
                      for f in (ROOT / source).rglob('*') if f.is_file()}
            if actual != variant['files'] or len(actual) != 1029:
                p.error('IQ2 DPP commit provider inventory changed')
        if args.source_variant == IQ2_FIXED_BOUNDS_VARIANT:
            variant = json.loads((ROOT / IQ2_FIXED_BOUNDS_MANIFEST).read_text())['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'patch', 'generator'):
                if file_sha256(ROOT / variant[key]) != variant[key + '_sha256']:
                    p.error('IQ2 fixed bounds source binding changed')
            source = variant['source']
            if file_sha256(ROOT / source / variant['numerical_include']) != variant['numerical_include_sha256']:
                p.error('IQ2 fixed bounds private body changed')
            actual = {str(f.relative_to(ROOT / source)): file_sha256(f)
                      for f in (ROOT / source).rglob('*') if f.is_file()}
            if actual != variant['files'] or len(actual) != 1028:
                p.error('IQ2 fixed bounds provider inventory changed')
        if args.source_variant == HC_RMS_ORDINARY_VARIANT:
            variant = json.loads((ROOT/HC_RMS_ORDINARY_MANIFEST).read_text())['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'component_qualification',
                        'qualified_include', 'patch', 'generator'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('HC ordinary RMS qualified source binding changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files'] or len(actual) != 1028:
                p.error('HC ordinary RMS provider inventory changed')
        if args.source_variant == HC_OWNER_VARIANT:
            info = json.loads((ROOT/HC_OWNER_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'draft_manifest', 'draft_static',
                        'numerical_include', 'fixture', 'generator', 'fixture_preparation', 'fixture_static'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('HC RMS ownership component identity changed')
            if variant['production_provider'] or variant['model_mode']:
                p.error('HC RMS ownership draft must remain component only')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files'] or len(actual) != 1027:
                p.error('HC RMS ownership retained provider inventory changed')
        if args.source_variant in DOWN_REGISTER_PALETTE_SOURCES.values():
            info = json.loads((ROOT/DOWN_REGISTER_PALETTE_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'draft_static', 'donor_include', 'control_include', 'patch', 'generator'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('Q2 down register palette measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files'] or len(actual) != 1028:
                p.error('Q2 down register palette provider inventory changed')
            if file_sha256(ROOT/source/variant['numerical_include']) != variant['numerical_include_sha256']:
                p.error('Q2 down register palette numerical include changed')
        if args.source_variant in IQ2_REGISTER_STAGE_SOURCES.values():
            info = json.loads((ROOT/IQ2_REGISTER_STAGE_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'donor_manifest', 'control_include', 'patch', 'generator'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('IQ2 register stage measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files'] or len(actual) != 1028:
                p.error('IQ2 register stage provider inventory changed')
            if file_sha256(ROOT/source/variant['numerical_include']) != variant['numerical_include_sha256']:
                p.error('IQ2 register stage numerical include changed')
        if args.source_variant in IQ2_TAIL16_SOURCES.values():
            info = json.loads((ROOT/IQ2_TAIL16_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'routing_audit', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('IQ2 tail16 measured source reference changed')
            for name, digest in variant['c17_map_files'].items():
                if file_sha256(ROOT/name) != digest:
                    p.error('IQ2 tail16 C17 map changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files'] or len(actual) != 1029:
                p.error('IQ2 tail16 provider inventory changed')
            if not variant['bounded_host_usage_records']:
                p.error('IQ2 tail16 must record actual map usage outside timers')
        if args.source_variant in IQ2_SLICE_COMMIT_SOURCES.values():
            info = json.loads((ROOT/IQ2_SLICE_COMMIT_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'control_include', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('IQ2 slice commit measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files']:
                p.error('IQ2 slice commit provider inventory changed')
        if args.source_variant in IQ2_SIGN_MASK_SOURCES.values():
            info = json.loads((ROOT/IQ2_SIGN_MASK_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'control_include', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('IQ2 sign mask measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files']:
                p.error('IQ2 sign mask provider inventory changed')
        if args.source_variant in IQ2_RAW_PREFETCH_SOURCES.values():
            info = json.loads((ROOT/IQ2_RAW_PREFETCH_MANIFEST).read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'control_include', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('IQ2 raw prefetch measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files']:
                p.error('IQ2 raw prefetch provider inventory changed')
        if args.source_variant in SSM_ROW128_SOURCES.values():
            info = json.loads((ROOT/'config/q2-ssm-row128-source.json').read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'control_include', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('SSM row128 measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files']:
                p.error('SSM row128 provider inventory changed')
        if args.source_variant in Q8_HALFPAIR_SOURCES.values():
            info = json.loads((ROOT/'config/q2-q8-halfpair-source.json').read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'control_include', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('Q8 halfpair measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files']:
                p.error('Q8 halfpair provider inventory changed')
        if args.source_variant in IQ2_HALFBYTE_SOURCES.values():
            info = json.loads((ROOT/'config/q2-iq2-halfbyte-perm-formatted-source.json').read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'measured_parent', 'patch'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('IQ2 halfbyte measured source reference changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files']:
                p.error('IQ2 halfbyte provider inventory changed')
        if args.source_variant in IQ2_HALFSTAGE_SOURCES.values():
            info = json.loads((ROOT/'config/q2-iq2-halfstage-swizzled-source.json').read_text())
            variant = info['variants'][args.source_variant]
            if file_sha256(ROOT/variant['parent_manifest']) != variant['parent_manifest_sha256']:
                p.error('IQ2 halfstage measured parent manifest changed')
            if file_sha256(ROOT/variant['control_include']) != variant['control_include_sha256']:
                p.error('IQ2 halfstage numerical control changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files']:
                p.error('IQ2 halfstage provider inventory changed')
        if args.source_variant in DEFERRED_SOURCES.values():
            info = json.loads((ROOT/'config/q2-hc-moe-deferred-source.json').read_text())
            variant = info['variants'][args.source_variant]
            for key in ('parent_manifest', 'donor_manifest'):
                if file_sha256(ROOT/variant[key]) != variant[key+'_sha256']:
                    p.error('MoE deferred retained source manifest changed')
            if file_sha256(ROOT/'experiments/q2_deferred_norm_state.h') != variant['c17_state_header_sha256']:
                p.error('MoE deferred state contract changed')
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files']:
                p.error('MoE deferred provider inventory changed')
        if args.mode in REAUDIT_SOURCES:
            info = json.loads((ROOT/'config/q2-reaudit-composition-source.json').read_text())
            if any(file_sha256(ROOT/name) != expected for name, expected in info['retained_manifests'].items()):
                p.error('Reaudit retained source manifest changed')
            variant = info['variants'][args.source_variant]
            source = variant['source']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != variant['files']:
                p.error('Reaudit composition inventory changed')
        if args.source_variant == Q8_PRODUCER_VARIANT:
            info = json.loads((ROOT/'config/q2-shared-q8-producer-source.json').read_text())
            parent_path = ROOT/'config/q2-iq2-mixed-model-source.json'
            parent = json.loads(parent_path.read_text())
            if file_sha256(parent_path) != info['parent_manifest_sha256'] or info['base'] != parent['candidate']:
                p.error('Shared Q8 producer fixed-reference parent changed')
            source = info['candidate']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != info['files']:
                p.error('Shared Q8 producer inventory changed')
        if args.mode == 'shared-q8-oracle-replay':
            from q2_oracle_replay import verify
            replay = verify(ROOT)
            for name in replay['arrays']:
                archive.add(ROOT/'evidence/q2-shared-q8-producer-component-r3/results'/name,
                            arcname='oracle-replay-data/'+name)
        if args.source_variant in NORM_SHAPE_VARIANTS:
            info = json.loads((ROOT/'config/q2-norm-fixed-shape-source.json').read_text())
            parent_path = ROOT/'config/q2-iq2-mixed-model-source.json'
            parent = json.loads(parent_path.read_text())
            if (file_sha256(parent_path) != info['parent_manifest_sha256'] or
                    info['base'] != parent['candidate']):
                p.error('Fixed norm shape mixed-map parent changed')
            candidate = args.source_variant == 'norm-fixed-shape'
            source = info['candidate'] if candidate else info['base']
            expected = info['files'] if candidate else parent['files']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != expected:
                p.error('Fixed norm shape provider inventory changed')
        if args.mode == 'hc-norm-ragged-bench':
            info = json.loads((ROOT/'config/q2-norm-ragged-source.json').read_text())
            parent_path = ROOT/'config/q2-iq2-signs-ordered-asm-source.json'
            parent = json.loads(parent_path.read_text())
            if (file_sha256(parent_path) != info['parent_manifest_sha256'] or
                    info['base'] != parent['candidate']):
                p.error('Ragged paired norm ordered parent changed')
            source = info['candidate']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != info['files']:
                p.error('Ragged paired norm provider inventory changed')
        if args.mode == 'scaled-row-check':
            info = json.loads((ROOT/'config/q2-scaled-row-reuse-source.json').read_text())
            parent_path = ROOT/'config/q2-iq2-signs-ordered-asm-source.json'
            parent = json.loads(parent_path.read_text())
            if (file_sha256(parent_path) != info['parent_manifest_sha256'] or
                    info['base'] != parent['candidate']):
                p.error('Scaled row ordered parent changed')
            candidate = args.source_variant == 'scaled-row-reuse'
            source = info['candidate'] if candidate else info['base']
            expected = info['files'] if candidate else parent['files']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != expected:
                p.error('Scaled row provider inventory changed')
        if args.mode in MIXED_TILE_MODES:
            manifest_path = ROOT/'config/q2-iq2-signs-ordered-asm-source.json'
            plan = json.loads((ROOT/'config/q2-iq2-mixed-plan.json').read_text())
            if file_sha256(manifest_path) != plan['provider_manifest_sha256']:
                p.error('IQ2 mixed tiles ordered provider changed')
            manifest = json.loads(manifest_path.read_text())
            source = manifest['candidate']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != manifest['files']:
                p.error('IQ2 mixed tiles provider inventory changed')
        if args.mode in ('iq2-wmma-signs-check', 'iq2-live-epilogue-check'):
            manifest = ('q2-iq2-prefill-scale-reuse-source.json' if args.source_variant == 'iq2-prefill-scale-reuse'
                        else 'q2-iq2-prefill-grid-lds-source.json' if args.source_variant == 'iq2-prefill-grid-lds'
                        else 'q2-iq2-live-stage-source.json' if args.source_variant == 'iq2-live-stage'
                        else 'q2-iq2-epilogue-break-source.json' if args.source_variant == 'iq2-epilogue-break'
                        else 'q2-iq2-live-epilogue-source.json' if args.mode == 'iq2-live-epilogue-check'
                        else 'q2-iq2-wmma-signs-source.json')
            info = json.loads((ROOT/'config'/manifest).read_text())
            parent_path = ROOT/'config/q2-iq2-signs-ordered-asm-source.json'
            if file_sha256(parent_path) != info['parent_manifest_sha256']:
                p.error('IQ2 WMMA ordered parent changed')
            parent = json.loads(parent_path.read_text())
            candidate = args.source_variant in ('iq2-wmma-signs', 'iq2-live-epilogue', 'iq2-epilogue-break', 'iq2-live-stage',
                                                 'iq2-prefill-scale-reuse', 'iq2-prefill-grid-lds')
            source = info['candidate'] if candidate else info['base']
            if info['base'] != parent['candidate']:
                p.error('IQ2 WMMA reference must preserve ordered decode')
            expected = info['files'] if candidate else parent['files']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != expected:
                p.error('IQ2 WMMA provider inventory changed')
        if args.mode == 'iq2-signs-check':
            manifest_name = ('q2-iq2-signs-ordered-asm-source.json'
                             if args.source_variant == 'iq2-signs-ordered'
                             else 'q2-iq2-signs-source.json')
            info = json.loads((ROOT/'config'/manifest_name).read_text())
            candidate = args.source_variant != 'iq2-signs-reference'
            source = info['candidate'] if candidate else info['base']
            expected = info['files'] if candidate else json.loads(
                (ROOT/'config/q2-curve-source.json').read_text())['variants']['q2']['files']
            actual = {str(f.relative_to(ROOT/source)): file_sha256(f)
                      for f in (ROOT/source).rglob('*') if f.is_file()}
            if actual != expected:
                p.error('IQ2 signs provider inventory changed')
        if args.native_curve or args.mode == 'native-curve-cpu':
            bench_source, _ = verify_native_curve(ROOT)
            archive.add(bench_source, arcname='native-bench-core')
        if provider_mode in CURVE_MODES:
            curve = __import__('json').loads((ROOT/'config/q2-curve-source.json').read_text())
            key = provider_mode.split('-')[0]
            provider = curve
            if provider_mode == 'q2-curve-iq2':
                candidate = json.loads((ROOT/'config/q2-iq2-signs-ordered-asm-source.json').read_text())
                provider = {'variants': {'q2': {'source': candidate['candidate'],
                                               'files': candidate['files']}}}
            if provider_mode == 'q2-point-norm':
                candidate = json.loads((ROOT/'config/q2-norm-ragged-source.json').read_text())
                component_plan = json.loads((ROOT/'config/q2-norm-ragged-plan.json').read_text())
                component = json.loads((ROOT/'config/q2-norm-ragged-results.json').read_text())
                if (file_sha256(ROOT/'config/q2-norm-ragged-source.json') != component_plan['source_manifest_sha256'] or
                    file_sha256(ROOT/'config/q2-norm-ragged-plan.json') != component['plan_sha256'] or
                    file_sha256(ROOT/'config/q2-iq2-signs-ordered-asm-source.json') != candidate['parent_manifest_sha256'] or
                    component['disposition'] != 'SELECT_ONE_CANONICAL_POINT_WITH_QUALITY_OPEN' or
                    component['validation_pass'] is not True or component['promoted'] is not False):
                    p.error('Paired norm provider or component decision changed')
                provider = {'variants': {'q2': {'source': candidate['candidate'], 'files': candidate['files']}}}
            if provider_mode == 'q2-curve-row':
                candidate = json.loads((ROOT/'config/q2-scaled-row-reuse-source.json').read_text())
                component = json.loads((ROOT/'config/q2-scaled-row-results.json').read_text())
                decision = json.loads((ROOT/'config/q2-scaled-row-decision.json').read_text())
                component_plan = json.loads((ROOT/'config/q2-scaled-row-plan.json').read_text())
                if (file_sha256(ROOT/'config/q2-scaled-row-reuse-source.json') != component_plan['source_manifest_sha256'] or
                    file_sha256(ROOT/'config/q2-scaled-row-plan.json') != component['plan_sha256'] or
                    file_sha256(ROOT/'config/q2-iq2-signs-ordered-asm-source.json') != candidate['parent_manifest_sha256'] or
                    file_sha256(ROOT/'config/q2-scaled-row-results.json') != decision['result_sha256'] or
                    decision['state'] != 'COMPONENT_TIMING_GAIN_WITH_UNCHANGED_NUMERICAL_REJECTIONS' or
                    not all(c['complete_pack_exact'] and c['complete_down_exact'] and c['retained_files_exact']
                            for c in component['comparisons']) or len(component['comparisons']) != 2):
                    p.error('Scaled row provider or component decision changed')
                provider = {'variants': {'q2': {'source': candidate['candidate'], 'files': candidate['files']}}}
            if provider_mode == 'q2-curve-scale':
                candidate = json.loads((ROOT/'config/q2-iq2-prefill-scale-reuse-source.json').read_text())
                decision = json.loads((ROOT/'config/q2-iq2-prefill-reuse-decision.json').read_text())
                if (file_sha256(ROOT/'config/q2-iq2-signs-ordered-asm-source.json') != candidate['parent_manifest_sha256'] or
                    file_sha256(ROOT/'config/q2-iq2-prefill-scale-reuse-source.json') != decision['scale']['source_manifest_sha256'] or
                    file_sha256(ROOT/'config/q2-iq2-prefill-reuse-results.json') != decision['result_sha256'] or
                    decision['scale']['decision'] != 'prepare_canonical_model_validation'):
                    p.error('Scale provider or component decision changed')
                provider = {'variants': {'q2': {'source': candidate['candidate'], 'files': candidate['files']}}}
            if provider_mode == 'q2-curve-iq2-mixed':
                candidate = json.loads((ROOT/'config/q2-iq2-mixed-model-source.json').read_text())
                if (file_sha256(ROOT/'config/q2-iq2-signs-ordered-asm-source.json') != candidate['parent_manifest_sha256'] or
                        file_sha256(ROOT/'config/q2-iq2-mixed-results.json') != candidate['component_result_sha256']):
                    p.error('Mixed IQ2 source or component qualification changed')
                provider = {'variants': {'q2': {'source': candidate['candidate'],
                                               'files': candidate['files']}}}
            if provider_mode == 'q2-curve-routes':
                candidate = json.loads((ROOT/'config/q2-route-profile-source.json').read_text())
                if file_sha256(ROOT/'config/q2-iq2-signs-ordered-asm-source.json') != candidate['parent_manifest_sha256']:
                    p.error('Routing profile parent changed')
                provider = {'variants': {'q2': {'source': candidate['candidate'],
                                               'files': candidate['files']}}}
            if provider_mode == 'q2-curve-ple-cache-first':
                candidate = json.loads((ROOT/'config/q2-ple-ordered-source.json').read_text())
                parents = {'parent_manifest_sha256': 'q2-iq2-signs-ordered-asm-source.json',
                           'ple_manifest_sha256': 'q2-ple-cache-first-source.json',
                           'curve_manifest_sha256': 'q2-curve-source.json',
                           'host_result_sha256': 'q2-ple-cache-first-host-results.json'}
                if any(file_sha256(ROOT/'config'/name) != candidate[field]
                       for field, name in parents.items()):
                    p.error('PLE ordered composition parent changed')
                provider = {'variants': {'q2': {'source': candidate['candidate'],
                                               'files': candidate['files']}}}
            if provider_mode.endswith('-ple'):
                provider = __import__('json').loads((ROOT/'config/q2-curve-profile-source.json').read_text())
                if file_sha256(ROOT/'config/q2-curve-source.json') != provider['parent_manifest_sha256']:
                    p.error('Canonical profile parent changed')
            source = provider['variants'][key]['source']
            if provider_mode in ('q2-curve-iq2', 'q2-curve-ple-cache-first', 'q2-curve-routes', 'q2-curve-iq2-mixed', 'q2-curve-scale', 'q2-curve-row', 'q2-point-norm') and {
                    str(f.relative_to(ROOT/source)) for f in (ROOT/source).rglob('*') if f.is_file()
                    } != set(provider['variants'][key]['files']):
                p.error('Canonical IQ2 provider inventory changed')
            for name, expected in provider['variants'][key]['files'].items():
                if file_sha256(ROOT/source/name) != expected:
                    p.error('Canonical provider source changed')
            for name, expected in curve['core_files'].items():
                if file_sha256(ROOT/curve['core_source']/name) != expected:
                    p.error('Canonical core source changed')
            archive.add(ROOT/curve['core_source'], arcname='curve-core')
        if args.mode in ('ple-lookahead-cpu', 'q2-ple-lookahead', 'q2-ple-first-access') and args.source_variant == 'qualified':
            source = '.deps/gufo-q2-bench-ple-lookahead'
        archive.add(ROOT / source, arcname='source')
        if args.mode in ORIGINAL_BASELINE_MODES:
            archive.add(ROOT / 'experiments/original-baseline', arcname='experiments/original-baseline')
        if args.mode in ('terminal-cpu', 'q2-terminal-build', 'q2-terminal-probe', 'q2-terminal-smoke', 'q2-terminal-full'):
            archive.add(ROOT / '.deps/lie-terminal-core-bench', arcname='terminal-core')
    dest = REMOTE + args.label
    # Exclusive destination and data-only extraction. No model or foreign path.
    script = '\n'.join([
        'import os,pathlib,sys,tarfile',
        'root=pathlib.Path(' + repr(dest) + ')',
        'root.mkdir()',
        'with tarfile.open(fileobj=sys.stdin.buffer,mode="r|gz") as archive:',
        ' for item in archive:',
        '  path=pathlib.PurePosixPath(item.name)',
        '  if path.is_absolute() or ".." in path.parts or not (item.isdir() or item.isfile()): raise ValueError("unsafe member")',
        '  if item.size>' + repr(source_data_limits(args.mode)) + '.get(item.name,16000000): raise ValueError("oversized source file")',
        '  archive.extract(item,root,filter="data")',
        'os.execv(sys.executable,[sys.executable,str(root/"tools/q2-runner.py"),' + repr(args.mode) + (',' + repr('--rebuild-mmq') if args.rebuild_mmq else '') + (',' + repr('--native-curve') if args.native_curve else '') + (',' + repr('--point-only') if args.point_only else '') + (',' + repr('--replay-from') + ',' + repr(args.replay_from) if args.replay_from else '') + '])',
    ])
    if args.detach:
        lines = script.splitlines()
        if not lines[-1].startswith('os.execv('): raise ValueError('Unexpected staging program')
        lines[-1:] = [
            'import subprocess,json',
            'with (root/"runner-console.log").open("xb") as log:',
            ' child=subprocess.Popen([sys.executable,str(root/"tools/q2-runner.py"),' + repr(args.mode) + '],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,close_fds=True)',
            'print(json.dumps({"state":"DETACHED_STARTED_NOT_COMPLETE","pid":child.pid,"root":str(root)}),flush=True)',
        ]
        script = '\n'.join(lines)
    argv = ['ssh', '-F', '/dev/null', '-o', 'BatchMode=yes', HOST,
            'python3 -c ' + shlex.quote(script)]
    result = {'mode': args.mode, 'source_variant': args.source_variant, 'source_path': source, 'rebuild_mmq': args.rebuild_mmq, 'native_curve': args.native_curve, 'point_only': args.point_only, 'label': args.label, 'remote': dest,
              'capsule_sha256': hashlib.sha256(capsule.read_bytes()).hexdigest(),
              'detached': args.detach, 'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with capsule.open('rb') as inp, (out/'remote.log').open('wb') as log:
        run = subprocess.run(argv, stdin=inp, stdout=log, stderr=subprocess.STDOUT)
    result['exit_code'] = run.returncode
    if args.detach:
        result['state'] = 'DETACHED_STARTED_NOT_COMPLETE' if run.returncode == 0 else 'STAGING_FAILED'
    result['finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (out/'transport.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result), flush=True)
    print((out/'remote.log').read_text()[-7000:], flush=True)
    raise SystemExit(run.returncode)


if __name__ == '__main__':
    main()
