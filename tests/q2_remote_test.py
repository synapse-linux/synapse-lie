#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Refuse unsafe experiment/archive combinations before any staging or SSH."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

path = Path(__file__).resolve().parents[1] / 'tools/q2-remote.py'
spec = importlib.util.spec_from_file_location('q2_remote', path)
remote = importlib.util.module_from_spec(spec)
spec.loader.exec_module(remote)


class RemoteGuardTests(unittest.TestCase):
    def test_collection_bounds_and_paths(self):
        def archive(mode, size=1, name='results/output.f32', kind=tarfile.REGTYPE):
            receipt = tarfile.TarInfo('results/result.json')
            data = json.dumps({'mode': mode}).encode()
            receipt.size = len(data)
            member = tarfile.TarInfo(name)
            member.size, member.type = size, kind
            result = Mock()
            result.getmembers.return_value = [receipt, member]
            result.extractfile.return_value = io.BytesIO(data)
            return result
        self.assertEqual(remote.collection_receipt(archive('q2-ple-first-access', 320000000))['mode'],
                         'q2-ple-first-access')
        self.assertEqual(remote.collection_receipt(archive('q2-terminal-full', 1024**3))['mode'],
                         'q2-terminal-full')
        for mode, size in [('q2-ple-lookahead', 129000000), ('q2-ple-first-access', 385000000)]:
            with self.assertRaisesRegex(ValueError, 'Oversized collection'):
                remote.collection_receipt(archive(mode, size))
        for mode, size in [('q2-terminal-full', 2 * 1024**3),
                           ('q2-terminal-smoke', 129000000), ('cpu', 129000000)]:
            with self.assertRaisesRegex(ValueError, 'Oversized collection'):
                remote.collection_receipt(archive(mode, size))
        for name, kind in [('../escape', tarfile.REGTYPE), ('/absolute', tarfile.REGTYPE),
                           ('source/file', tarfile.REGTYPE), ('results/link', tarfile.SYMTYPE),
                           ('results/result.json', tarfile.REGTYPE)]:
            value = archive('q2-ple-first-access', name=name, kind=kind)
            with self.assertRaisesRegex(ValueError, 'Unsafe collection'):
                remote.collection_receipt(value)
            value.extractfile.assert_not_called()

    def test_streamed_artifact_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'telemetry.jsonl'
            payload = b'bounded observation\n' * 100000
            path.write_bytes(payload)
            with patch.object(Path, 'read_bytes', side_effect=AssertionError('No whole-file read')):
                self.assertEqual(remote.file_sha256(path), hashlib.sha256(payload).hexdigest())

    def test_existing_collection_cannot_launch_model(self):
        self.refuse(['q2-ple-first-access', 'q2-fixture', '--existing-collection'],
                    'Existing collection requires collect mode')

    def refuse(self, argv, reason):
        with patch.object(sys, 'argv', [str(path), *argv]), \
             patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process may start')) as run, \
             patch.object(Path, 'mkdir', side_effect=AssertionError('No staging may start')) as mkdir, \
             contextlib.redirect_stderr(io.StringIO()) as error:
            with self.assertRaises(SystemExit) as result:
                remote.main()
            self.assertEqual(result.exception.code, 2)
            self.assertIn(reason, error.getvalue())
            run.assert_not_called()
            mkdir.assert_not_called()

    def test_terminal_tasks_require_persistent_supervision(self):
        for mode in ('q2-terminal-smoke', 'q2-terminal-full'):
            self.refuse([mode, 'q2-fixture'], 'require the persistent supervisor')
        self.refuse(['cpu', 'q2-fixture', '--detach'], 'limited to Terminal-Bench task runs')

    def test_terminal_variants_are_frozen(self):
        for mode in ('terminal-cpu', 'q2-terminal-build', 'q2-terminal-probe'):
            self.refuse([mode, 'q2-fixture', '--source-variant', 'shared-overlap'],
                        'three frozen Q2 variants')
            self.refuse([mode, 'q2-fixture', '--rebuild-mmq'], 'requires bench2k')

    def test_ple_source_is_fixed(self):
        for mode in ('ple-cpu', 'q2-ple', 'ud-ple', 'ple-io-cpu', 'q2-ple-io', 'ud-ple-io', 'ple-cache-cpu', 'q2-ple-cache64k', 'ple-lookahead-cpu', 'q2-ple-lookahead', 'q2-ple-first-access'):
            self.refuse([mode, 'q2-fixture', '--source-variant', 'hc-moe-fused'],
                        'fixed instrumented Q2/UD source')
            self.refuse([mode, 'q2-fixture', '--rebuild-mmq'], 'requires bench2k')

    def test_changed_executor_header_cannot_reuse_mmq(self):
        for variant in ('stack', 'iq2-pair', 'packed', 'hc-up-fused', 'hc-up-vec', 'hc-up-vec-exact', 'hc-moe-fused', 'hc-norm-half', 'hc-down64', 'hc-down64-wave4', 'hc-down64-k4', 'hc-down128-wave4', 'hc-down-coalesced', 'staged-weights', 'code-reuse', 'half-wave', 'half-wave-permlane', 'hc-prefetch', 'hc-prefetch2', 'hc-decode8', 'hc-decode16', 'hc-decode32', 'affine-palette', 'staged-palette', 'down-scatter', 'shared-overlap', 'scaled-input', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-sequence', 'hc-sequence-half-row', 'hc-single-chain', 'hc-full-row', 'hc-half-row', 'hc-row80', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced'):
            self.refuse(['q2-bench2k', 'q2-fixture', '--source-variant', variant],
                        'explicitly rebuild MMQ')

    def test_deferred_norm_requires_component_scope(self):
        for variant in ('qualified', 'hc-up-chains', 'hc-sequence'):
            self.refuse(['hc-deferred-bench', 'q2-fixture', '--source-variant', variant],
                        'requires the isolated hc-deferred-norm source')
        for mode in ('q2-bench', 'q2-bench2k', 'q2-profile', 'ud-bench2k'):
            self.refuse([mode, 'q2-fixture', '--source-variant', 'hc-deferred-norm'],
                        'not wired for model measurements')
        self.refuse(['hc-deferred-bench', 'q2-fixture', '--source-variant',
                     'hc-deferred-norm', '--rebuild-mmq'], 'requires bench2k')

    def test_sequence_requires_preserved_control_source(self):
        for variant in ('qualified', 'hc-up-chains', 'hc-norm-half'):
            self.refuse(['hc-sequence-bench', 'q2-fixture', '--source-variant', variant],
                        'requires the isolated hc-sequence source')
        self.refuse(['hc-sequence-bench', 'q2-fixture', '--source-variant',
                     'hc-sequence', '--rebuild-mmq'], 'requires bench2k')

    def test_norm_requires_paired_output_source(self):
        for mode in ('hc-norm-operators', 'hc-norm-bench'):
            for variant in ('qualified', 'hc-moe-fused', 'packed'):
                self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                            'require the isolated hc-norm-half source')

    def test_iq2_entry_requires_correct_source(self):
        self.refuse(['iq2-pair-operators', 'q2-fixture'], 'require the isolated IQ2 source')
        self.refuse(['routed-operators', 'q2-fixture'], 'require the isolated stack source')

    def test_scaled_input_source_guard(self):
        for variant in ('qualified', 'hc-up-chains', 'shared-overlap'):
            self.refuse(['scaled-input-check', 'q2-fixture', '--source-variant', variant],
                        'Scaled checks require the isolated scaled-input source')

    def test_scaled_tiles_component_only(self):
        for variant in ('qualified', 'hc-up-chains', 'scaled-input'):
            self.refuse(['scaled-tiles-check', 'q2-fixture', '--source-variant', variant],
                        'Scaled tile checks require the isolated scaled-tiles source')
        for mode in ('q2-bench', 'q2-bench2k', 'q2-profile', 'scaled-input-check'):
            self.refuse([mode, 'q2-fixture', '--source-variant', 'scaled-tiles'],
                        'component-only; no model dispatch')
        self.refuse(['q2-terminal-full', 'q2-fixture', '--detach',
                     '--source-variant', 'scaled-tiles'],
                    'requires one of its three frozen Q2 variants')

    def test_narrow_vector_component_only(self):
        for variant in ('qualified', 'hc-up-chains', 'scaled-input'):
            self.refuse(['narrow-vector-check', 'q2-fixture', '--source-variant', variant],
                        'Narrow checks require the isolated narrow-vector source')
        for mode in ('q2-bench', 'q2-bench2k', 'q2-profile', 'scaled-input-check'):
            self.refuse([mode, 'q2-fixture', '--source-variant', 'narrow-vector'],
                        'component-only; no model dispatch')
        self.refuse(['q2-terminal-full', 'q2-fixture', '--detach',
                     '--source-variant', 'narrow-vector'],
                    'requires one of its three frozen Q2 variants')

    def test_scaled_library_source_boundaries(self):
        self.refuse(['q2-bench2k', 'q2-fixture', '--source-variant', 'scaled-library'],
                    'requires a full MMQ rebuild')
        self.refuse(['q2-profile', 'q2-fixture', '--source-variant', 'scaled-library',
                     '--rebuild-mmq'], 'requires bench2k')
        for mode in ('q2-bench', 'ud-bench2k', 'q2-ple-lookahead',
                     'hc-library-bench', 'operators', 'cpu', 'scaled-input-check'):
            self.refuse([mode, 'q2-fixture', '--source-variant', 'scaled-library'],
                        'requires its explicit component, bench2k or profile experiment')
        self.refuse(['q2-terminal-full', 'q2-fixture', '--detach',
                     '--source-variant', 'scaled-library'],
                    'requires one of its three frozen Q2 variants')

    def test_library_norm_cycle_scope(self):
        for variant in ('qualified', 'scaled-library', 'hc-sequence'):
            self.refuse(['hc-library-norm-bench', 'q2-fixture', '--source-variant', variant],
                        'requires its preserved-control source')
        for mode in ('ud-bench2k', 'q2-profile', 'hc-sequence-bench', 'hc-pp-bench', 'cpu'):
            self.refuse([mode, 'q2-fixture', '--source-variant', 'library-norm-cycle'],
                        'requires its explicit component or bench2k experiment')
        self.refuse(['q2-bench2k', 'q2-fixture', '--source-variant', 'library-norm-cycle'],
                    'requires a full MMQ rebuild')
        self.refuse(['hc-library-norm-bench', 'q2-fixture', '--source-variant',
                     'library-norm-cycle', '--rebuild-mmq'], 'requires bench2k')
        # An allowed invocation must reach staging, without creating files or SSH.
        for mode in ('hc-library-norm-bench', 'q2-bench2k'):
            argv = [str(path), mode, 'q2-fixture', '--source-variant', 'library-norm-cycle']
            if mode == 'q2-bench2k':
                argv.append('--rebuild-mmq')
            with patch.object(sys, 'argv', argv), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')) as mkdir, \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process may start')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                mkdir.assert_called_once()
                run.assert_not_called()

    def test_hc_decode_reduction_scope(self):
        for variant in ('qualified', 'library-norm-bound', 'library-norm-cycle'):
            self.refuse(['hc-decode-reduce-bench', 'q2-fixture', '--source-variant', variant],
                        'HC decode reduction requires its preserved-control source')
        for mode in ('q2-bench2k', 'ud-bench2k', 'q2-profile', 'cpu', 'hc-bench'):
            self.refuse([mode, 'q2-fixture', '--source-variant', 'hc-decode-reduce'],
                        'HC decode reduction is component-only')
        self.refuse(['hc-decode-reduce-bench', 'q2-fixture', '--source-variant',
                     'hc-decode-reduce', '--rebuild-mmq'], 'requires bench2k')
        argv = [str(path), 'hc-decode-reduce-bench', 'q2-fixture',
                '--source-variant', 'hc-decode-reduce']
        with patch.object(sys, 'argv', argv), \
             patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')) as mkdir, \
             patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process may start')) as run:
            with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                remote.main()
            mkdir.assert_called_once()
            run.assert_not_called()

    def test_decode_baseline_scope(self):
        for mode, variant in (('q2-decode-baseline', 'library-norm-bound'),
                              ('ud-decode-baseline', 'qualified')):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'requires a full MMQ rebuild')
            for wrong in ('scaled-library', 'library-norm-cycle',
                          'qualified' if variant != 'qualified' else 'library-norm-bound'):
                self.refuse([mode, 'q2-fixture', '--source-variant', wrong,
                             '--rebuild-mmq'], 'requires its fixed Q2 or pristine UD source')
            argv = [str(path), mode, 'q2-fixture', '--source-variant', variant,
                    '--rebuild-mmq']
            with patch.object(sys, 'argv', argv), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')) as mkdir, \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process may start')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                mkdir.assert_called_once()
                run.assert_not_called()
        for mode in ('cpu', 'q2-bench2k', 'q2-profile', 'operators'):
            self.refuse([mode, 'q2-fixture', '--source-variant', 'library-norm-bound'],
                        'requires the Q2 decode baseline experiment')

    def test_original_baseline_scope(self):
        for mode, variant in (('q2-original-baseline', 'library-norm-bound'),
                              ('ud-original-baseline', 'qualified')):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Original baseline requires a full MMQ rebuild')
            for wrong in ('scaled-library', 'library-norm-cycle',
                          'qualified' if variant != 'qualified' else 'library-norm-bound'):
                self.refuse([mode, 'q2-fixture', '--source-variant', wrong,
                             '--rebuild-mmq'], 'Original baseline requires its fixed Q2 or pristine UD source')
            self.refuse([mode, 'q2-fixture', '--source-variant', 'hc-decode-reduce',
                         '--rebuild-mmq'], 'HC decode reduction is component-only')
            self.refuse([mode, 'q2-fixture', '--source-variant', variant,
                         '--rebuild-mmq', '--detach'], 'Persistent launch is limited')
            argv = [str(path), mode, 'q2-fixture', '--source-variant', variant,
                    '--rebuild-mmq']
            with patch.object(sys, 'argv', argv), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')) as mkdir, \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process may start')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                mkdir.assert_called_once()
                run.assert_not_called()

    def test_combined_source_boundaries(self):
        for variant in ('combined-retained', 'combined-scaled'):
            self.refuse(['q2-bench2k', 'q2-fixture', '--source-variant', variant],
                        'requires a full MMQ rebuild')
            for mode in ('q2-bench', 'ud-bench2k', 'q2-profile', 'q2-ple', 'operators', 'cpu'):
                self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                            'requires its explicit Q2 model or conversion checks')
            self.refuse(['q2-terminal-full', 'q2-fixture', '--detach',
                         '--source-variant', variant],
                        'requires one of its three frozen Q2 variants')

    def test_phased_hc_component_only(self):
        for variant in ('hc-down-phased', 'hc-down-phased-free', 'hc-row160-wide', 'hc-row160-loads'):
            for mode in ('q2-bench', 'q2-bench2k', 'q2-profile', 'operators', 'hc-input-bench'):
                self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                            'Phased HC source is component-only; no model dispatch')
            self.refuse(['q2-terminal-full', 'q2-fixture', '--detach',
                         '--source-variant', variant],
                        'requires one of its three frozen Q2 variants')

    def test_shared_fork_source_guard(self):
        for variant in ('qualified', 'hc-up-chains', 'down-scatter'):
            self.refuse(['shared-fork-check', 'q2-fixture', '--source-variant', variant],
                        'require the isolated shared-overlap source')

    def test_packed_bench_requires_measured_source(self):
        for variant in ('qualified', 'packed', 'hc-norm-half'):
            self.refuse(['packed-bench', 'q2-fixture', '--source-variant', variant],
                        'Packed benchmark requires')

    def test_packed_entry_requires_correct_source(self):
        self.refuse(['packed-operators', 'q2-fixture'], 'require the isolated packed source')

    def test_packed_tiles_bench_requires_retained_source(self):
        for mode in ('packed-tiles-bench', 'packed-tiles16-bench'):
            for variant in ('qualified', 'packed', 'affine-palette', 'staged-palette', 'down-scatter', 'shared-overlap', 'scaled-input', 'hc-down-wide'):
                self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                            'requires retained hc-up-chains source')
            self.refuse([mode, 'q2-fixture', '--source-variant',
                         'hc-up-chains', '--rebuild-mmq'], 'requires bench2k')

    def test_hc_input_requires_isolated_source(self):
        for variant in ('qualified', 'affine-palette', 'hc-library-down'):
            self.refuse(['hc-input-bench', 'q2-fixture', '--source-variant', variant],
                        'requires the isolated hc-input source')
        self.refuse(['hc-input-bench', 'q2-fixture', '--source-variant',
                     'hc-input', '--rebuild-mmq'], 'requires bench2k')

    def test_hc_up_chain_benchmark_requires_measured_sources(self):
        for variant in ('qualified', 'hc-up-fused', 'hc-input'):
            self.refuse(['hc-up-chain-bench', 'q2-fixture', '--source-variant', variant],
                        'requires palette or hc-up-chains')
        self.refuse(['hc-up-chain-bench', 'q2-fixture', '--source-variant',
                     'hc-up-chains', '--rebuild-mmq'], 'requires bench2k')

    def test_hc_library_requires_current_native_control(self):
        for variant in ('qualified', 'staged-palette', 'down-scatter', 'shared-overlap', 'scaled-input', 'hc-moe-fused', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-sequence', 'hc-sequence-half-row', 'hc-single-chain', 'hc-full-row', 'hc-half-row', 'hc-row80', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced'):
            self.refuse(['hc-library-bench', 'q2-fixture', '--source-variant', variant],
                        'requires the measured affine-palette source')
        self.refuse(['hc-library-bench', 'q2-fixture', '--source-variant',
                     'affine-palette', '--rebuild-mmq'], 'requires bench2k')

    def test_hc_up_entry_requires_correct_source(self):
        self.refuse(['hc-up-operators', 'q2-fixture'], 'require the isolated hc-up-fused source')
        self.refuse(['hc-up-operators', 'q2-fixture', '--source-variant', 'hc-prefetch'],
                    'require the isolated hc-up-fused source')
        self.refuse(['hc-up-operators', 'q2-fixture', '--source-variant', 'hc-prefetch2'],
                    'require the isolated hc-up-fused source')

    def test_hc_up_bench_requires_measured_source_family(self):
        self.refuse(['hc-up-bench', 'q2-fixture'], 'requires the measured hc-up-fused source')
        self.refuse(['hc-up-bench', 'q2-fixture', '--source-variant', 'packed'],
                    'requires the measured hc-up-fused source')

    def test_hc_moe_entry_requires_fused_source(self):
        for mode in ('hc-moe-operators', 'hc-moe-bench'):
            for variant in ('qualified', 'hc-up-vec-exact', 'packed'):
                self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                            'require the isolated hc-moe-fused source')

    def test_q2_source_cannot_replace_ud_control(self):
        for variant in ('packed', 'hc-up-vec', 'hc-up-vec-exact', 'hc-moe-fused', 'hc-norm-half', 'hc-down64', 'hc-down64-wave4', 'hc-down64-k4', 'hc-down128-wave4', 'hc-down-coalesced', 'staged-weights', 'code-reuse', 'half-wave', 'half-wave-permlane', 'hc-prefetch', 'hc-prefetch2', 'hc-decode8', 'hc-decode16', 'hc-decode32', 'affine-palette', 'staged-palette', 'down-scatter', 'shared-overlap', 'scaled-input', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-sequence', 'hc-sequence-half-row', 'hc-single-chain', 'hc-full-row', 'hc-half-row', 'hc-row80', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced'):
            self.refuse(['ud-bench2k', 'q2-fixture', '--source-variant', variant],
                        'Stack source requires')

    def test_rebuild_flag_does_not_silently_apply_elsewhere(self):
        self.refuse(['q2-profile', 'q2-fixture', '--rebuild-mmq'], 'requires bench2k')


if __name__ == '__main__':
    unittest.main()
