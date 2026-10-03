#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Refuse unsafe experiment/archive combinations before any staging or SSH."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
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
        for mode, size in [('q2-ple-lookahead', 129000000), ('q2-ple-first-access', 385000000)]:
            with self.assertRaisesRegex(ValueError, 'Oversized collection'):
                remote.collection_receipt(archive(mode, size))
        for name, kind in [('../escape', tarfile.REGTYPE), ('/absolute', tarfile.REGTYPE),
                           ('source/file', tarfile.REGTYPE), ('results/link', tarfile.SYMTYPE),
                           ('results/result.json', tarfile.REGTYPE)]:
            value = archive('q2-ple-first-access', name=name, kind=kind)
            with self.assertRaisesRegex(ValueError, 'Unsafe collection'):
                remote.collection_receipt(value)
            value.extractfile.assert_not_called()

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

    def test_ple_source_is_fixed(self):
        for mode in ('ple-cpu', 'q2-ple', 'ud-ple', 'ple-io-cpu', 'q2-ple-io', 'ud-ple-io', 'ple-cache-cpu', 'q2-ple-cache64k', 'ple-lookahead-cpu', 'q2-ple-lookahead', 'q2-ple-first-access'):
            self.refuse([mode, 'q2-fixture', '--source-variant', 'hc-moe-fused'],
                        'fixed instrumented Q2/UD source')
            self.refuse([mode, 'q2-fixture', '--rebuild-mmq'], 'requires bench2k')

    def test_changed_executor_header_cannot_reuse_mmq(self):
        for variant in ('stack', 'iq2-pair', 'packed', 'hc-up-fused', 'hc-up-vec', 'hc-up-vec-exact', 'hc-moe-fused', 'hc-norm-half', 'hc-down64', 'hc-down64-wave4', 'hc-down64-k4', 'hc-down128-wave4', 'hc-down-coalesced', 'staged-weights', 'code-reuse', 'half-wave', 'half-wave-permlane', 'hc-prefetch', 'hc-prefetch2', 'hc-decode8', 'hc-decode16', 'hc-decode32', 'affine-palette', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down'):
            self.refuse(['q2-bench2k', 'q2-fixture', '--source-variant', variant],
                        'explicitly rebuild MMQ')

    def test_norm_requires_paired_output_source(self):
        for mode in ('hc-norm-operators', 'hc-norm-bench'):
            for variant in ('qualified', 'hc-moe-fused', 'packed'):
                self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                            'require the isolated hc-norm-half source')

    def test_iq2_entry_requires_correct_source(self):
        self.refuse(['iq2-pair-operators', 'q2-fixture'], 'require the isolated IQ2 source')
        self.refuse(['routed-operators', 'q2-fixture'], 'require the isolated stack source')

    def test_packed_bench_requires_measured_source(self):
        for variant in ('qualified', 'packed', 'hc-norm-half'):
            self.refuse(['packed-bench', 'q2-fixture', '--source-variant', variant],
                        'Packed benchmark requires')

    def test_packed_entry_requires_correct_source(self):
        self.refuse(['packed-operators', 'q2-fixture'], 'require the isolated packed source')

    def test_hc_library_requires_current_native_control(self):
        for variant in ('qualified', 'hc-moe-fused', 'hc-chain-coalesced', 'hc-library-down'):
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
        for variant in ('packed', 'hc-up-vec', 'hc-up-vec-exact', 'hc-moe-fused', 'hc-norm-half', 'hc-down64', 'hc-down64-wave4', 'hc-down64-k4', 'hc-down128-wave4', 'hc-down-coalesced', 'staged-weights', 'code-reuse', 'half-wave', 'half-wave-permlane', 'hc-prefetch', 'hc-prefetch2', 'hc-decode8', 'hc-decode16', 'hc-decode32', 'affine-palette', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down'):
            self.refuse(['ud-bench2k', 'q2-fixture', '--source-variant', variant],
                        'Stack source requires')

    def test_rebuild_flag_does_not_silently_apply_elsewhere(self):
        self.refuse(['q2-profile', 'q2-fixture', '--rebuild-mmq'], 'requires bench2k')


if __name__ == '__main__':
    unittest.main()
