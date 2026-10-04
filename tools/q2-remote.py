#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Stage task-owned sources and fixed qualification jobs on .157 only."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
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
CURVE_MODES = ('q2-curve', 'ud-curve', 'q2-curve-ple', 'ud-curve-ple', 'q2-curve-iq2', 'q2-curve-ple-cache-first')
CURVE_VARIANTS = ('curve-q2', 'curve-ud', 'curve-ple-q2', 'curve-ple-ud', 'curve-iq2-q2', 'curve-ple-cache-first-q2')


def file_sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


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
    # Eight complete 36-row outputs alone occupy 286 MB in this fixed probe.
    # Keep other modes at their existing bound and retain a finite total cap.
    # Full Core-19 permits 19 x two three-hour attempts. Preserve its two-second
    # telemetry samples instead of silently dropping them after a short-run cap.
    limits = {'q2-ple-first-access': 384000000, 'q2-terminal-full': 2 * 1024**3}
    limit = limits.get(receipt.get('mode'), 128000000)
    if sum(member.size for member in members) > limit:
        raise ValueError('Oversized collection')
    return receipt


def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['cpu', 'ple-cache-first-cpu', 'ple-lookahead-cpu', 'q2-ple-lookahead', 'q2-ple-first-access', 'ple-cpu', 'ple-cache-cpu', 'q2-ple-cache64k', 'ple-io-cpu', 'q2-ple-io', 'ud-ple-io', 'q2-ple', 'ud-ple', 'hip-build', 'operators', 'operators-reference', 'iq2-signs-check', 'iq2-wmma-signs-check', 'hc-operators', 'hc-bench', 'hc-pp-operators', 'hc-pp-bench', 'hc-library-bench', 'hc-library-norm-bench', 'hc-library-ragged-bench', 'hc-decode-reduce-bench', 'hc-input-bench', 'hc-up-chain-bench', 'hc-up-operators', 'hc-up-bench', 'hc-moe-operators', 'hc-moe-bench', 'hc-norm-operators', 'hc-norm-bench', 'hc-sequence-bench', 'hc-deferred-bench', 'routed-operators', 'iq2-pair-operators', 'shared-fork-check', 'scaled-input-check', 'scaled-tiles-check', 'narrow-vector-check', 'packed-operators', 'packed-bench', 'packed-tiles-bench', 'packed-tiles16-bench', 'terminal-cpu', 'q2-terminal-build', 'q2-terminal-probe', 'q2-terminal-smoke', 'q2-terminal-full', 'q2-smoke', 'q2-bench', 'q2-bench2k', 'ud-bench2k', 'q2-decode-baseline', 'ud-decode-baseline', *ORIGINAL_BASELINE_MODES, *CURVE_MODES, 'q2-profile', 'ud-profile', 'ud-base', 'ud-patched', 'status', 'collect'])
    p.add_argument('label')
    p.add_argument('--source-variant', choices=['qualified', 'bounded-k', 'wide-barrier', 'hc', 'hc-prefill', 'stack', 'iq2-pair', 'packed', 'hc-up-fused', 'hc-up-vec', 'hc-up-vec-exact', 'hc-moe-fused', 'hc-norm-half', 'hc-down64', 'hc-down64-wave4', 'hc-down64-k4', 'hc-down128-wave4', 'hc-down-coalesced', 'staged-weights', 'code-reuse', 'half-wave', 'half-wave-permlane', 'hc-prefetch', 'hc-prefetch2', 'hc-decode8', 'hc-decode16', 'hc-decode32', 'affine-palette', 'staged-palette', 'down-scatter', 'shared-overlap', 'scaled-input', 'scaled-tiles', 'narrow-vector', 'hc-down-phased', 'hc-down-phased-free', 'hc-row160-wide', 'hc-row160-loads', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-sequence', 'hc-sequence-half-row', 'hc-deferred-norm', 'hc-single-chain', 'hc-full-row', 'hc-half-row', 'hc-row80', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced', *COMBINED_VARIANTS, 'scaled-library', 'library-norm-cycle', 'library-norm-bound', 'hc-decode-reduce', 'hc-library-ragged', *CURVE_VARIANTS, *SIGN_VARIANTS, *WMMA_SIGN_VARIANTS],
                   default='qualified', help='Isolated source; hc also supports HC operators and microbenchmark')
    p.add_argument('--detach', action='store_true', help='Persistent supervisor for Terminal-Bench tasks only')
    p.add_argument('--rebuild-mmq', action='store_true',
                   help='Recompile all MMQ sources for bench2k, decode-baseline or original-baseline; no prior archive reuse')
    p.add_argument('--existing-collection', action='store_true',
                   help='Validate/extract an already downloaded collection; no SSH or overwriting results')
    args = p.parse_args()
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
    if args.mode in CURVE_MODES or args.source_variant in CURVE_VARIANTS:
        expected = {'q2-curve': 'curve-q2', 'ud-curve': 'curve-ud',
                    'q2-curve-ple': 'curve-ple-q2', 'ud-curve-ple': 'curve-ple-ud',
                    'q2-curve-iq2': 'curve-iq2-q2',
                    'q2-curve-ple-cache-first': 'curve-ple-cache-first-q2'}.get(args.mode)
        if args.source_variant != expected:
            p.error('Canonical curve requires its matched Q2 or UD composition')
        if not args.rebuild_mmq:
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
    if args.mode == 'hc-library-norm-bench' and args.source_variant != 'library-norm-cycle':
        p.error('Library norm cycle requires its preserved-control source')
    if args.source_variant == 'library-norm-cycle':
        if args.mode not in ('hc-library-norm-bench', 'q2-bench2k'):
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
    if args.rebuild_mmq and args.mode not in ('q2-bench2k', 'ud-bench2k', 'q2-decode-baseline', 'ud-decode-baseline', *ORIGINAL_BASELINE_MODES, *CURVE_MODES, 'iq2-signs-check'):
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
    if args.source_variant not in ('qualified', 'hc', 'hc-prefill', 'stack', 'iq2-pair', 'packed', 'hc-up-fused', 'hc-up-vec', 'hc-up-vec-exact', 'hc-moe-fused', 'hc-norm-half', 'hc-down64', 'hc-down64-wave4', 'hc-down64-k4', 'hc-down128-wave4', 'hc-down-coalesced', 'staged-weights', 'code-reuse', 'half-wave', 'half-wave-permlane', 'hc-prefetch', 'hc-prefetch2', 'hc-decode8', 'hc-decode16', 'hc-decode32', 'affine-palette', 'staged-palette', 'down-scatter', 'shared-overlap', 'scaled-input', 'scaled-tiles', 'narrow-vector', 'hc-down-phased', 'hc-down-phased-free', 'hc-row160-wide', 'hc-row160-loads', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-sequence', 'hc-sequence-half-row', 'hc-deferred-norm', 'hc-single-chain', 'hc-full-row', 'hc-half-row', 'hc-row80', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced', *COMBINED_VARIANTS, 'scaled-library', 'library-norm-cycle', 'library-norm-bound', 'hc-decode-reduce', 'hc-library-ragged', *CURVE_VARIANTS, *SIGN_VARIANTS, *WMMA_SIGN_VARIANTS) and args.mode != 'q2-bench':
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
        for name in ['CMakeLists.txt', 'cmake', 'tests', 'config', 'experiments/q2_curve_profile.hpp', 'experiments/ple_flow.c', 'experiments/ple_flow.h', 'experiments/gpu_fork.c', 'experiments/gpu_fork.h', 'experiments/q2_shared_fork.hpp', 'tools/analyze-q2-terminal.py', 'tools/collect-q2-terminal.py', 'tools/q2-terminal-session.py', 'tools/q2-runner.py', 'tools/q2-remote.py', 'tools/q2-canonical-http.py', 'tools/q2-curve-session.py', 'tools/analyze-q2-curve-profile.py', 'tools/analyze-q2-curve.py', 'tools/analyze-q2-iq2-curve.py', 'tools/analyze-q2-ple-cache-first.py', 'tools/analyze-q2-iq2-wmma-signs.py', 'tools/q2_process.py', 'tools/q2_thermal.py', 'tools/axb35-fan-curves.py', 'tools/q2_reuse.py', 'tools/analyze-q2-profile.py', 'tools/analyze-q2-expert-profile.py', 'tools/q2-resource-report.py', 'tools/analyze-q2-hc-up.py']:
            archive.add(ROOT / name, arcname=name)
        source = '.deps/gufo-base' if args.mode in ('ud-base','ud-profile','ud-bench2k','ud-decode-baseline','ud-original-baseline') else '.deps/gufo-q2-register-reference' if args.mode == 'operators-reference' else '.deps/gufo-q2'
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
        if args.mode == 'iq2-wmma-signs-check':
            info = json.loads((ROOT/'config/q2-iq2-wmma-signs-source.json').read_text())
            parent_path = ROOT/'config/q2-iq2-signs-ordered-asm-source.json'
            if file_sha256(parent_path) != info['parent_manifest_sha256']:
                p.error('IQ2 WMMA ordered parent changed')
            parent = json.loads(parent_path.read_text())
            candidate = args.source_variant == 'iq2-wmma-signs'
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
        if args.mode in CURVE_MODES:
            curve = __import__('json').loads((ROOT/'config/q2-curve-source.json').read_text())
            key = args.mode.split('-')[0]
            provider = curve
            if args.mode == 'q2-curve-iq2':
                candidate = json.loads((ROOT/'config/q2-iq2-signs-ordered-asm-source.json').read_text())
                provider = {'variants': {'q2': {'source': candidate['candidate'],
                                               'files': candidate['files']}}}
            if args.mode == 'q2-curve-ple-cache-first':
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
            if args.mode.endswith('-ple'):
                provider = __import__('json').loads((ROOT/'config/q2-curve-profile-source.json').read_text())
                if file_sha256(ROOT/'config/q2-curve-source.json') != provider['parent_manifest_sha256']:
                    p.error('Canonical profile parent changed')
            source = provider['variants'][key]['source']
            if args.mode in ('q2-curve-iq2', 'q2-curve-ple-cache-first') and {
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
        '  if item.size>16000000: raise ValueError("oversized source file")',
        '  archive.extract(item,root,filter="data")',
        'os.execv(sys.executable,[sys.executable,str(root/"tools/q2-runner.py"),' + repr(args.mode) + (',' + repr('--rebuild-mmq') if args.rebuild_mmq else '') + '])',
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
    result = {'mode': args.mode, 'source_variant': args.source_variant, 'source_path': source, 'rebuild_mmq': args.rebuild_mmq, 'label': args.label, 'remote': dest,
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
